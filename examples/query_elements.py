"""Query elements: typed queries, filtering, sorting, paging and a table.

Demonstrates:
    * counting elements per typed class (``Wall``, ``Door``, ``Window``, ``Level``)
    * fluent filters (``contains``, ``equals``) and sorting
    * paging with ``skip`` / ``take``
    * numeric filtering and descending sort in plain Python
    * ``first_or_default``, ``get_element_by_id`` and ``get_all_parameters``

Run it:
    * locally, against an in-memory demo model:  ``python examples/query_elements.py``
    * inside Revit: RevitPy ribbon -> Run Script -> pick this file
"""

from __future__ import annotations

import sys
from typing import Any

from revitpy import RevitAPI
from revitpy.api import Door, Level, Wall, Window


def build_demo_model() -> Any:
    """Build a MockApplication with sample data (used outside Revit)."""
    from revitpy.testing.mock_revit import MockApplication

    app = MockApplication()
    doc = app.CreateDocument()

    for name, elevation in (("Level 1", 0.0), ("Level 2", 12.0), ("Roof", 24.0)):
        level = doc.CreateElement(name=name, category="Levels")
        level.SetParameterValue("Elevation", elevation)

    walls = [
        ("Exterior - Brick 300mm", "Level 1", 25.5, "1 hr"),
        ("Exterior - Brick 300mm", "Level 2", 25.5, "1 hr"),
        ("Exterior - Concrete 200mm", "Level 1", 30.0, "2 hr"),
        ("Exterior - Concrete 200mm", "Level 2", 30.0, "2 hr"),
        ("Exterior - Glass 150mm", "Level 1", 20.0, None),
        ("Interior - Stud 100mm", "Level 1", 15.0, None),
        ("Interior - Stud 100mm", "Level 2", 15.0, None),
        ("Interior - CMU 150mm", "Level 1", 18.0, "1 hr"),
    ]
    for name, level_name, length, fire_rating in walls:
        wall = doc.CreateElement(name=name, category="Walls")
        wall.SetParameterValue("Level", level_name)
        wall.SetParameterValue("Length", length)
        wall.SetParameterValue("Height", 12.0)
        if fire_rating:
            wall.SetParameterValue("Fire Rating", fire_rating)

    for name, level_name, mark in (
        ("Single-Flush", "Level 1", "D101"),
        ("Double-Flush", "Level 2", "D102"),
        ("Single-Flush", "Level 1", "D103"),
    ):
        door = doc.CreateElement(name=name, category="Doors")
        door.SetParameterValue("Level", level_name)
        door.SetParameterValue("Mark", mark)

    for name, level_name in (
        ("Fixed - 36x48", "Level 1"),
        ("Awning - 24x36", "Level 2"),
    ):
        window = doc.CreateElement(name=name, category="Windows")
        window.SetParameterValue("Level", level_name)

    return app


def get_revit_app() -> Any:
    """Return Revit's UIApplication inside Revit, else a demo model."""
    try:
        return __revit__  # noqa: F821 - injected by the RevitPy host / pyRevit
    except NameError:
        from loguru import logger

        logger.remove()
        logger.add(sys.stderr, level="WARNING")
        print("Not running inside Revit - using an in-memory demo model.\n")
        return build_demo_model()


def as_float(value: Any) -> float:
    """Convert a parameter value to float (the mock model stores numbers as text)."""
    try:
        return float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


def param(element: Any, name: str, default: Any = "") -> Any:
    """Read a parameter, returning ``default`` when the element doesn't have it."""
    from revitpy.api import ElementNotFoundError

    try:
        value = element.get_parameter_value(name)
    except ElementNotFoundError:
        return default
    return default if value is None else value


def print_table(headers: list[str], rows: list[list[Any]]) -> None:
    """Print rows as an aligned text table."""
    if not rows:
        print("  (no rows)")
        return
    cells = [[str(cell) for cell in row] for row in rows]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in cells))
        for i in range(len(headers))
    ]
    print(
        "  "
        + "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True)).rstrip()
    )
    print("  " + "  ".join("-" * w for w in widths))
    for row in cells:
        line = "  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True))
        print(("  " + line).rstrip())


def main() -> None:
    api = RevitAPI()
    api.connect(get_revit_app())
    print(f"Document: {api.get_document_info().title}\n")

    print("Element counts:")
    for cls in (Wall, Door, Window, Level):
        print(f"  {cls.__name__:<7} {api.query(cls).count()}")

    exterior = (
        api.query(Wall)
        .contains("Name", "Exterior")
        .order_by_ascending("Name")
        .execute()
    )
    print(f"\nExterior walls ({len(exterior)}):")
    print_table(
        ["ID", "Name", "Level", "Length (ft)"],
        [
            [
                w.id.value,
                w.name,
                param(w, "Level"),
                f"{as_float(param(w, 'Length')):.1f}",
            ]
            for w in exterior
        ],
    )

    level_1 = api.query(Wall).equals("Level", "Level 1").count()
    print(f"\nWalls on Level 1: {level_1}")

    print("\nAll walls, 3 per page:")
    page_size, page_number = 3, 0
    while True:
        page = (
            api.query(Wall)
            .order_by_ascending("Name")
            .skip(page_number * page_size)
            .take(page_size)
            .to_list()
        )
        if not page:
            break
        page_number += 1
        print(f"  page {page_number}: " + ", ".join(w.name for w in page))

    # Numeric comparisons and descending sorts are simplest in plain Python.
    long_walls = sorted(
        (w for w in api.query(Wall).execute() if as_float(param(w, "Length")) > 20),
        key=lambda w: as_float(param(w, "Length")),
        reverse=True,
    )
    print("\nWalls longer than 20 ft, longest first:")
    for wall in long_walls:
        print(f"  {as_float(param(wall, 'Length')):6.1f} ft  {wall.name}")

    missing = api.query(Wall).equals("Name", "Does Not Exist").first_or_default()
    print(
        f"\nWall named 'Does Not Exist': {'not found' if missing is None else missing}"
    )

    first = api.query(Wall).order_by_ascending("Name").first()
    element = api.get_element_by_id(first.id.value)
    if element is not None:
        print(f"\nParameters of {element.name} (id {element.id.value}):")
        for name, value in sorted(element.get_all_parameters().items()):
            print(f"  {name} = {value.value!r}")


if __name__ == "__main__":
    main()
