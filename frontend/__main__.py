"""Run: python -m frontend [--json FILE] [--mock-json] [--online] [--dark]."""
import argparse
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
from .main_window import MainWindow
from .providers import JsonNewsProvider, MockNewsProvider


def main():
    parser = argparse.ArgumentParser(description="MapNews 프론트엔드 · 기본값은 오프라인 MOCK")
    parser.add_argument("--json", metavar="FILE", help="PR #2 형식 JSON을 읽기 전용으로 불러오기")
    parser.add_argument("--mock-json", action="store_true", help="외부 JSON도 시연 데이터로 명시")
    parser.add_argument("--online", action="store_true", help="인터넷이 필요한 Folium 지도로 시작")
    parser.add_argument("--dark", action="store_true", help="다크 테마로 시작")
    args = parser.parse_args()
    if args.mock_json and not args.json:
        parser.error("--mock-json은 --json과 함께 사용하세요.")
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("MapNews")
    app.setStyle("Fusion")
    provider = JsonNewsProvider(args.json, is_mock=args.mock_json) if args.json else MockNewsProvider()
    window = MainWindow(provider)
    available = app.primaryScreen().availableGeometry()
    window.resize(min(1500, available.width()), min(900, available.height()))
    if args.dark and not window.dark:
        window.toggle_theme()
    window.show()
    if args.online:
        window.map.mode.setCurrentIndex(1)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
