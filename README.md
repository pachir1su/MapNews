# 창의적공학설계 5조 팀 프로젝트

**MapNews** · 한국기술교육대학교 — 뉴스의 사건 발생 위치를 지도에서 탐색하는 데스크톱 애플리케이션입니다.

이번 브랜치에는 **독립 실행 가능한 프론트엔드**가 구현되어 있습니다. PySide6 GUI, 뉴스 탐색/상세,
오프라인 지도, Folium 온라인 지도, Mock 데이터, 백엔드 연결 인터페이스를 포함합니다.
뉴스 크롤링·Gemini 분석·SQLite 저장·실시간 뉴스 수집은 별도 팀원 영역이며 여기서 구현하지 않습니다.
`data_ai`를 실행하거나 API 키를 요구하지 않습니다.

## Windows에서 시작

Python **3.11 또는 3.12, 64비트** 환경을 사용합니다. 저장소 루트에서 PowerShell로 실행합니다.
가상환경 활성화 없이도 아래 명령을 사용할 수 있습니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-frontend.txt
.\.venv\Scripts\python.exe -m frontend
```

## Linux/macOS에서 시작

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-frontend.txt
.venv/bin/python -m frontend
```

패키지 설치에는 인터넷이 필요합니다. 설치 후 기본 데모는 인터넷 없이 실행됩니다.
Ubuntu에서 Qt 라이브러리가 부족하면 `libegl1 libopengl0 libxtst6 libxkbfile1 libxcb-cursor0
libxkbcommon-x11-0 fonts-noto-cjk` 패키지가 필요할 수 있습니다. macOS 실기기 검증은 수행하지 않았습니다.

## 실행 모드

```bash
python -m frontend                               # 오프라인 Mock 20건
python -m frontend --dark                        # 다크 테마
python -m frontend --online                      # Folium + OpenStreetMap, 인터넷 필요
python -m frontend --json data_ai/results.json    # 외부 JSON, 읽기 전용
python -m frontend --json demo.json --mock-json   # 외부 시연 데이터 표시
```

- **기본 오프라인:** 로컬 Natural Earth 벡터 지도에 미리 준비한 대표 좌표를 표시합니다. 클릭·군집 기사 선택·검색·다중 분류·지역·정렬·상세가 네트워크 없이 동작합니다. 도로/건물 지도는 아닙니다.
- **온라인:** QtWebEngineView에 Folium/Leaflet 지도를 표시합니다. JS/CSS는 번들에 포함되어 있지만 OpenStreetMap 타일에는 인터넷이 필요합니다. 실패 시 오프라인 화면으로 전환합니다.
- **Mock:** PR #2의 가상 기사 20개를 원문 그대로 사용합니다. 실제 사건/실시간 뉴스가 아닙니다. example.com 원문 버튼은 비활성화됩니다. 좌표는 시연용 지역 대표 위치입니다.
- **백엔드 JSON:** 기존 PR #2 JSON과 호환됩니다. 좌표가 없는 기사는 목록/상세에만 표시됩니다. 프론트엔드가 실제 위치를 임의로 추정하지 않습니다.

## 조작

| 조작 | 동작 |
|---|---|
| 목록 클릭 / 방향키 | 기사 선택, 지도 강조·이동, 상세 갱신 |
| 지도 마커 클릭 | 같은 기사 목록 선택 |
| 군집 마커 클릭 | 오프라인: 기사 메뉴(13건 이상은 검색 창) / 온라인: 확대·겹침 분리 |
| 카테고리 버튼 | 다중 포함/제외; 모두 해제하면 결과 0건 |
| 검색 | 제목·요약·지역·분류, 여러 단어는 AND 검색 |
| Ctrl+K / Ctrl+F | 검색창 포커스 |
| Ctrl+Enter / 상세 | 별도 상세 창 |
| F5 / 새로고침 | 현재 Provider 다시 읽기 |
| Ctrl+T | 테마 전환, 다음 실행에 유지 |
| 결과 / 전국 / + / − | 검색 결과에 맞춤 / 초기 지도 범위 / 확대 / 축소 |
| 로딩 취소 | 현재 작업에 취소 요청, 기존 기사 유지 |
| JSON 열기 / 데모 | 데이터 소스 변경 |

패널 폭은 드래그로 조정할 수 있습니다. 폭 1250 미만에서는 상세 패널이 접히며 별도 상세 창을 사용합니다.
오류가 나면 기존 데이터를 유지하고 안내를 표시합니다. 실제 데이터에서 유효한 원문 주소는 기본 브라우저로 엽니다.

## 개발·검증

```bash
python -m pip install -r requirements-frontend-dev.txt
python -m ruff check frontend tests/frontend
python -m pytest -q
```

GUI 디스플레이가 없는 Linux에서는 `QT_QPA_PLATFORM=offscreen`을 설정합니다. WebEngine 테스트도
실제 Chromium/Leaflet/WebChannel을 실행합니다. 테스트를 위해 인터넷 타일은 비활성화합니다.
root 컨테이너에서만 `QTWEBENGINE_DISABLE_SANDBOX=1`이 필요할 수 있습니다. 일반 실행에는 설정하지 않습니다.
검증 결과와 한계는 [검증 기록](docs/frontend/VALIDATION.md), 시연 순서는 [시연 안내](docs/frontend/DEMO.md)를 참고하세요.

## 구조와 팀원 연결

- [모듈 구조·디자인·스레드·지도](docs/frontend/ARCHITECTURE.md)
- [JSON 계약·Provider 연결 방법](docs/frontend/DATA_CONTRACT.md)
- [문제 해결](docs/frontend/TROUBLESHOOTING.md)
- [원본 데이터와 로컬 지도 출처](frontend/resources/MAP_DATA.md)
- [번들 라이브러리 라이선스](frontend/resources/vendor/README.md)

main 직접 변경이나 PR #1/#2 병합 없이 별도 `frontend/desktop-news-explorer` 브랜치로 작업합니다.
