from pathlib import Path
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QStatusBar
from frontend.main_window import MainWindow
from frontend.map_data import load_boundaries, BOUNDARY_PATHS
from frontend.themes import system_is_dark


def test_only_system_controls_appearance(window, qtbot):
    hints = QApplication.styleHints()
    selected = window.state.selected_id
    for scheme, dark in ((Qt.ColorScheme.Dark, True), (Qt.ColorScheme.Light, False)):
        hints.colorSchemeChanged.emit(scheme)
        assert window.dark is dark
        assert window.map.offline.dark is dark
        assert window.delegate.dark is dark
        assert window.state.selected_id == selected
    assert not window.settings.contains('dark')
    assert not hasattr(window, 'theme_button')
    assert not any('테마' in button.text() or button.text() in ('다크', '라이트')
                   for button in window.findChildren(QPushButton))
    assert not window.findChildren(QStatusBar)
    assert not hasattr(window.map, 'caption')
    assert not window.banner.isVisible()
    assert not system_is_dark(Qt.ColorScheme.Unknown)


def test_legacy_preference_is_discarded(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / 'legacy.ini'), QSettings.IniFormat)
    settings.setValue('dark', not system_is_dark(QApplication.styleHints().colorScheme()))
    window = MainWindow(settings=settings, auto_load=False)
    qtbot.addWidget(window)
    assert window.dark == system_is_dark(QApplication.styleHints().colorScheme())
    assert not settings.contains('dark')
    window.close()


def test_province_and_district_zoom(window):
    levels, error = load_boundaries()
    assert not error
    assert len(levels['adm1']) == 16
    assert len(levels['adm2']) == 256
    view = window.map.offline
    view.home()
    assert not view.district_layer.isVisible()
    for _ in range(6):
        view.zoom(1.25)
    assert view.district_layer.isVisible()
    before = view.transform().m11()
    QApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert view.district_layer.isVisible()
    assert view.transform().m11() == before
    view.home()
    assert not view.district_layer.isVisible()


def test_missing_boundary_keeps_other_level(monkeypatch, tmp_path):
    monkeypatch.setitem(BOUNDARY_PATHS, 'adm2', Path(tmp_path / 'missing.json'))
    levels, error = load_boundaries()
    assert len(levels['adm1']) == 16
    assert not levels['adm2']
    assert '시·군·구' in error


def test_province_edges_match_district_geometry():
    levels, error = load_boundaries()
    assert not error

    def edges(rows):
        return {tuple(sorted((tuple(a), tuple(b))))
                for row in rows for polygon in row['polygons'] for ring in polygon
                for a, b in zip(ring, ring[1:])}

    # Prevent the visibly doubled borders caused by combining unrelated datasets.
    assert edges(levels['adm1']) <= edges(levels['adm2'])


def test_secondary_actions_and_information(window, qtbot):
    assert window.import_button in window.more_menu.actions()
    assert window.demo_button in window.more_menu.actions()
    window.more_menu.actions()[-1].trigger()
    from frontend.information import InformationDialog
    dialog = window.findChild(InformationDialog)
    assert dialog.isVisible()
    dialog.close()
    window.show_notice('일시적 알림')
    assert window.banner.isVisible()
    window.notice_timer.timeout.emit()
    assert not window.banner.isVisible()
