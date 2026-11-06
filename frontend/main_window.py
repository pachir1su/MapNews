"""Application shell: wires views to state and provider events, without backend imports."""
from PySide6.QtCore import QSettings, QThread, QTimer, Qt, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QFrame,
                               QHBoxLayout, QListView, QMainWindow, QPushButton,
                               QLineEdit, QProgressBar, QSplitter, QVBoxLayout, QWidget, QToolButton, QMenu)
from .detail import DetailPanel, label
from .map_panel import MapPanel
from .models import CATEGORIES, NewsBatch
from .news_list import ITEM_ROLE, NewsDelegate, NewsListModel
from .providers import JsonNewsProvider, MockNewsProvider
from .state import FilterState, NewsState
from .themes import apply_theme, system_is_dark
from .icons import icon
from .workers import LoadWorker


class MainWindow(QMainWindow):
    def __init__(self, provider=None, *, settings=None, auto_load=True):
        super().__init__()
        self.setWindowTitle("MapNews · 지역에서 읽는 뉴스")
        self.setMinimumSize(1000, 640)
        self.resize(1500, 900)
        self.settings = settings if settings is not None else QSettings("KOREATECH-Team5", "MapNews")
        self.settings.remove("dark")  # Migrate away from the former manual preference.
        self.dark = system_is_dark(QApplication.styleHints().colorScheme())
        self.provider = provider or MockNewsProvider()
        self.state = NewsState()
        self.worker = None
        self.closing = False
        self.batch = None
        self.category_buttons = {}
        self._shortcuts = []
        root = QWidget()
        root.setFocusPolicy(Qt.ClickFocus)
        root.setFocus()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
        top = QHBoxLayout(header)
        top.setContentsMargins(28, 16, 24, 16)
        top.setSpacing(12)
        top.addWidget(label("MapNews", "brand"))
        self.source_label = label("준비 중", "source")
        top.addWidget(self.source_label)
        top.addSpacing(24)
        self.search = QLineEdit()
        self.search.setPlaceholderText("궁금한 지역이나 뉴스를 검색하세요")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("뉴스 키워드 검색")
        self.search.setToolTip("제목·요약·지역 검색 · Ctrl+K")
        top.addWidget(self.search, 1)
        self.refresh_button = QPushButton()
        self.refresh_button.setFixedSize(42, 42)
        self.refresh_button.setAccessibleName("새로고침")
        self.refresh_button.setToolTip("새로고침 · F5")
        top.addWidget(self.refresh_button)
        self.detail_button = QPushButton("기사 보기")
        top.addWidget(self.detail_button)
        self.more_button = QToolButton()
        self.more_button.setFixedSize(42, 42)
        self.more_button.setAccessibleName("더 보기")
        self.more_button.setToolTip("데이터 열기 및 앱 정보")
        self.more_button.setPopupMode(QToolButton.InstantPopup)
        self.more_menu = QMenu(self)
        self.import_button = self.more_menu.addAction("뉴스 파일 열기…")
        self.demo_button = self.more_menu.addAction("데모 데이터로 보기")
        self.more_menu.addSeparator()
        self.more_menu.addAction("지도 및 데이터 정보", self.show_information)
        self.more_button.setMenu(self.more_menu)
        top.addWidget(self.more_button)
        layout.addWidget(header)
        self.banner = label("", "notice", True)
        self.banner.hide()
        layout.addWidget(self.banner)
        self.notice_timer = QTimer(self)
        self.notice_timer.setSingleShot(True)
        self.notice_timer.timeout.connect(self.banner.hide)
        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(16, 16, 16, 16)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.sidebar = self._sidebar()
        self.sidebar.setMinimumWidth(290)
        self.map = MapPanel()
        self.map.setMinimumWidth(410)
        self.detail = DetailPanel()
        self.detail.setMinimumWidth(280)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.map)
        self.splitter.addWidget(self.detail)
        self.splitter.setSizes([350, 760, 320])
        self.splitter.setHandleWidth(12)
        self.splitter.setStretchFactor(1, 1)
        workspace_layout.addWidget(self.splitter)
        layout.addWidget(workspace, 1)
        self.setCentralWidget(root)
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 0)
        self.loading_progress.setFixedWidth(90)
        self.loading_progress.setMaximumHeight(12)
        self.loading_progress.setAccessibleName('뉴스 로딩 중')
        self.cancel_button = QPushButton('로딩 취소')
        self.cancel_button.setToolTip('현재 로딩을 취소합니다. 기존 뉴스는 유지합니다.')
        self.cancel_button.clicked.connect(self.cancel_load)
        top.insertWidget(4, self.loading_progress)
        top.insertWidget(5, self.cancel_button)
        self.loading_progress.hide()
        self.cancel_button.hide()
        self.detail_dialog = QDialog(self)
        self.detail_dialog.setWindowTitle("MapNews · 기사 상세")
        self.detail_dialog.resize(440, 630)
        dialog_layout = QVBoxLayout(self.detail_dialog)
        self.dialog_detail = DetailPanel()
        dialog_layout.addWidget(self.dialog_detail)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(160)
        self.debounce.timeout.connect(self.apply_filters)
        self.search.textChanged.connect(self._search_changed)
        self.search.returnPressed.connect(self.apply_filters)
        self.refresh_button.clicked.connect(self.reload)
        self.import_button.triggered.connect(self.open_json)
        self.demo_button.triggered.connect(self.use_demo)
        self.detail_button.clicked.connect(self.show_detail)
        self.news.selectionModel().currentChanged.connect(self._list_selected)
        self.news.doubleClicked.connect(lambda _: self.show_detail())
        self.map.selected.connect(self.select_news)
        self.map.notice.connect(self.show_notice)
        for detail in (self.detail, self.dialog_detail):
            detail.locate.connect(self.locate_news)
            detail.notice.connect(self.show_notice)
        for key, handler in (("Ctrl+K", self.search.setFocus), ("Ctrl+F", self.search.setFocus),
                             ("F5", self.reload),
                             ("Ctrl+Return", self.show_detail), ("Escape", self.dismiss_detail)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)
        QApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        self.apply_theme()
        if auto_load:
            QTimer.singleShot(0, self.reload)

    def _sidebar(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 20, 16, 12)
        layout.setSpacing(14)
        title = QHBoxLayout()
        title.addWidget(label("지금 올라온 뉴스", "heading"))
        title.addStretch()
        self.reset_button = QPushButton("초기화")
        self.reset_button.setObjectName("quiet")
        self.reset_button.setToolTip("키워드·분류·지역·정렬 초기화")
        self.reset_button.clicked.connect(self.reset_filters)
        title.addWidget(self.reset_button)
        layout.addLayout(title)
        self.category_layout = QHBoxLayout()
        self.category_layout.setSpacing(3)
        for category in CATEGORIES:
            button = QPushButton(category)
            button.setCheckable(True)
            button.setChecked(True)
            button.setStyleSheet("padding:7px 7px;")
            button.setAccessibleName(category + " 기사 포함")
            button.clicked.connect(self.apply_filters)
            self.category_buttons[category] = button
            self.category_layout.addWidget(button)
        layout.addLayout(self.category_layout)
        self.other_button = QPushButton("기타 분류 포함")
        self.other_button.setCheckable(True)
        self.other_button.setChecked(True)
        self.other_button.clicked.connect(self.apply_filters)
        self.other_button.hide()
        layout.addWidget(self.other_button)
        row = QHBoxLayout()
        self.region = QComboBox()
        self.region.addItem("전체 지역", "")
        self.region.setAccessibleName("지역 필터")
        self.region.currentIndexChanged.connect(self.apply_filters)
        self.sort = QComboBox()
        self.sort.addItems(["최신순", "오래된순"])
        self.sort.setAccessibleName("기사 정렬")
        self.sort.currentIndexChanged.connect(self.apply_filters)
        row.addWidget(self.region, 1)
        row.addWidget(self.sort)
        layout.addLayout(row)
        self.count = label("0건", "muted")
        layout.addWidget(self.count)
        self.news = QListView()
        self.news.setAccessibleName("뉴스 목록. 방향키로 선택, Ctrl+Enter로 상세 보기")
        self.news.setUniformItemSizes(True)
        self.news.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.model = NewsListModel(self.news)
        self.delegate = NewsDelegate(self.news)
        self.news.setModel(self.model)
        self.news.setItemDelegate(self.delegate)
        layout.addWidget(self.news, 1)
        self.empty = label("데이터를 불러오는 중입니다.", "muted", True)
        self.empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty, 1)
        return panel

    @Slot()
    def reload(self):
        if self.closing or (self.worker and self.worker.isRunning()):
            return
        if self.worker:
            self.worker.deleteLater()
        self.notice_timer.stop()
        self.banner.hide()
        self.refresh_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.demo_button.setEnabled(False)
        self.loading_progress.show()
        self.cancel_button.setText('로딩 취소')
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.source_label.setText("불러오는 중")
        self.worker = LoadWorker(self.provider, self)
        self.worker.loaded.connect(self._loaded)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._load_finished)
        self.worker.start()

    @Slot(object)
    def _loaded(self, batch: NewsBatch):
        if self.closing or (self.worker and self.worker.cancel.is_set()):
            return
        self.batch = batch
        self.state.items = batch.items
        selected_region = self.region.currentData()
        self.region.blockSignals(True)
        self.region.clear()
        self.region.addItem("전체 지역", "")
        for region in sorted({item.location.split()[0] for item in batch.items}):
            self.region.addItem(region, region)
        index = self.region.findData(selected_region)
        self.region.setCurrentIndex(max(0, index))
        self.region.blockSignals(False)
        self.other_button.setVisible(any(item.category not in CATEGORIES for item in batch.items))
        for category, button in self.category_buttons.items():
            count = sum(item.category == category for item in batch.items)
            button.setToolTip(f"{category} {count}건 · 여러 분류를 동시에 선택할 수 있습니다")
        self.source_label.setText("데모" if batch.items and all(n.is_mock for n in batch.items) else "뉴스 데이터")
        self.source_label.setToolTip(batch.source)
        if batch.warnings:
            self.show_notice(f"확인이 필요한 데이터가 {len(batch.warnings)}건 있어요.")
            self.banner.setToolTip("\n".join(batch.warnings[:30]))
            self.banner.show()
        self.apply_filters()

    @Slot(str)
    def _failed(self, message):
        if self.closing or (self.worker and self.worker.cancel.is_set()):
            return
        self.notice_timer.stop()
        self.banner.setText(message + (" 기존 데이터는 유지합니다." if self.batch else ""))
        self.banner.show()
        if not self.state.items:
            self.empty.setText("데이터를 불러오지 못했습니다.\n상단의 새로고침 또는 데모를 선택하세요.")
            self.news.hide()
            self.empty.show()

    def _load_finished(self):
        self.loading_progress.hide()
        self.cancel_button.hide()
        self.source_label.setText("데모" if self.batch and all(n.is_mock for n in self.batch.items) else "뉴스 데이터" if self.batch else "데이터 없음")
        self.refresh_button.setEnabled(True)
        self.import_button.setEnabled(True)
        self.demo_button.setEnabled(True)
        if self.closing:
            QTimer.singleShot(0, self.close)
        elif self.worker and self.worker.cancel.is_set():
            self.show_notice('불러오기를 취소했어요.')
            if not self.batch:
                self.source_label.setText('데이터 없음')
                self.news.hide()
                self.empty.setText('로딩을 취소했습니다.\n새로고침 또는 데모를 선택하세요.')
                self.empty.show()

    @Slot()
    def cancel_load(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText('취소 중…')
            self.source_label.setText('취소 중')

    def _search_changed(self):
        self.count.setText("검색 중")
        self.debounce.start()

    @Slot()
    def apply_filters(self):
        if not hasattr(self, "map"):
            return
        self.debounce.stop()
        categories = {name for name, button in self.category_buttons.items() if button.isChecked()}
        if self.other_button.isChecked():
            categories.update(item.category for item in self.state.items if item.category not in CATEGORIES)
        self.state.filters = FilterState(self.search.text(), categories,
                                         self.region.currentData() or "", self.sort.currentIndex() == 0)
        visible = self.state.visible()
        current = self.state.reconcile_selection()
        selection = self.news.selectionModel()
        selection.blockSignals(True)
        self.model.replace(visible)
        if current:
            index = next(i for i, item in enumerate(visible) if item.id == current.id)
            self.news.setCurrentIndex(self.model.index(index))
        selection.blockSignals(False)
        self.map.set_items(visible)
        self._display_selection(current, focus=False)
        self.news.setVisible(bool(visible))
        self.empty.setVisible(not visible)
        self.empty.setText("검색 결과가 없습니다.\n검색어와 필터를 바꾸거나 초기화하세요."
                           if self.state.items else "등록된 뉴스가 없습니다.\nJSON 파일을 열거나 데모를 시작하세요.")
        located = sum(item.has_coordinates for item in visible)
        self.count.setText(f"뉴스 {len(visible)}개")
        self.count.setToolTip(f"전체 {len(self.state.items)}개 · 지도에 표시 {located}개")

    def reset_filters(self):
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        for button in self.category_buttons.values():
            button.setChecked(True)
        self.other_button.setChecked(True)
        self.region.blockSignals(True)
        self.region.setCurrentIndex(0)
        self.region.blockSignals(False)
        self.sort.blockSignals(True)
        self.sort.setCurrentIndex(0)
        self.sort.blockSignals(False)
        self.apply_filters()

    def _list_selected(self, current, previous):
        item = current.data(ITEM_ROLE)
        if item:
            self.select_news(item.id)

    @Slot(str)
    def select_news(self, identifier):
        if not any(item.id == identifier for item in self.model.items):
            return  # Ignore forged/stale marker ids without changing the selection.
        item = self.state.select(identifier)
        selection = self.news.selectionModel()
        selection.blockSignals(True)
        row = next(i for i, item in enumerate(self.model.items) if item.id == identifier)
        index = self.model.index(row)
        self.news.setCurrentIndex(index)
        self.news.scrollTo(index)
        selection.blockSignals(False)
        self._display_selection(item, focus=True)

    def _display_selection(self, item, focus):
        self.detail.set_item(item)
        self.dialog_detail.set_item(item)
        self.map.set_selected(item.id if item else None, focus)
        self.detail_button.setEnabled(item is not None)

    def locate_news(self, identifier):
        self.map.set_selected(identifier, focus=True)
        self.detail_dialog.hide()

    def show_detail(self):
        if self.state.selected_id:
            self.detail_dialog.show()
            self.detail_dialog.raise_()
            self.detail_dialog.activateWindow()

    def dismiss_detail(self):
        self.detail_dialog.hide()
        self.search.clearFocus()

    def show_notice(self, message):
        self.banner.setText(message)
        self.banner.show()
        self.notice_timer.start(6000)

    def use_demo(self):
        if self.worker and self.worker.isRunning():
            return
        self.provider = MockNewsProvider()
        self.reset_filters()
        self.reload()

    def open_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "뉴스 JSON 열기", "", "JSON (*.json)")
        if path:
            self.provider = JsonNewsProvider(path)
            self.reload()

    def show_information(self):
        from .information import InformationDialog
        dialog = InformationDialog(self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.show()

    def _system_theme_changed(self, scheme):
        if not self.closing:
            self.dark = system_is_dark(scheme)
            self.apply_theme()

    def apply_theme(self):
        apply_theme(QApplication.instance(), self.dark)
        self.delegate.dark = self.dark
        self.news.viewport().update()
        self.map.set_theme(self.dark)
        self.refresh_button.setIcon(icon("refresh", self.dark))
        self.more_button.setIcon(icon("more", self.dark))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "detail"):
            self.detail.setVisible(self.width() >= 1250)
            self.detail_button.setVisible(self.width() < 1250)

    def closeEvent(self, event):
        self.closing = True
        self.debounce.stop()
        self.notice_timer.stop()
        if self.worker:
            self.worker.cancel.set()
        running = [thread for thread in self.findChildren(QThread) if thread.isRunning()]
        if running:
            event.ignore()
            self.source_label.setText("종료 중")
            for thread in running:
                try:
                    thread.finished.connect(self.close, Qt.UniqueConnection)
                except (RuntimeError, TypeError):
                    pass
            return
        self.map.shutdown()
        self.detail_dialog.close()
        self.settings.sync()
        event.accept()
