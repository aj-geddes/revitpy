"""End-to-end tests of the Live Server, its client and ``revitpy live``."""

from __future__ import annotations

import builtins
import json
import os
import threading
import types
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from revitpy.cli import main
from revitpy.live_client import (
    LiveClient,
    LiveConnectionInfo,
    LiveServerError,
    LiveServerNotFoundError,
    call_live,
)
from revitpy.revit import host, live


class _Request:
    def __init__(self) -> None:
        self.IsCompleted = False
        self.Succeeded = False
        self.Result: Any = None
        self.Error: str | None = None


class FakeDispatcher:
    """Runs posted callables on a single 'Revit main thread'."""

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


UIAPP = types.SimpleNamespace(
    ActiveUIDocument=types.SimpleNamespace(
        Document=types.SimpleNamespace(Title="Tower.rvt")
    ),
    Application=types.SimpleNamespace(VersionNumber="2026"),
)


@pytest.fixture
def server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[LiveConnectionInfo]:
    discovery = tmp_path / "live.json"
    monkeypatch.setenv("REVITPY_LIVE_DISCOVERY", str(discovery))
    dispatcher = FakeDispatcher(UIAPP)
    monkeypatch.setattr(builtins, "__revitpy_dispatcher__", dispatcher, raising=False)
    monkeypatch.setattr(host, "_ui_application", None)

    live.start_live_server(UIAPP, port=0, token="test-token")
    try:
        yield LiveConnectionInfo.from_discovery()
    finally:
        live.stop_live_server()
        dispatcher.close()
        for name in ("live_helper_mod",):
            import sys

            sys.modules.pop(name, None)


class TestLifecycle:
    def test_discovery_file(self, server: LiveConnectionInfo) -> None:
        data = json.loads(Path(os.environ["REVITPY_LIVE_DISCOVERY"]).read_text())
        assert data["protocol"] == live.PROTOCOL_VERSION
        assert data["token"] == "test-token"
        assert data["revit_version"] == "2026"
        assert data["url"] == server.url
        if os.name != "nt":
            mode = Path(os.environ["REVITPY_LIVE_DISCOVERY"]).stat().st_mode
            assert mode & 0o777 == 0o600

    def test_stop_removes_discovery(self, server: LiveConnectionInfo) -> None:
        path = Path(os.environ["REVITPY_LIVE_DISCOVERY"])
        assert live.is_live_server_running()
        assert live.stop_live_server() == "RevitPy Live Server stopped."
        assert not path.exists()
        assert live.live_server_status() == "RevitPy Live Server is not running."

    def test_start_twice_is_idempotent(self, server: LiveConnectionInfo) -> None:
        assert server.url in live.start_live_server(UIAPP)

    def test_token_required(self) -> None:
        with pytest.raises(ValueError):
            live.LiveServer(auth_token="")


class TestMethods:
    def test_status(self, server: LiveConnectionInfo) -> None:
        status = call_live("live/status")
        assert status["protocol"] == 1
        assert status["revit_version"] == "2026"
        assert status["document"] == "Tower.rvt"
        assert status["debug"] == {"listening": False, "port": None}

    def test_execute_on_revit_thread(self, server: LiveConnectionInfo) -> None:
        result = call_live(
            "live/execute",
            {
                "code": "import threading\n"
                "print(threading.current_thread().name)\n"
                "print(__revit__.ActiveUIDocument.Document.Title, __name__)"
            },
        )
        assert result["success"] is True
        thread_name, title_line = result["output"].strip().splitlines()
        assert thread_name.startswith("revit-main")
        assert title_line == "Tower.rvt __main__"

    def test_script_errors_are_results(self, server: LiveConnectionInfo) -> None:
        result = call_live("live/execute", {"code": "1/0"})
        assert result["success"] is False
        assert "ZeroDivisionError" in result["error"]

    def test_system_exit_zero_is_success(self, server: LiveConnectionInfo) -> None:
        ok = call_live("live/execute", {"code": "raise SystemExit(0)"})
        failed = call_live("live/execute", {"code": "raise SystemExit(3)"})
        assert ok["success"] is True
        assert failed["success"] is False

    def test_run_file_and_reload(
        self, server: LiveConnectionInfo, tmp_path: Path
    ) -> None:
        helper = tmp_path / "live_helper_mod.py"
        script = tmp_path / "main.py"
        helper.write_text("VALUE = 1\n")
        script.write_text("import live_helper_mod\nprint(live_helper_mod.VALUE)\n")

        assert call_live("live/runFile", {"path": str(script)})["output"] == "1\n"

        helper.write_text("VALUE = 2\n")
        result = call_live("live/reload", {"paths": [str(helper)]})
        assert result == {"reloaded": ["live_helper_mod"], "errors": {}}
        assert call_live("live/runFile", {"path": str(script)})["output"] == "2\n"

    def test_reload_unknown_module(self, server: LiveConnectionInfo) -> None:
        result = call_live("live/reload", {"modules": ["never_imported_xyz"]})
        assert result["errors"] == {"never_imported_xyz": "not imported"}

    def test_run_file_missing(self, server: LiveConnectionInfo, tmp_path: Path) -> None:
        with pytest.raises(LiveServerError) as excinfo:
            call_live("live/runFile", {"path": str(tmp_path / "missing.py")})
        assert excinfo.value.code == -32602

    @pytest.mark.parametrize(
        ("method", "params"),
        [
            ("live/execute", {}),
            ("live/execute", {"code": 5}),
            ("live/reload", {"modules": "x"}),
            ("live/reload", {"paths": [1]}),
            ("debug/start", {"port": "x"}),
        ],
    )
    def test_invalid_params(
        self, server: LiveConnectionInfo, method: str, params: dict[str, Any]
    ) -> None:
        with pytest.raises(LiveServerError) as excinfo:
            call_live(method, params)
        assert excinfo.value.code == -32602

    def test_unknown_method(self, server: LiveConnectionInfo) -> None:
        with pytest.raises(LiveServerError) as excinfo:
            call_live("live/nope")
        assert excinfo.value.code == -32601

    def test_debug_without_debugpy(
        self, server: LiveConnectionInfo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        monkeypatch.setitem(sys.modules, "debugpy", None)
        result = call_live("debug/start", {"port": 0})
        assert result["listening"] is False
        assert "debugpy" in result["error"]

    def test_debug_start(
        self, server: LiveConnectionInfo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sys

        calls: list[Any] = []
        fake = types.SimpleNamespace(
            configure=lambda **kw: calls.append(("configure", kw)),
            listen=lambda addr: (calls.append(("listen", addr)), ("127.0.0.1", 5999))[
                1
            ],
        )
        monkeypatch.setitem(sys.modules, "debugpy", fake)
        assert call_live("debug/start", {"port": 5999}) == {
            "listening": True,
            "port": 5999,
        }
        assert ("listen", ("127.0.0.1", 5999)) in calls
        assert call_live("live/status")["debug"] == {"listening": True, "port": 5999}


class TestAnalyses:
    @pytest.fixture(autouse=True)
    def analysis(self) -> Iterator[None]:
        @live.register_analysis("test_count")
        def count(elements: list[Any], options: dict[str, Any], uiapp: Any) -> Any:
            if options.get("fail"):
                raise RuntimeError("analysis failed")
            return {
                "count": len(elements),
                "thread": threading.current_thread().name,
                "document": uiapp.ActiveUIDocument.Document.Title,
            }

        yield
        live.unregister_analysis("test_count")

    def test_list_and_analyze(self, server: LiveConnectionInfo) -> None:
        assert "test_count" in call_live("bridge/listAnalyses")["analyses"]
        result = call_live(
            "bridge/analyze", {"analysis": "test_count", "elements": [{"id": 1}] * 3}
        )
        assert result["success"] is True
        assert result["result"]["count"] == 3
        assert result["result"]["document"] == "Tower.rvt"
        assert result["result"]["thread"].startswith("revit-main")

    def test_analysis_errors_are_results(self, server: LiveConnectionInfo) -> None:
        result = call_live(
            "bridge/analyze", {"analysis": "test_count", "options": {"fail": True}}
        )
        assert result["success"] is False
        assert "analysis failed" in result["error"]

    def test_unknown_analysis(self, server: LiveConnectionInfo) -> None:
        with pytest.raises(LiveServerError) as excinfo:
            call_live("bridge/analyze", {"analysis": "nope"})
        assert excinfo.value.code == -32602

    def test_duplicate_registration(self) -> None:
        with pytest.raises(ValueError):
            live.register_analysis("test_count")(lambda e, o, u: None)
        live.register_analysis("test_count", replace=True)(lambda e, o, u: None)


class TestClient:
    def test_wrong_token_is_a_clean_error(self, server: LiveConnectionInfo) -> None:
        with pytest.raises(LiveServerError, match="refused"):
            call_live(
                "live/status", info=LiveConnectionInfo(url=server.url, token="wrong")
            )

    def test_no_discovery_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REVITPY_LIVE_DISCOVERY", str(tmp_path / "none.json"))
        with pytest.raises(LiveServerNotFoundError, match="not running"):
            LiveConnectionInfo.from_discovery()

    def test_unsupported_protocol(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "live.json"
        path.write_text(json.dumps({"url": "ws://x", "token": "t", "protocol": 99}))
        monkeypatch.setenv("REVITPY_LIVE_DISCOVERY", str(path))
        with pytest.raises(LiveServerError, match="protocol 99"):
            LiveConnectionInfo.from_discovery()

    def test_server_gone(self, tmp_path: Path) -> None:
        info = LiveConnectionInfo(url="ws://127.0.0.1:1", token="t")
        with pytest.raises(LiveServerNotFoundError, match="Cannot reach"):
            call_live("live/status", info=info)

    async def test_async_client_multiple_calls(
        self, server: LiveConnectionInfo
    ) -> None:
        async with LiveClient() as client:
            assert (await client.status())["protocol"] == 1
            result = await client.execute("print(40 + 2)")
            assert result["output"] == "42\n"
            assert "test_count" not in await client.list_analyses()

    async def test_client_requires_context(self, server: LiveConnectionInfo) -> None:
        with pytest.raises(RuntimeError):
            await LiveClient().call("live/status")


class TestCli:
    def test_status(self, server: LiveConnectionInfo) -> None:
        result = CliRunner().invoke(main, ["live", "status"])
        assert result.exit_code == 0, result.output
        assert "Revit 2026" in result.output
        assert "Tower.rvt" in result.output

    def test_exec_and_failure_exit_code(self, server: LiveConnectionInfo) -> None:
        ok = CliRunner().invoke(main, ["live", "exec", "print('hello')"])
        assert (ok.exit_code, ok.output) == (0, "hello\n")
        bad = CliRunner().invoke(main, ["live", "exec", "1/0"])
        assert bad.exit_code == 1

    def test_run_and_reload(self, server: LiveConnectionInfo, tmp_path: Path) -> None:
        helper = tmp_path / "live_helper_mod.py"
        helper.write_text("VALUE = 'a'\n")
        script = tmp_path / "go.py"
        script.write_text("import live_helper_mod\nprint(live_helper_mod.VALUE)\n")
        runner = CliRunner()
        assert runner.invoke(main, ["live", "run", str(script)]).output == "a\n"
        helper.write_text("VALUE = 'b'\n")
        reload = runner.invoke(main, ["live", "reload", str(helper)])
        assert reload.exit_code == 0 and "reloaded live_helper_mod" in reload.output
        assert runner.invoke(main, ["live", "run", str(script)]).output == "b\n"

    def test_not_running(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REVITPY_LIVE_DISCOVERY", str(tmp_path / "none.json"))
        result = CliRunner().invoke(main, ["live", "status"])
        assert result.exit_code == 1
        assert "not running" in result.output


def test_analysis_plugins_load_from_entry_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from importlib import metadata

    loaded: list[str] = []

    class FakeEntryPoint:
        def __init__(self, name: str, fail: bool = False) -> None:
            self.name, self._fail = name, fail

        def load(self) -> None:
            if self._fail:
                raise ImportError("broken plugin")
            loaded.append(self.name)

    def fake_entry_points(*, group: str) -> list[FakeEntryPoint]:
        assert group == live.ANALYSIS_ENTRY_POINT_GROUP
        return [FakeEntryPoint("good"), FakeEntryPoint("bad", fail=True)]

    monkeypatch.setattr(metadata, "entry_points", fake_entry_points)
    assert live.load_analysis_plugins() == ["good"]
    assert loaded == ["good"]


def test_worker_thread_analysis_runs_while_main_thread_is_busy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pyRevit button holds Revit's main thread while it waits for the reply.

    Main-thread analyses cannot start then; ``main_thread=False`` ones must.
    """

    class BusyMainThread:
        def Post(self, func: Callable[[Any], Any]) -> _Request:
            return _Request()  # never runs: the main thread is blocked

    monkeypatch.setenv("REVITPY_LIVE_DISCOVERY", str(tmp_path / "live.json"))
    monkeypatch.setattr(
        builtins, "__revitpy_dispatcher__", BusyMainThread(), raising=False
    )

    @live.register_analysis("worker_count", main_thread=False)
    def worker_count(elements: list[Any], options: dict[str, Any], uiapp: Any) -> Any:
        return {"count": len(elements), "uiapp": uiapp is None}

    @live.register_analysis("main_count")
    def main_count(elements: list[Any], options: dict[str, Any], uiapp: Any) -> Any:
        return len(elements)

    server = None
    try:
        live.start_live_server(UIAPP, port=0, token="t")
        server = True
        result = call_live(
            "bridge/analyze", {"analysis": "worker_count", "elements": [1, 2]}
        )
        assert result == {"success": True, "result": {"count": 2, "uiapp": True}}

        live._handle.server._execute_timeout = 0.2  # type: ignore[union-attr]
        blocked = call_live("bridge/analyze", {"analysis": "main_count"})
        assert blocked["success"] is False
        assert "Timed out" in blocked["error"]
    finally:
        if server:
            live.stop_live_server()
        live.unregister_analysis("worker_count")
        live.unregister_analysis("main_count")
