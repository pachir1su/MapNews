import subprocess
import sys

def run_step(step_name, command):
  print(f"\n==========================================")
  print(f"[{step_name}] 시작...")
  print(f"==========================================")

  # 현재 VS Code에서 실행 중인 파이썬 환경 그대로 사용
  result = subprocess.run([sys.executable] + command)

  # 중간에 오류가 나면 다음 단계로 넘어가지 않고 즉시 멈춤
  if result.returncode != 0:
    print(f"\n❌ [{step_name}] 단계에서 오류가 발생하여 중단합니다.")
    sys.exit(result.returncode)

  print(f"✅ [{step_name}] 완료!")

if __name__ == "__main__":
  # 1단계: 뉴스 크롤링 -> news_results.json 생성
  run_step("1단계: 뉴스 크롤링", ["search.py"])

  # 2단계: AI 카테고리 및 지역 분석 -> data_ai/results_sample.json 생성
  run_step(
      "2단계: AI 카테고리·지역 분석",
      [
          "data_ai/analyze_news.py",
          "news_results.json",
          "data_ai/results_sample.json",
      ],
  )

  # 3단계: 지역명을 위도/경도 좌표로 변환 -> map_visualization/map_results.json 생성
  run_step(
      "3단계: 지도 좌표 변환",
      ["map_visualization/map_visualization.py"],
  )

  print("\n🎉 모든 작업이 한 번에 완료되었습니다! (최종 파일: map_visualization/map_results.json)")