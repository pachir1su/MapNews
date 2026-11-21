import os
import re
import sys
import json
import time
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pipeline_transaction import output_lock
from data_ai.task_queue import (read_queue, rebuild_queue, select_ready,
                                mark_batch, write_queue)

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

def _env_limit(name, default, low, high):
    try:
        value = int(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        raise ValueError(f"{name}은 정수여야 합니다.") from None
    if not low <= value <= high:
        raise ValueError(f"{name}은 {low}~{high} 범위여야 합니다.")
    return value

MAX_AI_ARTICLES_PER_RUN = _env_limit("MAPNEWS_MAX_AI_ARTICLES", 30, 0, 1000)
MAX_AI_REQUESTS_PER_RUN = _env_limit("MAPNEWS_MAX_AI_REQUESTS", 12, 1, 60)
_api_attempts = 0
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
    """Bound all requests. Quota/auth failures never cause fallback storms."""
    global _api_attempts
    for model_name in MODEL_LIST:
        for attempt in range(1, 3):
            if _api_attempts >= MAX_AI_REQUESTS_PER_RUN:
                print("Gemini 요청 예산 소진: 남은 기사는 다음 실행으로 보류합니다.")
                return None
            try:
                _api_attempts += 1
                response = get_client().models.generate_content(
                    model=model_name, contents=prompt,
                    config={"response_mime_type": "application/json"},
                )
                value = getattr(response, "text", None)
                return value if isinstance(value, str) and value.strip() else None
            except Exception as exc:
                # Do not log the full request/credential-bearing exception.
                code = str(getattr(exc, "code", getattr(exc, "status_code", "")) or "")
                if not code:
                    message = str(exc)
                    code = next((c for c in ("401", "403", "404", "429", "502", "503", "504")
                                 if c in message), "")
                print(f"Gemini {type(exc).__name__} (status={code or 'unknown'})")
                if code in {"401", "403", "429"}:
                    return None
                if code == "404":
                    break  # Only genuinely missing models may fall back.
                if code in {"502", "503", "504"} and attempt < 2:
                    time.sleep(2)
                    continue
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
        "content_hash": str(raw.get("content_hash") or hashlib.sha256(
            (title + "\n" + str(raw.get("body") or raw.get("summary") or "")).encode("utf-8")
        ).hexdigest()),
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
    """Unique temporary JSON + fsync + rename, with cleanup on every failure."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=destination.parent,
                prefix=".mapnews-ai-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

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
            "source": ("demo" if original["url"].startswith("https://example.com/")
                       else source),
            "content_hash": original["content_hash"],
            "analysis_status": "gemini",
        }
        if is_valid_result(result):
            good.append(result)
        else:
            print(f"  이상한 결과라서 저장하지 않아요: id={original['id']}")
    return good


# ---------- 메인 ----------
def _read_input(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(32 * 1024 * 1024 + 1)
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("Gemini 입력 파일은 32 MiB 이하여야 합니다.")
    result = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(result, list) or len(result) > 10000:
        raise ValueError("Gemini 입력은 최대 10,000건 JSON 배열이어야 합니다.")
    return result


def _run_analysis(input_path, output_path, queue_path, source):
    global _api_attempts
    _api_attempts = 0
    raw_list = _read_input(input_path)
    articles, seen_ids = [], set()
    for raw in raw_list:
        article = normalize_article(raw)
        if article is None or article["id"] in seen_ids:
            continue
        seen_ids.add(article["id"])
        articles.append(article)
    if not articles:
        raise ValueError("AI 입력에 유효한 기사가 0건입니다. 기존 결과를 보존합니다.")

    # Saved AI results are the only durable completion authority; after a
    # crash, a stale queue alone never marks an article as completed.
    results = load_existing(output_path, source)
    input_hashes = {a["id"]: a["content_hash"] for a in articles}
    results = [r for r in results if (r["id"] not in input_hashes
               or r.get("content_hash") == input_hashes[r["id"]])]
    queue = rebuild_queue(articles, results, read_queue(queue_path))
    write_queue(queue_path, queue)
    ready = select_ready(queue, MAX_AI_ARTICLES_PER_RUN)
    article_lookup = {a["id"]: a for a in articles}
    todo = [article_lookup[r["id"]] for r in ready]
    done_count = sum(r["status"] == "completed" for r in queue)
    wait_count = sum(r["status"] in {"retry_wait", "failed"} for r in queue)
    print(f"입력 {len(articles)}개 / 완료 {done_count}개 / AI 대상 {len(todo)}개 "
          f"/ 재시도대기·종료 {wait_count}개")

    failures = 0
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start:start + BATCH_SIZE]
        good = analyze_batch(batch, source)
        if good is None:
            failures += len(batch)
            mark_batch(queue, failed=[a["id"] for a in batch],
                       reason="Gemini API 일시 불가/호출 한도")
            write_queue(queue_path, queue)
            break
        good_ids = {r["id"] for r in good}
        results.extend(good)
        # Persist result before queue completion: on crash, the next rebuild
        # derives completion from the result's (id, content_hash) pair.
        save_json_safely(output_path, results)
        missing = [a["id"] for a in batch if a["id"] not in good_ids]
        failures += len(missing)
        mark_batch(queue, completed=good_ids, failed=missing,
                   reason="AI 응답 JSON/기사 ID/분류 검증 실패")
        write_queue(queue_path, queue)

    if not Path(output_path).exists():
        save_json_safely(output_path, results)
    remaining = sum(r["status"] in {"pending", "retry_wait"} for r in queue)
    print(f"AI 결과 {len(results)}개 / 대기 {remaining}개 / 이번 실패 {failures}개")
    if failures:
        raise SystemExit(3)


def main():
    # python data_ai/analyze_news.py [입력] [결과] [파생 큐]
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_INPUT)
    is_demo = "dummy" in input_path.name.lower()
    source = "demo" if is_demo else "real"
    output_path = Path(sys.argv[2] if len(sys.argv) > 2
                       else (DEMO_OUTPUT if is_demo else REAL_OUTPUT))
    queue_path = Path(sys.argv[3]) if len(sys.argv) > 3 else (
        output_path.with_name("ai_queue.json") if output_path.name == "results_ai.json"
        else output_path.with_name(output_path.stem + ".queue.json")
    )
    if len({p.resolve() for p in (input_path, output_path, queue_path)}) != 3:
        raise ValueError("입력·분석 결과·작업 큐는 서로 다른 파일이어야 합니다.")
    with output_lock(queue_path):
        return _run_analysis(input_path, output_path, queue_path, source)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Gemini 분석 중단(기존 결과 보존): {type(exc).__name__}: {exc}",
              file=sys.stderr)
        raise SystemExit(1) from exc