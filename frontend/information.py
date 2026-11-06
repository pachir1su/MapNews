"""Secondary explanations belong here, away from everyday map exploration."""
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QTextBrowser


class InformationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("지도 및 데이터 정보")
        self.resize(540, 500)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml('''<h2>MapNews</h2>
        <p>한국기술교육대학교 창의적공학설계 5조</p>
        <h3>시연 데이터</h3>
        <p>데모 뉴스 20개는 가상 기사입니다. 좌표는 발생 지역의 대표 위치이며 실제 사건 지점이 아닙니다.
        실제 기사 원문은 제공하지 않습니다.</p>
        <h3>지도</h3>
        <p>기본 지도와 행정구역 경계는 인터넷 없이 표시합니다. 도로 정보는 제공하지 않습니다.
        시·도 경계는 항상, 시·군·구 경계는 확대 시 표시합니다.</p>
        <p>행정구역: 2026년 10월 1일 기준 스냅샷. 통계청 SGIS(공공누리 제1유형)의
        행정동 경계를 가공한 vuski/admdongkor(CC BY 4.0) 자료를 사용합니다.
        표시용으로 경계를 단순화하고 시·도 및 시·군·구로 합쳤습니다.</p>
        <p><a href="https://sgis.kostat.go.kr/">통계청 SGIS</a> ·
        <a href="https://github.com/vuski/admdongkor">vuski/admdongkor</a> ·
        <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> ·
        <a href="https://www.naturalearthdata.com/">Natural Earth (public domain)</a></p>
        <p>온라인 지도: © OpenStreetMap contributors.
        배경 타일을 불러올 때 인터넷이 필요합니다.</p>
        <h3>키보드</h3><p>Ctrl+K 검색 · F5 새로고침 · Ctrl+Enter 기사 보기<br>
        지도: + / − 확대·축소 · Home 전국</p>
        <p>화면 색상은 시스템의 화면 모양 설정을 자동으로 따릅니다.</p>''')
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
