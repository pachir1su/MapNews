"""Backend boundary. Implement load(cancel); use bounded I/O and check cancellation."""
import json
from pathlib import Path
from threading import Event
from typing import Protocol
from .models import NewsBatch, parse_news

RESOURCES = Path(__file__).resolve().parent / "resources"


class NewsProvider(Protocol):
    label: str

    def load(self, cancel: Event) -> NewsBatch: ...


class JsonNewsProvider:
    label = "외부 JSON · 진위 미검증"

    def __init__(self, path: str | Path, *, is_mock: bool = False):
        self.path = Path(path)
        self.is_mock = is_mock
        if is_mock:
            self.label = "MOCK · 외부 시연 데이터"

    def load(self, cancel: Event) -> NewsBatch:
        if cancel.is_set():
            return NewsBatch((), source=self.label)
        # Bound memory and parsing work; read bytes once to avoid stat/read races.
        with self.path.open("rb") as stream:
            raw = stream.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("JSON 파일은 8 MiB 이하여야 합니다.")
        payload = json.loads(raw.decode("utf-8-sig"))
        return parse_news(payload, is_mock=self.is_mock, source=self.label)


class MockNewsProvider:
    label = "MOCK · 시연 데이터 20건"

    def load(self, cancel: Event) -> NewsBatch:
        if cancel.is_set():
            return NewsBatch((), source=self.label)
        payload = json.loads((RESOURCES / "dummy_news.json").read_text(encoding="utf-8"))
        coordinates = json.loads((RESOURCES / "demo_coordinates.json").read_text(encoding="utf-8"))
        return parse_news(payload, is_mock=True, coordinates=coordinates, source=self.label)
