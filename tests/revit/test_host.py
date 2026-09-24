"""Tests for revitpy.revit.host with a simulated RevitPy host dispatcher."""

from __future__ import annotations

import asyncio
import builtins
import json
import threading
import types
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
import websockets

import revitpy.revit.host as host


class FakeRequest:
    def __init__(self) -> None:
        self.IsCompleted = False
        self.Succeeded = False
        self.Result: Any = None
        self.Error: str | None = None


class FakeDispatcher:
    """Runs posted callables on a dedicated 'Revit main thread'."""

    def __init__(self, uiapp: Any, delay_forever: bool = False) -> None:
        self._uiapp = uiapp
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="revit")
        self._delay_forever = delay_forever
        self.posted = 0

    def Post(self, func: Callable[[Any], Any]) -> FakeRequest:
        self.posted += 1
        request = FakeRequest()
        if self._delay_forever:
            return request

        def run() -> None:
            try:
                request.Result = func(self._uiapp)
                request.Succeeded = True
            except Exception as e:
                request.Error = f"Traceback: {e!r}"
            request.IsCompleted = True

        self._executor.submit(run)
        return request

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)


UIAPP = types.SimpleNamespace(
    ActiveUIDocument=None, Application=types.SimpleNamespace(), name="uiapp"
)


@pytest.fixture
def dispatcher(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeDispatcher]:
    fake = FakeDispatcher(UIAPP)
    monkeypatch.setattr(builtins, "__revitpy_dispatcher__", fake, raising=False)
    monkeypatch.setattr(host, "_ui_application", None)
    yield fake
    fake.shutdown()


def run_in_worker(func: Callable[[], Any]) -> Any:
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(func).result(timeout=10)


class TestCallOnRevitThread:
    def test_dispatches_from_worker_thread(self, dispatcher: FakeDispatcher) -> None:
        def call() -> Any:
            return host.call_on_revit_thread(
                lambda uiapp: (uiapp.name, threading.current_thread().name)
            )

        name, thread_name = run_in_worker(call)
        assert name == "uiapp"
        assert thread_name.startswith("revit")
        assert dispatcher.posted == 1
        assert host.in_revit_host()

    def test_errors_are_raised(self, dispatcher: FakeDispatcher) -> None:
        def fail(_uiapp: Any) -> None:
            raise ValueError("bad")

        with pytest.raises(host.RevitThreadError, match="bad"):
            run_in_worker(lambda: host.call_on_revit_thread(fail))

    def test_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stuck = FakeDispatcher(UIAPP, delay_forever=True)
        monkeypatch.setattr(builtins, "__revitpy_dispatcher__", stuck, raising=False)
        with pytest.raises(TimeoutError):
            run_in_worker(lambda: host.call_on_revit_thread(lambda _: 1, timeout=0.05))

    def test_outside_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delattr(builtins, "__revitpy_dispatcher__", raising=False)
        assert not host.in_revit_host()
        with pytest.raises(host.RevitHostUnavailableError):
            run_in_worker(lambda: host.call_on_revit_thread(lambda _: 1))

    def test_main_thread_runs_directly(self, dispatcher: FakeDispatcher) -> None:
        with pytest.raises(host.RevitHostUnavailableError):
            host.call_on_revit_thread(lambda _: 1)
        host.set_ui_application(UIAPP)
        assert host.call_on_revit_thread(lambda uiapp: uiapp.name) == "uiapp"
        assert dispatcher.posted == 0


class TestConfirmation:
    def test_denies_when_dialog_unavailable(self, dispatcher: FakeDispatcher) -> None:
        tool = types.SimpleNamespace(name="modify_parameter")
        # No Revit UI assemblies here, so showing the dialog fails -> deny.
        assert run_in_worker(lambda: host.revit_confirmation(tool, {})) is False


async def _rpc(url: str, token: str, method: str, params: dict[str, Any]) -> Any:
    headers = {"Authorization": f"Bearer {token}"}
    major = int(websockets.__version__.split(".")[0])
    if major >= 14:
        connection = websockets.connect(url, additional_headers=headers)
    else:
        connection = websockets.connect(url, extra_headers=headers)
    async with connection as ws:
        await ws.send(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        )
        return json.loads(await ws.recv())


class TestMcpServerLifecycle:
    def test_start_call_stop(self, dispatcher: FakeDispatcher) -> None:
        status = host.start_mcp_server(UIAPP, port=0, token="secret-token")
        try:
            assert host.is_mcp_server_running()
            assert "Bearer secret-token" in status
            assert host.start_mcp_server(UIAPP) == status  # idempotent

            url = status.splitlines()[0].rsplit(" ", 1)[-1]
            listed = asyncio.run(_rpc(url, "secret-token", "tools/list", {}))
            names = {t["name"] for t in listed["result"]["tools"]}
            assert "query_elements" in names

            called = asyncio.run(
                _rpc(
                    url,
                    "secret-token",
                    "tools/call",
                    {"name": "query_elements", "arguments": {"category": "Walls"}},
                )
            )
            # No active document: the tool reports it instead of faking data,
            # and it ran on the simulated Revit thread.
            assert called["result"]["isError"] is True
            assert "Not connected" in called["result"]["content"][0]["text"]
            assert dispatcher.posted >= 1
        finally:
            assert host.stop_mcp_server() == "RevitPy MCP server stopped."
        assert not host.is_mcp_server_running()
        assert host.mcp_server_status() == "RevitPy MCP server is not running."

    def test_toggle(
        self, dispatcher: FakeDispatcher, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REVITPY_MCP_PORT", "0")
        assert "running at" in host.toggle_mcp_server(UIAPP)
        assert host.toggle_mcp_server(UIAPP) == "RevitPy MCP server stopped."
