"""Folium page with pinned local Leaflet assets. Only online map tiles use network."""
import base64
import gzip
import json
from pathlib import Path
import folium
from folium.plugins import MarkerCluster
from branca.element import Element, MacroElement, Template
from .map_data import load_boundaries, boundary_geojson

RESOURCES = Path(__file__).parent / "resources"


def marker_payload(items):
    return [dict(id=n.id, title=n.title, category=n.category, location=n.location,
                 latitude=n.latitude, longitude=n.longitude, color=n.color)
            for n in items if n.has_coordinates]


def js_call(function: str, value) -> str:
    if function not in {"setNews", "selectNews", "setTheme"}:
        raise ValueError("Unknown map command")
    return f"window.{function}({json.dumps(value, ensure_ascii=True, allow_nan=False)});"


def build_map_html(*, online_tiles: bool = True) -> str:
    map_view = folium.Map(location=[36.0, 127.6], zoom_start=7, max_zoom=19,
                          tiles="OpenStreetMap" if online_tiles else None,
                          control_scale=True, prefer_canvas=True)
    # Folium's max_zoom argument configures tiles, not the tile-free map itself.
    map_view.options['maxZoom'] = 19
    map_view.default_js = []
    map_view.default_css = []
    cluster = MarkerCluster(options={"maxClusterRadius": 48,
                                      "spiderfyOnMaxZoom": True,
                                      "showCoverageOnHover": False}).add_to(map_view)
    cluster.default_js = []
    cluster.default_css = []
    root = map_view.get_root()
    root.header.add_child(Element("""
    <meta http-equiv="Content-Security-Policy" content="default-src 'none';
      script-src 'unsafe-inline' qrc:; style-src 'unsafe-inline';
      img-src data: https://tile.openstreetmap.org https://*.tile.openstreetmap.org;
      connect-src 'none';">
    """), name="policy")
    for name in ("leaflet.css", "MarkerCluster.css", "MarkerCluster.Default.css"):
        root.header.add_child(Element("<style>" + (RESOURCES / "vendor" / name).read_text(
            encoding="utf-8") + "</style>"))
    for name in ("leaflet.js", "leaflet.markercluster.js"):
        root.header.add_child(Element("<script>" + (RESOURCES / "vendor" / name).read_text(
            encoding="utf-8") + "\n</script>"))
    root.header.add_child(Element('<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'))
    root.header.add_child(Element("""
    <style>
    .news-pin { border:2px solid white; border-radius:50%; width:26px!important;
      height:26px!important; color:white; font:bold 12px sans-serif;
      display:flex; align-items:center; justify-content:center;
      box-shadow:0 2px 9px #17253d55; }
    .news-selected { outline:4px solid #3182f6; outline-offset:3px; }
    .map-dark .leaflet-tile-pane { filter:brightness(.65) saturate(.65); }
    .leaflet-popup-content { font:14px sans-serif; max-width:280px; }
    </style>
    """))
    script = (RESOURCES / "map.js").read_text(encoding="utf-8")
    script = script.replace("__MAP__", map_view.get_name()).replace("__CLUSTER__", cluster.get_name())
    levels, _ = load_boundaries()
    for level in ('adm1', 'adm2'):
        payload = json.dumps(boundary_geojson(levels[level]), ensure_ascii=True, separators=(',', ':'))
        encoded = base64.b64encode(gzip.compress(payload.encode(), mtime=0)).decode('ascii')
        script = script.replace('__' + level.upper() + '__', encoded)
    # MacroElement renders after the map and cluster. Root.script would run too early.
    bridge = MacroElement()
    bridge._template = Template("{% macro script(this, kwargs) %}" + script + "{% endmacro %}")
    bridge.add_to(map_view)
    return root.render()
