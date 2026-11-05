import os
import json
import time
from dotenv import load_dotenv
from google import genai

# ---------- 준비 ----------
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 사용할 모델 (성공했던 모델을 맨 위에 두세요)
MODEL_LIST = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
]

INPUT_FILE = "data_ai/dummy_news.json"      # 분석할 기사 (지금은 더미)
OUTPUT_FILE = "data_ai/results.json"        # 분석 결과 저장 파일
BATCH_SIZE = 5                              # 한 번 요청에 보낼 기사 수


# ---------- AI에게 물어보는 함수 ----------
def ask_gemini(prompt):
    """모델을 바꿔 가며 시도해요. 성공하면 글을, 전부 실패하면 None을 돌려줘요."""
    for model_name in MODEL_LIST:
        for attempt in range(1, 3):
            try:
                print(f"  [{model_name}] {attempt}번째 시도...")
                response = client.models.generate_content(
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
        text = text.split("\n", 1)[1]        # 첫 줄(```json) 제거
        text = text.rsplit("```", 1)[0]      # 마지막 ``` 제거
    return text.strip()


# ---------- 프롬프트 만들기 ----------
def make_prompt(batch):
    articles_text = ""
    for news in batch:
        articles_text += f"\n[기사 id={news['id']}]\n제목: {news['title']}\n본문: {news['summary']}\n"

    return f"""
아래 뉴스 기사들을 각각 분석해서, JSON 리스트로만 답해줘. 다른 설명은 쓰지 마.

각 기사마다 이 항목을 넣어줘:
- id: 기사 id (입력 그대로)
- location: 사건이 일어난 지역 (예: 충남 천안시 서북구, 시/군/구까지)
- category: 아래 5개 중 딱 1개
    · 사고: 사람이 다치거나 물건이 부서진 사건 (추돌, 추락, 안전사고 등)
    · 화재: 불이 난 사건
    · 교통: 정체, 통제, 공사 등 도로 상황 (사고 자체는 '사고')
    · 행사: 축제, 전시, 설명회 등 열리는 행사
    · 사회: 위 4개에 해당하지 않는 사회 소식
- summary: 2~3줄 핵심 요약

답변 형식 예시:
[{{"id": 1, "location": "...", "category": "...", "summary": "..."}}]

기사 목록:
{articles_text}
"""


# ---------- 메인 ----------
def main():
    # 1. 기사 읽기
    with open(INPUT_FILE, encoding="utf-8") as f:
        news_list = json.load(f)

    # 2. 이미 분석한 결과가 있으면 불러오기 (다시 안 부르려고)
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            results = json.load(f)
    else:
        results = []

    done_ids = {item["id"] for item in results}
    todo = [news for news in news_list if news["id"] not in done_ids]
    print(f"전체 {len(news_list)}개 중 {len(todo)}개를 분석해요.\n")

    # 3. 5개씩 묶어서 분석하기
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start:start + BATCH_SIZE]
        print(f"기사 {batch[0]['id']}번 ~ {batch[-1]['id']}번 분석 중...")

        answer = ask_gemini(make_prompt(batch))
        if answer is None:
            print("AI 호출에 실패했어요. 여기까지 저장하고 멈출게요.")
            break

        try:
            analyzed = json.loads(clean_json_text(answer))
        except json.JSONDecodeError:
            print("AI 답변을 JSON으로 읽지 못했어요. 여기까지 저장하고 멈출게요.")
            print(answer[:300])
            break

        # 4. 원래 기사 정보(title, url, datetime)와 합치기
        news_by_id = {news["id"]: news for news in batch}
        for item in analyzed:
            original = news_by_id.get(item["id"])
            if original is None:
                continue
            results.append({
                "id": item["id"],
                "title": original["title"],
                "category": item["category"],
                "location": item["location"],
                "summary": item["summary"],
                "url": original["url"],
                "datetime": original["datetime"],
            })

        # 5. 한 묶음 끝날 때마다 바로 저장 (중간에 멈춰도 안 날아가요)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"  저장 완료 (누적 {len(results)}개)\n")

    print(f"끝! 결과는 {OUTPUT_FILE}에 있어요.")


main()