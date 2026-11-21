# Gemini 파생 작업 큐 운영 규격

- 단일 원본: `news_results.json` 전체 기사 파일. AI 입력 큐는 이를 매 실행 동기화해 생성하는 파생 데이터입니다.
- 선택적 Gemini 실행: `python run_pipeline.py --with-ai --skip-fetch`. 기본은 비AI 규칙 분석입니다.
- 결과 파일: `data_ai/results_ai.json`; 기본 큐 파일: `data_ai/ai_queue.json`. 독립 실행의 경우 출력파일이 `foo.json`이면 `foo.queue.json`을 사용합니다.
- 큐 필드: `id`, `content_hash`, `title`, `body`(최대 1,500자), `datetime`, `source`, `status`, `attempts`, `retry_at`, `last_error`.
- 최신 기사순 최대 30건/실행, 5건/요청, 기본 최대 API 요청 12회(재시도·모델 대체 포함). 환경변수 `MAPNEWS_MAX_AI_ARTICLES`와 `MAPNEWS_MAX_AI_REQUESTS`로 조정할 수 있습니다.
- `pending`: 아직 처리 안 함; `completed`: 실제 결과 파일에서 같은 `id + content_hash` 확인; `retry_wait`: 실패 후 지수적 대기(60·120·240·480초); `failed`: 5회 실패, 수동 검사 후 재개 필요.
- 쿼터 오류(429)나 인증 오류(401/403)를 다른 모델로 무한 반복하지 않습니다. 서버 일시 장애 502/503/504는 전체 요청 예산 안에서만 짧게 재시도합니다.
- 큐 및 분석 결과는 서로 다른 원자적 파일 쓰기를 사용하며, 항상 **결과를 먼저 저장하고 큐 완료 상태를 나중에 반영**합니다. 중단 후 큐는 실제 저장 결과를 기준으로 다시 구성합니다.
- 큐 파일이 깨졌거나 스키마가 맞지 않으면 결과를 덮어쓰지 않고 종료합니다. 별도 수동 조치 없이 큐 파일을 덮어쓰지 않습니다.
- 중복 실행은 운영체제 파일 잠금으로 차단합니다. 큐와 결과가 동시에 살아 있어도 Gemini 자체 API에는 멱등성 키가 없기 때문에 요청 후 결과 저장 전 강제 종료 시 일부 재요청은 가능합니다.
- 수집 원본/큐/AI 분석 출력의 보관·배포 권한은 기사 제공사의 조건에 따릅니다. `ai_queue.json`은 버전 관리에 올리지 않습니다.
