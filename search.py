
import urllib.request
import xml.etree.ElementTree as ET
import json
import re
import html
import hashlib
import os
import tempfile
import argparse
import sys
from pathlib import Path

from html.parser import HTMLParser
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime


# ==========================================
# 1. RSS 주소 설정
# ==========================================

RSS_FEEDS = {
    # "뉴시스_사회": "https://www.newsis.com/RSS/society.xml",
    # "뉴시스_속보": "https://www.newsis.com/RSS/sokbo.xml",
    "뉴시스_지방": "https://www.newsis.com/RSS/country.xml",
    #"조선일보": "https://www.chosun.com/arc/outboundfeeds/rss/category/national/?outputType=xml"
}

OUTPUT_FILE = "news_results.json"

KST = timezone(timedelta(hours=9))


# ==========================================
# 2. HTML 태그 제거
# ==========================================

class TextParser(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts = []
        self.skip_tags = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip_tags += 1

        if tag in ("p", "div", "br", "li"):
            self.text_parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip_tags > 0:
            self.skip_tags -= 1

        if tag in ("p", "div", "li"):
            self.text_parts.append("\n")

    def handle_data(self, data):
        if self.skip_tags == 0:
            self.text_parts.append(data)


def clean_html_text(text):
    if not text:
        return ""

    parser = TextParser()
    parser.feed(html.unescape(text))

    result = "".join(parser.text_parts)

    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r"\n\s*\n+", "\n", result)

    return result.strip()


# ==========================================
# 3. 날짜 형식 통일
# ==========================================

def format_date(date_text):

    if not date_text:
        return ""

    try:
        date = parsedate_to_datetime(date_text)

        if date.tzinfo is None:
            date = date.replace(tzinfo=KST)

        date = date.astimezone(KST)

        return date.strftime("%Y-%m-%d %H:%M")

    except Exception:
        try:
            date = datetime.fromisoformat(date_text)

            if date.tzinfo is None:
                date = date.replace(tzinfo=KST)

            return date.astimezone(KST).strftime("%Y-%m-%d %H:%M")

        except Exception:
            return date_text


# ==========================================
# 4. 인터넷에서 데이터 가져오기
# ==========================================

def fetch_url(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ValueError("RSS 응답이 2 MiB를 초과했습니다.")
        return data


# ==========================================
# 5. RSS 데이터 분석
# ==========================================

def parse_rss(data):
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("DTD/ENTITY가 포함된 RSS는 처리하지 않습니다.")
    root = ET.fromstring(data)

    articles = []

    for item in root.iter():

        if item.tag.split("}")[-1] != "item":
            continue

        fields = {}

        for child in item:

            tag = child.tag.split("}")[-1]

            fields[tag] = child.text or ""

        title = fields.get("title", "").strip()
        link = fields.get("link", "").strip()

        description = fields.get("description", "").strip()

        if not description:
            description = fields.get("encoded", "").strip()

        pub_date = fields.get("pubDate", "").strip()
        writer = fields.get("creator", "").strip()

        if title and link:

            articles.append({
                "title": clean_html_text(title),
                "link": link,
                "description": clean_html_text(description),
                "date": pub_date,
                "writer": clean_html_text(writer)
            })

    return articles

def is_korean_article(title, content):
    text = title + " " + content

    korean_count = sum(
        1 for char in text
        if '가' <= char <= '힣'
        or 'ㄱ' <= char <= 'ㅎ'
        or 'ㅏ' <= char <= 'ㅣ'
    )

    alphabet_count = sum(1 for char in text if char.isalpha())

    if alphabet_count == 0:
        return False

    return korean_count / alphabet_count >= 0.3

# ==========================================
# 6. 조선일보 본문 추출
# ==========================================

def fetch_chosun_article(url):

    try:
        page = fetch_url(url).decode(
            "utf-8",
            errors="replace"
        )

        match = re.search(
            r"Fusion\.globalContent\s*=",
            page
        )

        if not match:
            return ""

        json_start = page.find("{", match.end())

        if json_start == -1:
            return ""

        decoder = json.JSONDecoder()

        data, _ = decoder.raw_decode(page[json_start:])

        content_elements = data.get("content_elements", [])

        paragraphs = []

        for element in content_elements:

            if element.get("type") == "text":

                content = element.get("content", "").strip()

                if content:
                    paragraphs.append(clean_html_text(content))

        return "\n".join(paragraphs)

    except Exception as e:
        print(f"조선일보 본문 추출 오류: {e}")
        return ""


# ==========================================
# 7. 언론사별 기사 본문 가져오기
# ==========================================

def fetch_article_text(article, source):

    # 뉴시스는 RSS description 사용
    if source.startswith("뉴시스"):
        return article["description"]

    # 조선일보는 원본 HTML에서 본문 추출
    if source == "조선일보":

        content = fetch_chosun_article(article["link"])

        if content:
            return content

        # 원본 본문 추출 실패 시 RSS 내용 사용
        return article["description"]

    return article["description"]


# ==========================================
# 8. Stable identity and safe archive storage
# ==========================================

MAX_ARCHIVE_ARTICLES = 10000
MAX_FEED_ITEMS = 1000
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid"}


def canonical_url(url):
    """Keep significant query keys; discard common tracking keys and fragments."""
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    try:
        parts = urlsplit(str(url).strip())
        if (parts.scheme.lower() not in ("https", "http") or not parts.hostname
                or parts.username or parts.password):
            return ""
        host = parts.hostname.lower()
        port = parts.port
        if port and (parts.scheme.lower(), port) not in {("https", 443), ("http", 80)}:
            host += ":" + str(port)
        query = urlencode(sorted((k, v) for k, v in parse_qsl(
            parts.query, keep_blank_values=True
        ) if not k.lower().startswith("utm_") and k.lower() not in TRACKING_KEYS))
        return urlunsplit((parts.scheme.lower(), host, parts.path or "/", query, ""))
    except (TypeError, ValueError):
        return ""


def make_article_id(url):
    return "news-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def article_fingerprint(title, summary):
    normalized = (str(title).strip() + "\n" + str(summary).strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_article(row):
    if not isinstance(row, dict):
        return None
    url = canonical_url(row.get("url") or row.get("link"))
    title = str(row.get("title") or "").strip()
    if not url or not title:
        return None
    summary = str(row.get("summary") or row.get("body") or row.get("description") or "").strip()
    item = dict(row)
    item.update({
        "id": make_article_id(url),
        "title": title,
        "url": url,
        "summary": summary,
        "datetime": str(row.get("datetime") or row.get("date") or "").strip(),
        "content_hash": article_fingerprint(title, summary),
        "source": "demo" if urlsplit(url).hostname == "example.com" else "real",
    })
    return item


def load_archive(path=OUTPUT_FILE):
    path = Path(path)
    if not path.exists():
        return []
    with path.open("rb") as stream:
        content = stream.read(32 * 1024 * 1024 + 1)
    if len(content) > 32 * 1024 * 1024:
        raise ValueError("기사 저장 파일이 32 MiB를 초과했습니다.")
    data = json.loads(content.decode("utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("기존 뉴스 저장 파일은 JSON 배열이어야 합니다.")
    deduplicated = {}
    for row in data:
        entry = normalize_article(row)
        if entry is not None:
            deduplicated[entry["id"]] = entry
    if data and not deduplicated:
        raise ValueError("기존 뉴스 파일에서 유효한 기사를 찾지 못했습니다.")
    return list(deduplicated.values())


def save_json(news_list, path=OUTPUT_FILE):
    """Atomic replacement: neither empty input nor interrupted writes destroy the archive."""
    if not news_list:
        raise ValueError("기사 0건인 결과로 기존 저장 파일을 덮어쓰지 않습니다.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".mapnews-", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(news_list, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


# ==========================================
# 9. RSS candidate retrieval
# ==========================================

def collect_all_news():
    news_by_id = {}
    checked_count = 0
    successes = 0
    failures = []
    now = datetime.now(KST).isoformat(timespec="seconds")

    for source, rss_url in RSS_FEEDS.items():
        try:
            articles = parse_rss(fetch_url(rss_url))
            successes += 1
            checked_count += len(articles)
            for article in articles[:MAX_FEED_ITEMS]:
                title = article["title"].strip()
                summary = fetch_article_text(article, source)
                if not is_korean_article(title, summary):
                    continue
                item = normalize_article({
                    "title": title, "summary": summary,
                    "url": article["link"], "datetime": format_date(article["date"]),
                    "publisher": source, "fetched_at": now,
                })
                if item:
                    news_by_id[item["id"]] = item
        except (OSError, ValueError, ET.ParseError) as exc:
            failures.append(f"{source}: {type(exc).__name__}: {exc}")
            print("수집 오류:", failures[-1], file=sys.stderr)

    if not successes or not news_by_id:
        raise RuntimeError("새 뉴스 수집 결과가 0건입니다. 이전 파일은 그대로 유지합니다.")
    if failures:
        print(f"일부 RSS 오류 {len(failures)}건. 정상 공급원 기사는 보존합니다.", file=sys.stderr)
    return list(news_by_id.values()), checked_count


def merge_archive(old, incoming, *, maximum=MAX_ARCHIVE_ARTICLES):
    if not incoming:
        raise ValueError("빈 수집 결과는 기존 데이터를 갱신하지 않습니다.")
    merged = {item["id"]: item for item in (normalize_article(x) for x in old) if item}
    added = updated = unchanged = 0
    for raw in incoming:
        item = normalize_article(raw)
        if not item:
            continue
        previous = merged.get(item["id"])
        if previous is None:
            added += 1
            merged[item["id"]] = item
        elif previous["content_hash"] != item["content_hash"]:
            updated += 1
            merged[item["id"]] = item
        else:
            unchanged += 1
            merged[item["id"]] = dict(previous, fetched_at=item.get("fetched_at", previous.get("fetched_at")))
    result = sorted(merged.values(), key=lambda x: (x.get("datetime") or "", x["id"]), reverse=True)
    if maximum < 1:
        raise ValueError("최대 보관 건수는 1 이상이어야 합니다.")
    return result[:maximum], {"new": added, "updated": updated, "unchanged": unchanged}


def main(argv=None):
    parser = argparse.ArgumentParser(description="MapNews RSS 안전 수집")
    parser.add_argument("--output", default=OUTPUT_FILE)
    args = parser.parse_args(argv)
    incoming, checked = collect_all_news()
    old = load_archive(args.output)
    archive, stats = merge_archive(old, incoming)
    save_json(archive, args.output)
    print(f"RSS 확인 {checked}건 / 신규 {stats['new']}건 / 갱신 {stats['updated']}건 / "
          f"재사용 {stats['unchanged']}건 / 보관 {len(archive)}건")
    return 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(errors="backslashreplace")
            except (OSError, ValueError):
                pass
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"뉴스 수집 실패: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
