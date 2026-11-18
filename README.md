# 창의적공학설계 5조 · MapNews

PySide6 기반 지도 뉴스 탐색 프로그램. 뉴스를 RSS로 수집하고, 기사 지역/분류를 분석한 뒤 지도와 목록에 보여줍니다.

## 실행 (Python 3.11 또는 3.12)

Windows PowerShell:

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements-integration.txt
    .\.venv\Scripts\python.exe run_pipeline.py --gui

Linux:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements-integration.txt
    .venv/bin/python run_pipeline.py --gui

- 기본값: 뉴시스 RSS 수집 → 기사 보관 → 로컬 규칙 기반 분류/지역 추출 → 기존 좌표 캐시만 사용 → GUI. Gemini API 키가 필요 없습니다.
- 실제 데이터 갱신 없이 저장된 기사를 시연: python run_pipeline.py --skip-fetch --gui
- 지도 타일 네트워크 없이 시작: python run_pipeline.py --skip-fetch --gui --offline-map
- 새로운 지역의 Nominatim 좌표 조회를 명시적으로 허용: python run_pipeline.py --geocode --gui. 지명 대표 좌표는 사건의 실제 주소가 아닙니다. 대량 실행 시 공용 지오코딩 서비스 정책을 준수하세요.
- Gemini 선택적 사용: pip install -r requirements-ai.txt 후 GEMINI_API_KEY 환경변수 설정, python run_pipeline.py --with-ai --max-ai-articles 30 --gui
- GUI만 실행(기본 내장 시연용 20건): python -m frontend
- 별도 실기사 JSON 열기: python -m frontend --json map_visualization/map_results.json

## 데이터 경로와 제한

1. search.py: RSS 응답당 최대 2 MiB, 공급원당 1,000개 후보를 읽고 URL 기반 고정 ID와 본문 해시를 사용합니다. news_results.json은 최대 10,000건으로 증분 저장되며 동일 URL의 수정 기사를 갱신합니다. 수집 0건/전체 실패 시 기존 파일을 보호합니다.
2. data_ai/rule_analysis.py: 기본값은 외부 AI API 없이 분류와 제목에 명시된 지역만 보수적으로 추출합니다. 위치를 못 찾으면 지도 핀을 임의 생성하지 않습니다. summary는 원문 일부를 발췌한 것으로 생성형 요약이 아닙니다.
3. data_ai/analyze_news.py: 선택적 Gemini 경로. 요청당 5건, 기본 실행당 신규 30건 이하 및 호출 시도 최대 12회. 기존 내용 해시가 같으면 API 재요청하지 않습니다. 분석 불가·처리 보류는 다음 실행로 넘기고 규칙 결과를 유지합니다.
4. map_visualization/map_visualization.py: 캐시된 좌표/명시적 지오코딩 결과를 붙입니다. 대표 좌표는 실제 사고 지점 확인 값이 아니며, 좌표가 없는 기사는 목록에서 볼 수 있습니다.
5. frontend: 실제 결과는 --json 파일로 전달되며, 인수 없이 시작하면 더미 뉴스 20건을 보여줍니다. 시연용 기사 링크는 열지 않습니다.

파일 기록은 임시 파일 + 원자적 교체로 수행해 저장 중단 때 이전 정상 결과를 보호합니다. 한 번 실행해 만든 결과인지 구분하려면 생성 시간과 수집·분석·좌표 건수를 로그로 함께 확인해야 합니다.

## 검증과 릴리즈

    python -m pip install -r requirements-integration.txt
    python -m pytest tests/integration -q
    python -m pytest tests/frontend -m "not webengine" -q
    python run_pipeline.py --skip-fetch

GitHub Actions의 MapNews integration은 Linux/Python 3.11과 Windows/Python 3.12에서 코드 검사, 파이프라인 테스트, Qt 테스트와 저장된 실기사 기반 오프라인 통합 실행을 검증합니다. CI는 실시간 RSS/Gemini/Nominatim의 응답을 보장하지 않습니다.

v0.1.0 태그는 docs/RELEASE_CHECKLIST.md의 실제 네트워크·GUI·릴리즈 조건을 통과한 뒤 생성합니다.

## 참고

프론트엔드 상세 디자인·자료 계약·실행 방법: docs/frontend/DATA_CONTRACT.md, docs/frontend/DEMO.md. 지도 배경에는 OpenStreetMap 타일을 쓰며 출처 표시는 그대로 유지합니다.
