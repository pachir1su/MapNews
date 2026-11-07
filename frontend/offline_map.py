"""Native offline administrative map. District detail follows the zoom level."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsScene, QGraphicsView, QMenu
from .themes import tokens
from .icons import category_icon
from .map_data import load_outlines, load_boundaries


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
        size = 38 if len(items) > 1 else 32
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
        self.setPen(QPen(QColor(tokens(self.view.dark)['accent'] if selected else "#ffffff"),
                         4 if selected else 2))

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setPen(Qt.white)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(12)
        painter.setFont(font)
        if len(self.items) > 1:
            painter.drawText(self.rect(), Qt.AlignCenter, str(len(self.items)))
        else:
            category_icon(self.items[0].category).render(painter, self.rect().adjusted(7, 7, -7, -7))

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
        self.boundaries, self.boundary_error = load_boundaries()
        self.district_layer = None
        self.province_labels = []
        self._first_show = True
        self._background()

    def _background(self):
        self.scene().clear()
        self.markers = []
        t = tokens(self.dark)
        self.setBackgroundBrush(QColor(t["map"]))
        base = [f for f in self.outlines if f['code'] != 'KOR']
        base += ([dict(f, code='KOR') for f in self.boundaries['adm1']]
                 or [f for f in self.outlines if f['code'] == 'KOR'])
        for feature in base:
            for polygon in feature['polygons']:
                path = QPainterPath()
                path.setFillRule(Qt.OddEvenFill)
                for ring in polygon:
                    path.moveTo(project(ring[0][1], ring[0][0]))
                    for lon, lat in ring[1:]:
                        path.lineTo(project(lat, lon))
                    path.closeSubpath()
                color = t['land'] if feature['code'] == 'KOR' else t['neighbor']
                item = self.scene().addPath(path, QPen(QColor(t['grid']), 0), QBrush(QColor(color)))
                item.setZValue(-2)
        # Keep the normal map quiet. A coordinate grid is only a recovery surface.
        for longitude in (range(124, 132) if not self.outlines else ()):
            a, b = project(32, longitude), project(40, longitude)
            self.scene().addLine(a.x(), a.y(), b.x(), b.y(), QPen(QColor(t["grid"]), 0))
            note = self.scene().addSimpleText(f"{longitude}°E")
            note.setBrush(QColor(t["muted"]))
            note.setPos(project(38.8, longitude))
        for latitude in (range(32, 41) if not self.outlines else ()):
            a, b = project(latitude, 124), project(latitude, 132)
            self.scene().addLine(a.x(), a.y(), b.x(), b.y(), QPen(QColor(t["grid"]), 0))
            note = self.scene().addSimpleText(f"{latitude}°N")
            note.setBrush(QColor(t["muted"]))
            note.setPos(project(latitude, 124.3))
        self.district_layer = None
        for level, color, width in (('adm2', 'district', .8), ('adm1', 'province', 1.3)):
            path = QPainterPath()
            for feature in self.boundaries[level]:
                for polygon in feature['polygons']:
                    for ring in polygon:
                        path.moveTo(project(ring[0][1], ring[0][0]))
                        for lon, lat in ring[1:]:
                            path.lineTo(project(lat, lon))
                        path.closeSubpath()
            pen = QPen(QColor(t[color]), width)
            pen.setCosmetic(True)
            layer = self.scene().addPath(path, pen)
            layer.setZValue(-1 if level == 'adm2' else 0)
            if level == 'adm2':
                self.district_layer = layer
        self.province_labels = []
        for feature in self.boundaries['adm1']:
            if not feature['label_point']:
                continue
            lon, lat = feature['label_point']
            name = feature['name']
            for suffix in ('특별자치도', '특별자치시', '통합특별시', '특별시', '광역시'):
                name = name.replace(suffix, '')
            name = {'경기도': '경기', '충청북도': '충북', '충청남도': '충남',
                    '경상북도': '경북', '경상남도': '경남', '전남광주': '전남'}.get(name, name)
            note = self.scene().addSimpleText(name)
            note.setBrush(QColor(t["muted"]))
            note.setPos(project(lat, lon))
            note.setToolTip(feature['name'])
            note.setFlag(note.GraphicsItemFlag.ItemIgnoresTransformations)
            self.province_labels.append((note, feature['code'] in {'26', '27', '28', '30', '31', '36'}))
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
        if self.district_layer:
            self.district_layer.setVisible(self.transform().m11() >= 2.4)
        for note, small in self.province_labels:
            note.setVisible(not small or self.transform().m11() >= 2.4)
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
