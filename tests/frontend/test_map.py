from threading import Event
import json
import re
import pytest
from frontend.map_html import build_map_html, js_call, marker_payload
from frontend.providers import MockNewsProvider


def test_payload_and_serialization():
    items = MockNewsProvider().load(Event()).items
    payload = marker_payload(items)
    assert len(payload) == 20
    assert payload[0]['latitude'] == 36.815
    bad = '\"; window.hacked=true; // </script>'
    script = js_call('selectNews', {'id': bad})
    encoded = script[len('window.selectNews('):-2]
    assert json.loads(encoded)['id'] == bad
    with pytest.raises(ValueError):
        js_call('eval', bad)


def test_folium_assets_are_local_and_bridge_order():
    html = build_map_html(online_tiles=False)
    assert 'L.markerClusterGroup' in html
    assert html.index('var map_') < html.index('const map = map_')
    assert 'qtwebchannel/qwebchannel.js' in html
    assert not re.search(r'<script[^>]+src=[\"\x27]https?://', html)
    assert not re.search(r'<link[^>]+href=[\"\x27]https?://', html)
    assert 'L.tileLayer(' not in html
    assert 'Content-Security-Policy' in html


def test_online_map_has_osm_attribution():
    html = build_map_html()
    assert 'tile.openstreetmap.org' in html
    assert 'OpenStreetMap' in html


@pytest.fixture
def web(qtbot):
    from frontend.web_map import WebMap
    view = WebMap(online_tiles=False)
    qtbot.addWidget(view)
    view.resize(900, 650)
    view.show()
    qtbot.waitUntil(lambda: view.ready, timeout=20000)
    yield view
    view.shutdown()
    qtbot.waitUntil(lambda: not view.builder.isRunning())
    from shiboken6 import isValid
    qtbot.waitUntil(lambda: not isValid(view.map_page))


def evaluate(qtbot, view, script):
    result = []
    view.page().runJavaScript(script, lambda value: result.append(value))
    qtbot.waitUntil(lambda: bool(result), timeout=5000)
    return result[0]


@pytest.mark.webengine
def test_real_webchannel_leaflet_and_marker_click(web, qtbot):
    items = MockNewsProvider().load(Event()).items
    web.set_items(items)
    def ev(script):
        return evaluate(qtbot, web, script)
    qtbot.waitUntil(lambda: ev("document.querySelectorAll('.leaflet-marker-icon').length") > 0)
    assert ev('window.mapReady') is True
    web.set_selected('1', focus=True)
    qtbot.waitUntil(lambda: ev("document.querySelectorAll('.news-selected').length") == 1, timeout=10000)
    assert ev("document.querySelector('.leaflet-popup-content strong').textContent") == items[0].title
    selected = []
    web.selected.connect(selected.append)
    ev("document.querySelector('.news-selected').click(); true;")
    qtbot.waitUntil(lambda: selected == ['1'], timeout=5000)
    with qtbot.assertNotEmitted(web.selected, wait=100):
        web.bridge.selectNews('forged')
    web.set_items(items[:2])
    web.set_selected('2', focus=True)
    qtbot.waitUntil(lambda: ev("document.querySelectorAll('.news-selected').length") == 1, timeout=10000)
    qtbot.waitUntil(lambda: ev("document.querySelector('.leaflet-popup-content strong')?.textContent") == items[1].title)


@pytest.mark.webengine
def test_html_in_news_is_literal(web, qtbot):
    from dataclasses import replace
    item = replace(MockNewsProvider().load(Event()).items[0], title="<img src=x onerror='window.hacked=true'>")
    web.set_items([item])
    web.set_selected(item.id, focus=True)
    qtbot.waitUntil(lambda: evaluate(qtbot, web, "document.querySelectorAll('.leaflet-popup-content strong').length") == 1)
    result = json.loads(evaluate(qtbot, web,
        "JSON.stringify({hacked:!!window.hacked, images:document.querySelectorAll('.leaflet-popup-content img').length,"
        "text:document.querySelector('.leaflet-popup-content strong').textContent})"))
    assert result['hacked'] is False
    assert result['images'] == 0
    assert result['text'] == item.title


@pytest.mark.webengine
def test_fit_results_and_rapid_selection(web, qtbot):
    items = MockNewsProvider().load(Event()).items
    web.set_items([items[5], items[13]])
    web.fit_results()
    script = """Array.from(document.querySelectorAll('.leaflet-marker-icon')).filter(el => {
        const r = el.getBoundingClientRect();
        return r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight;
    }).length"""
    qtbot.waitUntil(lambda: evaluate(qtbot, web, script) == 2, timeout=10000)
    web.set_selected(items[5].id, focus=True)
    web.set_selected(items[13].id, focus=True)
    qtbot.waitUntil(lambda: evaluate(qtbot, web,
        "document.querySelector('.leaflet-popup-content strong')?.textContent") == items[13].title,
        timeout=10000)
