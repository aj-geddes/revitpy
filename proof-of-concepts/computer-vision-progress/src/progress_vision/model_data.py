"""Read the facade panel grid from the model; write detected status back."""

from __future__ import annotations

import re

import pandas as pd
from poc_common import GenericModel, param

from revitpy import RevitAPI
from revitpy.extract import QuantityExtractor, QuantityType

# Panels are marked FP-<row>-<col>, row 0 being the lowest row.
MARK_PATTERN = re.compile(r"^FP-(\d+)-(\d+)$")


def facade_panels(api: RevitAPI) -> pd.DataFrame:
    """Facade panels with grid position, level and volume (m3)."""
    panels = [
        (element, match)
        for element in api.query(GenericModel).execute()
        if (match := MARK_PATTERN.match(str(param(element, "Mark", ""))))
    ]
    volumes = {
        item.element_id.value: item.value
        for item in QuantityExtractor().extract(
            [element for element, _ in panels], [QuantityType.VOLUME]
        )
    }
    rows = [
        {
            "element_id": element.id.value,
            "mark": match.group(0),
            "row": int(match.group(1)),
            "col": int(match.group(2)),
            "level": param(element, "Level", "(no level)"),
            "volume_m3": volumes.get(element.id.value, 0.0),
        }
        for element, match in panels
    ]
    columns = ["element_id", "mark", "row", "col", "level", "volume_m3"]
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values(["row", "col"])
        .reset_index(drop=True)
    )


def write_status(api: RevitAPI, panels: pd.DataFrame, photo_label: str) -> int:
    """Record each panel's detected status in ``Comments`` (one transaction)."""
    with api.transaction("Record facade progress"):
        for row in panels.itertuples(index=False):
            element = api.get_element_by_id(int(row.element_id))
            if element is None:
                continue
            status = "installed" if row.installed else "not installed"
            element.set_parameter_value(
                "Comments",
                f"{status} per {photo_label} (confidence {row.confidence:.2f})",
            )
    return len(panels)
