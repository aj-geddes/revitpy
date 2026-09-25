"""Read envelope, room and material data from the model; write results back."""

from __future__ import annotations

import pandas as pd
from poc_common import FT2_TO_M2, number, param

from revitpy import RevitAPI
from revitpy.api import Floor, Room, Wall, Window
from revitpy.extract import QuantityExtractor, QuantityType
from revitpy.sustainability import (
    BuildingCarbonSummary,
    CarbonBenchmark,
    CarbonCalculator,
    MaterialData,
)

U_VALUE = "U-Value (W/m2K)"


def envelope_table(api: RevitAPI) -> pd.DataFrame:
    """Exterior walls and windows with their area (m2) and U-value.

    Elements without a U-value are skipped: they cannot be assessed.
    """
    walls = [
        w
        for w in api.query(Wall).execute()
        if param(w, "Function", "Exterior") == "Exterior"
    ]
    windows = api.query(Window).execute().to_list()
    rows = []
    for kind, elements in (("wall", walls), ("window", windows)):
        for element in elements:
            u_value = number(element, U_VALUE, default=-1.0)
            if u_value < 0:
                continue
            rows.append(
                {
                    "element_id": element.id.value,
                    "name": element.name,
                    "kind": kind,
                    "level": param(element, "Level", "(no level)"),
                    "orientation": param(element, "Orientation", ""),
                    "area_m2": number(element, "Area") * FT2_TO_M2,
                    "u_value_w_m2k": u_value,
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "element_id",
            "name",
            "kind",
            "level",
            "orientation",
            "area_m2",
            "u_value_w_m2k",
        ],
    )


def room_table(api: RevitAPI) -> pd.DataFrame:
    """Rooms with level, area (m2) and design occupancy."""
    rows = [
        {
            "element_id": room.id.value,
            "name": room.name,
            "level": param(room, "Level", "(no level)"),
            "area_m2": number(room, "Area") * FT2_TO_M2,
            "occupancy": int(number(room, "Occupancy")),
        }
        for room in api.query(Room).execute()
    ]
    return pd.DataFrame(
        rows, columns=["element_id", "name", "level", "area_m2", "occupancy"]
    )


def gross_floor_area_m2(api: RevitAPI) -> float:
    """Sum of floor slab areas, used as the gross floor area."""
    return sum(number(f, "Area") for f in api.query(Floor).execute()) * FT2_TO_M2


def embodied_carbon(
    api: RevitAPI, floor_area_m2: float
) -> tuple[BuildingCarbonSummary, CarbonBenchmark]:
    """A1-A3 embodied carbon of walls and floors from their volume and material.

    ``QuantityExtractor`` reads each element's ``Volume`` parameter and
    converts ft3 to m3; ``CarbonCalculator`` applies the built-in generic
    (ICE v2.0) factors. Screening-level only.
    """
    elements = [
        *api.query(Wall).execute().to_list(),
        *api.query(Floor).execute().to_list(),
    ]
    by_id = {e.id.value: e for e in elements}
    items = QuantityExtractor().extract(elements, [QuantityType.VOLUME])
    materials = [
        MaterialData(
            name=str(param(by_id[item.element_id.value], "Material", "Concrete")),
            category=str(param(by_id[item.element_id.value], "Material", "Concrete")),
            volume_m3=item.value,
            element_id=str(item.element_id.value),
            level=item.level or None,
        )
        for item in items
    ]
    calculator = CarbonCalculator()
    summary = calculator.summarize(calculator.calculate(materials))
    benchmark = calculator.benchmark(summary, floor_area_m2, building_type="office")
    return summary, benchmark


def flag_upgrade_candidates(api: RevitAPI, candidates: pd.DataFrame) -> int:
    """Write a note into ``Comments`` of each candidate, in one transaction."""
    if candidates.empty:
        return 0
    with api.transaction("Flag envelope upgrade candidates"):
        for row in candidates.itertuples(index=False):
            element = api.get_element_by_id(int(row.element_id))
            if element is None:
                continue
            element.set_parameter_value(
                "Comments",
                f"Envelope upgrade candidate: U={row.u_value_w_m2k:.2f} W/m2K, "
                f"{row.heat_loss_w_per_k:.0f} W/K",
            )
    return len(candidates)
