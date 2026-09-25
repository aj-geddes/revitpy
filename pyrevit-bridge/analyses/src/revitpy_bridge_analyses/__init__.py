"""
RevitPy-side analyses for the pyRevit bridge.

Install this package into the Python that RevitPy embeds in Revit; the RevitPy
Live Server then loads :mod:`revitpy_bridge_analyses.analyses` through the
``revitpy.analyses`` entry point and pyRevit scripts can call the analyses with
``revitpy_bridge.RevitPyBridge().analyze(name, elements)``.

The functions below are plain functions of the serialized element dicts, usable
without the Live Server. All input lengths are Revit internal units (feet,
square feet, cubic feet).
"""

from .carbon import embodied_carbon
from .clashes import bounding_box_clashes
from .quantities import quantity_takeoff
from .summary import element_summary, parameter_statistics

__all__ = [
    "bounding_box_clashes",
    "element_summary",
    "embodied_carbon",
    "parameter_statistics",
    "quantity_takeoff",
]
