"""
Helpers for reading the element dicts serialized by ``revitpy_bridge.py``.

Measured values arrive in Revit internal units: feet, square feet, cubic feet
(angles in radians). The conversion factors below are exact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

__all__ = [
    "FT2_TO_M2",
    "FT3_TO_M3",
    "FT_TO_M",
    "NUMERIC_STORAGE",
    "element_ref",
    "filter_categories",
    "is_number",
    "numeric_value",
    "option",
    "parameters",
    "point",
    "rounded",
    "string_list_option",
    "text",
]

FT_TO_M = 0.3048
FT2_TO_M2 = 0.09290304
FT3_TO_M3 = 0.028316846592
NUMERIC_STORAGE = frozenset({"Double", "Integer"})


def is_number(value: Any) -> bool:
    """A finite int or float (``bool`` excluded)."""
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and isfinite(value)
    )


def parameters(element: Any) -> dict[str, dict[str, Any]]:
    """The element's parameters by name (malformed entries dropped)."""
    params = element.get("parameters") if isinstance(element, dict) else None
    if not isinstance(params, dict):
        return {}
    return {name: p for name, p in params.items() if isinstance(p, dict)}


def _numeric(param: Mapping[str, Any]) -> float | None:
    value = param.get("value")
    if param.get("storage_type") in NUMERIC_STORAGE and is_number(value):
        return float(value)
    return None


def numeric_value(
    element: Any, *, builtins: Sequence[str] = (), names: Sequence[str] = ()
) -> float | None:
    """A numeric parameter value, looked up by built-in parameter, then by name.

    Built-in names (``HOST_AREA_COMPUTED``) do not depend on Revit's language;
    parameter names (``Area``) do, so they are the fallback.
    """
    params = parameters(element)
    for builtin in builtins:
        for param in params.values():
            if param.get("builtin") == builtin:
                value = _numeric(param)
                if value is not None:
                    return value
    for name in names:
        param = params.get(name)
        if param is not None:
            value = _numeric(param)
            if value is not None:
                return value
    return None


def text(element: Any, key: str, default: str) -> str:
    """``element[key]`` when it is a non-empty string, else ``default``."""
    value = element.get(key) if isinstance(element, dict) else None
    return value if isinstance(value, str) and value else default


def element_ref(element: Any) -> dict[str, Any]:
    """The identifying fields of an element."""
    get = element.get if isinstance(element, dict) else (lambda _key: None)
    return {"id": get("id"), "name": get("name"), "category": get("category")}


def filter_categories(
    elements: Sequence[Any], categories: Sequence[str] | None
) -> list[dict[str, Any]]:
    """Dict elements, restricted to ``categories`` (case-insensitive) if given."""
    wanted = {category.lower() for category in categories or ()}
    return [
        element
        for element in elements
        if isinstance(element, dict)
        and (
            not wanted
            or (
                isinstance(element.get("category"), str)
                and element["category"].lower() in wanted
            )
        )
    ]


def option(
    options: Mapping[str, Any],
    key: str,
    default: Any,
    kind: type | tuple[type, ...],
) -> Any:
    """A typed option. ``None`` or missing gives ``default``.

    ``bool`` is not accepted as a number; ints are accepted (as float) where
    ``kind`` includes ``float``. A wrong type raises ``ValueError``.
    """
    value = options.get(key)
    if value is None:
        return default
    kinds = kind if isinstance(kind, tuple) else (kind,)
    if isinstance(value, bool) and bool not in kinds:
        valid = False
    elif float in kinds and isinstance(value, int | float):
        return float(value)
    else:
        valid = isinstance(value, kinds)
    if not valid:
        names = " or ".join(k.__name__ for k in kinds)
        raise ValueError(f"option '{key}' must be {names}")
    return value


def string_list_option(options: Mapping[str, Any], key: str) -> list[str] | None:
    """A list-of-strings option, or ``None`` when absent."""
    value = options.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"option '{key}' must be a list of strings")
    return list(value)


def rounded(value: float | None, digits: int = 4) -> float | None:
    """``round(value, digits)``; ``None`` for None, NaN or infinity."""
    if value is None or not isfinite(value):
        return None
    return round(value, digits)


def point(value: Any) -> tuple[float, float, float] | None:
    """An ``[x, y, z]`` list of finite numbers as a tuple, else ``None``."""
    if not isinstance(value, list | tuple) or len(value) != 3:
        return None
    if not all(is_number(coordinate) for coordinate in value):
        return None
    x, y, z = (float(coordinate) for coordinate in value)
    return (x, y, z)
