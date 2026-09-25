"""
Quantity take-off module for Revit element dictionaries.

Reads Revit element dictionaries and extracts area, volume, and length quantities
using built-in parameter names first (for non-English Revit compatibility), then English names.

Built-in parameter names (in order of precedence):
- AREA: HOST_AREA_COMPUTED, ROOM_AREA
- VOLUME: HOST_VOLUME_COMPUTED, ROOM_VOLUME
- LENGTH: CURVE_ELEM_LENGTH

English parameter names (fallback):
- AREA: Area
- VOLUME: Volume
- LENGTH: Length

All values are in Revit internal units (ft, ft², ft³) and converted to metric (m, m², m³).
Imperial equivalents are included in output for reference.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

from revitpy.extract import QuantityExtractor
from revitpy.extract.types import AggregationLevel, QuantityType

from ._elements import (
    FT2_TO_M2,
    FT3_TO_M3,
    FT_TO_M,
    filter_categories,
    is_number,
    numeric_value,
    option,
    rounded,
    string_list_option,
    text,
)

__all__ = [
    "AREA_PARAMETERS",
    "LENGTH_PARAMETERS",
    "VOLUME_PARAMETERS",
    "quantity_takeoff",
]

AREA_PARAMETERS = (("HOST_AREA_COMPUTED", "ROOM_AREA"), ("Area",))
VOLUME_PARAMETERS = (("HOST_VOLUME_COMPUTED", "ROOM_VOLUME"), ("Volume",))
LENGTH_PARAMETERS = (("CURVE_ELEM_LENGTH",), ("Length",))
_GROUP_BY = {
    "category": AggregationLevel.CATEGORY,
    "level": AggregationLevel.LEVEL,
    "element": AggregationLevel.ELEMENT,
    "building": AggregationLevel.BUILDING,
}


def quantity_takeoff(elements: list[Any], options: Mapping[str, Any]) -> dict[str, Any]:
    """
    Perform quantity take-off on a list of Revit element dictionaries.

    Args:
        elements: List of Revit element dictionaries with keys: id, name, category, level, parameters, location.
        options: Configuration options including:
            - categories: list[str] to filter elements by category
            - group_by: str, one of "category", "level", "element", "building" (default: "category")

    Returns:
        Dictionary with grouping results, totals, element counts, and metadata.

    Raises:
        ValueError: If group_by option is invalid.
    """
    # Validate and extract group_by option
    group_by_key = option(options, "group_by", "category", str).lower()
    if group_by_key not in _GROUP_BY:
        raise ValueError(
            f"Invalid group_by value '{group_by_key}'. "
            f"Valid values are: {', '.join(sorted(_GROUP_BY.keys()))}"
        )
    group_by_level = _GROUP_BY[group_by_key]

    # Filter elements by categories if specified
    filtered = filter_categories(elements, string_list_option(options, "categories"))

    # Process elements and extract quantities
    items: list[SimpleNamespace] = []
    elements_without_quantities: list[int] = []

    for el in filtered:
        # Extract numeric values in ft units
        area_ft2 = numeric_value(
            el, builtins=AREA_PARAMETERS[0], names=AREA_PARAMETERS[1]
        )
        volume_ft3 = numeric_value(
            el, builtins=VOLUME_PARAMETERS[0], names=VOLUME_PARAMETERS[1]
        )
        length_ft = numeric_value(
            el, builtins=LENGTH_PARAMETERS[0], names=LENGTH_PARAMETERS[1]
        )

        # Handle length from location if not found via parameters
        if length_ft is None:
            location = el.get("location")
            if isinstance(location, dict) and location.get("type") == "curve":
                loc_length = location.get("length")
                if is_number(loc_length):
                    length_ft = float(loc_length)

        # Convert to metric units (keep None if not found)
        area_m2 = area_ft2 * FT2_TO_M2 if area_ft2 is not None else None
        volume_m3 = volume_ft3 * FT3_TO_M3 if volume_ft3 is not None else None
        length_m = length_ft * FT_TO_M if length_ft is not None else None

        # Check if element has any quantity
        has_quantity = any(q is not None for q in [area_m2, volume_m3, length_m])
        if not has_quantity:
            elements_without_quantities.append(el.get("id"))

        # Create item for QuantityExtractor
        item = SimpleNamespace(
            id=el.get("id"),
            name=text(el, "name", str(el.get("id"))),
            category=text(el, "category", "<No Category>"),
            level=text(el, "level", ""),
            system="",
            area=area_m2,
            volume=volume_m3,
            length=length_m,
        )
        items.append(item)

    # Perform extraction using QuantityExtractor
    grouped = QuantityExtractor().extract_grouped(
        items,
        group_by=group_by_level,
        quantity_types=[
            QuantityType.AREA,
            QuantityType.VOLUME,
            QuantityType.LENGTH,
            QuantityType.COUNT,
        ],
    )

    groups: dict[str, dict[str, Any]] = {}
    totals = dict.fromkeys(_TOTAL_KEYS, 0.0)
    for key in sorted(grouped):
        sums = dict.fromkeys(_TOTAL_KEYS, 0.0)
        for item in grouped[key]:
            sums[_SUM_KEY[item.quantity_type]] += item.value
        for name, value in sums.items():
            totals[name] += value
        groups[key] = _report(sums)

    return {
        "group_by": group_by_key,
        "units": {
            "area": "m2 (ft2 also given)",
            "volume": "m3 (ft3 also given)",
            "length": "m (ft also given)",
            "source": "Revit internal units (ft, ft2, ft3) converted to metric",
        },
        "groups": groups,
        "totals": _report(totals),
        "element_count": len(filtered),
        "elements_without_quantities": elements_without_quantities,
    }


_SUM_KEY = {
    QuantityType.COUNT: "count",
    QuantityType.AREA: "area_m2",
    QuantityType.VOLUME: "volume_m3",
    QuantityType.LENGTH: "length_m",
}
_TOTAL_KEYS = ("count", "area_m2", "volume_m3", "length_m")


def _report(sums: dict[str, float]) -> dict[str, Any]:
    """Rounded metric sums plus imperial equivalents (from the unrounded sums)."""
    return {
        "count": int(sums["count"]),
        "area_m2": rounded(sums["area_m2"]),
        "volume_m3": rounded(sums["volume_m3"]),
        "length_m": rounded(sums["length_m"]),
        "area_ft2": rounded(sums["area_m2"] / FT2_TO_M2),
        "volume_ft3": rounded(sums["volume_m3"] / FT3_TO_M3),
        "length_ft": rounded(sums["length_m"] / FT_TO_M),
    }
