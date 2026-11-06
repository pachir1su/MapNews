# 구조와 디자인 결정

| 파일 | 책임 |
|---|---|
| frontend/__main__.py | CLI, Qt 실행, HiDPI 설정 |
| models.py | 불변 NewsItem/NewsBatch, JSON 검증과 URL 제한 |
| providers.py | MockNewsProvider, 읽기 전용 JsonNewsProvider, Provider 프로토콜 |
| workers.py | 취소 가능한 백그라운드 로딩과 결과/실패 신호 |
| state.py | 검색·필터·정렬·선택 상태, Qt 의존성 없음 |
| main_window.py | 위젯과 상태 연결, 로딩·오류·종료 흐름 |
| news_list.py | QAbstractListModel와 delegate, 화면에 보이는 카드만 그림 |
| detail.py | 일반 텍스트 상세, 원문 URL 재검증 |
| map_panel.py | 지도 모드 전환, 온라인 실패 fallback |
| offline_map.py | Native Qt 벡터 지도, 확대·이동·군집·선택 |
| map_html.py / resources/map.js | Folium 문서 생성, Leaflet 군집·선택·강조 |
| web_map.py | WebEngine 격리, 제한된 WebChannel, 요청 허용 목록 |
| themes.py | 라이트/다크 색상·간격·타이포그래피 |
| resources/ | 원본 Mock, 별도 좌표, 로컬 지도, 라이선스 포함 JS/CSS |
| tests/frontend/ | 순수 로직, pytest-qt GUI, 실제 WebChannel 회귀 테스트 |

## 디자인 비교와 선택

| 방향 | 장점 | 과제 | 결정 |
|---|---|---|---|
| 지도 전체 화면 + 플로팅 카드 | 지도 면적이 큼 | 여러 기사 비교·필터 탐색이 불편 | 보류 |
| 표 중심 대시보드 | 데이터가 촘촘함 | 사건 위치의 맥락이 약해짐 | 보류 |
| 뉴스 목록 / 지도 / 상세 3단 | 탐색·지역·맥락을 동시에 확인 | 좁은 창에서 공간 조절 필요 | 채택 |

기본 색은 네이비/오렌지, 카테고리는 독립된 5색과 한글 이름으로 구분한다.
라이트는 수업/프로젝터 가독성, 다크는 저조도 탐색을 고려한다. 색만으로 정보를 전달하지 않는다.
QSplitter로 폭을 조절한다. 폭 1250 미만이면 우측 상세를 숨기고 상단 상세 또는 Ctrl+Enter로
비모달 상세 창을 연다. 최소 크기는 1000×640이다. 기본 검토 대상은 1366×768/1920×1080이다.
카드 제목/요약은 말줄임하고 툴팁에 전체 텍스트를 제공한다. 상세는 줄바꿈·스크롤을 지원한다.

## 지도

기본은 네트워크를 사용하지 않는 Native Qt 지도다. Natural Earth의 공개 도메인 1:50m
지형을 번들로 제공한다. 저해상도 개요이며 도로/건물/정밀 사건 위치 지도는 아니다.
군집 마커를 누르면 해당 기사 목록 메뉴를 연다. 동일 좌표 기사도 개별 선택 가능하다.

온라인 모드는 Folium/Leaflet/MarkerCluster + QtWebEngineView를 사용한다. 라이브러리 JS/CSS는
로컬 번들이며, OpenStreetMap 타일에만 인터넷이 필요하다. attribution을 유지한다.
15초 초기화 timeout, 타일 실패, 렌더러 종료 시 오프라인 지도로 전환한다.
WebChannel은 기사 ID 선택과 초기화/오류 신호만 노출한다. 뉴스 원문 페이지는 내장 브라우저에
로드하지 않는다. 기사 텍스트는 DOM textContent, Python→JS 값은 JSON 직렬화로 전달한다.
알 수 없는 ID는 무시하고 외부 URL은 OS 브라우저로만 연다.

## 스레드·자원 수명

Provider 로딩과 Folium HTML 생성은 별도 QThread에서 수행한다. GUI 갱신은 Qt 신호로
주 스레드에서 실행한다. 하나의 Provider 로딩만 허용한다. 창 종료는 취소 신호를 보내고
작업 완료 후 진행한다. 지도 전환 시 타이머/페이지/WebChannel을 정리한다.
오래된 지도 객체의 지연 콜백이 새 페이지를 다시 시작하지 않도록 stopped 상태를 검사한다.
