"""Run: python -m frontend [--json FILE] [--mock-json] [--offline]."""
import argparse
import sys
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
from .main_window import MainWindow
from .providers import JsonNewsProvider, MockNewsProvider


def main():
    parser = argparse.ArgumentParser(description="MapNews · 지도에서 뉴스 탐색")
    parser.add_argument("--json", metavar="FILE", help="PR #2 형식 JSON을 읽기 전용으로 불러오기")
    parser.add_argument("--mock-json", action="store_true", help="외부 JSON도 시연 데이터로 명시")
    maps = parser.add_mutually_exclusive_group()
    maps.add_argument("--offline", action="store_true", help="네트워크 없이 로컬 지도로 시작")
    maps.add_argument("--online", action="store_true", help=argparse.SUPPRESS)  # Existing launchers remain valid.
    args = parser.parse_args()
    if args.mock_json and not args.json:
        parser.error("--mock-json은 --json과 함께 사용하세요.")
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("MapNews")
    app.setStyle("Fusion")
    provider = JsonNewsProvider(args.json, is_mock=args.mock_json) if args.json else MockNewsProvider()
    window = MainWindow(provider, online=not args.offline)
    available = app.primaryScreen().availableGeometry()
    window.resize(min(1500, available.width()), min(900, available.height()))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
