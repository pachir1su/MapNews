"""Verify the merged 341-story team map data in actual PySide6 widgets."""
from pathlib import Path
from threading import Event

from PySide6.QtCore import QSettings

from frontend.main_window import MainWindow
from frontend.providers import JsonNewsProvider


def test_merged_map_data_opens_in_native_qt_and_matches_pins(tmp_path, qtbot):
    path = Path("map_visualization/map_results.json")
    assert path.is_file(), "Team map sample JSON must exist"
    provider = JsonNewsProvider(path)
    batch = provider.load(Event())
    assert len(batch.items) == 341
    assert sum(item.has_coordinates for item in batch.items) == 209
    assert sum(item.is_mock for item in batch.items) >= 3

    window = MainWindow(
        provider=provider,
        settings=QSettings(str(tmp_path / "ui.ini"), QSettings.IniFormat),
        auto_load=False,
        online=False,
    )
    qtbot.addWidget(window)
    window._loaded(batch)

    assert window.news_count.text() == "341건"
    assert window.model.rowCount() == 341
    assert len(window.map.offline.marker_by_id) == 209
    assert len(window.map.offline.items) == 341

    first_real_with_pin = next(item for item in batch.items
                               if item.has_coordinates and not item.is_mock)
    window.select_news(first_real_with_pin.id)
    assert window.detail.item.id == first_real_with_pin.id
    assert window.detail.open_button.isHidden() is False
    example = next(item for item in batch.items if item.is_mock)
    window.select_news(example.id)
    assert window.detail.open_button.isHidden()
