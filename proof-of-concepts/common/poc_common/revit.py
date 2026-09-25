"""Connecting to a model and reading values through the RevitPy API.

Every proof of concept gets its model data the same way::

    api = connect(app)          # app = __revit__ inside Revit
    rooms = api.query(Room).execute()

When ``app`` is ``None`` (running outside Revit) the demo building from
:mod:`poc_common.demo_model` is used instead. It is a
``revitpy.testing.mock_revit.MockApplication``, so exactly the same query,
parameter and transaction code runs against it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from loguru import logger

from revitpy import RevitAPI
from revitpy.api import Element
from revitpy.api.exceptions import RevitAPIError

# Revit stores lengths in feet, areas in ft2 and volumes in ft3.
FT_TO_M = 0.3048
FT2_TO_M2 = FT_TO_M**2
FT3_TO_M3 = FT_TO_M**3


class StructuralColumn(Element):
    """Structural column. RevitPy has no built-in class, so declare one."""

    revit_categories = ("OST_StructuralColumns", "Structural Columns")


class StructuralFraming(Element):
    """Beams and braces (Structural Framing category)."""

    revit_categories = ("OST_StructuralFraming", "Structural Framing")


class GenericModel(Element):
    """Generic Models, used here for precast facade panels."""

    revit_categories = ("OST_GenericModel", "Generic Models")


def connect(app: Any | None = None, demo: Callable[[], Any] | None = None) -> RevitAPI:
    """Return a connected :class:`RevitAPI`.

    Args:
        app: Revit's ``UIApplication`` (``__revit__``) or any object RevitPy
            accepts. ``None`` means "not running in Revit".
        demo: Factory for a demo application used when ``app`` is ``None``.
            Defaults to :func:`poc_common.demo_model.build_demo_building`.
    """
    if app is None:
        if demo is None:
            from .demo_model import build_demo_building

            demo = build_demo_building
        app = demo()
    api = RevitAPI()
    api.connect(app)
    return api


def param(element: Element, name: str, default: Any = None) -> Any:
    """Read a parameter, returning ``default`` if it is missing or empty."""
    try:
        value = element.get_parameter_value(name)
    except RevitAPIError:
        return default
    return default if value is None or value == "" else value


def number(element: Element, name: str, default: float = 0.0) -> float:
    """Read a numeric parameter as ``float`` (``default`` if missing/invalid)."""
    value = param(element, name)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def document_title(api: RevitAPI) -> str:
    """Title of the active document."""
    return api.get_document_info().title


def source_label(api: RevitAPI, app: Any | None) -> str:
    """``"<title> (demo model)"`` for mock models, ``"<title> (Revit)"`` otherwise."""
    from revitpy.testing.mock_revit import MockApplication

    kind = "demo model" if app is None or isinstance(app, MockApplication) else "Revit"
    return f"{document_title(api)} ({kind})"


def quiet_logging(level: str = "WARNING") -> None:
    """Show only RevitPy log messages at ``level`` or above (keeps reports readable)."""
    logger.remove()
    logger.add(sys.stderr, level=level)
