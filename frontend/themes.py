"""Shared visual tokens: navy, restrained orange, consistent spacing."""
from PySide6.QtGui import QColor, QPalette

LIGHT = dict(bg="#eef2f7", panel="#ffffff", text="#17253d", muted="#63718a",
             border="#dbe3ee", accent="#c86722", selected="#fff0df", map="#e8eef5", grid="#cbd6e5")
DARK = dict(bg="#111923", panel="#192434", text="#ecf2fa", muted="#a4b3c8",
            border="#304055", accent="#ffb36b", selected="#443223", map="#111e2e", grid="#283c52")


def tokens(dark: bool) -> dict:
    return DARK if dark else LIGHT


def apply_theme(app, dark: bool):
    t = tokens(dark)
    palette = QPalette()
    for role, key in ((QPalette.Window, "bg"), (QPalette.Base, "panel"),
                      (QPalette.AlternateBase, "bg"), (QPalette.WindowText, "text"),
                      (QPalette.Text, "text"), (QPalette.Button, "panel"),
                      (QPalette.ButtonText, "text"), (QPalette.Highlight, "selected"),
                      (QPalette.HighlightedText, "text"), (QPalette.ToolTipBase, "panel"),
                      (QPalette.ToolTipText, "text")):
        palette.setColor(role, QColor(t[key]))
    app.setPalette(palette)
    app.setStyleSheet("""
    QWidget { font-family: "Malgun Gothic", "Noto Sans CJK KR", "Segoe UI", sans-serif;
              font-size: 13px; color: %(text)s; }
    QMainWindow, QDialog { background: %(bg)s; }
    QFrame#panel, QWidget#panel { background: %(panel)s; border: 1px solid %(border)s;
                               border-radius: 12px; }
    QLabel { background: transparent; }
    QLabel#brand { font-size: 23px; font-weight: 800; }
    QLabel#heading { font-size: 20px; font-weight: 700; }
    QLabel#muted { color: %(muted)s; }
    QLabel#badge { color: %(accent)s; font-weight: 700; padding: 5px; }
    QLineEdit, QComboBox { background: %(panel)s; border: 1px solid %(border)s;
                          border-radius: 7px; padding: 9px; min-height: 18px; }
    QPushButton { background: %(panel)s; border: 1px solid %(border)s;
                  border-radius: 7px; padding: 8px 12px; min-height: 18px; }
    QPushButton:hover { border-color: %(accent)s; }
    QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 2px solid %(accent)s; }
    QPushButton:checked { background: %(selected)s; border-color: %(accent)s; }
    QPushButton:disabled { color: %(muted)s; }
    QPushButton#primary { background: %(selected)s; color: %(accent)s; font-weight: 700; }
    QListView { background: %(panel)s; border: none; outline: none; }
    QScrollArea { background: transparent; border: none; }
    QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
    QScrollBar::handle:vertical { background: %(border)s; border-radius: 3px; min-height: 25px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QSplitter::handle { background: transparent; width: 8px; }
    QStatusBar { background: %(panel)s; color: %(muted)s; }
    QToolTip { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; padding: 6px; }
    """ % t)
