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
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addWidget(label("기사 상세", "heading"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 14, 0, 12)
        body.setSpacing(14)
        self.badge = label("", "badge", True)
        self.title = label("목록이나 지도에서\n뉴스를 선택하세요", "heading", True)
        self.meta = label("", "muted", True)
        self.summary = label("", "", True)
        self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.note = label("", "muted", True)
        self.link = label("", "muted", True)
        for widget in (self.badge, self.title, self.meta, label("AI 요약", "badge"),
                       self.summary, self.note, self.link):
            body.addWidget(widget)
        body.addStretch()
        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)
        self.locate_button = QPushButton("지도에서 위치 확인")
        self.locate_button.setObjectName("primary")
        self.open_button = QPushButton("기사 원문 열기 ↗")
        self.locate_button.clicked.connect(self._locate)
        self.open_button.clicked.connect(self._open)
        layout.addWidget(self.locate_button)
        layout.addWidget(self.open_button)
        self.set_item(None)

    def set_item(self, item: NewsItem | None):
        self.item = item
        self.badge.setText(f"{item.category}  /  {'MOCK · 가상 기사' if item.is_mock else '외부 제공 데이터'}"
                           if item else "")
        self.title.setText(item.title if item else "목록이나 지도에서\n뉴스를 선택하세요")
        self.meta.setText(f"{item.location}\n{item.date_label} KST" if item else "")
        self.summary.setText(item.summary if item else "선택한 기사의 요약과 위치를 여기서 확인합니다.")
        self.note.setText((item.coordinate_note or
                           ("제공된 좌표" if item.has_coordinates else "좌표 미제공 · 지도 표시 불가"))
                          if item else "")
        self.link.setText(item.url if item else "")
        self.locate_button.setEnabled(bool(item and item.has_coordinates))
        # Mock example.com links are placeholders, not genuine news.
        self.open_button.setEnabled(bool(item and safe_url(item.url) and not item.is_mock))
        self.open_button.setToolTip("시연 기사는 실제 원문이 없습니다." if item and item.is_mock
                                   else "검증된 HTTP(S) 주소를 기본 브라우저에서 엽니다.")
        self.scroll.verticalScrollBar().setValue(0)

    def _locate(self):
        if self.item and self.item.has_coordinates:
            self.locate.emit(self.item.id)

    def _open(self):
        if self.item and not self.item.is_mock and safe_url(self.item.url):
            if not QDesktopServices.openUrl(QUrl(self.item.url)):
                self.notice.emit("기본 브라우저를 열 수 없습니다. 원문 주소를 확인하세요.")
