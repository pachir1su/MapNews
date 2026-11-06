from dataclasses import replace
from pathlib import Path
import os
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from frontend.models import NewsBatch
from frontend.workers import LoadWorker
from frontend.offline_map import cluster_points, project


def test_main_widgets_and_demo(window):
    assert window.model.rowCount() == 20
    assert window.map.offline.items == window.model.items
    assert 'MOCK' in window.source_label.text()
    assert window.map.web is None


def test_list_selection_details_and_map(window):
    window.news.setCurrentIndex(window.model.index(3))
    assert window.state.selected_id == '4'
    assert window.detail.item.id == window.dialog_detail.item.id == '4'
    assert window.map.offline.selected_id == '4'
    assert not window.detail.open_button.isEnabled()


def test_map_selection_updates_list(window):
    window.map.offline.selected.emit('14')
    assert window.news.currentIndex().row() == 13
    assert window.detail.title.text() == window.state.items[13].title
    window.select_news('forged')
    assert window.state.selected_id == '14'


def test_keyboard_navigation(window, qtbot):
    window.news.setFocus()
    window.news.setCurrentIndex(window.model.index(0))
    qtbot.keyClick(window.news, Qt.Key_Down)
    assert window.state.selected_id == '2'


def test_search_debounce_and_reset(window, qtbot):
    window.search.setText('천안')
    qtbot.waitUntil(lambda: window.model.rowCount() == 1)
    assert len(window.map.offline.items) == 1
    window.select_news('1')
    window.search.setText('아무결과없음')
    qtbot.waitUntil(lambda: window.model.rowCount() == 0)
    assert window.state.selected_id is None
    assert window.detail.item is None
    assert window.empty.isVisible()
    window.reset_filters()
    assert window.model.rowCount() == 20


def test_category_and_region_controls(window):
    for name, button in window.category_buttons.items():
        button.setChecked(name == '행사')
    window.apply_filters()
    assert window.model.rowCount() == 4
    assert all(item.category == '행사' for item in window.map.offline.items)
    window.region.setCurrentIndex(window.region.findData('경기'))
    assert [item.id for item in window.model.items] == ['19']
    window.sort.setCurrentIndex(1)
    assert window.model.rowCount() == 1


def test_dark_light_and_responsive_detail(window, qtbot):
    previous = window.dark
    window.toggle_theme()
    assert window.dark != previous
    assert window.map.offline.dark == window.dark
    window.resize(1100, 700)
    qtbot.waitUntil(lambda: not window.detail.isVisible())
    window.select_news('1')
    window.show_detail()
    assert window.detail_dialog.isVisible()
    window.dismiss_detail()
    window.resize(1366, 768)
    qtbot.waitUntil(window.detail.isVisible)
    assert window.map.width() >= 410


def test_failure_retains_existing_data(window, qtbot):
    class Broken:
        label = '실패 테스트'
        def load(self, cancel):
            raise ConnectionError('do-not-display-secret')
    window.provider = Broken()
    window.reload()
    qtbot.waitUntil(lambda: not window.worker.isRunning())
    qtbot.waitUntil(lambda: '불러오지 못했습니다' in window.banner.text())
    assert window.model.rowCount() == 20
    assert 'do-not-display-secret' not in window.banner.text()
    assert window.refresh_button.isEnabled()


def test_empty_and_partial_batch(window):
    window._loaded(NewsBatch(()))
    assert window.model.rowCount() == 0
    assert window.empty.isVisible()
    from frontend.models import parse_news
    window._loaded(parse_news([{'id': 'a', 'title': '<img src=x onerror=alert(1)>'}]))
    window.select_news('a')
    assert window.detail.title.textFormat() == Qt.PlainText
    assert not window.detail.locate_button.isEnabled()
    assert not window.detail.open_button.isEnabled()
    assert len(window.map.offline.markers) == 0
    assert window.other_button.isVisible()


def test_same_coordinate_cluster_is_selectable(window):
    item = window.state.items[0]
    duplicate = replace(item, id='duplicate')
    groups = cluster_points([item, duplicate], 2)
    assert len(groups) == 1 and len(groups[0]) == 2
    window.map.offline.set_items([item, duplicate])
    assert len(window.map.offline.markers) == 1
    assert len(window.map.offline.markers[0].items) == 2
    point = project(36, 127)
    assert point.x() > 0 and point.y() < 0


def test_original_link_validation(window, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    calls = []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: calls.append(url.toString()) or True)
    item = replace(window.state.items[0], is_mock=False, url='https://news.example.org/story')
    window.detail.set_item(item)
    window.detail.open_button.click()
    assert calls == ['https://news.example.org/story']
    window.detail.set_item(replace(item, url='javascript:alert(1)'))
    window.detail._open()
    assert len(calls) == 1


def test_close_during_cooperative_load(window, qtbot):
    class Slow:
        label = 'slow'
        def load(self, cancel):
            cancel.wait(2)
            return NewsBatch(())
    window.provider = Slow()
    window.reload()
    assert window.worker.isRunning()
    window.close()
    qtbot.waitUntil(lambda: not window.worker.isRunning(), timeout=4000)
    qtbot.waitUntil(lambda: not window.isVisible())


def test_worker_runs_off_ui_thread(qtbot):
    import threading
    threads = []
    class Provider:
        def load(self, cancel):
            threads.append(threading.get_ident())
            return NewsBatch(())
    worker = LoadWorker(Provider())
    with qtbot.waitSignal(worker.loaded, timeout=3000):
        worker.start()
    worker.wait(3000)
    assert threads and threads[0] != threading.get_ident()


def test_map_failure_fallback(window):
    window.map._fallback('test map failure')
    assert window.map.mode.currentIndex() == 0
    assert window.map.active is window.map.offline
    assert 'test map failure' in window.statusBar().currentMessage()


def test_capture_review_screenshots(window):
    output = Path(os.environ.get('MAPNEWS_ARTIFACT_DIR', 'test-artifacts'))
    output.mkdir(exist_ok=True)
    window.select_news('1')
    for dark in (False, True):
        if window.dark != dark:
            window.toggle_theme()
        for width, height in ((1366, 768), (1920, 1080), (1100, 700)):
            window.resize(width, height)
            QTest.qWait(120)
            window.map.offline.home()
            assert window.grab().save(str(output / f"mapnews-{'dark' if dark else 'light'}-{width}.png"))


def test_native_marker_mouse_click(window, qtbot):
    item = window.state.items[13]
    window.map.offline.set_items([item])
    window.map.offline.home()
    marker = window.map.offline.markers[0]
    point = window.map.offline.mapFromScene(marker.pos())
    qtbot.mouseClick(window.map.offline.viewport(), Qt.LeftButton, pos=point)
    assert window.state.selected_id == item.id
    assert window.detail.item == item


def test_native_cluster_menu(window, qtbot):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMenu
    item = window.state.items[0]
    duplicate = replace(item, id='duplicate', title='동일 위치 두 번째 기사')
    window._loaded(NewsBatch((item, duplicate)))
    window.map.offline.home()
    marker = window.map.offline.markers[0]
    observed = []
    def choose_second():
        menu = QApplication.activePopupWidget()
        if isinstance(menu, QMenu):
            observed.extend(action.text() for action in menu.actions())
            next(action for action in menu.actions() if duplicate.title in action.text()).trigger()
            menu.close()
    QTimer.singleShot(100, choose_second)
    qtbot.mouseClick(window.map.offline.viewport(), Qt.LeftButton,
                     pos=window.map.offline.mapFromScene(marker.pos()))
    assert len(observed) == 2
    assert window.state.selected_id == 'duplicate'
    assert window.detail.item.title == duplicate.title


def test_refresh_reconciles_selection_and_updated_details(window):
    window.select_news('1')
    changed = replace(window.state.items[0], title='수정된 제목')
    window._loaded(NewsBatch((changed,)))
    assert window.state.selected_id == '1'
    assert window.detail.title.text() == '수정된 제목'
    window._loaded(NewsBatch(()))
    assert window.state.selected_id is None
    assert window.detail.item is None


def test_no_categories_means_empty(window):
    for button in window.category_buttons.values():
        button.setChecked(False)
    window.apply_filters()
    assert window.model.rowCount() == 0
    assert not window.map.offline.markers


def test_malformed_provider_returns_failure(qtbot):
    class InvalidProvider:
        def load(self, cancel):
            return {'news': []}
    worker = LoadWorker(InvalidProvider())
    with qtbot.waitSignal(worker.failed, timeout=3000) as signal:
        worker.start()
    worker.wait(3000)
    assert 'TypeError' in signal.args[0]
