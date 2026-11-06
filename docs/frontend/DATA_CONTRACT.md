# 프론트엔드 데이터 계약

## 기존 팀원 코드와의 경계

PR #2 `feature/data-ai`의 `db6050c6329a88c477598f352ed3fba89d3c6f75`를 조사했다.
`dummy_news.json`과 `results.json` 모두 최상위 배열이며 다음 필드를 사용한다.
프론트엔드는 `data_ai` 모듈을 import하거나 수정하지 않는다. 해당 스크립트는 import 시
Gemini 호출/파일 처리가 실행될 수 있으므로 데이터 파일 또는 Provider로만 연결한다.

| 필드 | 형식 | 누락·오류 시 처리 |
|---|---|---|
| id | 비어 있지 않은 문자열 또는 정수 | 해당 행 제외, 중복 ID는 첫 행 유지 |
| title | 문자열 | 제목 미제공 |
| category | 사고·화재·교통·행사·사회 | 미지 분류를 원문 유지, 화면에서 기타 필터 제공 |
| location | 지역 문자열 | 지역 미제공 |
| summary | 요약 문자열 | 요약 미제공 안내 |
| url | HTTP(S) 주소 | 잘못된 주소 비활성화; 사용자정보·제어문자 금지 |
| datetime | ISO 8601 또는 YYYY-MM-DD HH:MM | 미제공 표시, 정렬에서 항상 마지막 |
| latitude | -90~90 유한수, 선택 | 좌표 쌍이 없거나 잘못되면 목록에만 표시 |
| longitude | -180~180 유한수, 선택 | 위와 동일 |

시간대 없는 datetime은 한국 시간(+09:00)으로 해석한다. 시간대 있는 값은 한국 시간으로
변환한다. Boolean 좌표/ID와 NaN/Infinity 좌표는 거부한다. JSON은 UTF-8 또는 UTF-8 BOM,
최대 8 MiB/10,000행을 받는다. 검색어는 공백으로 나누어 AND 검색한다.
지역 필터는 `location` 첫 어절을 사용한다. 표준화·지오코딩은 백엔드가 담당한다.

```json
[{"id":"news-1","title":"기사 제목","category":"교통","location":"충남 천안시",
  "summary":"백엔드가 제공한 요약","url":"https://news.example.org/story",
  "datetime":"2026-11-04T10:23:00+09:00","latitude":36.81,"longitude":127.15}]
```

## 연결 방법 1: JSON

```bash
python -m frontend --json data_ai/results.json
```

기존 results.json은 좌표가 없으므로 목록과 상세는 동작하지만 지도에는 표시되지 않는다.
실제 좌표가 없는 기사에 프론트엔드가 임의 좌표를 붙이지 않는다. 백엔드가 선택 필드 두 개를
추가하거나 별도 Provider에서 결합하면 된다. 시연 파일은 `--mock-json`을 함께 지정한다.

## 연결 방법 2: Provider 주입

`frontend.providers.NewsProvider`의 `label`, `load(cancel)`만 구현하면 된다.
MainWindow 생성 시 `MainWindow(provider=your_provider)`로 전달한다.
`load`는 worker thread에서 호출되며 `NewsBatch`를 반환한다. `parse_news(rows)`를 활용하면
기존 계약 검증을 재사용한다. Qt 위젯은 Provider에서 만지지 않는다.

```python
from frontend.models import parse_news

class BackendNewsProvider:
    label = "백엔드 뉴스"

    def __init__(self, read_rows):
        self.read_rows = read_rows  # 팀원 측 read-only 함수 주입

    def load(self, cancel):
        rows = self.read_rows(cancel=cancel)  # 유한 timeout 및 취소 확인 필수
        return parse_news(rows, source=self.label)
```

Provider는 모든 네트워크 요청에 유한 timeout을 설정하고 작업 사이에 cancel.is_set()을
확인해야 한다. 프론트엔드는 실행 중인 QThread를 강제 종료하지 않는다. 취소를 무시하는
Provider는 창 종료를 지연시킨다. DB 연결이 스레드에 귀속된다면 worker 안에서 열고 닫는다.

갱신은 `reload()` → `LoadWorker.loaded(NewsBatch)` → `_loaded()` → 필터/지도/목록 갱신 순서다.
동시 재요청은 차단한다. 실패 시 이전 데이터와 선택을 유지한다. 동일 ID가 새 결과에 남아
있고 현재 필터를 통과하면 선택을 유지한다. 필터에서 빠지면 상세와 마커 강조를 함께 지운다.

## Mock와 실제 데이터

내장 20건은 PR #2 원본을 그대로 복사했다. `demo_coordinates.json`만 프론트엔드에서 추가했다.
이 좌표는 지역 대표 위치이며 사건 위치를 확인한 값이 아니다. Mock 원문 링크는
example.com 플레이스홀더이므로 열기 버튼이 비활성화된다. Gemini/API 키/서버가 필요 없다.
외부 JSON은 진위 미검증 데이터로 명시하며, 내장 데모 좌표를 추정해서 붙이지 않는다.
