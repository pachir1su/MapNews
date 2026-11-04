import os
import time
from dotenv import load_dotenv
from google import genai

# .env 파일에서 API 키 읽어오기
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

# 사용할 모델 목록 (앞에서부터 차례로 시도해요)
# list_models.py로 확인한 다른 모델 이름을 아래에 추가하세요. 따옴표와 쉼표 주의!
MODEL_LIST = [
    "gemini-3.8-flash",
    # "여기에-다른-모델-이름",
]

# 테스트용 가짜 기사
title = "천안 서북구 도로에서 차량 3중 추돌 사고"
body = "오늘 오전 충남 천안시 서북구 한 도로에서 차량 3대가 연쇄 추돌했다. 다친 사람은 없다."

# AI에게 시킬 말
prompt = f"""
아래 뉴스 기사를 읽고 JSON으로만 답해줘.
- location: 사건이 일어난 지역 (예: 충남 천안시 서북구)
- category: 사고, 화재, 교통, 행사, 사회 중 딱 1개
- summary: 2~3줄 요약

제목: {title}
본문: {body}
"""


def ask_gemini(prompt):
    """모델을 하나씩 바꿔 가며 성공할 때까지 시도해요. 성공하면 글을 돌려주고, 전부 실패하면 None."""
    for model_name in MODEL_LIST:
        for attempt in range(1, 4):  # 모델당 최대 3번
            try:
                print(f"[{model_name}] {attempt}번째 시도 중...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                message = str(e)
                if "429" in message:
                    print(f"[{model_name}] 오늘 사용 한도를 다 썼어요. 다음 모델로 넘어갈게요.")
                    break  # 이 모델은 포기하고 다음 모델로
                elif "503" in message:
                    print(f"[{model_name}] 서버가 바빠요.")
                    if attempt < 3:
                        print("10초 뒤 다시 시도해요...")
                        time.sleep(10)
                else:
                    print(f"[{model_name}] 에러: {message}")
                    break  # 다른 에러는 다음 모델로
    return None


result = ask_gemini(prompt)

if result:
    print("\n=== 성공! AI 답변 ===")
    print(result)
else:
    print("\n모든 모델이 실패했어요. 시간을 두고 다시 실행하거나, 오늘은 더미 데이터 작업부터 하세요.")