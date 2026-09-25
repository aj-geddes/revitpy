"""Round trip: pyRevit client (under CPython) -> real Live Server -> analyses."""

from __future__ import annotations

import inspect
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import revitpy_bridge
from bridge_fakes import make_wall
from revitpy_bridge import (
    AnalysisFailed,
    AuthenticationFailed,
    BridgeError,
    LiveServerNotRunning,
    RevitPyBridge,
    RpcError,
    UnknownAnalysis,
    serialize_elements,
)

from revitpy.revit import live

BRIDGE_ANALYSES = {
    "bounding_box_clashes",
    "element_summary",
    "embodied_carbon",
    "parameter_statistics",
    "quantity_takeoff",
}

OFF_MAIN_THREAD = "main_thread" in inspect.signature(live.register_analysis).parameters


@pytest.fixture
def failing_analysis() -> Any:
    @live.register_analysis("bridge_test_fails", replace=True)
    def fails(elements: list[Any], options: dict[str, Any], uiapp: Any) -> Any:
        raise RuntimeError(f"deliberate failure in {len(elements)} elements")

    yield "bridge_test_fails"
    live.unregister_analysis("bridge_test_fails")


class TestRoundTrip:
    def test_status_and_list(self, live_server: dict[str, str]) -> None:
        bridge = RevitPyBridge(timeout=30)
        status = bridge.status()
        assert status["protocol"] == 1
        assert status["document"] == "Tower.rvt"
        names = bridge.list_analyses()
        assert BRIDGE_ANALYSES <= set(names)
        assert names == sorted(names)

    def test_serialized_elements(self, live_server: dict[str, str]) -> None:
        payload = serialize_elements([make_wall(1), make_wall(2, x0=100)])
        json.dumps(payload)  # what goes over the wire
        result = RevitPyBridge().analyze("quantity_takeoff", payload)
        walls = result["groups"]["Walls"]
        assert walls["count"] == 2
        assert walls["area_ft2"] == pytest.approx(600, abs=1e-3)
        assert walls["volume_ft3"] == pytest.approx(400, abs=1e-3)
        assert walls["length_ft"] == pytest.approx(60, abs=1e-3)

    def test_revit_elements_are_serialized_automatically(
        self, live_server: dict[str, str]
    ) -> None:
        bridge = RevitPyBridge()
        summary = bridge.analyze("element_summary", [make_wall(1), make_wall(2)])
        assert summary["by_category"] == {"Walls": 2}
        assert summary["by_level"] == {"Level 1": 2}
        carbon = bridge.analyze("embodied_carbon", [make_wall(1)])
        assert carbon["materials"][0]["material"] == "Concrete, Cast-in-Place"
        assert carbon["total_kgco2e"] > 0

    def test_clashes_and_options(self, live_server: dict[str, str]) -> None:
        overlapping = [make_wall(1), make_wall(2, x0=20)]
        result = RevitPyBridge().analyze("bounding_box_clashes", overlapping)
        assert result["clash_count"] == 1
        filtered = RevitPyBridge().analyze(
            "bounding_box_clashes", overlapping, {"ignore_same_category": True}
        )
        assert filtered["clash_count"] == 0

    def test_invalid_option_is_analysis_failure(
        self, live_server: dict[str, str]
    ) -> None:
        with pytest.raises(AnalysisFailed) as excinfo:
            RevitPyBridge().analyze("quantity_takeoff", [], {"group_by": "phase"})
        assert excinfo.value.analysis == "quantity_takeoff"
        assert "group_by" in excinfo.value.details

    def test_failing_analysis(
        self, live_server: dict[str, str], failing_analysis: str
    ) -> None:
        with pytest.raises(AnalysisFailed) as excinfo:
            RevitPyBridge().analyze(failing_analysis, [{"id": 1}])
        assert "deliberate failure in 1 elements" in excinfo.value.details
        assert "deliberate failure" in str(excinfo.value)

    def test_unknown_analysis(self, live_server: dict[str, str]) -> None:
        with pytest.raises(UnknownAnalysis) as excinfo:
            RevitPyBridge().analyze("no_such_analysis", [])
        assert excinfo.value.code == -32602
        assert isinstance(excinfo.value, RpcError)

    def test_rpc_error(self, live_server: dict[str, str]) -> None:
        with pytest.raises(RpcError) as excinfo:
            RevitPyBridge().call("live/nope")
        assert excinfo.value.code == -32601
        assert not isinstance(excinfo.value, UnknownAnalysis)

    def test_explicit_url_and_token(self, live_server: dict[str, str]) -> None:
        bridge = RevitPyBridge(url=live_server["url"], token=live_server["token"])
        assert bridge.status()["protocol"] == 1

    def test_rereads_discovery_after_restart(self, live_server: dict[str, str]) -> None:
        bridge = RevitPyBridge()
        assert bridge.status()["protocol"] == 1
        live.stop_live_server()
        from bridge_support import UIAPP

        live.start_live_server(UIAPP, port=0, token="another-token")
        assert bridge.status()["protocol"] == 1


@pytest.mark.skipif(
    not OFF_MAIN_THREAD,
    reason="this revitpy's register_analysis has no main_thread option",
)
def test_analyses_run_while_revit_main_thread_is_busy(busy_live_server: Any) -> None:
    """A pyRevit button holds Revit's main thread while it waits for the reply."""
    started = time.monotonic()
    result = RevitPyBridge(timeout=20).analyze("element_summary", [make_wall(1)])
    assert result["element_count"] == 1
    assert time.monotonic() - started < 10
    assert busy_live_server.posted == 0  # never queued for the main thread


class TestErrors:
    def test_not_running(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REVITPY_LIVE_DISCOVERY", str(tmp_path / "none.json"))
        with pytest.raises(LiveServerNotRunning, match="not running"):
            RevitPyBridge().list_analyses()

    def test_invalid_discovery_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "live.json"
        path.write_text("{not json", encoding="utf-8")
        monkeypatch.setenv("REVITPY_LIVE_DISCOVERY", str(path))
        with pytest.raises(LiveServerNotRunning):
            RevitPyBridge().status()
        path.write_text(json.dumps({"url": "ws://x"}), encoding="utf-8")
        with pytest.raises(LiveServerNotRunning):
            RevitPyBridge().status()

    def test_unsupported_protocol(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "live.json"
        path.write_text(
            json.dumps({"url": "ws://x", "token": "t", "protocol": 99}),
            encoding="utf-8",
        )
        monkeypatch.setenv("REVITPY_LIVE_DISCOVERY", str(path))
        with pytest.raises(BridgeError, match="99"):
            RevitPyBridge().status()

    def test_discovery_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("REVITPY_LIVE_DISCOVERY", raising=False)
        assert revitpy_bridge.discovery_path() == os.path.join(
            os.path.expanduser("~"), ".revitpy", "live.json"
        )
        monkeypatch.setenv("REVITPY_LIVE_DISCOVERY", "/x/live.json")
        assert revitpy_bridge.discovery_path() == "/x/live.json"

    def test_wrong_token(self, live_server: dict[str, str]) -> None:
        bridge = RevitPyBridge(url=live_server["url"], token="wrong")
        with pytest.raises(AuthenticationFailed):
            bridge.status()

    def test_server_gone(self) -> None:
        bridge = RevitPyBridge(url="ws://127.0.0.1:1", token="t", timeout=5)
        with pytest.raises(LiveServerNotRunning, match="not running"):
            bridge.status()

    def test_no_websocket_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in ("websockets", "websockets.sync", "websockets.sync.client", "clr"):
            monkeypatch.setitem(sys.modules, name, None)
        with pytest.raises(BridgeError, match="websockets"):
            RevitPyBridge(url="ws://127.0.0.1:1", token="t").status()
