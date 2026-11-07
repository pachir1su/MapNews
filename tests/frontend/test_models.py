import json
from dataclasses import replace
from threading import Event
import pytest
from frontend.models import coordinate, parse_news, safe_url
from frontend.providers import JsonNewsProvider, MockNewsProvider, RESOURCES
from frontend.state import FilterState, NewsState


@pytest.fixture
def batch():
    return MockNewsProvider().load(Event())


def test_original_demo_snapshot_and_coordinates(batch):
    payload = json.loads((RESOURCES / 'dummy_news.json').read_text(encoding='utf-8'))
    assert len(payload) == len(batch.items) == 20
    assert set(payload[0]) == {'id', 'title', 'category', 'location', 'summary', 'url', 'datetime'}
    assert not batch.warnings
    assert all(n.is_mock and n.has_coordinates and '대표 좌표' in n.coordinate_note for n in batch.items)
    assert {n.category for n in batch.items} == {'사고', '화재', '교통', '행사', '사회'}
    assert len({n.id for n in batch.items}) == 20


@pytest.mark.parametrize('value', [None, {}, 'news', 1])
def test_bad_root(value):
    with pytest.raises(ValueError):
        parse_news(value)


def test_broken_rows_keep_valid_news():
    result = parse_news([None, {}, {'id': True}, {'id': 1, 'datetime': 'yesterday',
                         'category': '문화', 'latitude': 'nan', 'longitude': 127,
                         'url': 'javascript:alert(1)'}, {'id': '1'}, {'id': 2}])
    assert [n.id for n in result.items] == ['1', '2']
    assert result.items[0].category == '문화'
    assert result.items[0].published_at is None
    assert result.items[0].url == ''
    assert not result.items[0].has_coordinates
    assert result.items[1].title == '제목 미제공'
    assert len(result.warnings) >= 6


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'file:///tmp/test', '//example.com',
                                'https://user:pass@example.com', 'https://example.com/\nfoo',
                                'https://[invalid', 'https://example.com:bad', 'https:\\evil'])
def test_unsafe_links(url):
    assert safe_url(url) == ''


@pytest.mark.parametrize('url', ['https://news.example.org/a?q=1', 'http://example.org',
                                'https://한국.example/뉴스'])
def test_http_links(url):
    assert safe_url(url) == url


@pytest.mark.parametrize('value', [None, True, float('nan'), float('inf'), 91, -91, 'bad'])
def test_invalid_latitude(value):
    assert coordinate(value, 90) is None


def test_dates_normalize_to_kst():
    result = parse_news([{'id': 1, 'datetime': '2026-11-04T01:23:00Z'},
                         {'id': 2, 'datetime': '2026-11-04 10:23'}])
    assert result.items[0].published_at == result.items[1].published_at
    assert result.items[0].date_label == '2026.11.04 10:23'


def test_json_provider_has_no_demo_coordinate_inference(tmp_path):
    path = tmp_path / 'news.json'
    path.write_text('[{"id":1,"title":"외부 기사","category":"사고"}]', encoding='utf-8')
    result = JsonNewsProvider(path).load(Event())
    assert not result.items[0].is_mock
    assert not result.items[0].has_coordinates


def test_json_bom_and_coordinates(tmp_path):
    path = tmp_path / 'news.json'
    path.write_text('[{"id":"x","latitude":36.8,"longitude":127.1}]', encoding='utf-8-sig')
    item = JsonNewsProvider(path).load(Event()).items[0]
    assert item.has_coordinates and item.latitude == 36.8


def test_invalid_json_and_missing_file(tmp_path):
    path = tmp_path / 'news.json'
    with pytest.raises(FileNotFoundError):
        JsonNewsProvider(path).load(Event())
    path.write_text('{', encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        JsonNewsProvider(path).load(Event())


def test_provider_cancellation(tmp_path):
    event = Event()
    event.set()
    assert JsonNewsProvider(tmp_path / 'missing').load(event).items == ()
    assert MockNewsProvider().load(event).items == ()


def test_filter_categories(batch):
    state = NewsState(batch.items, FilterState(categories={'사고', '화재'}))
    assert len(state.visible()) == 8
    state.filters.categories = set()
    assert state.visible() == []
    state.filters.categories = None
    assert len(state.visible()) == 20


def test_search_region_combination(batch):
    state = NewsState(batch.items, FilterState(keyword='수원 화재', region='경기'))
    assert [n.id for n in state.visible()] == ['2']
    state.filters.keyword = '없는키워드'
    assert state.visible() == []


def test_case_insensitive_multiword_search(batch):
    item = replace(batch.items[0], title='MapNews DEMO')
    assert NewsState((item,), FilterState(keyword='mapnews demo')).visible() == [item]


def test_sort_invalid_date_last(batch):
    undated = replace(batch.items[0], id='undated', published_at=None)
    state = NewsState(batch.items + (undated,))
    assert state.visible()[0].id == '1'
    assert state.visible()[-1].id == 'undated'
    state.filters.newest_first = False
    assert state.visible()[0].id == '20'
    assert state.visible()[-1].id == 'undated'


def test_selection_and_filter_reconciliation(batch):
    state = NewsState(batch.items)
    assert state.select('1') == batch.items[0]
    state.filters.categories = {'행사'}
    assert state.reconcile_selection() is None
    assert state.selected_id is None
    assert state.select('forged') is None


def test_dataset_bounds():
    with pytest.raises(ValueError):
        parse_news([{}] * 10001)


def test_overflow_dates():
    result = parse_news([{'id': 1, 'datetime': '9999-12-31T23:59:59-12:00'}, {'id': 2}])
    assert result.items[0].published_at is None
    assert result.items[1].published_at is None
