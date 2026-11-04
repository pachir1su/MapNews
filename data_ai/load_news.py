import json

# 1. JSON 파일 열어서 파이썬 리스트로 바꾸기
with open("data_ai/dummy_news.json", encoding="utf-8") as f:
    news_list = json.load(f)

print(f"기사 총 {len(news_list)}개\n")

# 2. 기사 제목과 지역 출력하기
for news in news_list:
    print(f"[{news['category']}] {news['title']} ({news['location']})")

# 3. 카테고리별로 몇 개씩 있는지 세기
print("\n=== 카테고리별 개수 ===")
count = {}
for news in news_list:
    category = news["category"]
    count[category] = count.get(category, 0) + 1

for category, number in count.items():
    print(f"{category}: {number}개")