"""Virtualized list: paint visible cards instead of creating one widget per article."""
from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from .themes import tokens

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
        return QSize(300, 144)

    def paint(self, painter, option, index):
        item = index.data(ITEM_ROLE)
        if item is None:
            return
        t = tokens(self.dark)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        box = option.rect.adjusted(0, 4, 0, -4)
        selected = bool(option.state & QStyle.State_Selected)
        painter.setBrush(QColor(t["selected"] if selected else t["panel"]))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(box, 12, 12)
        x, y, w = box.x() + 14, box.y() + 15, box.width() - 28
        font = QFont(option.font)
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(t["accent"] if selected else t["muted"]))
        painter.drawText(QRect(x, y, w, 19), Qt.AlignLeft, item.category)
        painter.setPen(QColor(t["muted"]))
        date = item.date_label[5:] if item.published_at else "시각 미제공"
        painter.drawText(QRect(x, y, w, 19), Qt.AlignRight, date)
        font.setPixelSize(15)
        painter.setFont(font)
        painter.setPen(QColor(t["text"]))
        painter.drawText(QRect(x, y + 27, w, 23), Qt.AlignLeft,
                         painter.fontMetrics().elidedText(item.title, Qt.ElideRight, w))
        font.setPixelSize(12)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(t["muted"]))
        painter.drawText(QRect(x, y + 56, w, 19), Qt.AlignLeft,
                         painter.fontMetrics().elidedText(item.summary, Qt.ElideRight, w))
        painter.drawText(QRect(x, y + 84, w, 19), Qt.AlignLeft,
                         painter.fontMetrics().elidedText(item.location, Qt.ElideRight, w))
        if option.state & QStyle.State_HasFocus:
            painter.setPen(QPen(QColor(t["accent"]), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(box.adjusted(2, 2, -2, -2), 7, 7)
        painter.restore()
