"""Small original vector icons; no emoji glyphs or external asset requests."""
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from .themes import tokens

PATHS = {
    "refresh": '<path d="M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"/>',
    "more": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
}


def icon(name, dark=False):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'fill="none" stroke="{tokens(dark)["muted"]}" stroke-width="1.8" '
           f'stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>')
    image = QPixmap(48, 48)
    image.fill("transparent")
    painter = QPainter(image)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    image.setDevicePixelRatio(2)
    return QIcon(image)
