"""Focused interaction checks for the map-first desktop explorer."""

from PySide6.QtWidgets import QApplication


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


def test_news_context_menu_copies_the_actual_title(window):
    item = window.model.items[0]
    window._run_news_context_action(item.id, "copy")
    assert QApplication.clipboard().text() == item.title
    assert window.state.selected_id == item.id


def test_news_context_menu_ignores_missing_article(window):
    previous = window.state.selected_id
    window._run_news_context_action("not-an-article", "detail")
    assert window.state.selected_id == previous


def test_single_location_does_not_overzoom(window):
    from frontend.models import NewsBatch

    item = next(item for item in window.state.items if item.has_coordinates)
    window._loaded(NewsBatch((item,)))
    assert window.map.offline.markers
    assert window.map.offline.transform().m11() <= 2.8 + 1e-6


def test_article_row_uses_compact_readable_height(window):
    index = window.model.index(0)
    assert index.isValid()
    assert window.delegate.sizeHint(None, index).height() == 100


def test_escape_clears_search_when_search_is_focused(window):
    window.search.setText("천안")
    window.search.setFocus()
    assert window.search.hasFocus()
    window.dismiss_detail()
    assert window.search.text() == ""
    assert window.search.hasFocus()


def test_category_filter_buttons_wrap_into_two_rows(window):
    # Keep all five categories reachable at the minimum sidebar width.
    from frontend.models import CATEGORIES

    assert len(window.category_buttons) == len(CATEGORIES)
    assert window.category_layout.rowCount() == 2
    assert window.category_layout.columnCount() == 3
    for index, name in enumerate(CATEGORIES):
        assert window.category_layout.itemAtPosition(index // 3, index % 3).widget() is window.category_buttons[name]


def test_filter_button_summarizes_selected_conditions(window):
    assert window.filter_button.text() == "필터"
    first_category = next(iter(window.category_buttons.values()))
    first_category.setChecked(False)
    window.apply_filters()
    assert window.filter_button.text() == "필터 1"
    assert window.filter_button.property("filterActive") is True

    assert window.region.count() > 1
    window.region.setCurrentIndex(1)
    window.apply_filters()
    assert window.filter_button.text() == "필터 2"
    assert "2개 적용" in window.filter_button.accessibleName()

    window.reset_filters()
    assert window.filter_button.text() == "필터"
    assert window.filter_button.property("filterActive") is False


def test_filter_panel_keeps_visibility_separate_from_active_filters(window):
    window.filter_button.setChecked(True)
    assert window.filters_panel.isVisible()
    first_category = next(iter(window.category_buttons.values()))
    first_category.setChecked(False)
    window.apply_filters()
    window.filter_button.setChecked(False)
    assert window.filter_button.text() == "필터 1"
    assert window.filters_panel.isHidden()
    window.filter_button.setChecked(True)
    assert window.filters_panel.isVisible()
