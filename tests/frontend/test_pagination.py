"""Incremental loading: 10k saved rows need not create 10k Qt model rows."""
from PySide6.QtCore import QModelIndex
from frontend.news_list import NewsListModel, PAGE_SIZE, ITEM_ROLE
from frontend.models import parse_news
from frontend.main_window import MainWindow


def _items(count=10000):
    rows = [
        {"id": str(n), "title": f"뉴스 {n}", "datetime": "2026-11-18T10:00:00",
         "url": f"https://news.example.net/{n}", "location": "서울특별시"}
        for n in range(count)
    ]
    return parse_news(rows).items


def test_list_lazy_fetches_without_building_all_qt_rows(qtbot):
    model = NewsListModel()
    items = _items()
    model.replace(items)
    assert len(model.items) == 10000
    assert model.rowCount() == PAGE_SIZE
    assert model.canFetchMore()
    model.fetchMore()
    assert model.rowCount() == PAGE_SIZE * 2
    assert model.data(model.index(PAGE_SIZE), ITEM_ROLE) == items[PAGE_SIZE]
    assert not model.canFetchMore(model.index(0))


def test_map_selection_can_reveal_an_unfetched_article(qtbot, tmp_path):
    from PySide6.QtCore import QSettings
    window = MainWindow(
        settings=QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat),
        auto_load=False, online=False,
    )
    qtbot.addWidget(window)
    from frontend.models import NewsBatch
    batch = NewsBatch(_items(300))
    window._loaded(batch)
    assert len(window.model.items) == 300
    later_id = window.model.items[249].id
    window.select_news(later_id)
    assert window.state.selected_id == later_id
    assert window.news.currentIndex().isValid()
    assert window.news.currentIndex().row() == 249
    assert window.model.rowCount() >= 250


def test_invalid_map_selection_never_expands_or_changes_selected(qtbot):
    model = NewsListModel()
    model.replace(_items(100))
    previous = model.rowCount()
    assert not model.ensure_row(-1)
    assert not model.ensure_row(100)
    assert model.rowCount() == previous


def test_reload_resets_incremental_cursor(qtbot):
    model = NewsListModel()
    model.replace(_items(500))
    assert model.ensure_row(390)
    assert model.rowCount() >= 391
    model.replace(_items(10))
    assert model.rowCount() == 10
    assert not model.canFetchMore()
