"""Smoke test: every proof of concept runs as ``python -m <package>`` and exits 0."""

from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

import pytest

ENTRY_POINTS = {
    "energy_analytics": "Envelope heat loss",
    "space_planning": "Room clusters",
    "iot_monitor": "Alarms",
    "structural_analysis": "Beam checks",
    "progress_vision": "Progress",
}


@pytest.mark.parametrize("module", sorted(ENTRY_POINTS))
def test_entry_point_runs(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", module],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "demo model" in result.stdout
    assert ENTRY_POINTS[module] in result.stdout


def test_common_demo_model_is_a_revitpy_mock() -> None:
    from poc_common import build_demo_building, connect

    from revitpy.api import Room, Wall
    from revitpy.testing.mock_revit import MockApplication

    app = build_demo_building()
    assert isinstance(app, MockApplication)
    api = connect(app)
    assert len(api.query(Room).execute()) == 24
    walls = api.query(Wall).execute()
    assert {w.get_parameter_value("Function") for w in walls} == {
        "Exterior",
        "Interior",
    }


EXAMPLES = sorted(
    Path(__file__).resolve().parents[1].glob("*/examples/run_in_revit.py")
)


@pytest.mark.parametrize("script", EXAMPLES, ids=lambda p: p.parent.parent.name)
def test_in_revit_example_runs_with_revit_bound(
    script: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The in-Revit scripts run as __main__ with __revit__ bound, as the host does."""
    from poc_common import build_demo_building

    app = build_demo_building()
    runpy.run_path(str(script), init_globals={"__revit__": app}, run_name="__main__")
    out = capsys.readouterr().out
    assert "RevitPy Demo Office.rvt" in out
    assert "Wrote" in out  # results were written back to the model


def test_all_five_examples_found() -> None:
    assert len(EXAMPLES) == 5
