"""iot_monitor against the demo model through the RevitPy API."""

from __future__ import annotations

import asyncio

import pytest
from iot_monitor import monitor, replay, run
from iot_monitor.analysis import StreamingAnomalyDetector
from iot_monitor.model_data import sensor_rooms
from poc_common import build_demo_building, connect
from poc_common.timeseries import sensor_readings


@pytest.fixture
def app():
    return build_demo_building()


def test_sensor_rooms_maps_every_room(app):
    rooms = sensor_rooms(connect(app))
    assert len(rooms) == 24
    assert rooms.loc["S-101", "room"] == "Open Office A 101"


def test_only_the_faulty_sensor_alarms(app):
    report = run(app)
    assert report.alarmed_sensors == {"S-205"}
    assert set(report.alarm_summary["kind"]) == {"anomaly", "threshold"}
    doc = app.ActiveDocument
    for sensor, row in report.rooms.iterrows():
        text = doc.GetElement(int(row["room_id"])).GetParameterValue("Comments").value
        assert text.startswith(f"{sensor} {'ALARM' if sensor == 'S-205' else 'ok'}")


def test_clean_feed_raises_no_alarms(app):
    readings = sensor_readings(["S-101", "S-102"], steps=288, seed=7)
    report = run(app, readings=readings, write=False)
    assert report.alarms == []
    assert report.readings == len(readings)
    assert report.written == 0


def test_async_replay_preserves_order_and_count():
    readings = sensor_readings(["a", "b", "c"], steps=24, seed=1)
    seen = []

    async def collect():
        async for batch in replay(readings):
            seen.append(batch["timestamp"].iloc[0])

    asyncio.run(collect())
    assert seen == sorted(readings["timestamp"].unique())
    alarms, count = asyncio.run(monitor(replay(readings), StreamingAnomalyDetector()))
    assert count == len(readings)
