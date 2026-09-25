"""Read rooms from the model and write utilization results back."""

from __future__ import annotations

import re

import pandas as pd
from poc_common import FT2_TO_M2, number, param

from revitpy import RevitAPI
from revitpy.api import Room

ROOM_COLUMNS = [
    "room_id",
    "name",
    "base_name",
    "level",
    "department",
    "area_m2",
    "capacity",
]


def room_table(api: RevitAPI) -> pd.DataFrame:
    """Rooms with area (m2), design capacity (``Occupancy``) and department."""
    rows = []
    for room in api.query(Room).execute():
        name = room.name
        rows.append(
            {
                "room_id": room.id.value,
                "name": name,
                # "Meeting Small 203" -> "Meeting Small"
                "base_name": re.sub(r"\s+\d+$", "", name),
                "level": param(room, "Level", "(no level)"),
                "department": param(room, "Department", "(none)"),
                "area_m2": number(room, "Area") * FT2_TO_M2,
                "capacity": int(number(room, "Occupancy")),
            }
        )
    return pd.DataFrame(rows, columns=ROOM_COLUMNS)


def write_utilization(api: RevitAPI, features: pd.DataFrame, labels: pd.Series) -> int:
    """Write the utilization class into each room's ``Comments`` (one transaction)."""
    with api.transaction("Record room utilization"):
        for room_id, label in labels.items():
            room = api.get_element_by_id(int(room_id))
            if room is None:
                continue
            row = features.loc[room_id]
            room.set_parameter_value(
                "Comments",
                f"Utilization: {label} (mean {row.mean_utilization:.0%}, "
                f"peak {row.peak_utilization:.0%})",
            )
    return len(labels)
