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

이 문서는 사용 흐름 설명이다. 이번 변경의 실제 실행/시연은 아직 검증하지 않았다.

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

지도 시각화 코드가 합쳐진 작업 디렉터리에서는 다음과 같이
`data_ai/results.json`에 좌표를 붙인 프론트엔드 입력 파일을 만들 수 있다.

```bash
python -m frontend.tools.export_team_news --input data_ai/results.json --output test-artifacts/team-news.json
python -m frontend --json test-artifacts/team-news.json --mock-json
```

위 명령은 기존 시연 데이터에 대한 예시다. 실제 수집한 기사로 검증할
때는 `--mock-json`을 사용하지 않는다. 좌표가 없는 기사는 목록에
남기고 지도에만 표시하지 않는다. 원본 데이터 파일이나 다른 팀원
코드에는 변경을 가하지 않는다. 좌표 변환 모듈에는 `geopy`와
`folium` 의존성이 필요하다.
