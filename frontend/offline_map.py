"""Entirely native, network-free coordinate overview; not a street/boundary map."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsScene, QGraphicsView, QMenu
from .themes import tokens
from .map_data import load_outlines


def project(latitude: float, longitude: float) -> QPointF:
    # Equirectangular display in logical scene units; longitude compression at 36°N.
    return QPointF(longitude * 100 * math.cos(math.radians(36)), -latitude * 100)


def cluster_points(items, scale: float, radius: float = 36):
    """Bucket nearby markers in screen space. Identical positions remain selectable."""
    groups = {}
    for item in items:
        if item.has_coordinates:
            point = project(item.latitude, item.longitude)
            key = (round(point.x() * scale / radius), round(point.y() * scale / radius))
            groups.setdefault(key, []).append(item)
    return list(groups.values())


class Marker(QGraphicsEllipseItem):
    def __init__(self, view, items):
        size = 34 if len(items) > 1 else 24
        super().__init__(-size / 2, -size / 2, size, size)
        self.view, self.items = view, items
        self.setFlag(self.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setPos(project(sum(n.latitude for n in items) / len(items),
                            sum(n.longitude for n in items) / len(items)))
        self.setZValue(10)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("\n".join(f"{n.category} · {n.title}" for n in items[:12]))
        self.setBrush(QBrush(QColor(items[0].color if len(items) == 1 else "#577ca7")))
        self.update_selection()

    def update_selection(self):
        selected = any(n.id == self.view.selected_id for n in self.items)
        self.setPen(QPen(QColor("#ffb36b" if selected else "#ffffff"), 4 if selected else 2))

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setPen(Qt.white)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(12)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter,
                         str(len(self.items)) if len(self.items) > 1 else self.items[0].category[0])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if len(self.items) == 1:
                self.view.selected.emit(self.items[0].id)
            else:
                self.view.open_cluster(self.items, event.screenPos())
            event.accept()
        else:
            super().mousePressEvent(event)


class OfflineMap(QGraphicsView):
    selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(self.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(self.Shape.NoFrame)
        self.setAccessibleName("오프라인 좌표 지도. 목록에서 기사를 선택하거나 마커를 클릭하세요.")
        self.setToolTip("휠: 확대·축소 / 드래그: 이동 / 여러 기사 마커: 기사 선택 메뉴")
        self.items, self.markers = [], []
        self.item_by_id, self.marker_by_id = {}, {}
        self.cluster_picker = None
        self.selected_id = None
        self.dark = False
        self.outlines, self.resource_error = load_outlines()
        self._first_show = True
        self._background()

    def _background(self):
        self.scene().clear()
        self.markers = []
        t = tokens(self.dark)
        self.setBackgroundBrush(QColor(t["map"]))
        for feature in self.outlines:
            for polygon in feature['polygons']:
                path = QPainterPath()
                path.setFillRule(Qt.OddEvenFill)
                for ring in polygon:
                    path.moveTo(project(ring[0][1], ring[0][0]))
                    for lon, lat in ring[1:]:
                        path.lineTo(project(lat, lon))
                    path.closeSubpath()
                color = ('#253b50' if self.dark else '#ffffff') if feature['code'] == 'KOR' else (
                    '#1b2b3d' if self.dark else '#dce6ef')
                item = self.scene().addPath(path, QPen(QColor(t['grid']), 0), QBrush(QColor(color)))
                item.setZValue(-2)
        # The coordinate grid stays usable when the optional outline resource fails.
        for longitude in range(124, 132):
            a, b = project(32, longitude), project(40, longitude)
            self.scene().addLine(a.x(), a.y(), b.x(), b.y(), QPen(QColor(t["grid"]), 0))
            note = self.scene().addSimpleText(f"{longitude}°E")
            note.setBrush(QColor(t["muted"]))
            note.setPos(project(38.8, longitude))
        for latitude in range(32, 41):
            a, b = project(latitude, 124), project(latitude, 132)
            self.scene().addLine(a.x(), a.y(), b.x(), b.y(), QPen(QColor(t["grid"]), 0))
            note = self.scene().addSimpleText(f"{latitude}°N")
            note.setBrush(QColor(t["muted"]))
            note.setPos(project(latitude, 124.3))
        for name, lat, lon in (("서울", 37.56, 126.98), ("천안", 36.81, 127.15),
                               ("대전", 36.35, 127.38), ("대구", 35.87, 128.60),
                               ("광주", 35.16, 126.85), ("부산", 35.18, 129.07),
                               ("제주", 33.50, 126.53)):
            note = self.scene().addSimpleText(name)
            note.setBrush(QColor(t["muted"]))
            note.setPos(project(lat, lon) + QPointF(14, 9))
            note.setFlag(note.GraphicsItemFlag.ItemIgnoresTransformations)
        self._update_scene_bounds()
        self._draw_markers()

    def set_theme(self, dark):
        self.dark = dark
        self._background()
        if self.cluster_picker:
            self.cluster_picker.delegate.dark = dark
            self.cluster_picker.news.viewport().update()

    def set_items(self, items):
        self.close_picker()
        self.items = list(items)
        self.item_by_id = {item.id: item for item in self.items}
        self._update_scene_bounds()
        self._draw_markers()

    def _update_scene_bounds(self):
        bounds = QRectF(project(42, 120), project(28, 136))
        located = [item for item in self.items if item.has_coordinates]
        if located:
            top_left = project(max(n.latitude for n in located), min(n.longitude for n in located))
            bottom_right = project(min(n.latitude for n in located), max(n.longitude for n in located))
            bounds = bounds.united(QRectF(top_left, bottom_right).adjusted(-30, -30, 30, 30))
        self.setSceneRect(bounds)

    def _draw_markers(self):
        for marker in self.markers:
            self.scene().removeItem(marker)
        self.markers = []
        self.marker_by_id = {}
        for group in cluster_points(self.items, self.transform().m11()):
            marker = Marker(self, group)
            self.scene().addItem(marker)
            self.markers.append(marker)
            for item in group:
                self.marker_by_id[item.id] = marker

    def set_selected(self, identifier, focus=False):
        previous = self.marker_by_id.get(self.selected_id)
        self.selected_id = identifier
        if focus:
            item = self.item_by_id.get(identifier)
            if item and item.has_coordinates:
                self.centerOn(project(item.latitude, item.longitude))
        if previous:
            previous.update_selection()
        current = self.marker_by_id.get(identifier)
        if current and current is not previous:
            current.update_selection()

    def fit_results(self):
        points = [project(n.latitude, n.longitude) for n in self.items if n.has_coordinates]
        if not points:
            return
        left, right = min(p.x() for p in points), max(p.x() for p in points)
        top, bottom = min(p.y() for p in points), max(p.y() for p in points)
        self.fitInView(QRectF(left - 12, top - 12, right - left + 24, bottom - top + 24),
                       Qt.KeepAspectRatio)
        self._draw_markers()

    def open_cluster(self, items, screen_position):
        if len(items) <= 12:
            menu = QMenu(self)
            for item in items:
                action = menu.addAction(f'[{item.category}] {item.title}')
                action.triggered.connect(lambda checked=False, key=item.id: self.selected.emit(key))
            menu.exec(screen_position)
            menu.deleteLater()
            return
        from .cluster_dialog import ClusterDialog
        self.close_picker()
        picker = ClusterDialog(items, dark=self.dark, parent=self)
        self.cluster_picker = picker
        picker.selected.connect(self.selected)
        picker.destroyed.connect(lambda: self._picker_closed(picker))
        picker.show()

    def _picker_closed(self, picker):
        if self.cluster_picker is picker:
            self.cluster_picker = None

    def close_picker(self):
        if self.cluster_picker:
            self.cluster_picker.close()
            self.cluster_picker = None

    def home(self):
        self.fitInView(QRectF(project(38.7, 124.8), project(32.9, 130.2)), Qt.KeepAspectRatio)
        self._draw_markers()

    def zoom(self, factor):
        scale = self.transform().m11() * factor
        if 0.35 <= scale <= 25:
            self.scale(factor, factor)
            self._draw_markers()

    def wheelEvent(self, event):
        self.zoom(1.25 if event.angleDelta().y() > 0 else 0.8)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom(1.25)
        elif event.key() == Qt.Key_Minus:
            self.zoom(0.8)
        elif event.key() == Qt.Key_Home:
            self.home()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.home()
