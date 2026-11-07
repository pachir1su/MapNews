from PySide6.QtCore import Qt, Signal, QUrl, QSize
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget, QToolButton
from .models import NewsItem, safe_url
from .icons import icon


def label(text="", name="", wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.PlainText)
    widget.setWordWrap(wrap)
    if name:
        widget.setObjectName(name)
    return widget


class DetailPanel(QFrame):
    locate = Signal(str)
    notice = Signal(str)
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('sidebar')
        self.item = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 24)
        layout.setSpacing(16)
        self.back_button = QToolButton()
        self.back_button.setFixedSize(40, 40)
        self.back_button.setIconSize(QSize(20, 20))
        self.back_button.setAccessibleName('뉴스 목록으로')
        self.back_button.setToolTip('뒤로 · Esc')
        self.back_button.clicked.connect(self.back)
        layout.addWidget(self.back_button, 0, Qt.AlignLeft)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName('detailContent')
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 12, 0, 12)
        body.setSpacing(24)
        self.title = label('', 'articleTitle', True)
        self.meta = label('', 'muted', True)
        self.summary = label('', 'summary', True)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        for widget in (self.title, self.meta, self.summary):
            body.addWidget(widget)
        body.addStretch()
        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)
        self.locate_button = QPushButton('지도에서 보기')
        self.locate_button.setObjectName('quiet')
        self.open_button = QPushButton('원문 읽기')
        self.open_button.setObjectName('primary')
        self.locate_button.clicked.connect(self._locate)
        self.open_button.clicked.connect(self._open)
        layout.addWidget(self.locate_button)
        layout.addWidget(self.open_button)
        self.set_item(None)

    def set_theme(self, dark):
        self.back_button.setIcon(icon('back', dark))

    def set_item(self, item: NewsItem | None):
        previous = self.item.id if self.item else None
        self.item = item
        self.title.setText(item.title if item else '')
        self.meta.setText(f'{item.location}\n{item.date_label}' if item else '')
        self.summary.setText(item.summary if item else '')
        self.meta.setToolTip(item.category if item else '')
        self.locate_button.setToolTip(item.coordinate_note if item else '')
        self.locate_button.setVisible(bool(item and item.has_coordinates))
        self.open_button.setVisible(bool(item and safe_url(item.url) and not item.is_mock))
        self.open_button.setToolTip(item.url if item else '')
        if previous != (item.id if item else None):
            self.scroll.verticalScrollBar().setValue(0)

    def _locate(self):
        if self.item and self.item.has_coordinates:
            self.locate.emit(self.item.id)

    def _open(self):
        if self.item and not self.item.is_mock and safe_url(self.item.url):
            if not QDesktopServices.openUrl(QUrl(self.item.url)):
                self.notice.emit('원문을 열 수 없어요.')
