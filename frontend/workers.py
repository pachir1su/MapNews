"""One bounded background load at a time. Never terminate a running QThread."""
from threading import Event
from PySide6.QtCore import QThread, Signal
from .providers import NewsProvider
from .models import NewsBatch


class LoadWorker(QThread):
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, provider: NewsProvider, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.cancel = Event()

    def run(self):
        try:
            batch = self.provider.load(self.cancel)
            if not isinstance(batch, NewsBatch):
                raise TypeError('Provider.load must return NewsBatch')
            if not self.cancel.is_set():
                self.loaded.emit(batch)
        except Exception as error:
            if not self.cancel.is_set():
                # No credentials or raw network exception text in the GUI.
                self.failed.emit(f"데이터를 불러오지 못했습니다 ({type(error).__name__}). "
                                 "파일 형식·경로 또는 Provider 연결을 확인하고 다시 시도하세요.")
