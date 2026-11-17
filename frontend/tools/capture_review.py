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

        window.close()
        app.processEvents()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
