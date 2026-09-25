"""Map sensors to rooms and write readings back to the model."""

from __future__ import annotations

import pandas as pd
from poc_common import param

from revitpy import RevitAPI
from revitpy.api import Room

SENSOR_PARAMETER = "Sensor ID"


def sensor_rooms(api: RevitAPI) -> pd.DataFrame:
    """Rooms that carry a ``Sensor ID``, indexed by sensor id."""
    rows = [
        {
            "sensor_id": str(sensor),
            "room_id": room.id.value,
            "room": room.name,
            "level": param(room, "Level", "(no level)"),
        }
        for room in api.query(Room).execute()
        if (sensor := param(room, SENSOR_PARAMETER)) is not None
    ]
    return pd.DataFrame(
        rows, columns=["sensor_id", "room_id", "room", "level"]
    ).set_index("sensor_id")


def write_room_status(
    api: RevitAPI, rooms: pd.DataFrame, latest: pd.DataFrame, alarmed: set[str]
) -> int:
    """Write each room's latest reading into ``Comments`` in one transaction.

    Revit API calls must run on Revit's main thread: call this after the
    asyncio loop has finished (as :func:`iot_monitor.run` does), or from a
    background thread via ``revitpy.revit.host.call_on_revit_thread``.
    """
    written = 0
    with api.transaction("Update room sensor status"):
        for sensor_id, reading in latest.iterrows():
            if sensor_id not in rooms.index:
                continue
            room = api.get_element_by_id(int(rooms.loc[sensor_id, "room_id"]))
            if room is None:
                continue
            status = "ALARM" if sensor_id in alarmed else "ok"
            room.set_parameter_value(
                "Comments",
                f"{sensor_id} {status}: {reading.temperature_c:.1f} C, "
                f"{reading.co2_ppm:.0f} ppm CO2, {reading.humidity_pct:.0f}% RH "
                f"@ {pd.Timestamp(reading.timestamp):%Y-%m-%d %H:%M}",
            )
            written += 1
    return written
