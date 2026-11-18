"""MapNews 지도 시각화 모듈.

뉴스 수집과 Gemini 전처리는 백엔드에서 수행한다.
이 파일은 지역명을 좌표로 변환하여 프론트엔드에 전달한다.
기존 Folium HTML 지도 생성 기능도 별도로 유지한다.
"""

# ============================================================
# 1. 필요한 라이브러리 가져오기
# ============================================================

import json  # 지역-좌표 검색 결과를 JSON 파일에 저장
import math  # 위도/경도의 숫자 유효성 검사
import os    # Nominatim 사용자 식별 문자열 설정
import tempfile

# 뉴스 제목 등에 들어 있는 HTML 특수문자를 안전하게 처리
from html import escape

# 운영체제와 관계없이 파일 경로 지정
from pathlib import Path

import folium  # 지도, 마커, 팝업 생성

# 좌표 검색 요청 속도 제한
from geopy.extra.rate_limiter import RateLimiter

# 지역 이름을 위도/경도로 변환
from geopy.geocoders import Nominatim


# ============================================================
# 2. 지도와 파일에 관한 기본 설정
# ============================================================

# 현재 파이썬 파일이 들어 있는 폴더의 경로
BASE_DIR = Path(__file__).resolve().parent

# 실행하면 생성되는 HTML 지도 파일
MAP_FILE = BASE_DIR / "news_map.html"

# 검색한 좌표를 재사용하기 위한 캐시 파일
CACHE_FILE = BASE_DIR / ".geocode_cache.json"

# 대한민국 중심의 대략적인 좌표
MAP_CENTER = [36.5, 127.8]

# 초기 지도 확대 수준
MAP_ZOOM = 7

# 국내 사건 위치를 표시하는 프로젝트이므로 다른 나라의 잘못된 검색 결과를 방지한다.
# 해외 뉴스도 시각화해야 한다면 False로 변경하고 지명 검색 정책을 함께 수정한다.
KOREA_ONLY = True
# 대한민국 본토와 부속 도서를 포함하는 대략적인 범위(엄밀한 국경선 아님)
KOREA_BOUNDS = (33.0, 39.0, 124.0, 132.0)


# Gemini API에서 분류한 뉴스 카테고리에 따라
# 지도 위의 마커 색상을 구분한다.
#
# Gemini API가 반환하는 카테고리:
# 사고, 화재, 교통, 행사, 사회
#
# 카테고리 이름은 백엔드와 동일하게 사용해야 한다.

CATEGORY_COLORS = {
    "사고": "red",       # 사고 관련 뉴스: 빨간색
    "화재": "orange",    # 화재 관련 뉴스: 주황색
    "교통": "blue",      # 교통 관련 뉴스: 파란색
    "행사": "green",     # 행사 관련 뉴스: 초록색
    "사회": "purple",    # 사회 관련 뉴스: 보라색
    "미분류": "gray"     # 분류할 수 없는 뉴스: 회색
}


# ============================================================
# 3. geopy 위치 검색기 설정
# ============================================================

# Nominatim은 OpenStreetMap 기반 지명 검색 서비스이다.
#
# user_agent:
#   어떤 프로그램이 위치 검색을 요청했는지 식별한다.
#
# timeout:
#   서버 응답을 기다리는 최대 시간(초)이다.
_geolocator = Nominatim(
    user_agent=os.getenv(
        "MAPNEWS_USER_AGENT",
        "MapNewsStudentProject/1.0 (github.com/pachir1su/MapNews)"
    ),
    timeout=10,
)

# 공개 Nominatim 서비스는 요청 속도 제한이 있다.
# 최소 1.1초 간격으로 검색하도록 설정한다.
#
# max_retries:
#   일시적인 서버 오류가 발생하면 1번 재시도한다.
#
# error_wait_seconds:
#   재시도하기 전 최소 대기 시간이다.
#
# swallow_exceptions:
#   검색 서비스 오류가 계속 발생하면 None을 반환한다.
_geocode = RateLimiter(
    _geolocator.geocode,
    min_delay_seconds=1.1,
    max_retries=1,
    error_wait_seconds=2,
    swallow_exceptions=True,
)


# ============================================================
# 함수 1. 좌표의 유효성 검사
# ============================================================

def parse_coordinates(latitude, longitude):
    """
    위도와 경도가 정상적인 숫자인지 확인한다.

    정상적인 좌표라면 [위도, 경도]를 반환한다.
    사용할 수 없는 값이라면 None을 반환한다.
    """

    # DB에서 전달받은 좌표가 문자열일 수도 있으므로
    # float()을 통해 실수형으로 변환한다.
    try:
        # True/False는 float()로 1.0/0.0이 될 수 있으므로 좌표로 사용하지 않는다.
        if isinstance(latitude, bool) or isinstance(longitude, bool):
            return None
        lat = float(latitude)
        lon = float(longitude)

    # 숫자로 변환할 수 없다면 사용할 수 없는 좌표이다.
    except (TypeError, ValueError):
        return None

    # math.isfinite()는 무한대나 NaN 값이 아닌지 확인한다.
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None

    # 위도는 -90~90, 경도는 -180~180 범위여야 한다.
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None

    # (0, 0)은 값이 누락됐을 때 관례적으로 들어가는 가짜 좌표이다.
    if lat == 0 and lon == 0:
        return None

    # 한국 지도 프로젝트에서 한국 밖의 핀이 생기지 않도록 방지한다.
    if KOREA_ONLY:
        min_lat, max_lat, min_lon, max_lon = KOREA_BOUNDS
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            return None

    return [lat, lon]




def atomic_write_json(path, payload):
    """Keep last valid cache/output on disk or process failure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".mapnews-", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

# ============================================================
# 함수 2. 저장된 좌표 캐시 불러오기
# ============================================================

def load_coordinate_cache():
    """
    이전에 검색한 지역별 좌표를 JSON 파일에서 불러온다.

    같은 지역을 매번 인터넷에서 다시 검색하는 것을
    방지하기 위한 기능이다.
    """

    # 캐시 파일이 없으면 빈 딕셔너리를 반환한다.
    if not CACHE_FILE.exists():
        return {}

    try:
        # JSON 파일을 읽기 모드로 연다.
        with CACHE_FILE.open("r", encoding="utf-8") as file:
            saved = json.load(file)

    except (OSError, json.JSONDecodeError):
        print("좌표 캐시를 읽지 못해 새로 검색합니다.")
        return {}

    # 저장된 데이터가 딕셔너리가 아니면 사용하지 않는다.
    if not isinstance(saved, dict):
        return {}

    cache = {}

    # 저장된 지역과 좌표를 하나씩 확인한다.
    for place, coords in saved.items():

        # 지역명이 문자열이고 좌표가 2개인지 확인한다.
        if (
            isinstance(place, str)
            and isinstance(coords, list)
            and len(coords) == 2
        ):

            # 좌표의 유효성을 검사한다.
            parsed = parse_coordinates(coords[0], coords[1])

            if parsed is not None:
                cache[place] = parsed

    return cache


# ============================================================
# 함수 3. 좌표 캐시 저장
# ============================================================

def save_coordinate_cache(cache):
    """
    검색한 좌표를 JSON 파일로 저장한다.

    프로그램을 다시 실행하더라도
    이전에 검색한 지역의 좌표를 사용할 수 있다.
    """

    # 좌표 검색에 성공한 지역만 저장한다.
    saved = {
        name: coords
        for name, coords in cache.items()
        if coords is not None
    }

    # 캐시는 성능 개선용이다. 저장에 실패해도 뉴스 목록은 유지한다.
    try:
        atomic_write_json(CACHE_FILE, saved)
    except OSError as exc:
        print(f"좌표 캐시 저장 실패(뉴스 처리는 계속 진행): {exc}")


# ============================================================
# 함수 4. 지역 이름을 위도와 경도로 변환
# ============================================================

def get_coordinates(place_name, cache):
    """
    지역 이름을 받아 위도와 경도를 검색한다.

    place_name:
        Gemini API가 추출한 뉴스 발생 지역

    cache:
        이미 검색한 지역과 좌표를 저장한 딕셔너리
    """

    # 입력받은 지역 이름을 문자열로 변환한다.
    place_name = str(place_name or "").strip()

    # 분석 결과에 위치 정보가 없는 경우에는 검색하지 않는다.
    if place_name.lower() in {"", "미상", "알 수 없음", "없음", "n/a", "null", "none"}:
        return None

    # 캐시에 이미 존재하는 지역이라면
    # 인터넷 검색 없이 저장된 좌표를 사용한다.
    if place_name in cache:
        return cache[place_name]

    # 국내 행정구역 약칭을 정식 명칭으로 바꿔 지오코딩 성공률을 높인다.
    # 입력 데이터를 덮어쓰지 않고 '검색어'만 변경한다.
    abbreviations = {
        "충남": "충청남도", "충북": "충청북도", "경남": "경상남도",
        "경북": "경상북도", "전남": "전라남도", "전북": "전북특별자치도",
        "강원": "강원특별자치도", "경기": "경기도",
    }
    query = place_name
    for short, official in abbreviations.items():
        if query == short or query.startswith(short + " "):
            query = official + query[len(short):]
            break

    # Nominatim에서 동명이인 지명 때문에 해외 좌표를 돌려주지 않도록
    # 대한민국으로 검색 범위를 제한한다.
    try:
        if KOREA_ONLY:
            result = _geocode(query + ", 대한민국", country_codes="kr")
        else:
            result = _geocode(query)
    except Exception as exc:
        # 네트워크/서비스 예외가 한 건에서 발생해도 전체 기사는 유지한다.
        print(f"지오코딩 오류({place_name}): {type(exc).__name__}: {exc}")
        cache[place_name] = None
        return None

    # 검색에 실패했다면 해당 뉴스의 위치를 알 수 없다.
    if result is None:
        print(f"좌표 검색 실패: {place_name}")

        # 이번 실행에서는 같은 검색 실패를 반복하지 않는다.
        cache[place_name] = None

        return None

    # 검색 결과에서 위도와 경도를 추출한다.
    # 검색 서버 응답에도 유효성 검사를 수행한다.
    coordinates = parse_coordinates(result.latitude, result.longitude)
    if coordinates is None:
        print(f"잘못된 지오코딩 좌표 제외: {place_name}")
        cache[place_name] = None
        return None

    # 검색 결과를 캐시에 저장한다.
    cache[place_name] = coordinates

    return coordinates


# ============================================================
# 함수 5. 프론트엔드 전달용 뉴스 데이터 생성 [신규]
# ============================================================

def prepare_news_for_frontend(news_list, *, geocode_missing=True):
    """백엔드의 뉴스 목록에 위도/경도를 붙여 프론트엔드로 전달한다.

    입력: 크롤링과 Gemini 분석 결과가 합쳐진 뉴스 목록
        - 크롤링/DB 담당: id, title, url, datetime
        - Gemini 담당: category, location, summary

    출력: 다음 9개 키를 가진 딕셔너리의 리스트
        id, title, category, location, summary, url, datetime,
        latitude, longitude

    좌표를 찾지 못해도 기사 자체는 제거하지 않는다.
    대신 latitude와 longitude를 모두 None으로 반환한다.
    """

    # 이전 실행에서 검색한 지역 좌표를 가져온다.
    cache = load_coordinate_cache()
    frontend_news_list = []

    # 프론트엔드가 기대하는 필드 이름을 고정한다.
    fields = (
        "id", "title", "category", "location", "summary",
        "url", "datetime", "source", "publisher", "content_hash",
        "analysis_status", "coordinate_note"
    )

    for news in news_list:
        # sqlite3.Row와 일반 딕셔너리를 모두 처리한다.
        try:
            source = dict(news)
        except (TypeError, ValueError):
            print("올바르지 않은 뉴스 데이터를 건너뜁니다.")
            continue

        # 프론트엔드에 필요한 7개 기사 정보를 그대로 복사한다.
        # 누락된 필드는 None이 된다. 존재하지 않는 제목이나 ID를
        # 지도 모듈에서 임의로 만드는 것은 피한다.
        news_data = {field: source.get(field) for field in fields}

        # 기존 DB에 유효한 좌표가 있으면 우선 사용한다.
        coordinates = parse_coordinates(
            source.get("latitude"),
            source.get("longitude")
        )

        # 좌표가 없는 경우에만 발생 지역을 geopy로 검색한다.
        if coordinates is None and geocode_missing:
            coordinates = get_coordinates(
                news_data.get("location"), cache
            )

        if coordinates is None:
            # 좌표 검색 실패: 기사 목록/상세 화면은 유지하고
            # 프론트엔드는 지도 마커만 생성하지 않도록 한다.
            news_data["latitude"] = None
            news_data["longitude"] = None
        else:
            news_data["latitude"] = coordinates[0]
            news_data["longitude"] = coordinates[1]
            if not news_data.get("coordinate_note"):
                news_data["coordinate_note"] = (
                    "행정구역 대표 좌표일 수 있으며 실제 사건 지점은 검증되지 않았습니다."
                )

        frontend_news_list.append(news_data)

    # 다음 실행에서 같은 지역을 재검색하지 않도록 저장한다.
    save_coordinate_cache(cache)

    # 백엔드가 이 값을 프론트엔드로 전달해야 한다.
    return frontend_news_list


# ============================================================
# 함수 6. 기본 지도 생성 (기존 기능 유지)
# ============================================================

def create_base_map():
    """
    대한민국을 중심으로 기본 Folium 지도를 생성한다.
    """

    news_map = folium.Map(
        location=MAP_CENTER,
        zoom_start=MAP_ZOOM,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    return news_map


# ============================================================
# 함수 7. 뉴스 마커 추가 (기존 HTML 지도용)
# ============================================================


def add_news_marker(news_map, news, cache, category_layers, *, geocode_missing=True):
    """
    Gemini API가 분석한 뉴스 정보를 지도에 표시한다.

    전달받는 데이터 형식:
    {
        "location": "충남 천안시 서북구",
        "category": "사고",
        "summary": "차량 3대가 연쇄 추돌했으며..."
    }

    location : 사건이 발생한 지역
    category : Gemini가 분류한 뉴스 카테고리
    summary  : Gemini가 생성한 뉴스 요약
    """

    # ========================================================
    # 1. Gemini 분석 결과 가져오기
    # ========================================================

    # 뉴스 발생 지역
    # 지역 정보가 없으면 빈 문자열로 처리한다.
    place = str(news.get("location") or "").strip()

    # 뉴스 카테고리
    # 카테고리가 없으면 "미분류"로 설정한다.
    category = str(news.get("category") or "미분류").strip()

    # Gemini가 생성한 뉴스 요약
    # 요약이 없으면 기본 안내 문구를 사용한다.
    summary = str(
        news.get("summary") or "요약 정보 없음"
    ).strip()

    # ========================================================
    # 2. 뉴스 발생 지역의 좌표 검색
    # ========================================================

    # 프론트엔드가 지도에 핀을 찍는 것과 동일하게
    # latitude, longitude가 유효한 경우에만 마커를 생성한다.
    # HTML 지도 미리보기에서도 데이터가 없는 위치를 임의로 검색하지 않는다.
    coordinates = parse_coordinates(
        news.get("latitude"), news.get("longitude")
    )

    # 기존 Folium 사용처는 기본값(True)으로 검색할 수 있다.
    # Issue #10 검증 모드에서는 False로 설정해 프론트엔드와 같은
    # 입력 좌표만 사용하므로 핀 개수가 정확히 일치한다.
    if coordinates is None and geocode_missing:
        coordinates = get_coordinates(place, cache)

    # 좌표를 얻지 못한 경우에만 마커 생성을 생략한다.
    if coordinates is None:
        print(f"좌표 없음: {place or '지역 미상'}")
        return None

    # ========================================================
    # 3. 지도 팝업에 표시할 정보 생성
    # ========================================================

    # 외부에서 받은 데이터의 HTML 특수문자를 변환한다.
    # 의도하지 않은 HTML 코드가 실행되는 것을 방지한다.
    safe_place = escape(place)
    safe_category = escape(category)

    # Gemini 요약에 줄바꿈이 존재할 경우
    # HTML에서도 줄바꿈이 보이도록 변환한다.
    safe_summary = escape(summary).replace("\n", "<br>")

    # 마커를 클릭하면 나타나는 정보창의 내용이다.
    popup_html = (
        f"<b>뉴스 발생 지역</b><br>"
        f"{safe_place}<br><br>"

        f"<b>카테고리</b><br>"
        f"{safe_category}<br><br>"

        f"<b>뉴스 요약</b><br>"
        f"{safe_summary}"
    )

    # ========================================================
    # 4. 카테고리별 지도 레이어 생성
    # ========================================================

    # 해당 카테고리의 그룹이 아직 없다면
    # 새로운 FeatureGroup을 생성한다.
    if category not in category_layers:

        layer = folium.FeatureGroup(
            name=escape(category),
            show=True
        )

        # 카테고리 그룹을 지도에 추가한다.
        layer.add_to(news_map)

        # 생성한 그룹을 딕셔너리에 저장한다.
        category_layers[category] = layer

    # 카테고리에 해당하는 마커 색상을 가져온다.
    # CATEGORY_COLORS는 앞서 변경한 설정을 그대로 사용한다.
    marker_color = CATEGORY_COLORS.get(category, "gray")

    # ========================================================
    # 5. 지도 마커 생성
    # ========================================================

    # geopy로 찾은 좌표에 마커를 생성한다.
    folium.Marker(

        # 마커가 표시될 위도와 경도
        location=coordinates,

        # 클릭 시 뉴스 발생 지역, 카테고리, 요약 표시
        popup=folium.Popup(
            popup_html,
            max_width=350
        ),

        # 마커 위에 마우스를 올렸을 때 지역명 표시
        tooltip=folium.Tooltip(safe_place),

        # 뉴스 카테고리에 따라 마커 색상 구분
        icon=folium.Icon(
            color=marker_color,
            icon="info-sign"
        )

    ).add_to(category_layers[category])

    # 마커 생성에 성공했다면 좌표를 반환한다.
    return coordinates

# ============================================================
# 함수 8. 전체 뉴스 지도 생성 (기존 HTML 지도용)
# ============================================================

def create_news_map(news_list, output_file=MAP_FILE, *, geocode_missing=True):
    """
    백엔드에서 전달받은 뉴스 목록을 지도에 표시한다.

    news_list:
        전처리가 완료된 여러 뉴스 정보를 담은 리스트

    output_file:
        생성된 HTML 지도를 저장할 위치

    실제 뉴스 데이터와 시연용 데이터 모두
    동일한 형식으로 전달받도록 설계하였다.
    """

    # 대한민국 중심의 기본 지도를 생성한다.
    news_map = create_base_map()

    # 기존 좌표 검색 결과를 불러온다.
    cache = load_coordinate_cache()

    # 카테고리별 지도 레이어를 저장한다.
    category_layers = {}

    # 지도에 추가한 마커의 좌표를 저장한다.
    marker_positions = []

    # 전달받은 뉴스 목록을 반복문으로 처리한다.
    for news in news_list:

        # DB에서 가져온 sqlite3.Row 데이터도
        # 딕셔너리 형태로 변환할 수 있도록 한다.
        try:
            news_dict = dict(news)

        except (TypeError, ValueError):
            print("올바르지 않은 뉴스 데이터를 제외했습니다.")
            continue

        # 뉴스 1개를 지도에 추가한다.
        position = add_news_marker(
            news_map,
            news_dict,
            cache,
            category_layers,
            geocode_missing=geocode_missing
        )

        # 성공적으로 추가된 마커만 좌표 목록에 저장한다.
        if position is not None:
            marker_positions.append(position)

    # --------------------------------------------------------
    # 7-1. 카테고리별 필터 기능 추가
    # --------------------------------------------------------

    # 카테고리 그룹이 생성되었다면
    # 지도 오른쪽에 레이어 선택 메뉴를 만든다.
    if category_layers:

        folium.LayerControl(
            collapsed=False
        ).add_to(news_map)

    # --------------------------------------------------------
    # 7-2. 지도 표시 범위 자동 조정
    # --------------------------------------------------------

    # 지도에 마커가 2개 이상 있다면
    # 모든 마커가 화면 안에 보이도록 조정한다.
    if len(marker_positions) >= 2:

        news_map.fit_bounds(
            marker_positions,
            padding=(25, 25)
        )

    # --------------------------------------------------------
    # 7-3. 지도 파일 저장
    # --------------------------------------------------------

    # 검색한 좌표를 다음 실행에서도 사용할 수 있도록 저장한다.
    save_coordinate_cache(cache)

    # HTML 파일이 저장될 경로를 설정한다.
    output_file = Path(output_file)

    # 저장할 폴더가 없으면 생성한다.
    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # 완성된 지도를 HTML 파일로 저장한다.
    news_map.save(str(output_file))

    # 실행 결과 출력
    print(f"지도 생성 완료: {output_file}")

    print(
        f"표시한 뉴스: {len(marker_positions)}건"
    )

    print(
        f"제외한 뉴스: "
        f"{len(news_list) - len(marker_positions)}건"
    )

    # 지도에 실제로 등록된 마커 수를 검증에 활용한다.
    # 새 속성은 HTML 지도 기능과 무관한 검사 전용 정보다.
    news_map.mapnews_marker_count = count_folium_markers(news_map)

    # 다른 코드에서 지도 객체를 사용할 수 있도록 반환한다.
    return news_map


# ============================================================
# 함수 9. 프론트엔드 좌표 검사와 실제 Folium 마커 개수
# ============================================================

def count_valid_coordinate_news(news_list):
    """프론트엔드가 핀을 표시할 수 있는 기사 수를 반환한다."""
    return sum(
        parse_coordinates(news.get("latitude"), news.get("longitude")) is not None
        for news in news_list
    )


def count_folium_markers(element):
    """Folium 지도와 하위 카테고리 그룹에 등록된 실제 Marker 수를 센다."""
    total = 0
    for child in element._children.values():
        if isinstance(child, folium.Marker):
            total += 1
        total += count_folium_markers(child)
    return total


# ============================================================
# 프로그램 실행 (뉴스 결과 JSON -> 좌표 변환 후 JSON 저장)
# ============================================================

if __name__ == "__main__":
    import sys

    # 사용법: python map_visualization/map_visualization.py [입력파일] [출력파일]
    # 아무것도 적지 않으면 data_ai/results_sample.json을 읽어
    # map_visualization/map_results.json으로 저장한다.
    input_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else BASE_DIR.parent / "data_ai" / "results_sample.json"
    )
    output_path = (
        Path(sys.argv[2]) if len(sys.argv) > 2
        else BASE_DIR / "map_results.json"
    )

    if input_path.resolve() == output_path.resolve():
        raise SystemExit("지도 입력 파일과 출력 파일은 서로 달라야 합니다.")

    if not input_path.exists():
        print(f"입력 파일을 찾을 수 없습니다: {input_path}")
    else:
        with input_path.open("r", encoding="utf-8") as file:
            news_list = json.load(file)

        print(f"총 {len(news_list)}건의 뉴스를 불러왔습니다. 좌표 변환을 시작합니다...")

        # 지역명을 위도/경도로 변환
        frontend_news = prepare_news_for_frontend(news_list)

        # 최종 JSON 파일 저장
        if not frontend_news:
            raise ValueError("유효한 뉴스 0건: 이전 지도 결과 보존")
        atomic_write_json(output_path, frontend_news)

        print(f"완료! 좌표가 추가된 파일이 저장되었습니다: {output_path}")