"""Pure data contract and validation; no Qt, network or database dependencies."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from urllib.parse import urlsplit

CATEGORIES = ("사고", "화재", "교통", "행사", "사회")
COLORS = {"사고": "#e0a03a", "화재": "#ef6473", "교통": "#4b9df5",
          "행사": "#35bb9a", "사회": "#a18af5"}
KST = timezone(timedelta(hours=9))


def text(value: object, default: str = "", limit: int = 10000) -> str:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else default


def safe_url(value: object) -> str:
    url = text(value, limit=4096)
    if any(ord(c) <= 32 for c in url) or "\\" in url:
        return ""
    try:
        parts = urlsplit(url)
        _ = parts.port
        if (parts.scheme not in ("https", "http") or not parts.hostname
                or parts.username is not None or parts.password is not None):
            return ""
        parts.hostname.encode("idna")
    except (ValueError, UnicodeError):
        return ""
    return url


def coordinate(value: object, bound: float) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) and -bound <= number <= bound else None
    except (ValueError, TypeError, OverflowError):
        return None


@dataclass(frozen=True)
class NewsItem:
    id: str
    title: str
    category: str
    location: str
    summary: str
    url: str
    published_at: datetime | None
    latitude: float | None = None
    longitude: float | None = None
    is_mock: bool = False
    coordinate_note: str = ""

    @property
    def has_coordinates(self) -> bool:
        return (coordinate(self.latitude, 90) is not None
                and coordinate(self.longitude, 180) is not None)

    @property
    def date_label(self) -> str:
        return (self.published_at.astimezone(KST).strftime("%Y.%m.%d %H:%M")
                if self.published_at else "작성 시각 미제공")

    @property
    def color(self) -> str:
        return COLORS.get(self.category, "#8b96a9")


@dataclass(frozen=True)
class NewsBatch:
    items: tuple[NewsItem, ...]
    warnings: tuple[str, ...] = ()
    source: str = "JSON"


def parse_news(payload: object, *, is_mock: bool = False,
               coordinates: dict | None = None, source: str = "JSON") -> NewsBatch:
    """PR #2 list-of-objects contract. Invalid rows are reported, never silently fatal."""
    if not isinstance(payload, list):
        raise ValueError("뉴스 JSON의 최상위 값은 배열이어야 합니다.")
    if len(payload) > 10000:
        raise ValueError("한 번에 최대 10,000개 기사까지 불러올 수 있습니다.")
    items, warnings, seen = [], [], set()
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            warnings.append(f"{index + 1}행: 객체가 아니므로 제외")
            continue
        raw_id = row.get("id")
        if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)) or not str(raw_id).strip():
            warnings.append(f"{index + 1}행: 유효한 id가 없어 제외")
            continue
        identifier = str(raw_id).strip()
        if len(identifier) > 256 or identifier in seen:
            warnings.append(f"{index + 1}행: 중복 또는 너무 긴 id 제외")
            continue
        seen.add(identifier)
        date = None
        date_text = text(row.get("datetime"), limit=100)
        if date_text:
            try:
                date = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
                date = date.replace(tzinfo=KST) if date.tzinfo is None else date.astimezone(KST)
            except (ValueError, OverflowError):
                date = None
                warnings.append(f"{identifier}: 작성 시각 형식 오류")
        category = text(row.get("category"), "미분류", 100)
        if category not in CATEGORIES:
            warnings.append(f"{identifier}: 알 수 없는 분류 '{category}'를 원문대로 표시")
        lat = coordinate(row.get("latitude"), 90)
        lon = coordinate(row.get("longitude"), 180)
        note = ""
        if is_mock and coordinates and identifier in coordinates and lat is None and lon is None:
            lat, lon = coordinates[identifier]
            lat, lon = coordinate(lat, 90), coordinate(lon, 180)
            note = "시연용 지역 대표 좌표 · 실제 사건 지점이 아닙니다"
        if lat is None or lon is None:
            lat = lon = None
            warnings.append(f"{identifier}: 좌표 없음 또는 오류 · 목록에서만 표시")
        url = safe_url(row.get("url"))
        if row.get("url") and not url:
            warnings.append(f"{identifier}: 유효하지 않은 원문 링크 비활성화")
        items.append(NewsItem(
            identifier, text(row.get("title"), "제목 미제공", 1000), category,
            text(row.get("location"), "지역 미제공", 500),
            text(row.get("summary"), "요약이 아직 제공되지 않았습니다."),
            url, date, lat, lon, is_mock, note))
    return NewsBatch(tuple(items), tuple(warnings), source)
