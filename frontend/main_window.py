"""Application shell: wires views to state and provider events, without backend imports."""
from PySide6.QtCore import QByteArray, QSettings, QSize, QThread, QTimer, Qt, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame,
                               QHBoxLayout, QListView, QMainWindow, QPushButton,
                               QLineEdit, QProgressBar, QSplitter, QVBoxLayout, QWidget, QToolButton, QMenu, QStackedWidget)
from .detail import DetailPanel, label
from .map_panel import MapPanel
from .models import CATEGORIES, NewsBatch
from .news_list import ITEM_ROLE, NewsDelegate, NewsListModel
from .providers import JsonNewsProvider, MockNewsProvider
from .state import FilterState, NewsState
from .themes import apply_theme, system_is_dark
from .icons import icon
from .workers import LoadWorker
from .bookmarks import MAX_BOOKMARKS, bookmark_key, read_bookmarks, write_bookmarks


class MainWindow(QMainWindow):
    def __init__(self, provider=None, *, settings=None, auto_load=True, online=True):
        super().__init__()
        self.setWindowTitle("MapNews")
        self.setMinimumSize(800, 600)
        self.resize(1500, 900)
        self.settings = settings if settings is not None else QSettings("KOREATECH-Team5", "MapNews")
        self.settings.remove("dark")
        self.dark = system_is_dark(QApplication.styleHints().colorScheme())
        self.provider = provider or MockNewsProvider()
        self.state = NewsState()
        self.state.saved_keys = read_bookmarks(self.settings.value('bookmarks_v1', '[]'))
        self.worker = None
        self.pending_provider = None
        self.setAcceptDrops(True)
        self.closing = False
        self.batch = None
        self.load_error = ""
        self.load_cancelled = False
        self.category_buttons = {}
        self._map_result_ids = None
        self._shortcuts = []
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
        top = QHBoxLayout(header)
        top.setContentsMargins(24, 14, 24, 14)
        top.setSpacing(16)
        top.addWidget(label("MapNews", "brand"))
        top.addSpacing(18)
        self.search = QLineEdit()
        self.search.setPlaceholderText("지역, 뉴스 검색")
        self.search.setClearButtonEnabled(True)
        self.search.setAcceptDrops(False)
        self.search.setAccessibleName("뉴스 검색")
        self.search.setToolTip("Ctrl+K")
        self.search.setMaximumWidth(620)
        top.addWidget(self.search, 1)
        top.addStretch()
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 0)
        self.loading_progress.setFixedSize(64, 4)
        self.loading_progress.setTextVisible(False)
        self.loading_progress.setAccessibleName("불러오는 중")
        top.addWidget(self.loading_progress)
        self.cancel_button = QToolButton()
        self.cancel_button.setAccessibleName("불러오기 취소")
        self.cancel_button.setToolTip("불러오기 취소")
        self.cancel_button.setFixedSize(40, 40)
        self.cancel_button.setIconSize(QSize(20, 20))
        self.cancel_button.clicked.connect(self.cancel_load)
        top.addWidget(self.cancel_button)
        self.loading_progress.hide()
        self.cancel_button.hide()
        self.more_button = QToolButton()
        self.more_button.setFixedSize(40, 40)
        self.more_button.setIconSize(QSize(20, 20))
        self.more_button.setAccessibleName("더 보기")
        self.more_button.setToolTip("더 보기")
        self.more_button.setPopupMode(QToolButton.InstantPopup)
        self.more_menu = QMenu(self)
        self.refresh_button = self.more_menu.addAction("새로고침")
        self.refresh_button.setToolTip("F5")
        self.import_button = self.more_menu.addAction("뉴스 파일 열기…")
        self.default_data_action = self.more_menu.addAction("기본 데이터로 돌아가기")
        self.more_menu.addSeparator()
        self.more_menu.addAction("정보", self.show_information)
        self.more_menu.addAction("불러오기 정보", self.show_load_details)
        self.more_button.setMenu(self.more_menu)
        top.addWidget(self.more_button)
        layout.addWidget(header)
        self.banner = label("", "notice", True)
        self.banner.hide()
        layout.addWidget(self.banner)
        self.notice_timer = QTimer(self)
        self.notice_timer.setSingleShot(True)
        self.notice_timer.timeout.connect(self.banner.hide)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        self.panel_stack = QStackedWidget()
        self.panel_stack.setMinimumWidth(320)
        self.panel_stack.setMaximumWidth(440)
        self.sidebar = self._sidebar()
        self.detail = DetailPanel()
        self.detail.back.connect(self.dismiss_detail)
        self.detail.navigate.connect(self.navigate_article)
        self.detail.bookmark.connect(self.toggle_bookmark)
        self.panel_stack.addWidget(self.sidebar)
        self.panel_stack.addWidget(self.detail)
        self.map = MapPanel(online=online)
        self.map.setMinimumWidth(320)
        self.splitter.addWidget(self.panel_stack)
        self.splitter.addWidget(self.map)
        self.splitter.setSizes([370, 1100])
        saved = self.settings.value('splitter')
        if isinstance(saved, QByteArray):
            self.splitter.restoreState(saved)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter, 1)
        self.setCentralWidget(root)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(160)
        self.debounce.timeout.connect(self.apply_filters)
        self.search.textChanged.connect(self._search_changed)
        self.search.returnPressed.connect(self.apply_filters)
        self.refresh_button.triggered.connect(self.reload)
        self.import_button.triggered.connect(self.open_json)
        self.default_data_action.triggered.connect(self.use_default_data)
        self.news.selectionModel().currentChanged.connect(self._list_selected)
        self.news.clicked.connect(lambda index: self.show_detail())
        self.news.activated.connect(lambda index: self.show_detail())
        self.map.selected.connect(self._map_selected)
        self.map.notice.connect(self.show_notice)
        self.detail.locate.connect(self.locate_news)
        self.detail.notice.connect(self.show_notice)
        for key, handler in (("Ctrl+K", self.search.setFocus), ("Ctrl+F", self.search.setFocus),
                             ("F5", self.reload), ("Ctrl+Return", self.show_detail),
                             ("Escape", self.dismiss_detail)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)
        for key, handler in (('Ctrl+O', self.open_json), ('Ctrl+L', self.focus_list),
                             ('Ctrl+D', self.toggle_bookmark),
                             ('Alt+Left', self.dismiss_detail),
                             ('Alt+Up', lambda: self.navigate_article(-1)),
                             ('Alt+Down', lambda: self.navigate_article(1))):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)
        shortcut = QShortcut(QKeySequence('Down'), self.search)
        shortcut.setContext(Qt.WidgetShortcut)
        shortcut.activated.connect(self.focus_list)
        self._shortcuts.append(shortcut)
        QApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        self.apply_theme()
        if auto_load:
            QTimer.singleShot(0, self.reload)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'panel_stack'):
            self.panel_stack.setMaximumWidth(340 if self.width() < 1100 else 440)

    def focus_list(self):
        if self.debounce.isActive():
            self.apply_filters()
        self.panel_stack.setCurrentWidget(self.sidebar)
        if self.model.rowCount() and not self.news.currentIndex().isValid():
            self.news.setCurrentIndex(self.model.index(0))
        self.news.setFocus()

    def _sidebar(self):
        panel = QFrame()
        panel.setObjectName("sidebar")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)
        toolbar = QHBoxLayout()
        self.sort = QComboBox()
        self.sort.setObjectName("sort")
        self.sort.addItems(["최신순", "오래된순"])
        self.sort.setAccessibleName("기사 정렬")
        self.sort.currentIndexChanged.connect(self.apply_filters)
        toolbar.addWidget(self.sort)
        toolbar.addStretch()
        self.saved_button = QToolButton()
        self.saved_button.setFixedSize(40, 40)
        self.saved_button.setIconSize(QSize(20, 20))
        self.saved_button.setCheckable(True)
        self.saved_button.setAccessibleName('저장한 기사만 보기')
        self.saved_button.setToolTip('저장한 기사')
        self.saved_button.toggled.connect(self.apply_filters)
        toolbar.addWidget(self.saved_button)
        self.filter_button = QPushButton("필터")
        self.filter_button.setCheckable(True)
        self.filter_button.setAccessibleName("검색 필터 펼치기")
        toolbar.addWidget(self.filter_button)
        layout.addLayout(toolbar)
        self.filters_panel = QWidget()
        filters = QVBoxLayout(self.filters_panel)
        filters.setContentsMargins(0, 4, 0, 8)
        filters.setSpacing(12)
        self.category_layout = QHBoxLayout()
        self.category_layout.setSpacing(4)
        for category in CATEGORIES:
            button = QPushButton(category)
            button.setCheckable(True)
            button.setChecked(True)
            button.setStyleSheet("padding:7px 7px;")
            button.setAccessibleName(category + " 기사 포함")
            button.clicked.connect(self.apply_filters)
            self.category_buttons[category] = button
            self.category_layout.addWidget(button)
        filters.addLayout(self.category_layout)
        self.other_button = QPushButton("기타")
        self.other_button.setCheckable(True)
        self.other_button.setChecked(True)
        self.other_button.clicked.connect(self.apply_filters)
        self.other_button.hide()
        filters.addWidget(self.other_button)
        row = QHBoxLayout()
        self.region = QComboBox()
        self.region.addItem("전체 지역", "")
        self.region.setAccessibleName("지역 필터")
        self.region.currentIndexChanged.connect(self.apply_filters)
        row.addWidget(self.region, 1)
        self.reset_button = QPushButton("초기화")
        self.reset_button.setObjectName("quiet")
        self.reset_button.clicked.connect(self.reset_filters)
        row.addWidget(self.reset_button)
        filters.addLayout(row)
        layout.addWidget(self.filters_panel)
        self.filters_panel.hide()
        self.filter_button.toggled.connect(self.filters_panel.setVisible)
        self.news = QListView()
        self.news.setAccessibleName("뉴스 목록")
        self.news.setUniformItemSizes(True)
        self.news.setMouseTracking(True)
        self.news.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.model = NewsListModel(self.news)
        self.delegate = NewsDelegate(self.news)
        self.news.setModel(self.model)
        self.news.setItemDelegate(self.delegate)
        layout.addWidget(self.news, 1)
        self.empty = label("불러오는 중", "muted", True)
        self.empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty, 1)
        self.empty_reset = QPushButton("필터 초기화")
        self.empty_reset.clicked.connect(self.reset_filters)
        self.empty_reset.hide()
        layout.addWidget(self.empty_reset)
        self.retry_button = QPushButton("다시 불러오기")
        self.retry_button.clicked.connect(self.reload)
        self.retry_button.hide()
        layout.addWidget(self.retry_button)
        self.empty_open = QPushButton("뉴스 파일 열기")
        self.empty_open.clicked.connect(self.open_json)
        self.empty_open.hide()
        layout.addWidget(self.empty_open)
        return panel

    def update_empty_state(self):
        busy = bool(self.worker and self.worker.isRunning())
        has_rows = bool(self.model.items)
        self.empty.setVisible(not has_rows)
        self.news.setVisible(has_rows)
        if not has_rows:
            if self.state.items:
                message = '저장한 기사가 없어요' if (self.state.filters.saved_only
                           and not any(bookmark_key(item) in self.state.saved_keys
                                       for item in self.state.items)) else '검색 결과가 없어요'
            elif busy:
                message = '불러오는 중'
            elif self.load_error:
                message = '뉴스를 불러오지 못했어요'
            elif self.load_cancelled:
                message = '불러오기를 취소했어요'
            else:
                message = '아직 뉴스가 없어요'
            self.empty.setText(message)
        self.empty_reset.setVisible(not has_rows and bool(self.state.items))
        self.empty_reset.setText('전체 기사 보기' if self.state.filters.saved_only else '필터 초기화')
        self.empty_open.setVisible(not self.state.items and not busy)
        self.retry_button.setVisible(not busy and bool(self.load_error or self.load_cancelled))

    @Slot()
    def reload(self):
        if self.closing or (self.worker and self.worker.isRunning()):
            return
        if self.worker:
            self.worker.deleteLater()
        self.notice_timer.stop()
        self.banner.hide()
        self.load_error = ""
        self.load_cancelled = False
        self.refresh_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.default_data_action.setEnabled(False)
        self.retry_button.hide()
        self.loading_progress.show()
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.worker = LoadWorker(self.pending_provider or self.provider, self)
        self.worker.loaded.connect(self._loaded)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._load_finished)
        self.worker.start()
        self.update_empty_state()

    @Slot(object)
    def _loaded(self, batch: NewsBatch):
        if self.closing or (self.worker and self.worker.cancel.is_set()):
            return
        replacing = self.pending_provider is not None
        if replacing and self.worker:
            self.provider = self.worker.provider
            self.pending_provider = None
            self.state.selected_id = None
        self.load_error = ""
        self.load_cancelled = False
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
        if batch.warnings:
            self.show_notice(f"확인이 필요한 데이터가 {len(batch.warnings)}건 있어요.")
            self.banner.setToolTip("\n".join(batch.warnings[:30]))
            self.banner.show()
        if replacing:
            self.reset_filters()
        else:
            self.apply_filters()

    @Slot(str)
    def _failed(self, message):
        if self.closing or (self.worker and self.worker.cancel.is_set()):
            return
        self.load_error = message
        self.notice_timer.stop()
        self.banner.setToolTip("")
        self.banner.setText(message + (" 기존 데이터는 유지합니다." if self.batch else ""))
        self.banner.show()
        if not self.state.items:
            self.empty.setText("뉴스를 불러오지 못했어요")
            self.retry_button.show()
            self.news.hide()
            self.empty.show()

    def _load_finished(self):
        self.loading_progress.hide()
        self.cancel_button.hide()
        self.refresh_button.setEnabled(True)
        self.import_button.setEnabled(True)
        self.default_data_action.setEnabled(True)
        if self.closing:
            QTimer.singleShot(0, self.close)
        elif self.worker and self.worker.cancel.is_set():
            self.pending_provider = None
            self.load_cancelled = True
            self.show_notice('불러오기를 취소했어요.')
            if not self.batch:
                self.news.hide()
                self.empty.setText('불러오기를 취소했어요')
                self.retry_button.show()
                self.empty.show()

        self.update_empty_state()

    @Slot()
    def cancel_load(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)

    def _search_changed(self):
        self.panel_stack.setCurrentWidget(self.sidebar)
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
                                         self.region.currentData() or "", self.sort.currentIndex() == 0,
                                         self.saved_button.isChecked())
        visible = self.state.visible()
        current = self.state.reconcile_selection()
        selection = self.news.selectionModel()
        selection.blockSignals(True)
        self.model.replace(visible)
        if current:
            index = next(i for i, item in enumerate(visible) if item.id == current.id)
            self.news.setCurrentIndex(self.model.index(index))
        selection.blockSignals(False)
        located_ids = frozenset(item.id for item in visible if item.has_coordinates)
        changed = self._map_result_ids is not None and located_ids != self._map_result_ids
        self._map_result_ids = located_ids
        self.map.set_items(visible)
        self._display_selection(current, focus=False)
        if changed and located_ids:
            self.map.active.fit_results()
        self.update_empty_state()
        active = (not all(button.isChecked() for button in self.category_buttons.values())
                  or (any(item.category not in CATEGORIES for item in self.state.items)
                      and not self.other_button.isChecked())
                  or bool(self.region.currentData()))
        self.filter_button.setText("필터 적용 중" if active else "필터")
        self.news.setAccessibleDescription(f"검색 결과 {len(visible)}개")
        self._update_saved_icon()
        if not current:
            self.panel_stack.setCurrentWidget(self.sidebar)

    def reset_filters(self):
        self.saved_button.blockSignals(True)
        self.saved_button.setChecked(False)
        self.saved_button.blockSignals(False)
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
        self.detail.set_saved(bool(item and bookmark_key(item) in self.state.saved_keys))
        ids = [row.id for row in self.model.items]
        index = ids.index(item.id) if item and item.id in ids else -1
        self.detail.set_navigation(index > 0, 0 <= index < len(ids) - 1)
        self.map.set_selected(item.id if item else None, focus)

    def toggle_bookmark(self):
        item = next((item for item in self.model.items if item.id == self.state.selected_id), None)
        if not item:
            return
        key = bookmark_key(item)
        if key in self.state.saved_keys:
            self.state.saved_keys.remove(key)
        elif len(self.state.saved_keys) >= MAX_BOOKMARKS:
            self.detail.set_saved(False)
            self.show_notice('저장 공간이 가득 찼어요. 기존 저장을 해제해 주세요.')
            return
        else:
            self.state.saved_keys.add(key)
        self.settings.setValue('bookmarks_v1', write_bookmarks(self.state.saved_keys))
        self.settings.sync()
        self.detail.set_saved(key in self.state.saved_keys)
        if self.state.filters.saved_only:
            self.apply_filters()
        if self.settings.status() != QSettings.NoError:
            self.show_notice('저장 상태를 기기에 기록하지 못했어요.')

    def _update_saved_icon(self):
        from .themes import tokens
        saved = self.saved_button.isChecked()
        self.saved_button.setIcon(icon('bookmark', self.dark,
                                       tokens(self.dark)['accent'] if saved else None))
        self.saved_button.setToolTip('전체 기사 보기' if saved else '저장한 기사')

    def _map_selected(self, identifier):
        self.select_news(identifier)
        if self.state.selected_id == identifier:
            self.show_detail()

    def navigate_article(self, offset):
        ids = [item.id for item in self.model.items]
        if self.state.selected_id not in ids:
            return
        index = ids.index(self.state.selected_id) + offset
        if 0 <= index < len(ids):
            self.select_news(ids[index])
            self.show_detail()

    def locate_news(self, identifier):
        self.map.set_selected(identifier, focus=True)

    def show_detail(self):
        if self.state.selected_id:
            self.panel_stack.setCurrentWidget(self.detail)
            self.detail.scroll.setFocus()

    def dismiss_detail(self):
        if self.panel_stack.currentWidget() is self.detail:
            self.panel_stack.setCurrentWidget(self.sidebar)
            self.news.setFocus()
        elif self.filters_panel.isVisible():
            self.filter_button.setChecked(False)
        else:
            self.search.clearFocus()

    def show_notice(self, message):
        self.banner.setToolTip("")
        self.banner.setText(message)
        self.banner.show()
        self.notice_timer.start(6000)

    def use_default_data(self):
        if self.worker and self.worker.isRunning():
            return
        self.pending_provider = MockNewsProvider()
        self.reload()

    def open_json(self):
        if self.worker and self.worker.isRunning():
            return
        path, _ = QFileDialog.getOpenFileName(self, '뉴스 JSON 열기',
                                              self.settings.value('import_directory', ''), 'JSON (*.json)')
        if path:
            self.import_json(path)

    def import_json(self, path):
        if self.worker and self.worker.isRunning():
            return
        from pathlib import Path
        self.settings.setValue('import_directory', str(Path(path).parent))
        self.pending_provider = JsonNewsProvider(path)
        self.reload()

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if (not (self.worker and self.worker.isRunning()) and len(urls) == 1
                and urls[0].isLocalFile() and urls[0].toLocalFile().lower().endswith('.json')):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if (not (self.worker and self.worker.isRunning()) and len(urls) == 1
                and urls[0].isLocalFile() and urls[0].toLocalFile().lower().endswith('.json')):
            self.import_json(urls[0].toLocalFile())
            event.acceptProposedAction()
        else:
            event.ignore()

    def show_load_details(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit
        dialog = QDialog(self)
        dialog.setWindowTitle('불러오기 정보')
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.resize(560, 420)
        layout = QVBoxLayout(dialog)
        lines = [self.load_error] if self.load_error else []
        if self.batch:
            lines.extend([self.batch.source, f'기사 {len(self.batch.items)}건',
                          f'좌표 있는 기사 {sum(n.has_coordinates for n in self.batch.items)}건',
                          '', *self.batch.warnings])
        content = QPlainTextEdit()
        content.setReadOnly(True)
        content.setPlainText('\n'.join(lines) if lines else '아직 불러온 데이터가 없어요.')
        layout.addWidget(content)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.close)
        layout.addWidget(buttons)
        dialog.show()

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
        self.filter_button.setIcon(icon("filter", self.dark))
        self.cancel_button.setIcon(icon("x", self.dark))
        self.detail.set_theme(self.dark)
        self._update_saved_icon()

    def closeEvent(self, event):
        self.closing = True
        self.debounce.stop()
        self.notice_timer.stop()
        if self.worker:
            self.worker.cancel.set()
        running = [thread for thread in self.findChildren(QThread) if thread.isRunning()]
        if running:
            event.ignore()
            for thread in running:
                try:
                    thread.finished.connect(self.close, Qt.UniqueConnection)
                except (RuntimeError, TypeError):
                    pass
            return
        self.map.shutdown()
        self.settings.setValue("splitter", self.splitter.saveState())
        self.settings.sync()
        event.accept()
