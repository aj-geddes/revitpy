"""Room schedule: collect rooms, build a sorted schedule with totals, export it.

Demonstrates:
    * turning ``Room`` elements into plain row dicts
    * ``revitpy.extract.ScheduleBuilder`` for sorting, column projection,
      totals and grouping
    * ``revitpy.extract.DataExporter`` writing CSV and JSON

Run it:
    * locally, against an in-memory demo model:
      ``python examples/room_schedule_export.py [--output DIR]``
    * inside Revit: RevitPy ribbon -> Run Script -> pick this file. Files are
      written to ``%TEMP%/revitpy_room_schedule``.

Areas are reported in square feet (Revit's internal unit).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any

from revitpy import RevitAPI
from revitpy.api import ElementNotFoundError, Room
from revitpy.extract import (
    DataExporter,
    ExportConfig,
    ExportFormat,
    ScheduleBuilder,
    ScheduleConfig,
)

COLUMNS = ["Number", "Name", "Level", "Department", "Area"]
DEFAULT_OUTPUT = Path(tempfile.gettempdir()) / "revitpy_room_schedule"


def build_demo_model() -> Any:
    """Build a MockApplication with sample rooms (used outside Revit)."""
    from revitpy.testing.mock_revit import MockApplication

    app = MockApplication()
    doc = app.CreateDocument()
    rooms = [
        ("101", "Office", "Level 1", "Engineering", 250.75),
        ("102", "Office", "Level 1", "Engineering", 220.50),
        ("103", "Conference", "Level 1", "Admin", 400.00),
        ("104", "Corridor", "Level 1", "Admin", 150.25),
        ("201", "Office", "Level 2", "Sales", 275.00),
        ("202", "Restroom", "Level 2", "Admin", 90.00),
        ("203", "Storage", "Level 2", "Facilities", 120.50),
        ("204", "Office", "Level 2", "Sales", 230.25),
    ]
    for number, name, level, department, area in rooms:
        room = doc.CreateElement(name=name, category="Rooms")
        room.SetParameterValue("Number", number)
        room.SetParameterValue("Level", level)
        room.SetParameterValue("Department", department)
        room.SetParameterValue("Area", area)
    return app


def get_revit_app() -> tuple[Any, bool]:
    """Return ``(application, inside_revit)``; a demo model outside Revit."""
    try:
        return __revit__, True  # noqa: F821 - injected by the RevitPy host / pyRevit
    except NameError:
        from loguru import logger

        logger.remove()
        logger.add(sys.stderr, level="WARNING")
        print("Not running inside Revit - using an in-memory demo model.\n")
        return build_demo_model(), False


def as_float(value: Any) -> float:
    """Convert a parameter value to float (the mock model stores numbers as text)."""
    try:
        return float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


def param(element: Any, name: str, default: Any = "") -> Any:
    """Read a parameter, returning ``default`` when the element doesn't have it."""
    try:
        value = element.get_parameter_value(name)
    except ElementNotFoundError:
        return default
    return default if value is None else value


def room_rows(api: RevitAPI) -> list[dict[str, Any]]:
    """One row dict per room."""
    return [
        {
            "Number": str(param(room, "Number")),
            "Name": str(param(room, "Name", room.name)),
            "Level": str(param(room, "Level")),
            "Department": str(param(room, "Department")),
            "Area": round(as_float(param(room, "Area", 0.0)), 2),
        }
        for room in api.query(Room).to_list()
    ]


def print_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    """Print row dicts as an aligned text table."""
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    print(("  " + "  ".join(c.ljust(widths[c]) for c in columns)).rstrip())
    print("  " + "  ".join("-" * widths[c] for c in columns))
    for row in rows:
        line = "  ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns)
        print(("  " + line).rstrip())


def main() -> None:
    app, inside_revit = get_revit_app()

    output_dir = DEFAULT_OUTPUT
    if not inside_revit:  # the embedded interpreter has no command line
        parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
        parser.add_argument(
            "--output",
            type=Path,
            default=DEFAULT_OUTPUT,
            help=f"directory for the exported files (default: {DEFAULT_OUTPUT})",
        )
        output_dir = parser.parse_args().output
    output_dir.mkdir(parents=True, exist_ok=True)

    api = RevitAPI()
    api.connect(app)

    rows = room_rows(api)
    if not rows:
        print("The model has no rooms - nothing to export.")
        return

    builder = ScheduleBuilder(
        ScheduleConfig(
            columns=COLUMNS,
            sort_by=["Level", "Number"],
            include_totals=True,
            title="Room Schedule",
        )
    )
    schedule = builder.build(rows)

    print(f"{builder.config.title} ({len(rows)} rooms, areas in sq ft)")
    print_table(schedule, COLUMNS)

    print("\nArea by level:")
    for level, level_rows in sorted(builder.group_data(rows, "Level").items()):
        area = sum(row["Area"] for row in level_rows)
        print(f"  {level:<10} {area:>9.2f} sq ft  ({len(level_rows)} rooms)")

    exporter = DataExporter()
    written = [
        exporter.export(
            schedule,
            ExportConfig(format=fmt, output_path=output_dir / f"room_schedule.{ext}"),
        )
        for fmt, ext in ((ExportFormat.CSV, "csv"), (ExportFormat.JSON, "json"))
    ]
    print("\nWrote:")
    for path in written:
        print(f"  {Path(path).resolve()}")


if __name__ == "__main__":
    main()
