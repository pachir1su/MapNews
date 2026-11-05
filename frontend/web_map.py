"""QtWebEngine isolation and a small, validated QtWebChannel bridge."""
from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile,
                                    QWebEngineSettings, QWebEngineUrlRequestInterceptor)
from PySide6.QtWebEngineWidgets import QWebEngineView
from .map_html import build_map_html, js_call, marker_payload

ALLOWED_HOSTS = {"tile.openstreetmap.org", "a.tile.openstreetmap.org",
                 "b.tile.openstreetmap.org", "c.tile.openstreetmap.org"}


class RequestPolicy(QWebEngineUrlRequestInterceptor):
    """Online mode may fetch only map dependencies. No news URL is loaded in WebEngine."""
    def interceptRequest(self, info):
        url = info.requestUrl()
        permitted = url.scheme() in {"qrc", "data", "about"}
        if url.scheme() == "https" and url.host() in ALLOWED_HOSTS:
            permitted = True
        info.block(not permitted)


class MapPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, kind, is_main_frame):
        return url.scheme() in {"about", "data", "qrc"}


class NewsBridge(QObject):
    selected = Signal(str)
    initialized = Signal()
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.valid_ids = set()

    @Slot(str)
    def selectNews(self, identifier):
        if identifier in self.valid_ids:
            self.selected.emit(identifier)

    @Slot()
    def ready(self):
        self.initialized.emit()

    @Slot(str)
    def mapFailed(self, reason):
        # JS may report failures but cannot inject arbitrary UI strings.
        self.failed.emit("온라인 지도 연결 실패 · 오프라인 좌표 화면으로 전환합니다.")


class MapBuilder(QThread):
    built = Signal(str)
    failed = Signal(str)

    def __init__(self, parent=None, *, online_tiles=True):
        super().__init__(parent)
        self.online_tiles = online_tiles

    def run(self):
        try:
            self.built.emit(build_map_html(online_tiles=self.online_tiles))
        except Exception:
            self.failed.emit("지도 화면을 생성하지 못했습니다.")


class WebMap(QWebEngineView):
    selected = Signal(str)
    failed = Signal(str)

    def __init__(self, parent=None, *, online_tiles=True):
        super().__init__(parent)
        self.ready = False
        self.rows = []
        self.current_id = None
        self.dark = False
        self.pending_focus = False
        self.profile = QWebEngineProfile(self)
        self.policy = RequestPolicy(self.profile)
        self.profile.setUrlRequestInterceptor(self.policy)
        self.map_page = MapPage(self.profile, self)
        self.setPage(self.map_page)
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, False)
        self.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, False)
        self.channel = QWebChannel(self.map_page)
        self.bridge = NewsBridge(self.channel)
        self.channel.registerObject("newsBridge", self.bridge)
        self.map_page.setWebChannel(self.channel)
        self.bridge.selected.connect(self.selected)
        self.bridge.initialized.connect(self._ready)
        self.bridge.failed.connect(self.failed)
        self.map_page.renderProcessTerminated.connect(
            lambda *args: self.failed.emit("지도 렌더러가 종료되었습니다."))
        self.loadFinished.connect(self._loaded)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.failed.emit("온라인 지도 응답 시간 초과"))
        self.builder = MapBuilder(self, online_tiles=online_tiles)
        self.builder.built.connect(self._html)
        self.builder.failed.connect(self.failed)
        self.builder.start()
        self.timer.start(15000)

    @Slot(str)
    def _html(self, html):
        self.setHtml(html, QUrl("about:blank"))

    def _loaded(self, success):
        if not success:
            self.failed.emit("지도 페이지 로딩 실패")

    @Slot()
    def _ready(self):
        self.ready = True
        self.timer.stop()
        self.set_items(self.rows)
        self.set_theme(self.dark)
        self.set_selected(self.current_id, self.pending_focus)

    def set_items(self, items):
        self.rows = list(items)
        self.bridge.valid_ids = {item.id for item in self.rows if item.has_coordinates}
        if self.ready:
            self.page().runJavaScript(js_call("setNews", marker_payload(self.rows)))

    def set_selected(self, identifier, focus=False):
        self.current_id, self.pending_focus = identifier, focus
        if self.ready:
            self.page().runJavaScript(js_call("selectNews", {"id": identifier, "focus": focus}))

    def set_theme(self, dark):
        self.dark = dark
        if self.ready:
            self.page().runJavaScript(js_call("setTheme", dark))

    def home(self):
        if self.ready:
            self.page().runJavaScript("window.mapHome();")

    def zoom(self, factor):
        if self.ready:
            self.page().runJavaScript("window.mapZoom(1);" if factor > 1 else "window.mapZoom(-1);")

    def shutdown(self):
        self.timer.stop()
        self.stop()
        self.page().setWebChannel(None)
        # Builder only renders a fixed small local template; parent stays alive until finished.
