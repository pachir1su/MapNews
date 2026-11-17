"""Exercise the real map-visualization module from main without remote geocoding.

The CI step checks out the source module and sample JSON into a temporary folder;
nothing is copied into the frontend branch or written back to team files.
"""
import importlib.util
import json
import os
from pathlib import Path
from threading import Event

import pytest

from frontend.providers import JsonNewsProvider
from frontend.tools.export_team_news import export_news


@pytest.mark.skipif(not os.environ.get("MAPNEWS_TEAM_MAIN_DIR"),
                    reason="Requires the separate main-branch data contract CI step")
def test_current_main_map_contract_exports_to_real_qt_map(tmp_path, window, monkeypatch):
    root = Path(os.environ["MAPNEWS_TEAM_MAIN_DIR"])
    spec = importlib.util.spec_from_file_location(
        "mapnews_team_module_under_test", root / "map_visualization.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    rows = json.loads((root / "results.json").read_text(encoding="utf-8"))
    assert isinstance(rows, list) and rows
    # The repository's results are demo stories, not verified live news.
    # Provide only one known test coordinate to check data compatibility.
    first = dict(rows[0])
    first["latitude"] = 36.81
    first["longitude"] = 127.15
    sampled = [first, dict(rows[1])]
    source = tmp_path / "main-analysis.json"
    target = tmp_path / "frontend-news.json"
    source.write_text(json.dumps(sampled, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(module, "load_coordinate_cache", lambda: {})
    monkeypatch.setattr(module, "save_coordinate_cache", lambda cache: None)
    monkeypatch.setattr(module, "get_coordinates", lambda location, cache: None)

    total, mapped = export_news(source, target, module.prepare_news_for_frontend,
                                require_pins=True)
    assert (total, mapped) == (2, 1)
    batch = JsonNewsProvider(target, is_mock=True).load(Event())
    assert len(batch.items) == 2
    assert batch.items[0].has_coordinates
    assert not batch.items[1].has_coordinates
    window._loaded(batch)
    assert window.news_count.text() == "2건"
    assert len(window.map.offline.marker_by_id) == 1
