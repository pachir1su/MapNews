"""Bundled Lucide SVGs shared by Qt controls, list rows and Leaflet markers."""
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from .themes import tokens

ICON_DIR = Path(__file__).parent / 'resources' / 'icons'
CATEGORY_ICONS = {'사고': 'triangle-alert', '화재': 'flame', '교통': 'car-front',
                  '행사': 'calendar-days', '사회': 'users-round'}
ALIASES = {'refresh': 'refresh-cw', 'more': 'ellipsis', 'back': 'arrow-left',
           'filter': 'sliders-horizontal', 'home': 'locate-fixed', 'fit': 'maximize'}


@lru_cache(maxsize=96)
def svg_text(name: str, color: str) -> str:
    name = ALIASES.get(name, name)
    # Only our registry reaches filesystem paths; news never supplies asset markup.
    if name not in {*CATEGORY_ICONS.values(), *ALIASES.values(), 'map-pin', 'layers',
                    'plus', 'minus', 'x', 'search', 'arrow-up-right'}:
        name = 'map-pin'
    return (ICON_DIR / f'{name}.svg').read_text(encoding='utf-8').replace('currentColor', color)


@lru_cache(maxsize=96)
def renderer(name: str, color: str):
    return QSvgRenderer(QByteArray(svg_text(name, color).encode()))


def icon(name: str, dark=False, color=None):
    image = QPixmap(48, 48)
    image.fill('transparent')
    painter = QPainter(image)
    renderer(name, color or tokens(dark)['muted']).render(painter)
    painter.end()
    image.setDevicePixelRatio(2)
    return QIcon(image)


def category_icon(category, color='#ffffff'):
    return renderer(CATEGORY_ICONS.get(category, 'map-pin'), color)
