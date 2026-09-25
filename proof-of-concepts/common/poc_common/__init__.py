"""Shared helpers for the RevitPy proof-of-concept demos.

- :mod:`poc_common.revit` connects to Revit (or the demo model) and reads
  parameters through the RevitPy API.
- :mod:`poc_common.demo_model` builds the demo office building as a
  ``revitpy.testing`` mock model.
- :mod:`poc_common.timeseries` generates the synthetic weather, metering,
  occupancy, sensor and photo data the demos analyse.
"""

from .demo_model import ROOM_SCHEDULE, build_demo_building, room_profiles
from .revit import (
    FT2_TO_M2,
    FT3_TO_M3,
    FT_TO_M,
    GenericModel,
    StructuralColumn,
    StructuralFraming,
    connect,
    document_title,
    number,
    param,
    quiet_logging,
    source_label,
)

__all__ = [
    "FT2_TO_M2",
    "FT3_TO_M3",
    "FT_TO_M",
    "ROOM_SCHEDULE",
    "GenericModel",
    "StructuralColumn",
    "StructuralFraming",
    "build_demo_building",
    "connect",
    "document_title",
    "number",
    "param",
    "quiet_logging",
    "room_profiles",
    "source_label",
]
