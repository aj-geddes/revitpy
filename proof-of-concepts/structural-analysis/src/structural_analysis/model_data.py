"""Read structural members and levels from the model; write check results back."""

from __future__ import annotations

import pandas as pd
from poc_common import (
    FT2_TO_M2,
    FT_TO_M,
    StructuralColumn,
    StructuralFraming,
    number,
    param,
)

from revitpy import RevitAPI
from revitpy.api import Floor, Level
from revitpy.extract import QuantityExtractor, QuantityType

MEMBER_COLUMNS = [
    "element_id",
    "name",
    "kind",
    "level",
    "section",
    "length_m",
    "tributary_width_m",
    "tributary_area_m2",
]


def levels(api: RevitAPI) -> pd.DataFrame:
    """Levels sorted by elevation (m)."""
    rows = [
        {"level": lvl.name, "elevation_m": number(lvl, "Elevation") * FT_TO_M}
        for lvl in api.query(Level).execute()
    ]
    return (
        pd.DataFrame(rows, columns=["level", "elevation_m"])
        .sort_values("elevation_m")
        .reset_index(drop=True)
    )


def floor_areas(api: RevitAPI) -> pd.Series:
    """Floor area (m2) per level."""
    rows = [
        (param(f, "Level", "(no level)"), number(f, "Area") * FT2_TO_M2)
        for f in api.query(Floor).execute()
    ]
    return (
        pd.DataFrame(rows, columns=["level", "area_m2"])
        .groupby("level")["area_m2"]
        .sum()
    )


def members(api: RevitAPI) -> pd.DataFrame:
    """Beams and columns with section, length (m) and tributary data.

    ``QuantityExtractor`` reads each member's ``Length`` parameter and
    converts feet to metres.
    """
    elements = [
        *api.query(StructuralFraming).execute().to_list(),
        *api.query(StructuralColumn).execute().to_list(),
    ]
    lengths = {
        item.element_id.value: item.value
        for item in QuantityExtractor().extract(elements, [QuantityType.LENGTH])
    }
    rows = [
        {
            "element_id": e.id.value,
            "name": e.name,
            "kind": "column" if isinstance(e, StructuralColumn) else "beam",
            "level": param(e, "Level", "(no level)"),
            "section": param(e, "Section", ""),
            "length_m": lengths.get(e.id.value, 0.0),
            "tributary_width_m": number(e, "Tributary Width") * FT_TO_M,
            "tributary_area_m2": number(e, "Tributary Area") * FT2_TO_M2,
        }
        for e in elements
    ]
    return pd.DataFrame(rows, columns=MEMBER_COLUMNS)


def write_checks(api: RevitAPI, checks: pd.DataFrame) -> int:
    """Write each member's utilization into ``Comments`` in one transaction."""
    with api.transaction("Record member checks"):
        for row in checks.itertuples(index=False):
            element = api.get_element_by_id(int(row.element_id))
            if element is None:
                continue
            verdict = "OK" if row.passes else "FAILS"
            element.set_parameter_value(
                "Comments",
                f"Demo check {verdict}: utilization {row.utilization:.2f} "
                f"({row.governing})",
            )
    return len(checks)
