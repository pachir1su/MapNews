"""Map-first surface: quiet floating controls and a discoverable fallback menu."""
from PySide6.QtCore import QSize, QTimer, Signal, Qt
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (QFrame, QGridLayout, QVBoxLayout, QToolButton,
                               QStackedWidget, QMenu, QWidget)
from .icons import icon
from .offline_map import OfflineMap


class MapPanel(QFrame):
    selected = Signal(str)
    notice = Signal(str)

    def __init__(self, parent=None, *, online=True):
        super().__init__(parent)
        self.setObjectName('mapSurface')
        self.rows = []
        self.current_id = None
        self.dark = False
        self.web = None
        self.online = False
        self.stopped = False
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        self.offline = OfflineMap()
        self.offline.selected.connect(self.selected)
        self.stack.addWidget(self.offline)
        layout.addWidget(self.stack, 0, 0)
        controls = QWidget()
        controls.setObjectName('mapControls')
        column = QVBoxLayout(controls)
        column.setContentsMargins(16, 16, 16, 16)
        column.setSpacing(8)
        self.buttons = {}
        for name, title, handler in (
                ('plus', '확대', lambda: self.active.zoom(1.25)),
                ('minus', '축소', lambda: self.active.zoom(.8)),
                ('home', '전국 보기', lambda: self.active.home()),
                ('fit', '검색 결과에 맞추기', lambda: self.active.fit_results())):
            button = self._button(name, title)
            button.clicked.connect(handler)
            column.addWidget(button)
        self.layer_button = self._button('layers', '지도 선택')
        menu = QMenu(self)
        group = QActionGroup(self)
        self.online_action = menu.addAction('OpenStreetMap')
        self.offline_action = menu.addAction('오프라인 지도')
        for action in (self.online_action, self.offline_action):
            action.setCheckable(True)
            group.addAction(action)
        self.offline_action.setChecked(True)
        self.online_action.triggered.connect(lambda: self.set_online(True))
        self.offline_action.triggered.connect(lambda: self.set_online(False))
        self.layer_button.setMenu(menu)
        self.layer_button.setPopupMode(QToolButton.InstantPopup)
        column.addWidget(self.layer_button)
        layout.addWidget(controls, 0, 0, Qt.AlignTop | Qt.AlignRight)
        if online:
            QTimer.singleShot(0, lambda: self.set_online(True) if not self.stopped else None)

    def _button(self, name, title):
        button = QToolButton()
        button.setObjectName('mapControl')
        button.setFixedSize(44, 44)
        button.setIconSize(QSize(20, 20))
        button.setAccessibleName(title)
        button.setToolTip(title)
        self.buttons[name] = button
        return button

    @property
    def active(self):
        return self.web if self.online and self.web else self.offline

    def set_online(self, enabled):
        if self.stopped or (enabled and self.online and self.web):
            return
        self.online = enabled
        self.online_action.setChecked(enabled)
        self.offline_action.setChecked(not enabled)
        if not enabled:
            if self.web:
                old, self.web = self.web, None
                old.shutdown()
                self.stack.removeWidget(old)
                if old.builder.isRunning():
                    old.builder.finished.connect(old.deleteLater)
                else:
                    old.deleteLater()
            self.stack.setCurrentWidget(self.offline)
            return
        try:
            from .web_map import WebMap
            view = WebMap(self)
            self.web = view
            view.selected.connect(self.selected)
            view.failed.connect(lambda reason: self._fallback(reason) if self.web is view else None)
            self.stack.addWidget(view)
            self.stack.setCurrentWidget(view)
            view.set_items(self.rows)
            view.set_theme(self.dark)
            view.set_selected(self.current_id)
        except (ImportError, RuntimeError):
            self._fallback('지도를 열 수 없어요.')

    def _fallback(self, reason):
        self.set_online(False)
        self.notice.emit('오프라인 지도로 표시해요.')

    def set_items(self, items):
        self.rows = list(items)
        self.offline.set_items(self.rows)
        if self.web:
            self.web.set_items(self.rows)

    def set_selected(self, identifier, focus=False):
        self.current_id = identifier
        self.offline.set_selected(identifier, focus)
        if self.web:
            self.web.set_selected(identifier, focus)

    def set_theme(self, dark):
        self.dark = dark
        self.offline.set_theme(dark)
        for name, button in self.buttons.items():
            button.setIcon(icon(name, dark))
        if self.web:
            self.web.set_theme(dark)

    def shutdown(self):
        self.offline.close_picker()
        self.set_online(False)
        self.stopped = True
