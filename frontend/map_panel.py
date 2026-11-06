from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout
from .detail import label
from .offline_map import OfflineMap


class MapPanel(QFrame):
    selected = Signal(str)
    notice = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.rows = []
        self.current_id = None
        self.dark = False
        self.web = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        toolbar = QHBoxLayout()
        toolbar.addWidget(label("지역별 뉴스", "heading"))
        toolbar.addStretch()
        self.mode = QComboBox()
        self.mode.addItems(["오프라인 좌표", "온라인 지도"])
        self.mode.setAccessibleName("지도 표시 방식")
        toolbar.addWidget(self.mode)
        for title, handler in (("−", lambda: self.active.zoom(0.8)),
                               ("+", lambda: self.active.zoom(1.25)),
                               ("결과", lambda: self.active.fit_results()),
                               ("전국", lambda: self.active.home())):
            button = QPushButton(title)
            button.setToolTip({"−": "축소", "+": "확대", "결과": "검색 결과 전체를 지도에 맞춤",
                               "전국": "초기 위치로 이동"}[title])
            button.setAccessibleName(button.toolTip())
            button.clicked.connect(handler)
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        self.stack = QStackedWidget()
        self.offline = OfflineMap()
        self.offline.selected.connect(self.selected)
        self.stack.addWidget(self.offline)
        layout.addWidget(self.stack, 1)
        self.caption = label("", "muted", True)
        layout.addWidget(self.caption)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self._caption()
        if self.offline.resource_error:
            QTimer.singleShot(0, lambda: self.notice.emit(self.offline.resource_error))

    @property
    def active(self):
        return self.web if self.mode.currentIndex() == 1 and self.web else self.offline

    def _caption(self):
        offline_caption = ("오프라인 좌표 격자 · 지형 자원 없음 / 마커 탐색 가능" if self.offline.resource_error else
                           "오프라인 · Natural Earth 저해상도 지도 / 도로 정보 없음 / 마커 클릭으로 기사 선택")
        self.caption.setText(offline_caption
                             if self.mode.currentIndex() == 0 else
                             "온라인 · © OpenStreetMap contributors / 지도 타일에 인터넷 필요")

    def _mode_changed(self, index):
        self._caption()
        if index == 0:
            if self.web:
                self.web.shutdown()
                old = self.web
                self.web = None
                self.stack.removeWidget(old)
                if old.builder.isRunning():
                    old.builder.finished.connect(old.deleteLater)
                else:
                    old.deleteLater()
            self.stack.setCurrentWidget(self.offline)
            return
        try:
            from .web_map import WebMap
            self.web = WebMap(self)
            self.web.selected.connect(self.selected)
            current_web = self.web
            self.web.failed.connect(lambda reason: self._fallback(reason) if self.web is current_web else None)
            self.stack.addWidget(self.web)
            self.stack.setCurrentWidget(self.web)
            self.web.set_items(self.rows)
            self.web.set_theme(self.dark)
            self.web.set_selected(self.current_id)
            self.notice.emit("온라인 지도를 연결하고 있습니다…")
        except (ImportError, RuntimeError):
            self._fallback("QtWebEngine을 사용할 수 없습니다.")

    def _fallback(self, reason):
        self.mode.setCurrentIndex(0)
        self.notice.emit(reason + " 오프라인 좌표 화면을 사용합니다.")

    def set_items(self, items):
        self.rows = list(items)
        self.offline.set_items(items)
        if self.web:
            self.web.set_items(items)

    def set_selected(self, identifier, focus=False):
        self.current_id = identifier
        self.offline.set_selected(identifier, focus)
        if self.web:
            self.web.set_selected(identifier, focus)

    def set_theme(self, dark):
        self.dark = dark
        self.offline.set_theme(dark)
        if self.web:
            self.web.set_theme(dark)

    def shutdown(self):
        self.offline.close_picker()
        self.mode.setCurrentIndex(0)
