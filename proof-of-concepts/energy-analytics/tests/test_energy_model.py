"""energy_analytics against the demo model through the RevitPy API."""

from __future__ import annotations

import pandas as pd
import pytest
from energy_analytics import run
from energy_analytics.model_data import (
    envelope_table,
    flag_upgrade_candidates,
    gross_floor_area_m2,
)
from poc_common import FT2_TO_M2, build_demo_building, connect
from poc_common.timeseries import hourly_weather, metered_energy


@pytest.fixture
def app():
    return build_demo_building()


def comments(app, element_id: int) -> str:
    return app.ActiveDocument.GetElement(element_id).GetParameterValue("Comments").value


def test_envelope_reads_exterior_walls_and_windows_in_metric(app):
    envelope = envelope_table(connect(app))
    # 4 facades x 3 levels of exterior walls and of windows; partitions excluded.
    assert (envelope["kind"] == "wall").sum() == 12
    assert (envelope["kind"] == "window").sum() == 12
    # Each level's envelope is the 100 m perimeter x 4 m storey height.
    per_level = envelope.groupby("level")["area_m2"].sum()
    assert per_level.to_numpy() == pytest.approx([400.0] * 3)
    raw = app.ActiveDocument.GetElementsByCategory("Windows")[0]
    row = envelope.set_index("element_id").loc[raw.Id.IntegerValue]
    assert row["area_m2"] == pytest.approx(
        raw.GetParameterValue("Area").value * FT2_TO_M2
    )


def test_gross_floor_area(app):
    assert gross_floor_area_m2(connect(app)) == pytest.approx(3 * 600.0)


def test_run_flags_only_poor_elements_and_writes_comments(app):
    report = run(app, days=120)
    assert set(report.candidates["u_value_w_m2k"]) == {1.6, 5.7}
    # 8 original-envelope walls (levels 2-3) and 2 single-glazed windows.
    assert report.flagged == len(report.candidates) == 10
    worst = report.candidates.iloc[0]
    assert "U=5.70" in comments(app, int(worst["element_id"]))
    # Level 1 (refurbished) is untouched.
    level1 = app.ActiveDocument.GetElementsByCategory("Walls")[0]
    assert comments(app, level1.Id.IntegerValue) == ""


def test_meter_regression_recovers_the_model_heat_loss(app):
    report = run(app, write=False)
    assert report.change_point.r2 > 0.85
    assert report.metered_ua_w_per_k == pytest.approx(report.model_ua_w_per_k, rel=0.1)
    assert report.flagged == 0


def test_run_uses_supplied_meter_data(app):
    metered = metered_energy(hourly_weather(days=60, seed=3), 900.0, 1800.0, seed=3)
    report = run(app, metered=metered, write=False)
    assert len(report.daily) == 60
    assert not any("synthetic" in note for note in report.notes)


def test_embodied_carbon_uses_extracted_volumes(app):
    report = run(app, days=30, write=False)
    # Concrete slabs alone: 3 x 600 m2 x 0.25 m x ICE v2.0 concrete 256.8 kgCO2e/m3.
    assert report.carbon.by_material["Concrete"] > 3 * 150.0 * 256.8
    assert report.carbon_benchmark.target_kgco2e_per_m2 == 350.0


def test_write_back_is_atomic(app):
    api = connect(app)
    envelope = envelope_table(api)
    candidates = envelope.head(3).assign(heat_loss_w_per_k=[1.0, 2.0, "bad"])
    with pytest.raises(ValueError):
        flag_upgrade_candidates(api, candidates)
    # The failure on the third element rolled back the first two writes.
    for element_id in candidates["element_id"]:
        assert comments(app, int(element_id)) == ""


def test_html_dashboard(app, tmp_path):
    out = tmp_path / "energy.html"
    run(app, days=30, write=False, html=out)
    assert "plotly" in out.read_text(encoding="utf-8").lower()


def test_report_text(app):
    text = run(app, days=30, write=False).to_text()
    assert "Envelope heat loss" in text
    assert isinstance(run(app, days=30, write=False).daily, pd.DataFrame)
