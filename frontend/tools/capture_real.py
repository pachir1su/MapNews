"""Capture the actual team's merged map JSON in real Qt widgets (not mockups)."""
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
from frontend.providers import JsonNewsProvider


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("map_visualization/map_results.json"))
    parser.add_argument("--output", type=Path, default=Path("test-artifacts/real-screenshots"))
    args = parser.parse_args(argv)
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=True)
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication.instance() or QApplication(["MapNews real-news capture"])
    app.setStyle("Fusion")
    provider = JsonNewsProvider(args.input)
    batch = provider.load(Event())
    if not batch.items:
        raise ValueError("실제 데이터가 없어 화면 캡처를 생성하지 않습니다.")

    with TemporaryDirectory(prefix="mapnews-real-capture-") as directory:
        settings = QSettings(str(Path(directory) / "ui.ini"), QSettings.IniFormat)
        window = MainWindow(provider=provider, settings=settings, auto_load=False, online=False)
        window.resize(1366, 768)
        window.show()
        window._loaded(batch)
        window.map.offline.home()

        def save(filename):
            QTest.qWait(200)
            app.processEvents()
            if not window.grab().save(str(target / filename)):
                raise RuntimeError(f"Qt capture failed: {filename}")

        save("01-real-team-map.png")
        located = next((item for item in batch.items if item.has_coordinates and not item.is_mock), None)
        if located:
            window.select_news(located.id)
            window.show_detail()
            save("02-real-news-detail.png")
            window.dismiss_detail()

        first_region = next((item.location.split()[0] for item in batch.items
                             if item.has_coordinates and item.location.strip()), "")
        if first_region:
            index = window.region.findData(first_region)
            if index >= 0:
                window.region.setCurrentIndex(index)
                window.apply_filters()
                save("03-real-region-filter.png")

        window.close()
        app.processEvents()
    print(f"Qt screenshots created: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
