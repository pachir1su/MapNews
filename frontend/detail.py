from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QFrame, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)
from .models import NewsItem, safe_url


def label(text="", name="", wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.PlainText)  # News strings can never become rich text.
    widget.setWordWrap(wrap)
    if name:
        widget.setObjectName(name)
    return widget


class DetailPanel(QFrame):
    locate = Signal(str)
    notice = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.item = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(label("선택한 뉴스", "muted"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName('detailContent')
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 24, 0, 12)
        body.setSpacing(20)
        self.badge = label("", "badge", True)
        self.title = label("목록이나 지도에서\n뉴스를 선택하세요", "articleTitle", True)
        self.meta = label("", "muted", True)
        self.summary = label("", "summary", True)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        for widget in (self.badge, self.title, self.meta, label("핵심 요약", "muted"),
                       self.summary):
            body.addWidget(widget)
        body.addStretch()
        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)
        self.locate_button = QPushButton("지도에서 위치 확인")
        self.locate_button.setObjectName("quiet")
        self.open_button = QPushButton("원문 읽기")
        self.open_button.setObjectName("primary")
        self.locate_button.clicked.connect(self._locate)
        self.open_button.clicked.connect(self._open)
        layout.addWidget(self.locate_button)
        layout.addWidget(self.open_button)
        self.set_item(None)

    def set_item(self, item: NewsItem | None):
        self.item = item
        self.badge.setText(f"{item.category}  /  {'데모' if item.is_mock else '뉴스'}"
                           if item else "")
        self.title.setText(item.title if item else "목록이나 지도에서\n뉴스를 선택하세요")
        self.meta.setText(f"{item.location}\n{item.date_label} KST" if item else "")
        self.summary.setText(item.summary if item else "선택한 기사의 요약과 위치를 여기서 확인합니다.")
        self.meta.setToolTip(item.coordinate_note if item else "")
        self.locate_button.setToolTip(item.coordinate_note if item else "")
        self.locate_button.setEnabled(bool(item and item.has_coordinates))
        # Mock example.com links are placeholders, not genuine news.
        self.open_button.setEnabled(bool(item and safe_url(item.url) and not item.is_mock))
        self.open_button.setToolTip("시연 기사는 실제 원문이 없습니다." if item and item.is_mock
                                   else (item.url if item and item.url else "원문 주소가 없어요."))
        self.scroll.verticalScrollBar().setValue(0)

    def _locate(self):
        if self.item and self.item.has_coordinates:
            self.locate.emit(self.item.id)

    def _open(self):
        if self.item and not self.item.is_mock and safe_url(self.item.url):
            if not QDesktopServices.openUrl(QUrl(self.item.url)):
                self.notice.emit("기본 브라우저를 열 수 없습니다. 원문 주소를 확인하세요.")
