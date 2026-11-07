"""Regression coverage for long sessions, dense clusters and damaged resources."""
import json
from dataclasses import replace
from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtWidgets import QMenu
import pytest
from frontend.main_window import MainWindow
from frontend.map_data import load_outlines
from frontend.models import NewsBatch
from frontend.offline_map import project


@pytest.mark.parametrize('payload', [[], {}, {'type': 'FeatureCollection', 'features': []},
    {'type': 'FeatureCollection', 'features': [{'geometry': {'type': 'Point', 'coordinates': [127, 36]}}]},
    {'type': 'FeatureCollection', 'features': [{'geometry': {'type': 'Polygon',
        'coordinates': [[[127, 36], [127, 37], [True, 37], [127, 36]]]}}]}])
def test_invalid_map_data_falls_back(tmp_path, payload):
    path = tmp_path / 'bad.geojson'
    path.write_text(json.dumps(payload), encoding='utf-8')
    outlines, warning = load_outlines(path)
    assert outlines == []
    assert '좌표 격자' in warning


def test_missing_map_data_keeps_main_window_working(qtbot, monkeypatch, tmp_path):
    import frontend.map_data as map_data
    monkeypatch.setattr(map_data, 'MAP_PATH', tmp_path / 'missing.geojson')
    window = MainWindow(settings=QSettings(str(tmp_path / 'test.ini'), QSettings.IniFormat))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.batch is not None)
    assert window.model.rowCount() == 20
    assert window.map.offline.resource_error
    assert '좌표 격자' in window.map.offline.resource_error
    window.select_news('1')
    assert window.detail.item.id == '1'
    assert window.map.offline.marker_by_id['1']
    qtbot.waitUntil(lambda: not window.worker.isRunning())
    window.close()


def test_bundled_outline_is_valid():
    outlines, warning = load_outlines()
    assert not warning
    assert {outline['code'] for outline in outlines} == {'KOR', 'PRK', 'JPN', 'CHN'}


def test_large_cluster_search_and_selection(window, qtbot):
    base = window.state.items[0]
    items = tuple(replace(base, id=f'row-{i}', title=f'군집 기사 unique-{i}') for i in range(1000))
    window._loaded(NewsBatch(items))
    view = window.map.offline
    view.home()
    qtbot.mouseClick(view.viewport(), Qt.LeftButton, pos=view.mapFromScene(view.markers[0].pos()))
    picker = view.cluster_picker
    assert picker is not None and picker.isVisible()
    assert picker.proxy.rowCount() == 1000
    assert not view.findChildren(QMenu)
    picker.search.setText('unique-877')
    assert picker.proxy.rowCount() == 1
    qtbot.mouseClick(picker.choose, Qt.LeftButton)
    assert window.state.selected_id == 'row-877'
    assert window.detail.item.title == '군집 기사 unique-877'
    qtbot.waitUntil(lambda: view.cluster_picker is None)


def test_large_cluster_empty_filter_and_stale_picker(window, qtbot):
    items = tuple(replace(window.state.items[0], id=str(i)) for i in range(30))
    window._loaded(NewsBatch(items))
    view = window.map.offline
    view.open_cluster(items, view.mapToGlobal(view.rect().center()))
    picker = view.cluster_picker
    picker.search.setText('없는기사')
    assert picker.proxy.rowCount() == 0
    assert not picker.choose.isEnabled()
    assert picker.empty.isVisible()
    window.search.setText('없는기사')
    window.apply_filters()
    assert view.cluster_picker is None
    from shiboken6 import isValid
    qtbot.waitUntil(lambda: not isValid(picker))


def test_selection_keeps_existing_marker_objects(window):
    view = window.map.offline
    before = list(view.markers)
    window.select_news('1')
    window.select_news('2')
    assert view.markers == before
    assert view.marker_by_id['2'].pen().width() == 4


def test_fit_results_with_foreign_and_missing_coordinates(window):
    item = replace(window.state.items[0], latitude=51.5, longitude=-0.12)
    unlocated = replace(item, id='missing', latitude=None, longitude=None)
    window._loaded(NewsBatch((item, unlocated)))
    view = window.map.offline
    view.fit_results()
    point = view.mapFromScene(project(item.latitude, item.longitude))
    assert view.viewport().rect().contains(point)
    assert len(view.markers) == 1
    window._loaded(NewsBatch(()))
    previous = view.transform()
    view.fit_results()
    assert view.transform() == previous


def test_user_cancellation_preserves_selection_and_ui_responsiveness(window, qtbot):
    window.select_news('1')
    old = window.batch
    class Slow:
        def load(self, cancel):
            cancel.wait(2)
            return NewsBatch(())
    window.provider = Slow()
    ticks = []
    timer = QTimer(window)
    timer.setInterval(15)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    window.reload()
    assert window.loading_progress.isVisible() and window.cancel_button.isVisible()
    qtbot.waitUntil(lambda: len(ticks) >= 3)
    qtbot.mouseClick(window.cancel_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: not window.worker.isRunning())
    qtbot.waitUntil(lambda: not window.loading_progress.isVisible())
    timer.stop()
    assert window.batch is old
    assert window.state.selected_id == '1'
    assert window.model.rowCount() == 20
    assert '취소' in window.banner.text()
    assert window.refresh_button.isEnabled()


def test_first_load_cancel_has_recovery_state(qtbot, tmp_path):
    class Slow:
        def load(self, cancel):
            cancel.wait(2)
            return NewsBatch(())
    window = MainWindow(Slow(), settings=QSettings(str(tmp_path / 'cancel.ini'), QSettings.IniFormat),
                        auto_load=False)
    qtbot.addWidget(window)
    window.show()
    window.reload()
    window.cancel_load()
    qtbot.waitUntil(lambda: not window.worker.isRunning())
    qtbot.waitUntil(lambda: window.refresh_button.isEnabled())
    assert window.batch is None and window.empty.isVisible()
    assert '취소' in window.empty.text()
    window.use_demo()
    qtbot.waitUntil(lambda: window.batch is not None)
    assert window.model.rowCount() == 20
    qtbot.waitUntil(lambda: not window.worker.isRunning())
    window.close()


@pytest.mark.webengine
def test_repeated_online_offline_disposes_pages_and_profiles(window, qtbot, monkeypatch):
    from shiboken6 import isValid
    import frontend.web_map as web_module
    real = web_module.WebMap
    monkeypatch.setattr(web_module, 'WebMap', lambda parent: real(parent, online_tiles=False))
    window.select_news('1')
    for _ in range(3):
        window.map.mode.setCurrentIndex(1)
        view = window.map.web
        qtbot.waitUntil(lambda: view.ready, timeout=15000)
        assert view.current_id == '1'
        profile = view.profile
        window.map.mode.setCurrentIndex(0)
        qtbot.waitUntil(lambda: not isValid(view))
        qtbot.waitUntil(lambda: not isValid(profile))
        assert window.state.selected_id == '1'


@pytest.mark.webengine
def test_close_while_map_builder_runs(window, qtbot, monkeypatch):
    import frontend.web_map as web_module
    real = web_module.WebMap
    monkeypatch.setattr(web_module, 'WebMap', lambda parent: real(parent, online_tiles=False))
    window.map.mode.setCurrentIndex(1)
    window.close()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=15000)
