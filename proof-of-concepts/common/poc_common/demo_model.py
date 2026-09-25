"""A small three-storey office building as a RevitPy mock model.

The model is a ``revitpy.testing.mock_revit.MockApplication`` whose active
document holds Levels, Rooms, Walls, Windows, Floors, Structural Columns,
Structural Framing and precast facade panels (Generic Models). Values are
stored the way Revit stores them: lengths in feet, areas in ft2, volumes in
ft3.

Parameters the demos rely on that are not built into Revit are *project
parameters* you would add to a real model (listed in the PoC READMEs):
``U-Value (W/m2K)``, ``Sensor ID``, ``Orientation``, ``Section``,
``Tributary Width`` and ``Tributary Area``. ``Department``, ``Occupancy``,
``Material``, ``Function``, ``Mark``, ``Level`` and ``Comments`` stand in for
the Revit parameters of the same names.
"""

from __future__ import annotations

from dataclasses import dataclass

from revitpy.testing.mock_revit import MockApplication

from .revit import FT_TO_M

M_TO_FT = 1 / FT_TO_M
M2_TO_FT2 = M_TO_FT**2
M3_TO_FT3 = M_TO_FT**3

LEVELS = ("Level 1", "Level 2", "Level 3")
STOREY_HEIGHT_M = 4.0
FOOTPRINT_M = (30.0, 20.0)  # east-west x north-south
SLAB_THICKNESS_M = 0.25
FACADE_ROWS = 6  # two precast panel rows per storey on the south facade
FACADE_COLS = 10


@dataclass(frozen=True)
class RoomSpec:
    """One room per level in the demo schedule."""

    name: str
    department: str
    area_m2: float
    capacity: int
    profile: str  # only used by the synthetic occupancy generator


ROOM_SCHEDULE: tuple[RoomSpec, ...] = (
    RoomSpec("Open Office A", "Engineering", 180.0, 24, "typical"),
    RoomSpec("Open Office B", "Design", 150.0, 20, "busy"),
    RoomSpec("Meeting Large", "Shared", 45.0, 16, "underused"),
    RoomSpec("Meeting Small", "Shared", 18.0, 6, "busy"),
    RoomSpec("Focus Room", "Shared", 9.0, 2, "typical"),
    RoomSpec("Training", "Shared", 60.0, 30, "underused"),
    RoomSpec("Project Room", "Engineering", 35.0, 10, "typical"),
    RoomSpec("Break Area", "Amenity", 40.0, 12, "busy"),
)

# (orientation, facade length m, window-to-wall ratio)
_FACADES = (
    ("North", FOOTPRINT_M[0], 0.25),
    ("South", FOOTPRINT_M[0], 0.45),
    ("East", FOOTPRINT_M[1], 0.30),
    ("West", FOOTPRINT_M[1], 0.30),
)


def build_demo_building(title: str = "RevitPy Demo Office.rvt") -> MockApplication:
    """Build the demo model and return its (mock) Revit application.

    The content is deterministic, so tests can assert on exact counts.
    """
    app = MockApplication()
    doc = app.CreateDocument()
    doc.Title = title

    for i, level in enumerate(LEVELS):
        lvl = doc.CreateElement(name=level, category="Levels")
        lvl.SetParameterValue("Elevation", i * STOREY_HEIGHT_M * M_TO_FT)

        _add_rooms(doc, level, i)
        _add_envelope(doc, level, i)
        _add_floor(doc, level)
        _add_structure(doc, level, i)

    _add_facade_panels(doc)
    return app


def _add_rooms(doc, level: str, level_index: int) -> None:
    clear_height_ft = 3.0 * M_TO_FT
    for n, spec in enumerate(ROOM_SCHEDULE, start=1):
        number = f"{level_index + 1}{n:02d}"
        room = doc.CreateElement(name=f"{spec.name} {number}", category="Rooms")
        area_ft2 = spec.area_m2 * M2_TO_FT2
        room.SetParameterValue("Number", number)
        room.SetParameterValue("Level", level)
        room.SetParameterValue("Area", area_ft2)
        room.SetParameterValue("Volume", area_ft2 * clear_height_ft)
        room.SetParameterValue("Department", spec.department)
        room.SetParameterValue("Occupancy", spec.capacity)
        room.SetParameterValue("Sensor ID", f"S-{number}")


def _add_envelope(doc, level: str, level_index: int) -> None:
    # Level 1 was refurbished; the upper floors keep the original envelope.
    wall_u = 0.35 if level_index == 0 else 1.6
    for orientation, length_m, wwr in _FACADES:
        gross_m2 = length_m * STOREY_HEIGHT_M
        glazing_m2 = gross_m2 * wwr
        opaque_m2 = gross_m2 - glazing_m2
        wall = doc.CreateElement(
            name=f"Exterior {orientation} {level}", category="Walls"
        )
        wall.SetParameterValue("Level", level)
        wall.SetParameterValue("Function", "Exterior")
        wall.SetParameterValue("Material", "Concrete")
        wall.SetParameterValue("Area", opaque_m2 * M2_TO_FT2)
        wall.SetParameterValue("Volume", opaque_m2 * 0.2 * M3_TO_FT3)
        wall.SetParameterValue("U-Value (W/m2K)", wall_u)
        wall.SetParameterValue("Orientation", orientation)

        window = doc.CreateElement(
            name=f"Glazing {orientation} {level}", category="Windows"
        )
        window.SetParameterValue("Level", level)
        window.SetParameterValue("Area", glazing_m2 * M2_TO_FT2)
        # Single glazing survives on the upper north facade.
        single = orientation == "North" and level_index > 0
        window.SetParameterValue("U-Value (W/m2K)", 5.7 if single else 1.4)
        window.SetParameterValue("Orientation", orientation)

    partitions = doc.CreateElement(name=f"Partitions {level}", category="Walls")
    partitions.SetParameterValue("Level", level)
    partitions.SetParameterValue("Function", "Interior")
    partitions.SetParameterValue("Material", "Gypsum Board")
    area_m2 = 220.0
    partitions.SetParameterValue("Area", area_m2 * M2_TO_FT2)
    partitions.SetParameterValue("Volume", area_m2 * 0.1 * M3_TO_FT3)


def _add_floor(doc, level: str) -> None:
    area_m2 = FOOTPRINT_M[0] * FOOTPRINT_M[1]
    floor = doc.CreateElement(name=f"Slab {level}", category="Floors")
    floor.SetParameterValue("Level", level)
    floor.SetParameterValue("Material", "Concrete")
    floor.SetParameterValue("Area", area_m2 * M2_TO_FT2)
    floor.SetParameterValue("Volume", area_m2 * SLAB_THICKNESS_M * M3_TO_FT3)


def _add_structure(doc, level: str, level_index: int) -> None:
    """Columns on a 5 x 3 grid (four 7.5 m bays in x, two 10 m bays in y), beams."""
    height_ft = STOREY_HEIGHT_M * M_TO_FT
    column_section = "W10x49" if level_index == 0 else "W8x31"
    for gx in range(5):
        for gy in range(3):
            column = doc.CreateElement(
                name=f"C-{chr(65 + gx)}{gy + 1} {level}",
                category="Structural Columns",
            )
            column.SetParameterValue("Level", level)
            column.SetParameterValue("Length", height_ft)
            column.SetParameterValue("Section", column_section)
            column.SetParameterValue("Material", "Steel")
            # Corner, edge or interior column: share of one 7.5 x 10 m bay.
            edge_x = gx in (0, 4)
            edge_y = gy in (0, 2)
            share = 0.25 if edge_x and edge_y else 0.5 if edge_x or edge_y else 1.0
            column.SetParameterValue("Tributary Area", share * 75.0 * M2_TO_FT2)

    # Secondary beams: 7.5 m spans at 2.5 m spacing, 4 per bay line.
    for n in range(12):
        section = "W14x22" if (level_index == 2 and n < 2) else "W16x26"
        beam = doc.CreateElement(
            name=f"B-{level_index + 1}{n + 1:02d}", category="Structural Framing"
        )
        beam.SetParameterValue("Level", level)
        beam.SetParameterValue("Length", 7.5 * M_TO_FT)
        beam.SetParameterValue("Section", section)
        beam.SetParameterValue("Material", "Steel")
        tributary_m = 2.9 if n < 2 else 2.5
        beam.SetParameterValue("Tributary Width", tributary_m * M_TO_FT)


def _add_facade_panels(doc) -> None:
    panel_w = FOOTPRINT_M[0] / FACADE_COLS
    panel_h = STOREY_HEIGHT_M / (FACADE_ROWS // len(LEVELS))
    for row in range(FACADE_ROWS):
        level = LEVELS[row * len(LEVELS) // FACADE_ROWS]
        for col in range(FACADE_COLS):
            panel = doc.CreateElement(
                name=f"Precast Panel {row:02d}-{col:02d}", category="Generic Models"
            )
            panel.SetParameterValue("Mark", f"FP-{row:02d}-{col:02d}")
            panel.SetParameterValue("Level", level)
            panel.SetParameterValue("Material", "Concrete")
            area_m2 = panel_w * panel_h
            panel.SetParameterValue("Area", area_m2 * M2_TO_FT2)
            panel.SetParameterValue("Volume", area_m2 * 0.15 * M3_TO_FT3)


def room_profiles() -> dict[str, str]:
    """Map room *base* names to the synthetic occupancy profile."""
    return {spec.name: spec.profile for spec in ROOM_SCHEDULE}
