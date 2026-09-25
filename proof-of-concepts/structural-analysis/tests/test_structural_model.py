"""structural_analysis against the demo model through the RevitPy API."""

from __future__ import annotations

import pytest
from poc_common import StructuralFraming, build_demo_building, connect
from structural_analysis import run
from structural_analysis.model_data import members


@pytest.fixture
def app():
    return build_demo_building()


def test_members_are_typed_and_lengths_converted(app):
    frame = members(connect(app))
    assert (frame["kind"] == "beam").sum() == 36
    assert (frame["kind"] == "column").sum() == 45
    beams = frame[frame["kind"] == "beam"]
    assert beams["length_m"].to_numpy() == pytest.approx([7.5] * 36)
    columns = frame[frame["kind"] == "column"]
    assert columns["length_m"].to_numpy() == pytest.approx([4.0] * 45)


def test_undersized_beams_fail_and_are_reported(app):
    report = run(app)
    failing = report.checks[~report.checks["passes"]]
    assert set(failing["name"]) == {"B-301", "B-302"}
    assert set(failing["governing"]) == {"bending"}
    comment = (
        app.ActiveDocument.GetElement(int(failing["element_id"].iloc[0]))
        .GetParameterValue("Comments")
        .value
    )
    assert comment.startswith("Demo check FAILS")


def test_upsizing_in_a_transaction_fixes_the_failures(app):
    api = connect(app)
    with api.transaction("Upsize beams"):
        for beam in api.query(StructuralFraming).execute():
            if beam.get_parameter_value("Section") == "W14x22":
                beam.set_parameter_value("Section", "W18x35")
    report = run(app, write=False)
    assert report.checks["passes"].all()


def test_ground_floor_interior_column_axial_load(app):
    report = run(app, dead_kpa=4.0, live_kpa=2.5, write=False)
    checks = report.checks
    ground = checks[(checks["kind"] == "column") & (checks["level"] == "Level 1")]
    # Interior column: 75 m2 tributary x 6.5 kPa x 3 floors = 1462.5 kN on a
    # W10x49, governed by squash load (A = 14.4 in2; A fy / 1.67 = 1917 kN).
    worst = ground["utilization"].max()
    capacity_kn = 14.4 * 0.00064516 * 345e3 / 1.67
    assert worst == pytest.approx(1462.5 / capacity_kn, rel=1e-3)
    assert set(ground["governing"]) == {"yield"}


def test_lateral_results_are_consistent(app):
    report = run(app, write=False)
    assert len(report.periods_s) == 3
    assert report.periods_s[0] > report.periods_s[1] > report.periods_s[2] > 0
    assert 0 < report.roof_drift_mm < report.drift_limit_mm
    # Steel mass from section weights: 36 x 7.5 m W16x26/W14x22 plus columns.
    assert 15.0 < report.steel_tonnes < 25.0
