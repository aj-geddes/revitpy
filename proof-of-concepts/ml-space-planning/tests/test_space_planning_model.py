"""space_planning against the demo model through the RevitPy API."""

from __future__ import annotations

import pytest
from poc_common import ROOM_SCHEDULE, build_demo_building, connect
from space_planning import run
from space_planning.model_data import room_table


@pytest.fixture
def app():
    return build_demo_building()


def test_room_table_converts_areas_and_reads_capacity(app):
    rooms = room_table(connect(app))
    assert len(rooms) == 3 * len(ROOM_SCHEDULE)
    first = rooms[rooms["name"] == "Open Office A 101"].iloc[0]
    assert first["area_m2"] == pytest.approx(180.0)
    assert first["capacity"] == 24
    assert first["base_name"] == "Open Office A"
    assert first["level"] == "Level 1"


def test_clusters_recover_the_underused_rooms(app):
    report = run(app, write=False)
    names = report.rooms.set_index("room_id")["base_name"]
    underused = {
        names[i]
        for i in report.clusters.labels[report.clusters.labels == "underused"].index
    }
    assert underused == {s.name for s in ROOM_SCHEDULE if s.profile == "underused"}
    assert report.clusters.silhouette > 0.5


def test_forecast_beats_or_matches_last_week(app):
    report = run(app, write=False)
    assert report.forecast.mae_model <= report.forecast.mae_naive
    assert len(report.forecast.predictions) == 7 * 24


def test_assignment_uses_shared_rooms_that_fit(app):
    report = run(app, write=False)
    rooms = report.rooms.set_index("room_id")
    assigned = rooms.loc[report.assignment["room_id"]]
    assert set(assigned["department"]) == {"Shared"}
    assert (report.assignment["capacity"] >= report.assignment["headcount"]).all()
    assert report.assignment["room_id"].is_unique


def test_run_writes_utilization_to_comments(app):
    report = run(app)
    assert report.written == 24
    doc = app.ActiveDocument
    room_id = int(report.clusters.labels.index[0])
    text = doc.GetElement(room_id).GetParameterValue("Comments").value
    assert text.startswith(f"Utilization: {report.clusters.labels.iloc[0]}")
