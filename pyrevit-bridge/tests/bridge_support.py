"""Paths, the fake Revit UIApplication and fake main-thread dispatchers."""

from __future__ import annotations

import sys
import types
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

BRIDGE_DIR = Path(__file__).resolve().parents[1]
EXTENSION_DIR = BRIDGE_DIR / "RevitPyBridge.extension"
LIB_DIR = EXTENSION_DIR / "lib"
ANALYSES_SRC = BRIDGE_DIR / "analyses" / "src"


def add_import_paths() -> None:
    """Make revitpy_bridge (extension lib) and the analyses package importable."""
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    try:
        import revitpy_bridge_analyses  # noqa: F401
    except ImportError:
        sys.path.insert(0, str(ANALYSES_SRC))


UIAPP = types.SimpleNamespace(
    ActiveUIDocument=types.SimpleNamespace(
        Document=types.SimpleNamespace(Title="Tower.rvt")
    ),
    Application=types.SimpleNamespace(VersionNumber="2026"),
)


class _Request:
    def __init__(self) -> None:
        self.IsCompleted = False
        self.Succeeded = False
        self.Result: Any = None
        self.Error: str | None = None


class FakeDispatcher:
    """Runs posted callables on a single 'Revit main thread' (as in test_live)."""

    def __init__(self, uiapp: Any) -> None:
        self._pool = ThreadPoolExecutor(1, thread_name_prefix="revit-main")
        self._uiapp = uiapp

    def Post(self, func: Callable[[Any], Any]) -> _Request:
        request = _Request()

        def run() -> None:
            try:
                request.Result = func(self._uiapp)
                request.Succeeded = True
            except Exception as exc:
                request.Error = repr(exc)
            request.IsCompleted = True

        self._pool.submit(run)
        return request

    def close(self) -> None:
        self._pool.shutdown(wait=True)


class BusyMainThreadDispatcher:
    """Revit's main thread held by the caller: posted work never runs.

    This is the situation of a pyRevit button waiting for its reply.
    """

    def __init__(self) -> None:
        self.posted = 0

    def Post(self, func: Callable[[Any], Any]) -> _Request:
        self.posted += 1
        return _Request()

    def close(self) -> None:
        pass
