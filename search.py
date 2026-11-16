
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
import html
import re
import json
import time


# ==========================================
# 1. SBS 사회 분야 RSS
# ==========================================

RSS_URLS = {
    "사회": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=03&plink=RSSREADER"
}

REQUEST_DELAY = 0.3


# ==========================================
# 2. 지역명 사전
# ==========================================

REGION_ALIASES = {

    "서울특별시": ["서울특별시", "서울시", "서울"],
    "부산광역시": ["부산광역시", "부산시", "부산"],
    "대구광역시": ["대구광역시", "대구시", "대구"],
    "인천광역시": ["인천광역시", "인천시", "인천"],
    "광주광역시": ["광주광역시", "광주시", "광주"],
    "대전광역시": ["대전광역시", "대전시", "대전"],
    "울산광역시": ["울산광역시", "울산시", "울산"],
    "세종특별자치시": ["세종특별자치시", "세종시", "세종"],
    "경기도": ["경기도", "경기"],
    "강원특별자치도": ["강원특별자치도", "강원도", "강원"],
    "충청북도": ["충청북도", "충북"],
    "충청남도": ["충청남도", "충남"],
    "전북특별자치도": ["전북특별자치도", "전라북도", "전북"],
    "전라남도": ["전라남도", "전남"],
    "경상북도": ["경상북도", "경북"],
    "경상남도": ["경상남도", "경남"],
    "제주특별자치도": ["제주특별자치도", "제주도", "제주"],

    # ======================================
    # 경기도 시
    # ======================================

    "경기도 성남시": ["성남시", "성남"],
    "경기도 수원시": ["수원시", "수원"],
    "경기도 용인시": ["용인시", "용인"],
    "경기도 고양시": ["고양시", "고양"],
    "경기도 부천시": ["부천시", "부천"],
    "경기도 안양시": ["안양시", "안양"],
    "경기도 화성시": ["화성시", "화성"],
    "경기도 평택시": ["평택시", "평택"],
    "경기도 의정부시": ["의정부시"],
    "경기도 남양주시": ["남양주시", "남양주"],
    "경기도 안산시": ["안산시", "안산"],
    "경기도 시흥시": ["시흥시", "시흥"],
    "경기도 김포시": ["김포시", "김포"],
    "경기도 파주시": ["파주시", "파주"],
    "경기도 광주시": ["경기도 광주시"],
    "경기도 하남시": ["하남시", "하남"],
    "경기도 오산시": ["오산시", "오산"],
    "경기도 이천시": ["이천시", "이천"],
    "경기도 구리시": ["구리시", "구리"],
    "경기도 광명시": ["광명시", "광명"],
    "경기도 군포시": ["군포시", "군포"],
    "경기도 양주시": ["양주시", "양주"],
    "경기도 안성시": ["안성시", "안성"],
    "경기도 포천시": ["포천시", "포천"],
    "경기도 의왕시": ["의왕시", "의왕"],
    "경기도 여주시": ["여주시", "여주"],
    "경기도 동두천시": ["동두천시", "동두천"],
    "경기도 과천시": ["과천시", "과천"],

    # ======================================
    # 서울특별시 구
    # ======================================

    "서울특별시 강남구": ["강남구"],
    "서울특별시 서초구": ["서초구"],
    "서울특별시 송파구": ["송파구"],
    "서울특별시 마포구": ["마포구"],
    "서울특별시 종로구": ["종로구"],
    "서울특별시 영등포구": ["영등포구"],
    "서울특별시 관악구": ["관악구"],
    "서울특별시 강서구": ["강서구"],
    "서울특별시 노원구": ["노원구"],

    # ======================================
    # 부산광역시 구
    # ======================================

    "부산광역시 해운대구": ["해운대구"],
    "부산광역시 수영구": ["수영구"],
    "부산광역시 사하구": ["사하구"],
    "부산광역시 연제구": ["연제구"],

    # ======================================
    # 강원특별자치도 시
    # ======================================

    "강원특별자치도 춘천시": ["춘천시", "춘천"],
    "강원특별자치도 강릉시": ["강릉시", "강릉"],
    "강원특별자치도 원주시": ["원주시", "원주"],
    "강원특별자치도 동해시": ["동해시", "동해"],
    "강원특별자치도 태백시": ["태백시", "태백"],
    "강원특별자치도 속초시": ["속초시", "속초"],
    "강원특별자치도 삼척시": ["삼척시", "삼척"],

    # ======================================
    # 충청북도 시
    # ======================================

    "충청북도 청주시": ["청주시", "청주"],
    "충청북도 충주시": ["충주시", "충주"],
    "충청북도 제천시": ["제천시", "제천"],

    # ======================================
    # 충청남도 시
    # ======================================

    "충청남도 천안시": ["천안시", "천안"],
    "충청남도 아산시": ["아산시", "아산"],
    "충청남도 공주시": ["공주시", "공주"],
    "충청남도 보령시": ["보령시", "보령"],
    "충청남도 서산시": ["서산시", "서산"],
    "충청남도 논산시": ["논산시", "논산"],
    "충청남도 계룡시": ["계룡시", "계룡"],
    "충청남도 당진시": ["당진시", "당진"],

    # ======================================
    # 전북특별자치도 시
    # ======================================

    "전북특별자치도 전주시": ["전주시", "전주"],
    "전북특별자치도 군산시": ["군산시", "군산"],
    "전북특별자치도 익산시": ["익산시", "익산"],
    "전북특별자치도 정읍시": ["정읍시", "정읍"],
    "전북특별자치도 남원시": ["남원시", "남원"],
    "전북특별자치도 김제시": ["김제시", "김제"],

    # ======================================
    # 전라남도 시
    # ======================================

    "전라남도 여수시": ["여수시", "여수"],
    "전라남도 순천시": ["순천시", "순천"],
    "전라남도 목포시": ["목포시", "목포"],
    "전라남도 나주시": ["나주시", "나주"],
    "전라남도 광양시": ["광양시", "광양"],

    # ======================================
    # 경상북도 시
    # ======================================

    "경상북도 포항시": ["포항시", "포항"],
    "경상북도 경주시": ["경주시", "경주"],
    "경상북도 김천시": ["김천시", "김천"],
    "경상북도 안동시": ["안동시", "안동"],
    "경상북도 구미시": ["구미시", "구미"],
    "경상북도 영주시": ["영주시", "영주"],
    "경상북도 영천시": ["영천시", "영천"],
    "경상북도 상주시": ["상주시", "상주"],
    "경상북도 문경시": ["문경시", "문경"],
    "경상북도 경산시": ["경산시", "경산"],

    # ======================================
    # 경상남도 시
    # ======================================

    "경상남도 창원시": ["창원시", "창원"],
    "경상남도 김해시": ["김해시", "김해"],
    "경상남도 진주시": ["진주시", "진주"],
    "경상남도 통영시": ["통영시", "통영"],
    "경상남도 사천시": ["사천시", "사천"],
    "경상남도 밀양시": ["밀양시", "밀양"],
    "경상남도 거제시": ["거제시", "거제"],
    "경상남도 양산시": ["양산시", "양산"],

    # ======================================
    # 제주특별자치도
    # ======================================

    "제주특별자치도 제주시": ["제주시", "제주"],
    "제주특별자치도 서귀포시": ["서귀포시", "서귀포"],

}


# ==========================================
# 3. HTML 본문 추출기
# ==========================================

class ArticleParser(HTMLParser):

    BLOCK_TAGS = {
        "script", "style", "nav", "footer",
        "header", "aside", "form", "noscript"
    }

    TARGET_PATTERN = re.compile(
        r"(article.*(body|cont|content|text|txt|view)"
        r"|news.*(body|cont|content|text|txt|view)"
        r"|text_area|view_cont|view_text"
        r"|article_body|article_content|article_cont"
        r"|article_text|article_txt|article_view"
        r"|news_body|news_content|news_cont)",
        re.IGNORECASE
    )

    def __init__(self):
        super().__init__()
        self.text = []
        self.stack = []
        self.capture_depth = 0
        self.block_depth = 0

    def handle_starttag(self, tag, attrs):

        attributes = dict(attrs)

        class_name = attributes.get("class", "")
        element_id = attributes.get("id", "")

        parent_blocked = self.block_depth > 0
        is_block = tag in self.BLOCK_TAGS

        identifier = class_name + " " + element_id

        is_target = (
            tag == "article"
            or (
                not parent_blocked
                and self.TARGET_PATTERN.search(identifier)
            )
        )

        if is_block:
            self.block_depth += 1

        if is_target and not parent_blocked and not is_block:
            self.capture_depth += 1

        self.stack.append({
            "tag": tag,
            "block": is_block,
            "capture": (
                is_target and not parent_blocked and not is_block
            )
        })

    def handle_endtag(self, tag):

        for i in range(len(self.stack) - 1, -1, -1):

            if self.stack[i]["tag"] == tag:

                removed = self.stack[i:]

                for item in removed:

                    if item["block"]:
                        self.block_depth = max(
                            0, self.block_depth - 1
                        )

                    if item["capture"]:
                        self.capture_depth = max(
                            0, self.capture_depth - 1
                        )

                self.stack = self.stack[:i]
                break

    def handle_data(self, data):

        if self.capture_depth > 0 and self.block_depth == 0:

            cleaned = data.strip()

            if cleaned:
                self.text.append(cleaned)

    def get_text(self):

        return " ".join(self.text)


# ==========================================
# 4. HTML에서 불필요한 태그 제거
# ==========================================

class SimpleTextParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):

        cleaned = data.strip()

        if cleaned:
            self.text.append(cleaned)

    def get_text(self):

        return " ".join(self.text)


def clean_html_text(text):

    parser = SimpleTextParser()

    parser.feed(html.unescape(text))

    return parser.get_text()


# ==========================================
# 5. 인터넷 데이터 가져오기
# ==========================================

def fetch_url(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=15
    ) as response:

        return response.read()


# ==========================================
# 6. RSS 분석
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
        description = fields.get(
            "description", ""
        ).strip()

        pub_date = fields.get("pubDate", "").strip()

        if not title or not link:
            continue

        articles.append({
            "title": title,
            "link": link,
            "description": description,
            "date": pub_date
        })

    return articles


# ==========================================
# 7. 기사 본문 가져오기
# ==========================================

def fetch_article_text(url, description):

    try:

        data = fetch_url(url)

        parser = ArticleParser()

        parser.feed(
            data.decode("utf-8", errors="replace")
        )

        body = parser.get_text()

        if body:
            return body

        # 본문 영역을 찾지 못한 경우
        # 페이지 전체 대신 RSS 설명 사용
        return clean_html_text(description)

    except Exception:
        return clean_html_text(description)


# ==========================================
# 8. 지역명 언급 횟수 계산
# ==========================================

def count_regions(text):

    matches = []

    for region, aliases in REGION_ALIASES.items():

        for alias in aliases:

            for match in re.finditer(
                re.escape(alias),
                text
            ):

                matches.append({
                    "region": region,
                    "alias": alias,
                    "start": match.start(),
                    "end": match.end()
                })

    # 같은 위치에서 겹치는 별칭은 긴 이름을 우선
    matches.sort(
        key=lambda x: (
            x["start"],
            -(x["end"] - x["start"])
        )
    )

    counts = {}
    occupied_until = -1

    for match in matches:

        if match["start"] < occupied_until:
            continue

        region = match["region"]

        counts[region] = counts.get(region, 0) + 1

        occupied_until = match["end"]

    return counts


# ==========================================
# 9. 가장 많이 언급된 지역 분석
# ==========================================

def analyze_by_rules(text):

    counts = count_regions(text)

    if not counts:
        return {
            "region": None,
            "confidence": "판단 불가",
            "reason": "지역명을 찾지 못함",
            "candidates": []
        }

    ranked = sorted(
        counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    best_region, best_count = ranked[0]

    # 가장 많이 언급된 지역이 공동 1위라면 제외
# 1위와 차순위의 언급 횟수 차이가 3회 미만이면 제외
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < 3:
        return {
            "region": None,
            "confidence": "판단 불가",
            "reason": "1위와 차순위 지역의 언급 횟수 차이가 3회 미만",
            "candidates": []
        }

    if best_count >= 5:
        confidence = "높음"

    elif best_count >= 3:
        confidence = "보통"

    else:
        confidence = "낮음"

    candidates = []

    for region, count in ranked:
        candidates.append({
            "region": region,
            "count": count
        })

    return {
        "region": best_region,
        "confidence": confidence,
        "reason": str(best_count) + "회 언급",
        "candidates": candidates
    }


# ==========================================
# 10. 사회 뉴스 수집
# ==========================================

def collect_all_news():

    all_articles = []

    seen_links = set()

    for category, rss_url in RSS_URLS.items():

        print(f"\n[{category} 뉴스] RSS 수집 중...")

        try:

            rss_data = fetch_url(rss_url)

            articles = parse_rss(rss_data)

        except Exception:
            continue

        for article in articles:

            if article["link"] in seen_links:
                continue

            seen_links.add(article["link"])

            body = fetch_article_text(
                article["link"],
                article["description"]
            )

            # 기사 제목과 본문만 분석
            analysis_text = (
                article["title"] + " " + body
            )

            analysis = analyze_by_rules(
                analysis_text
            )

            result = {
                "title": article["title"],
                "category": category,
                "date": article["date"],
                "region": analysis["region"],
                "confidence": analysis["confidence"],
                "reason": analysis["reason"],
                "link": article["link"],
                "body": body,
                "candidates": analysis["candidates"]
            }

            all_articles.append(result)

            time.sleep(REQUEST_DELAY)

    return all_articles


# ==========================================
# 11. 결과 출력 및 저장
# ==========================================

def main():

    results = collect_all_news()

    output_count = 0

    print("\n" + "=" * 50)
    print("수집 결과")
    print("=" * 50)

    for article in results:

        if article["region"] is None:
            continue

        output_count += 1

        print("\n기사 제목:", article["title"])
        print("분야:", article["category"])
        print("발행일:", article["date"])
        print("지역:", article["region"])
        print("신뢰도:", article["confidence"])
        print("이유:", article["reason"])
        print("링크:", article["link"])

    with open("news_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print("\n" + "=" * 50)
    print("수집 완료")
    print("확인한 기사 수:", len(results), "개")
    print("출력된 기사 수:", output_count, "개")
    print("제외된 기사 수:", len(results) - output_count, "개")
    print("JSON 저장 완료: news_results.json")
    print("=" * 50)


if __name__ == "__main__":
    main()
