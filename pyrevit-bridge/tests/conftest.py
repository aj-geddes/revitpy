"""Fixtures for the pyRevit bridge tests.

``revitpy_bridge`` (the pyRevit-side module) lives in the sample extension's
``lib`` folder, as pyRevit expects, so it is put on ``sys.path`` here. The
RevitPy-side package is used from its source tree when it is not installed.
"""

from __future__ import annotations

import builtins
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from bridge_support import (
    UIAPP,
    BusyMainThreadDispatcher,
    FakeDispatcher,
    add_import_paths,
)

add_import_paths()

from revitpy.revit import host, live  # noqa: E402


def _start_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dispatcher: Any
) -> Iterator[dict[str, str]]:
    discovery = tmp_path / "live.json"
    monkeypatch.setenv("REVITPY_LIVE_DISCOVERY", str(discovery))
    monkeypatch.setattr(builtins, "__revitpy_dispatcher__", dispatcher, raising=False)
    monkeypatch.setattr(host, "_ui_application", None)

    from revitpy_bridge_analyses.analyses import register_all

    register_all()
    live.start_live_server(UIAPP, port=0, token="test-token")
    try:
        yield json.loads(discovery.read_text(encoding="utf-8"))
    finally:
        live.stop_live_server()
        dispatcher.close()


@pytest.fixture
def live_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, str]]:
    """A real Live Server with a fake Revit main thread; yields the discovery data."""
    yield from _start_server(tmp_path, monkeypatch, FakeDispatcher(UIAPP))


@pytest.fixture
def busy_live_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[BusyMainThreadDispatcher]:
    """A real Live Server whose Revit main thread never becomes free."""
    dispatcher = BusyMainThreadDispatcher()
    for _ in _start_server(tmp_path, monkeypatch, dispatcher):
        yield dispatcher
