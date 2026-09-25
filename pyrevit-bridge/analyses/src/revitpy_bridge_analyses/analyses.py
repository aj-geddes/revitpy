"""
Registers the bridge analyses with the RevitPy Live Server.

The Live Server imports this module at start-up through the
``revitpy.analyses`` entry point declared in this package's
``pyproject.toml``. Each analysis is a pure function of the serialized element
dicts sent by ``revitpy_bridge.py`` on the pyRevit side; none of them calls the
Revit API.

The analyses are registered with ``main_thread=False`` so the Live Server runs
them on a worker thread. That matters: a pyRevit button that calls
``bridge/analyze`` blocks Revit's main thread until the reply arrives, so an
analysis queued for the main thread could not start until the button gave up.
Versions of revitpy whose ``register_analysis`` has no ``main_thread`` option
are still supported (the analyses then run on the main thread, which works for
callers outside Revit's main thread, such as ``revitpy live`` or scripts).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from revitpy.revit.live import register_analysis

from .carbon import embodied_carbon
from .clashes import bounding_box_clashes
from .quantities import quantity_takeoff
from .summary import element_summary, parameter_statistics

__all__ = ["ANALYSES", "register_all"]

Analysis = Callable[[list[Any], Mapping[str, Any]], Any]

ANALYSES: dict[str, Analysis] = {
    "element_summary": element_summary,
    "parameter_statistics": parameter_statistics,
    "quantity_takeoff": quantity_takeoff,
    "embodied_carbon": embodied_carbon,
    "bounding_box_clashes": bounding_box_clashes,
}


def _handler(func: Analysis) -> Callable[[list[Any], dict[str, Any], Any], Any]:
    def handler(elements: list[Any], options: dict[str, Any], uiapp: Any) -> Any:
        return func(elements, options)

    handler.__name__ = func.__name__
    handler.__doc__ = func.__doc__
    return handler


def register_all() -> list[str]:
    """Register (or re-register, e.g. after ``live/reload``) every analysis."""
    for name, func in ANALYSES.items():
        try:
            register_analysis(name, replace=True, main_thread=False)(_handler(func))
        except TypeError:  # revitpy without off-main-thread analyses
            register_analysis(name, replace=True)(_handler(func))
    return sorted(ANALYSES)


register_all()
