"""A virtualized, searchable picker for dense clusters; no thousands of QActions."""
from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal, Slot
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QListView, QPushButton, QVBoxLayout
from .detail import label
from .news_list import ITEM_ROLE, NewsDelegate, NewsListModel


class ClusterDialog(QDialog):
    selected = Signal(str)

    def __init__(self, items, *, dark=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle('MapNews · 이 지역의 뉴스')
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(620, 650)
        self.setMinimumSize(360, 400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addWidget(label('이 지역의 뉴스', 'heading'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('이 군집에서 제목·지역·분류 검색')
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('군집 기사 검색')
        layout.addWidget(self.search)
        self.count = label('', 'muted')
        layout.addWidget(self.count)
        self.model = NewsListModel(self)
        self.model.replace(items)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.news = QListView()
        self.news.setModel(self.proxy)
        self.news.setUniformItemSizes(True)
        self.news.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.news.setAccessibleName('군집 뉴스 목록')
        self.delegate = NewsDelegate(self.news)
        self.delegate.dark = dark
        self.news.setItemDelegate(self.delegate)
        layout.addWidget(self.news, 1)
        self.empty = label('검색 결과가 없습니다.', 'muted')
        layout.addWidget(self.empty)
        buttons = QHBoxLayout()
        buttons.addStretch()
        close = QPushButton('닫기')
        close.clicked.connect(self.close)
        self.choose = QPushButton('기사 선택')
        self.choose.setObjectName('primary')
        self.choose.setDefault(True)
        self.choose.clicked.connect(self.choose_current)
        buttons.addWidget(close)
        buttons.addWidget(self.choose)
        layout.addLayout(buttons)
        self.search.textChanged.connect(self.filter_items)
        self.search.returnPressed.connect(self.choose_current)
        self.news.activated.connect(self.choose_current)
        self.news.selectionModel().currentChanged.connect(
            lambda current, previous: self.choose.setEnabled(current.isValid()))
        self.filter_items('')
        self.search.setFocus()

    @Slot(str)
    def filter_items(self, value):
        self.proxy.setFilterFixedString(value)
        count = self.proxy.rowCount()
        self.count.setText(f'{count}건 / 이 군집 {self.model.rowCount()}건')
        self.empty.setVisible(count == 0)
        self.choose.setEnabled(count > 0)
        if count:
            self.news.setCurrentIndex(self.proxy.index(0, 0))

    @Slot()
    def choose_current(self):
        item = self.news.currentIndex().data(ITEM_ROLE)
        if item is not None:
            self.selected.emit(item.id)
            self.close()
