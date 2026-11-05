"""Entirely native, network-free coordinate overview; not a street/boundary map."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsScene, QGraphicsView, QMenu
from .themes import tokens


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
        selected = any(n.id == view.selected_id for n in items)
        self.setBrush(QBrush(QColor(items[0].color if len(items) == 1 else "#577ca7")))
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
                menu = QMenu(self.view)
                for item in self.items:
                    action = menu.addAction(f"[{item.category}] {item.title}")
                    action.triggered.connect(lambda checked=False, key=item.id: self.view.selected.emit(key))
                menu.exec(event.screenPos())
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
        self.setAccessibleName("오프라인 좌표 지도. 목록에서 기사를 선택하거나 마커를 클릭하세요.")
        self.setToolTip("휠: 확대·축소 / 드래그: 이동 / 여러 기사 마커: 기사 선택 메뉴")
        self.items, self.markers = [], []
        self.selected_id = None
        self.dark = False
        self._first_show = True
        self._background()

    def _background(self):
        self.scene().clear()
        self.markers = []
        t = tokens(self.dark)
        self.setBackgroundBrush(QColor(t["map"]))
        # Deliberately a labeled coordinate grid, with no claimed geographical boundaries.
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
        self.setSceneRect(QRectF(project(42, 120), project(28, 136)))
        self._draw_markers()

    def set_theme(self, dark):
        self.dark = dark
        self._background()

    def set_items(self, items):
        self.items = list(items)
        self._draw_markers()

    def _draw_markers(self):
        for marker in self.markers:
            self.scene().removeItem(marker)
        self.markers = []
        for group in cluster_points(self.items, self.transform().m11()):
            marker = Marker(self, group)
            self.scene().addItem(marker)
            self.markers.append(marker)

    def set_selected(self, identifier, focus=False):
        self.selected_id = identifier
        if focus:
            item = next((n for n in self.items if n.id == identifier and n.has_coordinates), None)
            if item:
                self.centerOn(project(item.latitude, item.longitude))
        self._draw_markers()

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
