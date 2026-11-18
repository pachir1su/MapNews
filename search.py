
import urllib.request
import xml.etree.ElementTree as ET
import json
import re
import html
import hashlib
import random

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
        return response.read()


# ==========================================
# 5. RSS 데이터 분석
# ==========================================

def parse_rss(data):

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
# 8. 기사 ID 생성
# ==========================================

def make_article_id(url):

    return hashlib.sha1(
        url.encode("utf-8")
    ).hexdigest()[:12]


# ==========================================
# 9. 전체 뉴스 수집
# ==========================================

def collect_all_news():

    news_list = []
    checked_count = 0
    seen_links = set()
    seen_titles = set()

    for source, rss_url in RSS_FEEDS.items():

        print(f"\n[{source}] RSS 수집 시작")

        try:
            rss_data = fetch_url(rss_url)

            articles = parse_rss(rss_data)

            checked_count += len(articles)

            print(f"확인한 기사: {len(articles)}개")

            for article in articles:

                link = article["link"]
                title = article["title"].strip()

                # 기사 본문 가져오기
                summary = fetch_article_text(article, source)

                # 한국어 기사인지 확인
                if not is_korean_article(title, summary):
                    continue

                # URL 및 제목 기준 중복 제거
                if link in seen_links or title in seen_titles:
                    continue

                seen_links.add(link)
                seen_titles.add(title)

                article_id = len(news_list) + 1

                news = {
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "datetime": format_date(article["date"]),
                }

                news_list.append(news)
                news_list = random.sample(news_list, min(30, len(news_list)))


        except Exception as e:
            print(f"{source} 수집 오류: {e}")

    return news_list, checked_count


# ==========================================
# 10. JSON 파일 저장
# ==========================================

def save_json(news_list):

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:

        json.dump(
            news_list,
            file,
            ensure_ascii=False,
            indent=4
        )

    print(f"\nJSON 저장 완료: {OUTPUT_FILE}")


# ==========================================
# 11. 프로그램 실행
# ==========================================

def main():

    print("뉴스 수집을 시작합니다.")

    news_list, checked_count = collect_all_news()

    save_json(news_list)

    print("\n========== 수집 결과 ==========")
    print(f"확인한 전체 기사 수: {checked_count}개")
    print(f"중복 제거 후 수집 기사 수: {len(news_list)}개")
    print("================================")


if __name__ == "__main__":
    main()
