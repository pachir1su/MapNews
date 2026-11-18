import os
import re
import sys
import json
import time
import hashlib
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

# ---------- 설정 ----------
# 사용할 모델 (앞에서부터 차례로 시도해요)
MODEL_LIST = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
]

CATEGORIES = ["사고", "화재", "교통", "행사", "사회"]

DEFAULT_INPUT = "data_ai/dummy_news.json"   # 아무것도 안 정하면 더미 기사를 분석해요
DEMO_OUTPUT = "data_ai/results.json"        # 더미 분석 결과
REAL_OUTPUT = "data_ai/results_real.json"   # 실제(크롤러) 분석 결과

BATCH_SIZE = 5            # 한 번 요청에 보낼 기사 수
MAX_BODY_CHARS = 1500     # 기사 본문은 이 글자 수까지만 AI에게 보내요
KST = timezone(timedelta(hours=9))


# ---------- AI 연결 ----------
_client = None


def get_client():
    """처음 부를 때만 Gemini 연결을 만들어요."""
    global _client
    if _client is None:
        from dotenv import load_dotenv
        from google import genai
        load_dotenv()
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def ask_gemini(prompt):
    """모델을 바꿔 가며 시도해요. 성공하면 글을, 전부 실패하면 None을 돌려줘요."""
    for model_name in MODEL_LIST:
        for attempt in range(1, 3):
            try:
                print(f"  [{model_name}] {attempt}번째 시도...")
                response = get_client().models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={"response_mime_type": "application/json"},
                )
                return response.text
            except Exception as e:
                message = str(e)
                if "429" in message or "404" in message:
                    print(f"  [{model_name}] 쓸 수 없어요. 다음 모델로 넘어가요.")
                    break
                elif "503" in message and attempt < 2:
                    print("  서버가 바빠요. 5초 뒤 다시 해요...")
                    time.sleep(5)
                else:
                    print(f"  에러: {message[:150]}")
                    break
    return None


def clean_json_text(text):
    """AI 답변에 ```json 표시가 붙어 있으면 벗겨내요."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    return text.strip()


# ---------- 입력 기사 정리 ----------
def normalize_datetime(value):
    """날짜를 '2026-11-04 10:23' 모양(한국 시간)으로 바꿔요. 못 바꾸면 원래 글자를 그대로 둬요."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        dt = parsedate_to_datetime(text)        # RSS 날짜: Mon, 16 Nov 2026 10:23:00 +0900
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(text)   # 2026-11-04 10:23 또는 2026-11-04T10:23:00+09:00
        except ValueError:
            return text
    if dt.tzinfo is not None:
        dt = dt.astimezone(KST)
    return dt.strftime("%Y-%m-%d %H:%M")


def normalize_article(raw):
    """더미 파일이든 크롤러 파일이든 같은 모양(id, title, body, url, datetime, hint)으로 맞춰요."""
    if not isinstance(raw, dict):
        return None

    title = str(raw.get("title") or "").strip()
    if not title:
        return None

    url = str(raw.get("url") or raw.get("link") or "").strip()

    # id는 항상 '글자'로 통일해요. 없으면 url(또는 제목)로 만들어요.
    article_id = raw.get("id")
    if article_id is None or str(article_id).strip() == "":
        key = url or title
        article_id = "news-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]

    body = str(raw.get("body") or raw.get("summary") or raw.get("description") or "").strip()

    return {
        "id": str(article_id).strip(),
        "title": title,
        "body": body[:MAX_BODY_CHARS],
        "url": url,
        "datetime": normalize_datetime(raw.get("datetime") or raw.get("date")),
        "hint": str(raw.get("location") or raw.get("region") or "").strip(),
    }


# ---------- 결과 검사와 저장 ----------
def is_valid_result(item):
    """저장된 분석 결과가 쓸 만한지 확인해요. 이상하면 다시 분석해요."""
    return (
        isinstance(item, dict)
        and str(item.get("id") or "").strip() != ""
        and str(item.get("title") or "").strip() != ""
        and item.get("category") in CATEGORIES
        and isinstance(item.get("location"), str)
        and str(item.get("summary") or "").strip() != ""
    )


def load_existing(path, source):
    """이미 분석한 결과를 불러와요. 파일이 깨졌으면 덮어쓰지 않도록 멈춰요."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("최상위가 리스트가 아니에요")
    except (OSError, ValueError) as e:
        raise SystemExit(
            f"{path} 파일을 읽지 못했어요({e}).\n"
            f"덮어쓰지 않도록 멈출게요. 파일 이름을 바꿔 두고 다시 실행해 주세요."
        )

    results = []
    seen = set()
    for item in data:
        if not is_valid_result(item):
            continue
        item["id"] = str(item["id"]).strip()     # id 자료형 통일(글자)
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        item.setdefault("source", source)
        results.append(item)
    return results


def save_json_safely(path, data):
    """임시 파일에 먼저 쓰고, 성공하면 바꿔치기해요. 중간에 실패해도 기존 파일은 안전해요."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


# ---------- 프롬프트와 분석 ----------
def make_prompt(batch):
    articles_text = ""
    for news in batch:
        hint = news["hint"] or "없음"
        articles_text += (
            f"\n[기사 id={news['id']}]\n"
            f"제목: {news['title']}\n"
            f"본문: {news['body']}\n"
            f"크롤러가 찾은 지역(참고용, 틀릴 수 있음): {hint}\n"
        )

    return f"""
아래 뉴스 기사들을 각각 분석해서, JSON 리스트로만 답해줘. 다른 설명은 쓰지 마.

각 기사마다 이 항목을 넣어줘:
- id: 기사 id (입력 그대로, 글자로)
- location: 사건이 일어난 지역 (예: 충남 천안시 서북구, 시/군/구까지). 지역을 알 수 없으면 빈 글자("")
- category: 아래 5개 중 딱 1개
    · 사고: 사람이 다치거나 물건이 부서진 사건 (추돌, 추락, 안전사고 등)
    · 화재: 불이 난 사건
    · 교통: 정체, 통제, 공사 등 도로 상황 (사고 자체는 '사고')
    · 행사: 축제, 전시, 설명회 등 열리는 행사
    · 사회: 위 4개에 해당하지 않는 사회 소식
- summary: 2~3줄 핵심 요약

답변 형식 예시:
[{{"id": "news-1", "location": "...", "category": "...", "summary": "..."}}]

기사 목록:
{articles_text}
"""


def analyze_batch(batch, source):
    """기사 묶음을 분석해서 쓸 만한 결과 리스트를 돌려줘요. 실패한 기사는 빠져요."""
    answer = ask_gemini(make_prompt(batch))
    if answer is None:
        print("  AI 호출에 실패했어요.")
        return None

    try:
        analyzed = json.loads(clean_json_text(answer))
        if not isinstance(analyzed, list):
            raise ValueError("리스트가 아니에요")
    except ValueError:
        print("  AI 답변을 JSON으로 읽지 못했어요:", answer[:200])
        return []

    by_id = {news["id"]: news for news in batch}
    good = []
    for item in analyzed:
        if not isinstance(item, dict):
            continue
        original = by_id.get(str(item.get("id")).strip())
        if original is None:
            continue
        result = {
            "id": original["id"],
            "title": original["title"],                     # 원본 값 그대로
            "category": str(item.get("category") or "").strip(),
            "location": str(item.get("location") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
            "url": original["url"],                         # 원본 값 그대로
            "datetime": original["datetime"],               # 원본 값 그대로
            "source": source,
        }
        if is_valid_result(result):
            good.append(result)
        else:
            print(f"  이상한 결과라서 저장하지 않아요: id={original['id']}")
    return good


# ---------- 메인 ----------
def main():
    # 사용법: python data_ai/analyze_news.py [입력파일] [출력파일]
    input_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    is_demo = "dummy" in os.path.basename(input_path).lower()
    source = "demo" if is_demo else "real"
    output_path = sys.argv[2] if len(sys.argv) > 2 else (DEMO_OUTPUT if is_demo else REAL_OUTPUT)

    # 1. 기사 읽기
    with open(input_path, encoding="utf-8") as f:
        raw_list = json.load(f)

    articles = []
    seen_ids = set()
    for raw in raw_list:
        article = normalize_article(raw)
        if article is None or article["id"] in seen_ids:   # 제목이 없거나 id가 겹치면 제외
            continue
        seen_ids.add(article["id"])
        articles.append(article)

    # 2. 이미 분석한 결과 불러오기 (다시 안 부르려고)
    results = load_existing(output_path, source)
    done_ids = {item["id"] for item in results}
    todo = [a for a in articles if a["id"] not in done_ids]
    print(f"입력 {len(articles)}개 / 이미 분석 {len(done_ids)}개 / 이번에 분석 {len(todo)}개 ({source})\n")

    # 3. 5개씩 묶어서 분석하기
    failed = 0
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start:start + BATCH_SIZE]
        print(f"{start + 1}번째 ~ {start + len(batch)}번째 기사 분석 중...")
        good = analyze_batch(batch, source)
        if good is None:
            print("여기까지 저장하고 멈출게요.")
            failed += len(todo) - start
            break
        results.extend(good)
        failed += len(batch) - len(good)
        save_json_safely(output_path, results)       # 한 묶음마다 안전하게 저장
        print(f"  저장 완료 (누적 {len(results)}개)\n")

    save_json_safely(output_path, results)
    print(f"끝! 결과 {len(results)}개 -> {output_path} (실패·보류 {failed}개)")


if __name__ == "__main__":
    main()