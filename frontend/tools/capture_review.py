"""Capture real Qt widgets and the offline map without creating mockup images.

Usage: python -m frontend.tools.capture_review --output test-artifacts/screenshots
"""
import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from frontend.main_window import MainWindow
from frontend.providers import MockNewsProvider


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("test-artifacts/screenshots"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication(["MapNews screenshot capture"])
    app.setStyle("Fusion")

    with TemporaryDirectory(prefix="mapnews-capture-") as directory:
        settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.IniFormat)
        window = MainWindow(settings=settings, auto_load=False, online=False)
        window.resize(1366, 768)
        window.show()
        window._loaded(MockNewsProvider().load(Event()))
        window.map.offline.home()

        def capture(name: str) -> None:
            QTest.qWait(180)
            app.processEvents()
            path = output / f"{name}.png"
            if not window.grab().save(str(path)):
                raise RuntimeError(f"Unable to save screenshot: {path}")
            print(f"Captured {path}")

        capture("01-map-overview")

        region = window.state.items[0].location.split()[0]
        window.region.setCurrentIndex(window.region.findData(region))
        window.filter_button.setChecked(True)
        window.apply_filters()
        capture("02-region-filter")

        window.reset_filters()
        window.filter_button.setChecked(False)
        window.select_news(window.model.items[0].id)
        window.show_detail()
        capture("03-news-detail")

        window.dismiss_detail()
        window.resize(1000, 700)
        capture("04-compact-window")

        window.resize(1366, 768)
        window.search.setText("천안")
        window.apply_filters()
        capture("05-keyword-search")

        window.reset_filters()
        window.filter_button.setChecked(True)
        for name, button in window.category_buttons.items():
            button.setChecked(name == "행사")
        window.apply_filters()
        capture("06-category-filter")

        window.reset_filters()
        window.filter_button.setChecked(False)
        window.search.setText("검색결과없음")
        window.apply_filters()
        capture("07-empty-search")

        window.reset_filters()
        window.select_news(window.model.items[0].id)
        window.toggle_bookmark()
        window.show_detail()
        capture("08-saved-news-detail")

        window.dismiss_detail()
        window.saved_button.setChecked(True)
        window.apply_filters()
        capture("09-saved-news-list")

        window.saved_button.setChecked(False)
        window.reset_filters()
        window.map.offline.home()
        for _ in range(6):
            window.map.offline.zoom(1.25)
        capture("10-district-map")

        QApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        window.map.offline.home()
        capture("11-dark-theme")

        QApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
        window.resize(1920, 1080)
        window.map.offline.home()
        capture("12-wide-desktop")

        window.show_load_details()
        app.processEvents()
        from PySide6.QtWidgets import QDialog
        dialogs = window.findChildren(QDialog)
        if not dialogs:
            raise RuntimeError("Load details dialog did not open")
        dialog = dialogs[-1]
        QTest.qWait(160)
        detail_path = output / "13-load-details.png"
        if not dialog.grab().save(str(detail_path)):
            raise RuntimeError(f"Unable to save screenshot: {detail_path}")
        dialog.close()
        print(f"Captured {detail_path}")

        window.close()
        app.processEvents()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
