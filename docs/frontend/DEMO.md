# 사용 흐름

기본 제공 기사 20개는 PR #2에서 가져온 가상 데이터다. API 키·뉴스 서버는 필요하지 않다.
지도 타일과 패키지 설치에는 인터넷이 필요하다. 네트워크 없이 사용하려면 설치 후 `--offline`으로 실행한다.

1. `python -m frontend`로 OpenStreetMap을 연다. 오프라인 시작은 `python -m frontend --offline`.
2. 목록 또는 지도 마커를 눌러 왼쪽 패널에서 기사를 읽는다. 뒤로 또는 Esc로 목록에 돌아온다.
3. Ctrl+K로 검색한다. 필터를 눌러 분류/지역 조건을 고르고, 정렬을 바꾼다.
4. 지도 옆 아이콘으로 확대·축소, 전국 보기, 검색 결과 맞춤을 사용한다.
5. 군집을 눌러 같은 지역의 기사를 탐색한다. 확대하면 시·군·구 경계가 추가된다.
6. 검색 결과가 없으면 필터 초기화로 돌아간다.
7. 더 보기에서 뉴스 JSON을 읽거나 기본 데이터로 돌아온다. 데이터 설명과 출처는 정보에 있다.

화면 색상은 시스템 설정을 따른다. 상세가 별도 창으로 열리지 않아 좁은 화면에서도 같은 동선을 사용한다.
가상 기사에는 원문 버튼이 없으며 실제 데이터의 유효한 URL만 기본 브라우저에서 연다.

GitHub Actions에서 Linux와 Windows의 프론트엔드 자동 검증을 수행한다. 아래 화면은 실제 Qt 실행 캡처로 생성한다.

## 실제 프론트엔드 화면

```bash
python -m frontend.tools.capture_review --output test-artifacts/screenshots
```

Qt 오프스크린 실행으로 제공된 가상 기사 20건을 사용하며 생성한 화면은
실행 가능한 위젯에서 직접 캡처한 자료다. 이미지 생성 결과가 아니다.
팀 크롤러 및 데이터베이스 연동 결과와 구분한다.

| 캡처 파일 | 화면 |
|---|---|
| 01-map-overview.png | 기본 지도와 뉴스 목록 |
| 02-region-filter.png | 지역 필터 적용 |
| 03-news-detail.png | 기사 상세 |
| 04-compact-window.png | 작은 창 |
| 05-keyword-search.png | 키워드 검색 |
| 06-category-filter.png | 카테고리 필터 |
| 07-empty-search.png | 검색 결과 없음 |
| 08-saved-news-detail.png | 저장한 기사 상세 |
| 09-saved-news-list.png | 저장한 기사 목록 |
| 10-district-map.png | 행정구역 확대 |
| 11-dark-theme.png | 시스템 색상 변경 신호를 적용한 다크 모드 |
| 12-wide-desktop.png | 1920×1080 큰 창 |
| 13-load-details.png | 데이터 불러오기 정보 |

GitHub Actions Linux 검사에서 `mapnews-qt-screens` 아티팩트로 제공한다.
검사 전체가 실패하더라도 캡처 업로드가 완료되면 확인할 수 있다.

## 팀원 데이터 연동

`frontend.tools.export_team_news`는 다른 팀원의 코드를 변경하지 않는 프론트엔드 입력 변환기다.
변환된 9개 필드 JSON은 `python -m frontend --json`으로 열 수 있다. 기사 정보는 원본 값을
보존하고, 좌표가 없는 기사는 목록에만 표시한다.

### 팀 지도 코드가 현재 작업 디렉터리에 있는 경우

```bash
python -m frontend.tools.export_team_news --input data_ai/results.json --output test-artifacts/team-news.json
python -m frontend --json test-artifacts/team-news.json --mock-json
```

좌표 계산은 `map_visualization.map_visualization.prepare_news_for_frontend()`가 담당한다.
`data_ai/results.json`은 가상 기사이므로 시연에서만 `--mock-json`을 붙인다.
좌표 변환 모듈을 사용하려면 해당 팀 모듈과 `geopy`, `folium`이 설치되어 있어야 한다.

### 프론트엔드 브랜치에서 독립 검증

이미 팀원이 지역별로 확인하고 저장한 `map_visualization/.geocode_cache.json`이 있다면
팀 지도 모듈을 가져오지 않아도 캐시의 **일치하는 지역명만** 좌표로 연결할 수 있다.
이 옵션은 네트워크 검색을 하지 않으며 임의 좌표를 생성하지 않는다.

```bash
python -m frontend.tools.export_team_news --input news_results.json --coordinate-cache map_visualization/.geocode_cache.json --output test-artifacts/team-news.json
python -m frontend --json test-artifacts/team-news.json
```

입력 파일에 실제 위도와 경도가 이미 있다면 다음 명령을 사용할 수 있다.

```bash
python -m frontend.tools.export_team_news --input news_results.json --existing-coordinates --output test-artifacts/team-news.json
python -m frontend --json test-artifacts/team-news.json
```

좌표가 0건이면 출력 파일을 덮어쓰지 않고 중단한다.
지역 정보가 없는 뉴스만 목록으로 보고 싶을 때만 `--allow-no-pins`를 명시한다.
실제 수집 기사 파일에는 `--mock-json`을 쓰지 않는다.

PR #6의 크롤러가 생성하는 파일은 `news_results.json`이고, AI 분석 스크립트의
현재 입력은 `data_ai/dummy_news.json`으로 고정되어 있다. **실제 뉴스 → AI 분석 → 좌표 변환**
과정 전체를 실행하려면 담당자 간 파일 경로/ID/분류 규격을 통일해야 한다.
이 프론트엔드 도구가 그 단계들을 대신 수행하거나 자동으로 뉴스 진위를 판단하지는 않는다.

### 확인 방법

변환 결과에서 좌표가 있는 기사 수와 프론트엔드의 지도 마커가 나타나는지 확인한다.
서로 가까운 좌표는 화면에서 군집 마커 하나로 묶일 수 있으므로 육안의 핀 수가 반드시
기사 수와 같지는 않다. 검색과 필터, 기사 상세에서 같은 ID가 선택되는지도 확인한다.
