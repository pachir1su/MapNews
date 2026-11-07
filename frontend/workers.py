"""One bounded background load at a time. Never terminate a running QThread."""
from threading import Event
import json
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
                if isinstance(error, json.JSONDecodeError):
                    message = f'JSON {error.lineno}행 {error.colno}열을 확인해 주세요.'
                elif isinstance(error, UnicodeError):
                    message = 'UTF-8로 저장한 JSON 파일을 열어 주세요.'
                elif isinstance(error, FileNotFoundError):
                    message = '파일을 찾을 수 없어요. 다른 파일을 선택해 주세요.'
                elif isinstance(error, PermissionError):
                    message = '이 파일을 읽을 권한이 없어요.'
                elif isinstance(error, ValueError):
                    message = 'JSON 배열 형식과 파일 크기를 확인해 주세요. 최대 8 MiB·10,000건입니다.'
                else:
                    message = '뉴스를 불러오지 못했어요. 다시 시도해 주세요.'
                self.failed.emit(message)
