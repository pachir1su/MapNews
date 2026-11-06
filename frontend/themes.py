"""Quiet surfaces and semantic colors. The OS alone chooses the appearance."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

LIGHT = dict(bg="#f2f4f6", panel="#ffffff", text="#191f28", muted="#6b7684",
             border="#e5e8eb", accent="#1b64da", selected="#edf4ff", map="#edf1f5",
             grid="#d3dae2", land="#ffffff", neighbor="#e3e8ed", province="#8f9dad",
             district="#c1ccd8", primary="#3182f6", input="#f2f4f6")
DARK = dict(bg="#101215", panel="#191b20", text="#f2f4f6", muted="#a2aab6",
            border="#30343b", accent="#85b8ff", selected="#203451", map="#121820",
            grid="#303b49", land="#252e3a", neighbor="#1b232e", province="#8393a8",
            district="#435368", primary="#266ddb", input="#262a32")


def system_is_dark(scheme):
    # Unknown is a deterministic light fallback on platforms without appearance reporting.
    return scheme == Qt.ColorScheme.Dark


def tokens(dark: bool) -> dict:
    return DARK if dark else LIGHT


def apply_theme(app, dark: bool):
    t = dict(tokens(dark))
    t["chevron"] = (Path(__file__).parent / "resources" / "chevron.svg").as_posix()
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
              font-size: 14px; color: %(text)s; }
    QMainWindow, QDialog { background: %(bg)s; }
    QFrame#panel, QWidget#panel { background: %(panel)s; border: none; border-radius: 16px; }
    QFrame#header { background: %(panel)s; border: none; }
    QLabel { background: transparent; }
    QWidget#detailContent { background: %(panel)s; }
    QLabel#brand { font-size: 23px; font-weight: 700; }
    QLabel#heading { font-size: 20px; font-weight: 700; }
    QLabel#muted { color: %(muted)s; }
    QLabel#articleTitle { font-size: 24px; font-weight: 700; }
    QLabel#summary { font-size: 15px; }
    QLabel#badge { color: %(accent)s; font-weight: 600; }
    QLabel#source { color: %(muted)s; background: %(input)s; border-radius: 6px; padding: 4px 8px; font-size: 12px; }
    QLabel#notice { background: %(selected)s; color: %(text)s; border-radius: 10px; padding: 10px 16px; }
    QLineEdit, QComboBox { background: %(input)s; border: 1px solid transparent;
                          border-radius: 10px; padding: 9px 12px; min-height: 20px; }
    QComboBox { padding-right: 26px; }
    QComboBox::drop-down { border: none; width: 24px; }
    QComboBox::down-arrow { image: url("%(chevron)s"); width: 14px; height: 14px; }
    QPushButton, QToolButton { background: %(input)s; border: 1px solid transparent;
                  border-radius: 10px; padding: 9px 12px; min-height: 20px; }
    QPushButton:hover, QToolButton:hover { background: %(selected)s; }
    QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 2px solid %(accent)s; }
    QPushButton:checked { background: %(selected)s; color: %(accent)s; font-weight: 600; }
    QPushButton#quiet { background: transparent; color: %(muted)s; }
    QToolButton::menu-indicator { image: none; }
    QPushButton:disabled { color: %(muted)s; }
    QPushButton#primary { background: %(primary)s; color: white; font-weight: 600; }
    QPushButton#primary:disabled { background: %(input)s; color: %(muted)s; }
    QMenu { background: %(panel)s; border: 1px solid %(border)s; padding: 6px; }
    QMenu::item { padding: 10px 20px; border-radius: 6px; }
    QMenu::item:selected { background: %(selected)s; }
    QMenu::item:disabled { color: %(muted)s; }
    QListView { background: %(panel)s; border: none; outline: none; }
    QScrollArea { background: transparent; border: none; }
    QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
    QScrollBar::handle:vertical { background: %(border)s; border-radius: 3px; min-height: 25px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QSplitter::handle { background: transparent; width: 8px; }
    QToolTip { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; padding: 6px; }
    """ % t)
