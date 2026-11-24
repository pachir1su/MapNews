# 창의적공학설계 5조 · MapNews

PySide6 기반 지도 뉴스 탐색 프로그램. 뉴스를 RSS로 수집하고, 기사 지역/분류를 분석한 뒤 지도와 목록에 보여줍니다.

## 프로그램 실행 방법

### 1. 준비물

- Python 3.11 또는 3.12 ([다운로드](https://www.python.org/downloads/))
- Git ([다운로드](https://git-scm.com/downloads)) 또는 GitHub의 Code > Download ZIP
- 인터넷 연결: 최초 패키지 설치, RSS 수집, 온라인 지도 타일에 필요합니다. 설치 후에는 저장된 기사와 오프라인 지도로 실행할 수 있습니다.
- 기본 실행에는 Gemini API 키가 필요 없습니다.

### 2. Windows (PowerShell)

아래 명령을 한 줄씩 실행합니다. 명령어는 MapNews 저장소의 최상위 폴더에서 실행합니다.

**① Python과 Git 설치 확인**

~~~powershell
py -3.12 --version
git --version
~~~

Python 3.11만 설치되어 있다면 아래 명령의 -3.12를 -3.11로 바꿉니다.

**② 소스 코드 다운로드**

~~~powershell
git clone https://github.com/pachir1su/MapNews.git
cd MapNews
~~~

ZIP으로 받았다면 압축을 풀고 run_pipeline.py가 있는 폴더를 PowerShell에서 열면 됩니다.

**③ 가상환경 생성**

~~~powershell
py -3.12 -m venv .venv
~~~

가상환경을 직접 활성화하지 않고 가상환경의 Python을 사용하므로 PowerShell 실행 정책을 변경할 필요가 없습니다.

**④ 필요한 라이브러리 설치**

~~~powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-integration.txt
~~~

**⑤ 프로그램 실행**

~~~powershell
.\.venv\Scripts\python.exe run_pipeline.py --gui
~~~

뉴스 수집, 지역 및 분류 분석, 기존 좌표 캐시 적용을 거쳐 GUI가 열립니다. 뉴스 수집에 실패하면 정상적인 기존 데이터를 보호하며 실행이 중단될 수 있습니다.

**⑥ 저장된 기사로 실행 (네트워크 장애 시 권장)**

~~~powershell
.\.venv\Scripts\python.exe run_pipeline.py --skip-fetch --gui --offline-map
~~~

새 뉴스 수집 및 온라인 지도 타일 요청 없이 저장된 news_results.json을 분석해 표시합니다. 위치 근거가 없거나 좌표가 없는 기사는 목록에 남습니다.

### 3. Linux

**① Python과 Git 버전 확인 및 다운로드**

~~~bash
python3 --version
git --version
git clone https://github.com/pachir1su/MapNews.git
cd MapNews
~~~

python3가 3.11 또는 3.12인지 확인합니다. venv가 없다면 사용하는 배포판의 Python venv 패키지를 설치합니다. GUI 실행에는 그래픽 데스크톱 및 Qt가 요구하는 시스템 라이브러리가 필요합니다.

**② 가상환경 생성 및 의존성 설치**

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-integration.txt
~~~

**③ 실행**

~~~bash
.venv/bin/python run_pipeline.py --gui
~~~

저장된 기사 및 오프라인 지도:

~~~bash
.venv/bin/python run_pipeline.py --skip-fetch --gui --offline-map
~~~

### 4. 실행 방식 선택

아래 명령은 Windows PowerShell 기준입니다. Linux에서는 .\.venv\Scripts\python.exe 대신 .venv/bin/python을 사용합니다.

| 실행 목적 | 명령어 |
|---|---|
| 새 기사 수집 및 GUI | `.\.venv\Scripts\python.exe run_pipeline.py --gui` |
| 저장 기사 및 온라인 지도 | `.\.venv\Scripts\python.exe run_pipeline.py --skip-fetch --gui` |
| 저장 기사 및 오프라인 지도 | `.\.venv\Scripts\python.exe run_pipeline.py --skip-fetch --gui --offline-map` |
| GUI만 시연 (가상 기사 20건) | `.\.venv\Scripts\python.exe -m frontend` |
| GUI만 오프라인 시연 | `.\.venv\Scripts\python.exe -m frontend --offline` |
| 기존 지도 결과 JSON 직접 열기 | `.\.venv\Scripts\python.exe -m frontend --json map_visualization/map_results.json` |
| 분석 및 좌표 변환만 수행 | `.\.venv\Scripts\python.exe run_pipeline.py --skip-fetch` |

기존 지도 결과 JSON은 파이프라인이 정상적으로 완료되어 해당 파일이 생성된 경우에만 직접 열 수 있습니다. 시연용 가상 기사에는 원문 링크가 제공되지 않습니다.

### 5. 선택 기능: 새로운 지역 좌표 조회

~~~powershell
.\.venv\Scripts\python.exe run_pipeline.py --geocode --gui
~~~

Nominatim에 네트워크 요청을 보내는 기능입니다. 기본 실행에서는 사용하지 않습니다. 공용 지오코딩 서비스의 사용 정책을 준수해야 하며, 지명의 대표 좌표는 실제 사건의 주소가 아닙니다.

### 6. 선택 기능: Gemini AI 분석

**① AI 관련 의존성 설치**

~~~powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
~~~

**② 현재 PowerShell 세션에 API 키 설정**

~~~powershell
$env:GEMINI_API_KEY = Read-Host "Gemini API key"
~~~

키를 소스 코드, README, 커밋 또는 공개 로그에 기록하지 마세요.

**③ AI 분석을 포함하여 실행**

~~~powershell
.\.venv\Scripts\python.exe run_pipeline.py --with-ai --max-ai-articles 30 --gui
~~~

Linux에서는 터미널에서 키를 입력한 뒤 실행합니다.

~~~bash
.venv/bin/python -m pip install -r requirements-ai.txt
read -rs GEMINI_API_KEY
export GEMINI_API_KEY
.venv/bin/python run_pipeline.py --with-ai --max-ai-articles 30 --gui
~~~

API 호출에는 인터넷 연결이 필요하며 사용량 제한이나 비용이 발생할 수 있습니다. 기본 실행은 로컬 규칙 기반 분석이므로 키 없이 사용할 수 있습니다.

### 7. 프로그램 사용 방법

1. 목록의 기사 또는 지도 마커를 선택하면 기사 상세 정보가 열립니다.
2. 검색창에 키워드를 입력하거나 지역과 카테고리 필터를 적용합니다.
3. 지도 확대 및 축소, 전국 보기, 검색 결과에 맞춘 지도 이동을 이용합니다.
4. 기사 상세에서 뒤로 가기 또는 Esc를 누르면 목록으로 돌아갑니다.
5. 실제 기사에는 유효한 원문 링크가 있는 경우 브라우저에서 원문을 열 수 있습니다.
6. 종료 후 다시 실행할 때는 프로젝트 폴더에서 원하는 실행 명령만 입력하면 됩니다. 매번 가상환경을 만들거나 라이브러리를 설치할 필요는 없습니다.

### 8. 실행 오류 해결

| 증상 | 확인할 사항 |
|---|---|
| py 또는 python3 명령을 찾을 수 없음 | Python 설치 및 버전 확인, 터미널 재시작 |
| run_pipeline.py 또는 requirements 파일을 찾을 수 없음 | 저장소 최상위 폴더인지 확인 |
| ModuleNotFoundError | 가상환경의 Python으로 requirements-integration.txt 재설치 |
| RSS 수집 실패 | 인터넷 연결 확인 또는 --skip-fetch로 기존 기사 사용 |
| 지도 타일이 표시되지 않음 | --offline-map 또는 GUI 단독 --offline으로 시작 |
| JSON 파일이 없거나 유효하지 않음 | 정상 기사 원본 파일 확인 후 파이프라인 재실행. 기존 정상 파일을 임의로 삭제하지 않음 |
| Gemini 인증 및 할당량 오류 | API 키와 사용량 확인, --with-ai 없이 기본 실행 |
| 지도에 핀이 적음 | 지역 근거 및 좌표 캐시 유무 확인. 좌표 없는 기사는 목록에서 확인 |

명령행 도움말 확인:

~~~powershell
.\.venv\Scripts\python.exe run_pipeline.py --help
.\.venv\Scripts\python.exe -m frontend --help
~~~

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
