# 문제 해결

| 증상 | 원인 / 해결 |
|---|---|
| No module named frontend | 저장소 루트에서 실행. `frontend` 폴더 안에서 실행하지 않음 |
| No module named PySide6 | 실행한 Python과 설치한 pip가 다름. `.venv`의 Python으로 `-m pip install` 사용 |
| Qt platform plugin xcb 오류 | Linux 시스템 라이브러리 설치. 화면 없는 테스트에서는 QT_QPA_PLATFORM=offscreen |
| libXtst / libxkbfile 누락 | Linux에서 libxtst6, libxkbfile1 설치. 오프라인 기본 화면은 WebEngine 없이도 동작 |
| 한글이 네모로 표시 | Linux에 fonts-noto-cjk 설치. Windows에서는 맑은 고딕 사용 |
| 지도 타일이 비어 있음 | 인터넷 또는 타일 서버 연결 실패. 오프라인으로 자동 전환되며 드롭다운으로도 전환 가능 |
| 기사 목록은 있지만 마커 없음 | latitude/longitude 누락 또는 잘못된 범위. 좌표 없는 외부 데이터는 임의 위치 추정하지 않음 |
| 0건 검색 결과 | 카테고리를 모두 해제했거나 지역/키워드 조건이 맞지 않음. 초기화 선택 |
| 원문 버튼 비활성화 | Mock이거나 URL이 없거나 HTTP(S) 주소 검증 실패 |
| 외부 JSON 로딩 실패 | UTF-8 JSON 배열인지, 8 MiB/10,000행 이내인지 확인. 기존 데이터는 유지됨 |
| 중복 기사 일부 제외 | 중복 ID가 존재함. 첫 행만 유지되며 데이터 경고에 표시 |
| 종료를 기다리는 상태 | Provider가 취소를 확인하지 않거나 I/O timeout이 너무 김. Provider 계약의 유한 timeout 준수 |
| 좁은 창에서 상세가 사라짐 | 의도된 반응형 동작. 상단 상세 또는 Ctrl+Enter 사용 |
| root 컨테이너 Chromium sandbox 오류 | 테스트 컨테이너에서만 QTWEBENGINE_DISABLE_SANDBOX=1 지정. 일반 사용자 실행에서는 사용하지 않음 |

프로그램은 임의로 Gemini API를 호출하거나 SQLite/원본 JSON을 수정하지 않습니다.
대용량 뉴스는 10,000건을 상한으로 하며, 화면 표시 성능은 GPU/배율/좌표 분포에 영향을 받습니다.
