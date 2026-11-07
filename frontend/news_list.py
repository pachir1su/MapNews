"""Virtualized list: paint visible cards instead of creating one widget per article."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPen, QTextLayout, QTextOption
from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from .themes import tokens
from .icons import category_icon

ITEM_ROLE = Qt.UserRole + 1


class NewsListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.items):
            return None
        item = self.items[index.row()]
        if role == ITEM_ROLE:
            return item
        if role in (Qt.DisplayRole, Qt.AccessibleTextRole):
            return f"{item.category} · {item.title} · {item.location} · {item.date_label}"
        if role == Qt.ToolTipRole:
            return item.title + "\n" + item.summary
        return None

    def replace(self, items):
        self.beginResetModel()
        self.items = list(items)
        self.endResetModel()


class NewsDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dark = False

    def sizeHint(self, option, index):
        return QSize(300, 116)

    def paint(self, painter, option, index):
        item = index.data(ITEM_ROLE)
        if item is None:
            return
        t = tokens(self.dark)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        box = option.rect.adjusted(0, 3, -1, -3)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(t['selected'] if selected else t['input'] if hovered else t['panel']))
        painter.drawRoundedRect(box, 12, 12)
        glyph = QRectF(box.x() + 12, box.y() + 20, 32, 32)
        painter.setBrush(QColor(t['input'] if not selected else t['panel']))
        painter.drawRoundedRect(glyph, 10, 10)
        category_icon(item.category, item.color).render(painter, glyph.adjusted(7, 7, -7, -7))
        x, y, width = box.x() + 56, box.y() + 19, max(20, box.width() - 70)
        font = QFont(option.font)
        font.setPixelSize(15)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(t['text']))
        title = item.title.replace('\n', ' ')
        text = QTextLayout(title, font)
        text_option = QTextOption()
        text_option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        text.setTextOption(text_option)
        text.beginLayout()
        first = text.createLine()
        first.setLineWidth(width)
        first.setPosition(QPointF(0, 0))
        second = text.createLine()
        if second.isValid():
            second.setLineWidth(width)
        text.endLayout()
        first.draw(painter, QPointF(x, y))
        if second.isValid():
            remaining = title[second.textStart():]
            painter.drawText(QRect(x, y + 23, width, 24), Qt.AlignLeft | Qt.AlignVCenter,
                             painter.fontMetrics().elidedText(remaining, Qt.ElideRight, width))
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(t['muted']))
        date = item.date_label[5:] if item.published_at else ''
        metadata = ' · '.join(part for part in (item.location, date) if part)
        painter.drawText(QRect(x, y + 57, width, 20), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(metadata, Qt.ElideRight, width))
        if option.state & QStyle.State_HasFocus:
            painter.setPen(QPen(QColor(t['accent']), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(box.adjusted(1, 1, -1, -1), 11, 11)
        painter.restore()
