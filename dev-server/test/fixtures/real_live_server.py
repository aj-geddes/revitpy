"""Run the real RevitPy Live Server outside Revit, for the dev-server integration test.

Revit's main-thread dispatcher is replaced by a single worker thread (the same
approach as tests/revit/test_live.py). The server writes its discovery file to
REVITPY_LIVE_DISCOVERY, prints ``READY <url>`` and runs until stdin closes.

Exit code 3 with ``SKIP: ...`` on stdout means revitpy is not importable.
"""

from __future__ import annotations

import builtins
import json
import os
import sys
import types
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

try:
    from revitpy.revit import live
except Exception as exc:  # revitpy (or one of its dependencies) is missing
    print(f"SKIP: cannot import revitpy.revit.live ({exc!r})", flush=True)
    sys.exit(3)


class _Request:
    def __init__(self) -> None:
        self.IsCompleted = False
        self.Succeeded = False
        self.Result: Any = None
        self.Error: str | None = None


class FakeDispatcher:
    """Runs posted callables on one 'Revit main thread'."""

    def __init__(self, uiapp: Any) -> None:
        self._pool = ThreadPoolExecutor(1, thread_name_prefix="revit-main")
        self._uiapp = uiapp

    def Post(self, func: Callable[[Any], Any]) -> _Request:  # noqa: N802 - Revit API name
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


UIAPP = types.SimpleNamespace(
    ActiveUIDocument=types.SimpleNamespace(
        Document=types.SimpleNamespace(Title="DevServer.rvt")
    ),
    Application=types.SimpleNamespace(VersionNumber="2026"),
)


def main() -> int:
    if not os.environ.get("REVITPY_LIVE_DISCOVERY"):
        print("REVITPY_LIVE_DISCOVERY must be set", file=sys.stderr)
        return 2
    token = os.environ.get("REVITPY_LIVE_TOKEN", "dev-server-test-token")
    dispatcher = FakeDispatcher(UIAPP)
    builtins.__revitpy_dispatcher__ = dispatcher  # type: ignore[attr-defined]
    live.start_live_server(UIAPP, host="127.0.0.1", port=0, token=token)
    try:
        with open(live.discovery_path(), encoding="utf-8") as stream:
            print(f"READY {json.load(stream)['url']}", flush=True)
        sys.stdin.read()  # the test closes stdin (or kills us) to stop
    finally:
        live.stop_live_server()
        dispatcher.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
