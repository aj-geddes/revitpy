"""Coarse clash screening by axis-aligned bounding-box overlap over serialized Revit element dicts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from ._elements import (
    FT3_TO_M3,
    element_ref,
    filter_categories,
    option,
    point,
    rounded,
    string_list_option,
)

__all__ = ["bounding_box_clashes"]

METHOD = (
    "Axis-aligned bounding-box overlap (feet). A hit means the boxes overlap, "
    "not that the solids intersect; use it to shortlist pairs for review."
)


def bounding_box_clashes(
    elements: list[Any], options: Mapping[str, Any]
) -> dict[str, Any]:
    """
    Perform coarse clash screening by axis-aligned bounding-box overlap.

    Args:
        elements: List of serialized Revit element dicts with optional "bounding_box".
        options: Configuration options:
            - categories: list[str] to filter elements by category
            - tolerance_ft: float >= 0, minimum overlap required per axis (default 0.0)
            - ignore_same_category: bool, skip pairs in same category (default False)
            - max_results: int >= 1, max clashes to return (default 500)

    Returns:
        Clash report dict with counts, clash details, and metadata.
    """
    # Parse options with validation
    tolerance_ft = option(options, "tolerance_ft", 0.0, float)
    if tolerance_ft < 0:
        raise ValueError("tolerance_ft must be >= 0")

    ignore_same_category = option(options, "ignore_same_category", False, bool)
    max_results = option(options, "max_results", 500, int)
    if max_results < 1:
        raise ValueError("max_results must be >= 1")

    # Filter elements by categories if specified
    elements = filter_categories(elements, string_list_option(options, "categories"))

    # Extract bounding boxes and element metadata
    valid_boxes = []
    skipped_without_box = 0

    for el in elements:
        try:
            # Get element reference info
            ref = element_ref(el)
            el_id = ref["id"]
            el_name = ref["name"]
            el_category = ref["category"]

            # Get bounding box
            bbox = el.get("bounding_box")
            if bbox is None:
                skipped_without_box += 1
                continue

            min_pt = point(bbox.get("min"))
            max_pt = point(bbox.get("max"))

            if min_pt is None or max_pt is None:
                skipped_without_box += 1
                continue

            # Validate box geometry: min <= max on all axes
            if not (
                min_pt[0] <= max_pt[0]
                and min_pt[1] <= max_pt[1]
                and min_pt[2] <= max_pt[2]
            ):
                skipped_without_box += 1
                continue

            valid_boxes.append(
                {
                    "id": el_id,
                    "name": el_name,
                    "category": el_category,
                    "min": min_pt,
                    "max": max_pt,
                }
            )
        except Exception:
            skipped_without_box += 1
            continue

    checked = len(valid_boxes)

    # Sort boxes by min_x for sweep algorithm
    valid_boxes.sort(key=lambda b: b["min"][0])

    # Find clashes using sweep algorithm
    clashes = []
    by_category_pair: dict[str, int] = defaultdict(int)

    for i in range(len(valid_boxes)):
        box_i = valid_boxes[i]
        min_i = box_i["min"]
        max_i = box_i["max"]

        # Sweep j > i while box_j.min_x < box_i.max_x - tolerance
        j = i + 1
        while j < len(valid_boxes):
            box_j = valid_boxes[j]
            min_j = box_j["min"]
            max_j = box_j["max"]

            # Stop if box_j starts too far right to overlap with box_i
            if min_j[0] >= max_i[0] - tolerance_ft:
                break

            # Skip same element id
            if box_i["id"] is not None and box_i["id"] == box_j["id"]:
                j += 1
                continue

            # Skip same category if requested
            if ignore_same_category and box_i["category"] == box_j["category"]:
                j += 1
                continue

            # Compute overlaps on each axis
            overlaps = []
            for k in range(3):
                overlap = min(max_i[k], max_j[k]) - max(min_i[k], min_j[k])
                overlaps.append(overlap)

            # Check if all overlaps exceed tolerance (must be > tolerance, not >=)
            if all(o > tolerance_ft for o in overlaps):
                # Calculate overlap volume
                overlap_vol_ft3 = overlaps[0] * overlaps[1] * overlaps[2]
                overlap_vol_m3 = overlap_vol_ft3 * FT3_TO_M3

                # Build overlap bounding box
                overlap_min = [max(min_i[k], min_j[k]) for k in range(3)]
                overlap_max = [min(max_i[k], max_j[k]) for k in range(3)]

                # Create clash record
                cat_i = (
                    box_i["category"]
                    if box_i["category"] is not None
                    else "<No Category>"
                )
                cat_j = (
                    box_j["category"]
                    if box_j["category"] is not None
                    else "<No Category>"
                )
                pair_key = f"{min(cat_i, cat_j)} x {max(cat_i, cat_j)}"
                by_category_pair[pair_key] += 1

                clash = {
                    "a_id": box_i["id"],
                    "a_category": box_i["category"],
                    "a_name": box_i["name"],
                    "b_id": box_j["id"],
                    "b_category": box_j["category"],
                    "b_name": box_j["name"],
                    "overlap_ft3": rounded(overlap_vol_ft3, 4),
                    "overlap_m3": rounded(overlap_vol_m3, 4),
                    "overlap_min": [rounded(v, 4) for v in overlap_min],
                    "overlap_max": [rounded(v, 4) for v in overlap_max],
                }
                clashes.append(clash)

            j += 1

    # Sort clashes by overlap_ft3 descending, then a_id, then b_id
    clashes.sort(
        key=lambda c: (-c["overlap_ft3"], _id_key(c["a_id"]), _id_key(c["b_id"]))
    )

    # Truncate to max_results
    truncated = len(clashes) > max_results
    kept_clashes = clashes[:max_results]

    return {
        "clash_count": len(clashes),
        "clashes": kept_clashes,
        "truncated": truncated,
        "checked": checked,
        "skipped_without_box": skipped_without_box,
        "by_category_pair": dict(by_category_pair),
        "tolerance_ft": tolerance_ft,
        "method": METHOD,
    }


def _id_key(element_id: Any) -> tuple[int, str]:
    """Sort key for ids that may be missing or of mixed types."""
    if isinstance(element_id, int):
        return (0, f"{element_id:020d}")
    return (1, str(element_id))
