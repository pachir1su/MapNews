"""Focused interaction checks for the map-first desktop explorer."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMenu


def test_search_shortcut_replaces_existing_keyword(window):
    window.search.setText("천안")
    window.focus_search()
    assert window.search.hasFocus()
    assert window.search.selectedText() == "천안"


def test_result_count_stays_in_sync_with_filters(window):
    assert window.news_count.text() == "20건"
    window.search.setText("no-news-matches-this-query")
    window.apply_filters()
    assert window.news_count.text() == "0건"
    assert window.model.rowCount() == 0

    window.reset_filters()
    assert window.news_count.text() == "20건"
    assert window.model.rowCount() == 20


def test_news_context_menu_copies_the_actual_title(window, monkeypatch):
    item = window.model.items[0]
    index = window.model.index(0)

    def choose_copy(menu, position):
        return next(action for action in menu.actions() if action.text() == "제목 복사")

    monkeypatch.setattr(QMenu, "exec", choose_copy)
    window._show_news_context_menu(window.news.visualRect(index).center())
    assert QApplication.clipboard().text() == item.title
    assert window.state.selected_id == item.id
