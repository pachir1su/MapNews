"""Malformed location and bounded-loading error regressions."""
from dataclasses import replace
from threading import Event

from frontend.models import NewsBatch
from frontend.state import FilterState, NewsState
from frontend.workers import LoadWorker


def test_empty_location_remains_safe_under_region_filter(window):
    item = replace(window.state.items[0], id="empty-location", location="")
    state = NewsState(items=(item,), filters=FilterState(region="서울특별시"))
    assert state.visible() == []
    window._loaded(NewsBatch((item,)))
    assert window.model.rowCount() == 1
    assert window.region.itemText(0) == "전체 지역"


def test_unknown_region_does_not_crash_or_display_wrong_items(window):
    item = replace(window.state.items[0], id="region-not-provided", location="")
    state = NewsState(items=(item,), filters=FilterState(region="서울특별시"))
    assert state.visible() == []
    state.filters.region = ""
    assert [n.id for n in state.visible()] == [item.id]


def test_worker_error_reports_current_32mib_limit(qtbot):
    class RejectingProvider:
        def load(self, cancel: Event):
            raise ValueError("JSON shape")
    worker = LoadWorker(RejectingProvider())
    messages = []
    worker.failed.connect(messages.append)
    worker.run()
    assert len(messages) == 1
    assert "32 MiB" in messages[0] and "10,000건" in messages[0]


def test_worker_json_error_does_not_expose_untrusted_traceback(qtbot):
    class RejectingProvider:
        def load(self, cancel: Event):
            raise ValueError("API_SECRET=never-print-me")
    worker = LoadWorker(RejectingProvider())
    messages = []
    worker.failed.connect(messages.append)
    worker.run()
    assert len(messages) == 1
    assert "API_SECRET" not in messages[0]
