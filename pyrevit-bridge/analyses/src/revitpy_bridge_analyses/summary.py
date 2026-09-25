"""
Element summaries and parameter statistics over serialized element dicts.

Pure functions; numeric parameter values are Revit internal units (feet-based).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from ._elements import (
    NUMERIC_STORAGE,
    filter_categories,
    is_number,
    option,
    parameters,
    rounded,
    string_list_option,
)

__all__ = ["element_summary", "parameter_statistics"]


def element_summary(elements: list[Any], options: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize element distribution by category, level, and type."""
    filtered = filter_categories(elements, string_list_option(options, "categories"))

    category_counter: Counter[str] = Counter()
    level_counter: Counter[str] = Counter()
    by_type: dict[str, Counter[str]] = {}
    with_bbox = 0
    with_materials = 0
    param_names: set[str] = set()

    for elem in filtered:
        cat = elem.get("category") or "<No Category>"
        lvl = elem.get("level") or "<No Level>"
        typ = elem.get("type_name") or "<No Type>"

        category_counter[cat] += 1
        level_counter[lvl] += 1

        if cat not in by_type:
            by_type[cat] = Counter()
        by_type[cat][typ] += 1

        if elem.get("bounding_box"):
            with_bbox += 1
        if elem.get("materials"):
            with_materials += 1

        elem_params = parameters(elem)
        param_names.update(elem_params.keys())

    # Build ordered dicts
    by_category = dict(sorted(category_counter.items(), key=lambda x: (-x[1], x[0])))

    by_level = dict(sorted(level_counter.items(), key=lambda x: (-x[1], x[0])))

    by_type_ordered: dict[str, dict[str, int]] = {}
    for cat in sorted(by_type.keys()):
        by_type_ordered[cat] = dict(
            sorted(by_type[cat].items(), key=lambda x: (-x[1], x[0]))
        )

    return {
        "element_count": len(filtered),
        "by_category": by_category,
        "by_level": by_level,
        "by_type": by_type_ordered,
        "with_bounding_box": with_bbox,
        "with_materials": with_materials,
        "parameter_names": len(param_names),
    }


def parameter_statistics(
    elements: list[Any], options: Mapping[str, Any]
) -> dict[str, Any]:
    """Per-parameter statistics across the elements.

    Numeric parameters (Double/Integer storage) get min/max/mean/sum in Revit
    internal units; text and element-id parameters get their most common
    values (Revit's display string when available).
    """
    filtered = filter_categories(elements, string_list_option(options, "categories"))
    requested = string_list_option(options, "parameters")
    top = option(options, "top", 10, int)
    if top < 1:
        raise ValueError("option 'top' must be at least 1")
    include_empty = option(options, "include_empty", False, bool)

    names = sorted(
        set(requested)
        if requested is not None
        else {name for element in filtered for name in parameters(element)}
    )
    stats: dict[str, dict[str, Any]] = {}
    not_found: list[str] = []

    for name in names:
        storage_type: str | None = None
        data_type: str | None = None
        numbers: list[float] = []
        texts: list[str] = []
        missing = 0
        for element in filtered:
            param = parameters(element).get(name)
            if param is None:
                continue
            storage = param.get("storage_type")
            if storage_type is None:
                storage_type = storage
            if data_type is None:
                data_type = param.get("data_type")
            value = param.get("value")
            if value is None:
                missing += 1
            elif storage in NUMERIC_STORAGE and is_number(value):
                numbers.append(float(value))
            else:
                display = param.get("display")
                texts.append(
                    display if isinstance(display, str) and display else str(value)
                )

        if storage_type is None:
            not_found.append(name)
            continue
        if not numbers and not texts and not include_empty:
            continue
        if storage_type in NUMERIC_STORAGE:
            count = len(numbers)
            total = sum(numbers)
            stats[name] = {
                "kind": "numeric",
                "storage_type": storage_type,
                "data_type": data_type,
                "count": count,
                "missing": missing,
                "min": rounded(min(numbers), 6) if numbers else None,
                "max": rounded(max(numbers), 6) if numbers else None,
                "mean": rounded(total / count, 6) if numbers else None,
                "sum": rounded(total, 6) if numbers else None,
                "units": (
                    "Revit internal units (feet-based)"
                    if storage_type == "Double"
                    else None
                ),
            }
        else:
            counter = Counter(texts)
            ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
            stats[name] = {
                "kind": "text",
                "storage_type": storage_type,
                "data_type": data_type,
                "count": len(texts),
                "missing": missing,
                "distinct": len(counter),
                "top": [{"value": v, "count": c} for v, c in ranked[:top]],
            }

    return {
        "element_count": len(filtered),
        "parameters": stats,
        "not_found": not_found,
    }
