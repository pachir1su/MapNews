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

기본 지도는 OpenStreetMap으로 인터넷이 필요합니다. 설치 후 `--offline`으로 시작하면 네트워크 없이 사용할 수 있습니다.
Ubuntu에서 Qt 라이브러리가 부족하면 `libegl1 libopengl0 libxtst6 libxkbfile1 libxcb-cursor0
libxkbcommon-x11-0 fonts-noto-cjk` 패키지가 필요할 수 있습니다. macOS 실기기 검증은 수행하지 않았습니다.

## 실행 모드

```bash
python -m frontend                               # OpenStreetMap + 기본 제공 기사 20건
python -m frontend --offline                     # 로컬 지도, 인터넷 없이 실행
python -m frontend --json data_ai/results.json    # 외부 JSON, 읽기 전용
python -m frontend --json demo.json --mock-json   # 외부 JSON을 가상 기사로 취급
```

- **오프라인 옵션:** 로컬 Natural Earth/SGIS 벡터 지도에 미리 준비한 대표 좌표를 표시합니다. 클릭·군집 기사 선택·검색·다중 분류·지역·정렬·상세가 네트워크 없이 동작합니다. 시·도 경계가 표시되고 확대하면 시·군·구 경계가 나타납니다. 도로/건물 지도는 아닙니다. 경계 기준연도는 2026년 10월 1일 스냅샷입니다.
- **기본 OpenStreetMap:** QtWebEngineView에 Folium/Leaflet 지도를 표시합니다. JS/CSS는 번들에 포함되어 있지만 OpenStreetMap 타일에는 인터넷이 필요합니다. 실패 시 오프라인 화면으로 전환합니다.
- **Mock:** PR #2의 가상 기사 20개를 원문 그대로 사용합니다. 실제 사건/실시간 뉴스가 아닙니다. 가상 기사에는 원문 버튼을 표시하지 않습니다. 데이터 성격은 더 보기 → 정보에 설명합니다. 좌표는 시연용 지역 대표 위치입니다.
- **백엔드 JSON:** 기존 PR #2 JSON과 호환됩니다. 좌표가 없는 기사는 목록/상세에만 표시됩니다. 프론트엔드가 실제 위치를 임의로 추정하지 않습니다.

## 조작

| 조작 | 동작 |
|---|---|
| 목록 / 마커 클릭 | 왼쪽 목록 자리에 기사 상세 표시, 지도 선택 동기화 |
| 목록 방향키 / Enter | 선택 이동 / 상세 열기 |
| 상세 뒤로 버튼 / Esc | 목록 복귀; 검색 조건과 목록 위치 유지 |
| 군집 마커 클릭 | 오프라인: 기사 선택 / 온라인: 확대·겹침 분리 |
| 필터 | 카테고리·지역 조건 펼치기; 여러 분류 선택 가능 |
| 검색 | 제목·요약·지역·분류, 여러 단어는 AND 검색 |
| Ctrl+K / Ctrl+F | 검색창 포커스 |
| F5 / 더 보기 → 새로고침 | 현재 Provider 다시 읽기 |
| 지도 아이콘 | 확대·축소·전국·검색 결과 맞춤·지도 선택 |
| 로딩 중 취소 아이콘 | 현재 작업에 취소 요청, 기존 기사 유지 |
| 더 보기 → 뉴스 파일 열기 / 기본 데이터로 돌아가기 | 데이터 소스 변경 |

화면 색상은 **시스템 설정을 자동으로 따릅니다**. 수동 테마 버튼·단축키·저장 옵션은 없습니다.
실행 중 시스템 화면 모양을 바꾸면 목록·상세·지도도 함께 갱신됩니다. 시스템이 화면 모양을 제공하지 않으면 밝은 화면으로 표시합니다.

하단 상시 상태 표시줄과 설명은 제거했습니다. 데이터·지도 출처와 단축키는 **더 보기 → 정보**에서 확인합니다.
패널 폭은 드래그로 조정할 수 있습니다. 목록과 상세는 같은 왼쪽 패널을 사용하므로 좁은 창에서도 지도 공간을 유지합니다.
오류가 나면 기존 데이터를 유지하고 안내를 표시합니다. 실제 데이터에서 유효한 원문 주소는 기본 브라우저로 엽니다.

## 개발 상태와 테스트 인계

이번 UI 개편은 개발 담당 범위로만 반영했으며 **테스트·OS별 실행·CI를 수행하지 않았습니다**.
기존 테스트는 이전 화면 구조를 기준으로 하므로 테스트 담당자의 갱신과 실행이 필요합니다.
이전 통과 기록을 현재 변경의 검증 결과로 사용하지 않습니다.

- [이번 변경의 테스트 인계](docs/frontend/QA_HANDOFF.md)
- [이전 버전 검증 기록](docs/frontend/VALIDATION.md)
- [사용 흐름](docs/frontend/DEMO.md)

## 읽기·파일 열기 단축키

- 상세 위 이전/다음 버튼 또는 Alt+위/아래로 검색 결과 순서대로 읽습니다.
- Ctrl+L 또는 검색창에서 아래 방향키로 목록에 이동하고, Enter로 상세를 엽니다.
- Esc/Alt+왼쪽으로 목록에 돌아옵니다. Ctrl+O 또는 JSON 파일 드래그로 데이터를 엽니다.
- 새 파일은 로딩 성공 후 적용합니다. 실패하면 기존 기사와 검색 조건이 남으며 재시도할 수 있습니다.
- 더 보기 → 불러오기 정보에서 좌표 누락·제외된 행 등 데이터 경고를 확인합니다.

## 구조와 팀원 연결

- [UI 개편 방향과 참고](docs/frontend/DESIGN.md)
- [모듈 구조·디자인·스레드·지도](docs/frontend/ARCHITECTURE.md)
- [JSON 계약·Provider 연결 방법](docs/frontend/DATA_CONTRACT.md)
- [문제 해결](docs/frontend/TROUBLESHOOTING.md)
- [원본 데이터와 로컬 지도 출처](frontend/resources/MAP_DATA.md)
- [번들 라이브러리 라이선스](frontend/resources/vendor/README.md) · [SVG 아이콘 출처](frontend/resources/icons/README.md)

main 직접 변경이나 PR #1/#2 병합 없이 별도 `frontend/desktop-news-explorer` 브랜치로 작업합니다.
