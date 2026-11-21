"""Conservative, deterministic and API-free article classification/location extraction.

Coordinates are NOT calculated here. A named city/district is a regional hint,
not proof of the incident's exact address. Reporter datelines are never treated
as incident locations, and unknown/ambiguous places remain unmapped.
"""
import re

from search import normalize_article

CATEGORIES = ("사고", "화재", "교통", "행사", "사회")
RULE_VERSION = "regional-headline-v4"

# Explicit administrative labels. Add only verified Korean names; do not derive
# location from arbitrary words ending in '시' (e.g. 반드시, 대학입시).
SIDO = {
    "서울": "서울특별시", "부산": "부산광역시",
    "대구": "대구광역시", "인천": "인천광역시",
    "광주": "광주광역시", "대전": "대전광역시",
    "울산": "울산광역시", "세종": "세종특별자치시",
    "경기": "경기도", "강원": "강원특별자치도",
    "충남": "충청남도", "충북": "충청북도",
    "전북": "전북특별자치도", "전남": "전라남도",
    "경북": "경상북도", "경남": "경상남도",
    "제주": "제주특별자치도",
}
# Explicitly controlled dictionary: a regional centre pin is never advertised
# as an exact incident location. Ambiguous bare names are intentionally omitted.
LOCALITIES = {
    "서울특별시": "강남구 강북구 강동구 성북구 서초구 송파구 관악구 금천구 동작구 마포구 양천구 영등포구 용산구 동대문구 종로구 구로구 은평구 노원구 도봉구 성동구 광진구 서대문구 중랑구",
    "경기도": "하남시 안성시 성남시 안산시 수원시 화성시 용인시 김포시 의왕시 군포시 과천시 고양시 양평군 연천군 이천시 평택시 광명시 안양시 포천시 파주시 오산시 시흥시 남양주시 광주시 부천시 여주시 동두천시 의정부시 가평군",
    "충청남도": "천안시 아산시 서산시 태안군 공주시 논산시 보령시 당진시 홍성군 예산군 부여군 금산군 서천군 청양군 계룡시",
    "충청북도": "청주시 충주시 제천시 단양군 음성군 진천군 괴산군 보은군 옥천군 영동군 증평군",
    "전북특별자치도": "전주시 군산시 정읍시 익산시 남원시 김제시 무주군 고창군 부안군 진안군 완주군 임실군 장수군 순창군",
    "전라남도": "순천시 여수시 목포시 나주시 광양시 고흥군 화순군 담양군 무안군 영암군 영광군 보성군 장흥군 완도군 신안군 해남군 곡성군 구례군 장성군 함평군 강진군 진도군",
    "경상북도": "포항시 영덕군 경주시 영양군 구미시 안동시 울진군 김천시 상주시 경산시 문경시 영주시 청도군 칠곡군 성주군 의성군 봉화군 영천시",
    "경상남도": "창원시 밀양시 양산시 창녕군 거제시 김해시 진주시 통영시 사천시 거창군 합천군 남해군 하동군 고성군 함안군 함양군 산청군 의령군",
    "강원특별자치도": "원주시 춘천시 강릉시 속초시 동해시 삼척시 태백시 평창군 정선군 횡성군 인제군 양구군 화천군 홍천군 양양군 고성군 철원군 영월군",
    "제주특별자치도": "제주시 서귀포시",
    "부산광역시": "해운대구 수영구 사하구 부산진구 기장군 영도구 금정구 연제구 동래구",
    "대구광역시": "달서구 수성구 달성군 군위군",
    "인천광역시": "연수구 계양구 미추홀구 남동구 강화군 옹진군",
    "대전광역시": "유성구 대덕구",
    "울산광역시": "울주군",
}
# A standalone '서구', '동구' or '광주시' is ambiguous. Districts become
# resolvable when a full metropolitan prefix is present in the headline.
AMBIGUOUS = {
    "광주", "광주시", "서구", "동구", "중구", "남구", "북구",
    "강서구", "고성군",
    # Common Korean non-place words; require the explicit administrative suffix.
    "강화", "예산", "달성", "진도", "영양", "상주", "공주",
    "영광", "함양", "양산", "진주", "보성", "화성", "무주",
}

def _build_aliases():
    mapping = {}
    for short, full in SIDO.items():
        mapping[short] = full
        mapping[full] = full
    mapping.update({"서울시": "서울특별시", "세종시": "세종특별자치시"})
    for province, names in LOCALITIES.items():
        for name in names.split():
            full = f"{province} {name}"
            if name not in AMBIGUOUS and name not in mapping:
                mapping[name] = full
            short = name[:-1] if name.endswith(("시", "군", "구")) else name
            if short not in AMBIGUOUS and short not in mapping:
                mapping[short] = full
    return mapping

ALIASES = _build_aliases()
TOKEN_RX = re.compile(
    r"(?<![가-힣])(" +
    "|".join(re.escape(name) for name in sorted(ALIASES, key=len, reverse=True)) +
    r")(?=$|[^가-힣]|(?:에서|으로|은|는|이|가|을|를|에|의|서|와|과|도|만|로|엔)(?=$|[^가-힣]))"
)
DISTRICT_RX = re.compile(r"^\s+([가-힣]{1,8}구)(?=$|[^가-힣]|[은는이가을를에의서])")
SHORT_DISTRICTS = {"서구", "동구", "중구", "남구", "북구", "강서구"}
CITY_DISTRICTS = {
    "충청남도 천안시": {"서북구", "동남구"},
    "경기도 수원시": {"권선구", "영통구", "장안구", "팔달구"},
    "경기도 성남시": {"분당구", "수정구", "중원구"},
    "경기도 고양시": {"덕양구", "일산동구", "일산서구"},
    "경기도 안산시": {"단원구", "상록구"},
    "경기도 용인시": {"기흥구", "수지구", "처인구"},
    "충청북도 청주시": {"흥덕구", "상당구", "서원구", "청원구"},
    "전북특별자치도 전주시": {"완산구", "덕진구"},
    "경상북도 포항시": {"남구", "북구"},
    "경상남도 창원시": {"성산구", "진해구", "의창구", "마산회원구", "마산합포구"},
}
ACTIVITY_RX = re.compile(r"사고|화재|추락|충돌|전복|살인|시신|발견|실종|대피|수색|축제|공연|개최")
BODY_EVENT_RX = re.compile(r"^(?:에서|에|의)\s*(?:.{0,20}?)(?:발생|발견|추락|충돌|열렸|열린|개최|대피|숨졌|수색)")
DATELINE_RX = re.compile(r"^\s*\[[^\]\n]{1,90}=(?:뉴시스|연합뉴스|뉴스1)\]\s*[^=\n]{0,90}기자\s*=")

MEDIA_QUOTED_TITLE_RX = re.compile(r"'[^']{2,60}'|‘[^’]{2,60}’|“[^”]{2,60}”")
MEDIA_ARTICLE_RX = re.compile(r"배급사|영화|다큐멘터리|연출작|신작 드라마")
MEDIA_REPORT_RX = re.compile(r"상영|개봉|영화제|OTT|드라마|영화")
# Only an explicit place followed by a concrete local event may be sourced
# from the opening paragraph. Reporter location and incidental mentions do not count.
LEAD_LOCAL_PREDICATE_RX = re.compile(
    r"^(?:.{0,90}?)(?:에서|서|에|의|이|가)"
    r"[^.!?\n]{0,105}?"
    r"(?:발견|적발|발생|숨졌|추락|충돌|들이받|불이\s*났|대피|실시|개최|열렸|"
    r"훈련|캠페인|현장\s*점검|점검|찾아|방문|선정|접수|신고|개청|연다|확인했|압수\s*수색|확인하고\s*있)"
)
# Specific headlines may describe an institution, but the ceremony takes place
# elsewhere. A single event pin must not be pinned to an awardee's home city.
REMOTE_CEREMONY_RX = re.compile(r"표창|수상|정부포상|상훈|시상")
DIGEST_RX = re.compile(r"^\[[^\]]{1,30}소식\]")
MULTISITE_REPORT_RX = re.compile(r"수능|전국.*(?:현장|점검)|복수.*(?:현장|학교)")
CEREMONY_LEAD_RX = re.compile(r"시상식|수여식")
QUALIFIED_SHORT_LOCALITIES = {
    ("경남", "양산"): "경상남도 양산시",
    ("경남", "진주"): "경상남도 진주시",
    ("경기", "화성"): "경기도 화성시",
    ("충남", "공주"): "충청남도 공주시",
    ("인천", "강화"): "인천광역시 강화군",
}
QUALIFIED_RX = re.compile(
    r"(?<![가-힣])(경남|경기|충남|인천)\s+"
    r"(양산|진주|화성|공주|강화)(?=$|[^가-힣]|(?:에서|서|에)(?=$|[^가-힣]))"
)

def _qualified_places(text):
    return [
        (QUALIFIED_SHORT_LOCALITIES[(m.group(1), m.group(2))], m.start())
        for m in QUALIFIED_RX.finditer(text)
        if (m.group(1), m.group(2)) in QUALIFIED_SHORT_LOCALITIES
    ]

def _conflicting_venue(headline_region, title, lead):
    if not (headline_region and REMOTE_CEREMONY_RX.search(title)
            and CEREMONY_LEAD_RX.search(lead[:500])):
        return False
    specific = {place for place, _ in _find_places(lead[:400]) if " " in place}
    return any(
        place != headline_region
        and not place.startswith(headline_region + " ")
        and not headline_region.startswith(place + " ")
        for place in specific
    )

LEAD_EVENT_TITLE_RX = re.compile(
    r"화재|추락|사망|음주운전|적발|사고|발견|실종|시신|수색|사건|"
    r"구조훈련|훈련|캠페인|현장|점검|모색|회의|선정|개소|개청|개최|축제|방문|피싱|압수수색|현장교육|한 컷|불|거리서"
)


CATEGORY_WORDS = (
    ("화재", ("화재", "불길", "불이 나", "불이 난", "산불")),
    ("사고", ("추돌", "충돌", "전복", "추락", "사망 사고", "부상 사고", "교통사고")),
    ("교통", ("도로 통제", "교통 통제", "정체", "차량 통행", "우회 도로")),
    ("행사", ("축제", "전시회", "설명회", "박람회", "개최", "공연")),
)

def classify(title, summary=""):
    text = (title + " " + summary[:120]).lower()
    for category, words in CATEGORY_WORDS:
        if any(word in text for word in words):
            return category
    return "사회"

def _find_places(text):
    """Find only bounded gazetteer tokens, rather than arbitrary '*시' words."""
    found = []
    for match in TOKEN_RX.finditer(text):
        name = match.group(1)
        canonical = ALIASES[name]
        # Extend city names only when an explicit following district exists.
        if canonical.endswith("시"):
            district = DISTRICT_RX.match(text[match.end():])
            if district and district.group(1) in CITY_DISTRICTS.get(canonical, set()):
                canonical = canonical + " " + district.group(1)
        # A province + adjacent ambiguous city/district is still unambiguous.
        if canonical in SIDO.values():
            remainder = text[match.end():]
            district = DISTRICT_RX.match(remainder)
            if district and district.group(1) in SHORT_DISTRICTS:
                canonical += " " + district.group(1)
        found.append((canonical, match.start()))
    return found

def _choose_unique(found):
    if not found:
        return "", "none"
    specific = {x for x, _ in found if " " in x}
    if len(specific) == 1:
        selected = next(iter(specific))
        provinces = {x for x, _ in found if " " not in x}
        if provinces and provinces != {selected.split(" ", 1)[0]}:
            # A headline beginning with one explicit city is often followed
            # by broader comparison regions. Prefer that singular city only
            # when it appears before all conflicting province references.
            first_specific = min(pos for name, pos in found if name == selected)
            other_positions = [
                pos for name, pos in found
                if " " not in name and name != selected.split(" ", 1)[0]
            ]
            if other_positions and first_specific >= min(other_positions):
                return "", "ambiguous"
        return selected, "headline"
    if len(specific) > 1:
        return "", "ambiguous"
    names = {x for x, _ in found}
    if len(names) == 1:
        return next(iter(names)), "headline"
    return "", "ambiguous"

def locate(title, summary=""):
    """Return (coarse_region, evidence_type), never an invented event address."""
    title = str(title or "")
    body = str(summary or "")
    if DIGEST_RX.search(title):
        return "", "ambiguous"
    headline = title
    # A quoted name of a film must not be treated as its physical screening
    # location. Strip only when the headline AND article lead substantiate
    # that the quote is a media title.
    if MEDIA_REPORT_RX.search(title) and MEDIA_ARTICLE_RX.search(
            DATELINE_RX.sub("", body, count=1)[:260]):
        headline = MEDIA_QUOTED_TITLE_RX.sub("", headline)
    location, kind = _choose_unique(_find_places(headline))
    lead = DATELINE_RX.sub("", body, count=1)
    if location and _conflicting_venue(location, title, lead):
        return "", "ambiguous"
    if location or kind == "ambiguous":
        return location, kind
    # Look for explicit local event evidence in the lead only, never treat
    # [서울=뉴시스] or other reporter datelines as event locations.
    if not (ACTIVITY_RX.search(title) or LEAD_EVENT_TITLE_RX.search(title)):
        return "", "none"
    # In a broad multi-school report, multiple explicit on-site locations
    # invalidate a single-pin inference even if only one venue has a nearby verb.
    if MULTISITE_REPORT_RX.search(title):
        visited = {name for name, _ in _find_places(lead[:1100]) if " " in name}
        if len(visited) > 1:
            return "", "ambiguous"
    lead = lead[:410]
    matched = []
    for match in TOKEN_RX.finditer(lead):
        name = match.group(1)
        canonical = ALIASES[name]
        # A named metropolitan city and following district are a precise
        # enough administrative reference; the province alone is not.
        if canonical in SIDO.values():
            district = DISTRICT_RX.match(lead[match.end():])
            if district and district.group(1) in SHORT_DISTRICTS:
                canonical += " " + district.group(1)
        if " " not in canonical:
            continue  # province-only lead reference is insufficient
        # Extend explicit city + verified district without inventing districts.
        if canonical.endswith("시"):
            district = DISTRICT_RX.match(lead[match.end():])
            if district and district.group(1) in CITY_DISTRICTS.get(canonical, set()):
                canonical += " " + district.group(1)
        if LEAD_LOCAL_PREDICATE_RX.match(lead[match.end():match.end() + 190]):
            matched.append((canonical, match.start()))
    # Qualified place pairs rescue noun-like short names only when the
    # explicit administrative province supports a single concrete locality.
    if not matched:
        for name, pos in _qualified_places(lead):
            tail = lead[pos + 2:pos + 170]
            if re.search(r"모여|모였|열렸|개최|진행|서|에서|에", tail):
                matched.append((name, pos))
    inferred, kind = _choose_unique(matched)
    return inferred, "lead-event" if inferred else kind

def extract_location(title, summary=""):
    return locate(title, summary)[0]

def enrich(rows, previous=()):
    """Keep valid Gemini analysis; refresh stale rules after algorithm upgrades."""
    cache = {str(r.get("id")): r for r in previous if isinstance(r, dict)}
    result = []
    for raw in rows:
        item = normalize_article(raw)
        if item is None:
            continue
        old = cache.get(item["id"])
        reused = bool(
            old and old.get("content_hash") == item["content_hash"]
            and old.get("category") in CATEGORIES
            and (old.get("analysis_status") == "gemini"
                 or old.get("rule_version") == RULE_VERSION)
        )
        if reused:
            category = old["category"]
            location = str(old.get("location") or "")
            summary = str(old.get("summary") or "")
            status = old.get("analysis_status") or "rule-based"
            location_source = old.get("location_source") or "cached"
        else:
            category = classify(item["title"], item["summary"])
            location, location_source = locate(item["title"], item["summary"])
            summary = " ".join(item["summary"].split())[:350]
            if not summary:
                summary = "원문 요약이 제공되지 않았습니다."
            status = "rule-based"
        result.append({
            "id": item["id"], "title": item["title"], "category": category,
            "location": location, "summary": summary, "url": item["url"],
            "datetime": item["datetime"], "source": item["source"],
            "publisher": str(item.get("publisher") or ""),
            "content_hash": item["content_hash"], "analysis_status": status,
            "rule_version": RULE_VERSION, "location_source": location_source,
        })
    return result
