"""Secondary explanations belong here, away from everyday map exploration."""
from html import escape
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QTextBrowser


class InformationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("정보")
        self.resize(540, 500)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        batch = getattr(parent, 'batch', None)
        if batch is None:
            source = '아직 불러온 데이터가 없습니다.'
        else:
            source = f'{escape(batch.source)} · {len(batch.items)}건'
            mock_count = sum(item.is_mock for item in batch.items)
            if mock_count:
                source += f'<br>가상 기사 {mock_count}건 포함'
        browser.setHtml(f'<h2>MapNews</h2><p>{source}</p>' + '''
        <p>한국기술교육대학교 창의적공학설계 5조</p>
        <h3>기본 제공 데이터</h3>
        <p>기본 제공 뉴스 20개는 가상 기사입니다. 좌표는 발생 지역의 대표 위치이며 실제 사건 지점이 아닙니다.
        실제 기사 원문은 제공하지 않습니다.</p>
        <h3>지도</h3>
        <p>기본 지도는 OpenStreetMap이며 인터넷 연결이 필요합니다. 연결할 수 없으면 로컬 지도로 전환합니다. 로컬 지도는 도로 정보를 제공하지 않습니다.
        시·도 경계는 항상, 시·군·구 경계는 확대 시 표시합니다.</p>
        <p>행정구역: 2026년 10월 1일 기준 스냅샷. 통계청 SGIS(공공누리 제1유형)의
        행정동 경계를 가공한 vuski/admdongkor(CC BY 4.0) 자료를 사용합니다.
        표시용으로 경계를 단순화하고 시·도 및 시·군·구로 합쳤습니다.</p>
        <p><a href="https://sgis.kostat.go.kr/">통계청 SGIS</a> ·
        <a href="https://github.com/vuski/admdongkor">vuski/admdongkor</a> ·
        <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> ·
        <a href="https://www.naturalearthdata.com/">Natural Earth (public domain)</a></p>
        <p>© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>.
        배경 타일을 불러올 때 인터넷이 필요합니다.</p>
        <p>아이콘: <a href="https://lucide.dev/">Lucide</a> 0.468.0 (ISC / MIT). 원문 라이선스를 함께 배포합니다.</p>
        <h3>키보드</h3><p>Ctrl+K 검색 · F5 새로고침 · Enter 기사 보기 · Esc 목록으로<br>
        지도: + / − 확대·축소 · Home 전국</p>
        <p>화면 색상은 시스템의 화면 모양 설정을 자동으로 따릅니다.</p>''')
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
