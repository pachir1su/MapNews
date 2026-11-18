"""Deterministic, zero-API baseline for MapNews news enrichment.

Rule-based results are intentionally conservative: an unknown incident location
stays unknown. A reporter's "[서울=...]" dateline is not a verified event location.
"""
import re
from urllib.parse import urlsplit

from search import article_fingerprint, normalize_article

CATEGORIES = ("사고", "화재", "교통", "행사", "사회")
REGIONS = (
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
    "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원특별자치도",
    "충청남도", "충청북도", "전북특별자치도", "전라남도", "경상남도",
    "경상북도", "제주특별자치도", "서울", "부산", "대구", "인천",
    "광주", "대전", "울산", "세종", "경기", "강원", "충남",
    "충북", "전북", "전남", "경남", "경북", "제주",
)
REGION_RX = re.compile(
    r"(?<![가-힣])(" + "|".join(re.escape(x) for x in REGIONS) +
    r")(?:\s+([가-힣]{1,12}(?:시|군|구)))?"
    r"(?:\s+([가-힣]{1,12}(?:구|군)))?"
)
CITY_RX = re.compile(r"(?<![가-힣])([가-힣]{2,9}(?:시|군))(?=\s|[·,에서의]|$)")
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


def extract_location(title):
    """Only take clearly named locations in the headline, not the reporter's dateline."""
    match = REGION_RX.search(title)
    if match:
        return " ".join(x for x in match.groups() if x)
    match = CITY_RX.search(title)
    return match.group(1) if match else ""


def enrich(rows, previous=()):
    """Preserve a compatible cached result; reclassify changed article content."""
    cache = {str(r.get("id")): r for r in previous if isinstance(r, dict)}
    result = []
    for raw in rows:
        item = normalize_article(raw)
        if item is None:
            continue
        previous_item = cache.get(item["id"])
        if (previous_item and previous_item.get("content_hash") == item["content_hash"]
                and previous_item.get("category") in CATEGORIES):
            category = previous_item["category"]
            location = str(previous_item.get("location") or "")
            summary = str(previous_item.get("summary") or "")
            status = previous_item.get("analysis_status") or "rule-based"
        else:
            category = classify(item["title"], item["summary"])
            location = extract_location(item["title"])
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
        })
    return result
