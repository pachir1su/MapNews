import pytest
from PySide6.QtCore import QCoreApplication, QSettings, Qt
from frontend.main_window import MainWindow

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)


@pytest.fixture
def window(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / 'test.ini'), QSettings.IniFormat)
    window = MainWindow(settings=settings)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.batch is not None, timeout=10000)
    qtbot.waitUntil(lambda: not window.worker.isRunning(), timeout=10000)
    yield window
    window.close()
