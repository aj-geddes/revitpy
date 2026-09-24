"""Bulk-update parameters in one transaction, and see a failed update roll back.

Demonstrates:
    * tagging every wall's ``Mark`` and ``Comments`` inside a single transaction
    * an exception inside ``with api.transaction(...)`` rolling back every change
    * re-reading values with ``use_cache=False`` to see what the model holds

Run it:
    * locally, against an in-memory demo model:
      ``python examples/bulk_update_parameters.py``
    * inside Revit: RevitPy ribbon -> Run Script -> pick this file.
      Note: this example really changes Mark/Comments on the walls of the
      active model (use Undo to revert).
"""

from __future__ import annotations

import sys
from typing import Any

from revitpy import RevitAPI
from revitpy.api import Wall


def build_demo_model() -> Any:
    """Build a MockApplication with sample data (used outside Revit)."""
    from revitpy.testing.mock_revit import MockApplication

    app = MockApplication()
    doc = app.CreateDocument()
    for index in range(6):
        kind = "Exterior - Brick" if index < 3 else "Interior - Stud"
        wall = doc.CreateElement(name=kind, category="Walls")
        wall.SetParameterValue("Level", f"Level {index % 2 + 1}")
    return app


def get_revit_app() -> Any:
    """Return Revit's UIApplication inside Revit, else a demo model."""
    try:
        return __revit__  # noqa: F821 - injected by the RevitPy host / pyRevit
    except NameError:
        from loguru import logger

        logger.remove()
        logger.add(sys.stderr, level="ERROR")
        print("Not running inside Revit - using an in-memory demo model.\n")
        return build_demo_model()


def current_walls(api: RevitAPI) -> list[Any]:
    """Re-query the walls so we read fresh values from the model."""
    return api.query(Wall).order_by_ascending("Name").to_list()


def show(walls: list[Any]) -> None:
    """Print id, name, Mark and Comments as the model currently holds them."""
    print(f"  {'ID':<6} {'Name':<18} {'Mark':<7} Comments")
    for wall in walls:
        mark = wall.get_parameter_value("Mark", use_cache=False)
        comments = wall.get_parameter_value("Comments", use_cache=False)
        print(f"  {wall.id.value:<6} {wall.name:<18} {mark!s:<7} {comments}")


def faulty_update(api: RevitAPI) -> None:
    """Change every wall, then fail before the transaction can commit."""
    with api.transaction("Faulty update"):
        for wall in current_walls(api):
            wall.set_parameter_value("Comments", "SHOULD NOT PERSIST")
        raise ValueError("simulated failure halfway through")


def main() -> None:
    api = RevitAPI()
    api.connect(get_revit_app())

    walls = current_walls(api)
    print(f"Found {len(walls)} walls in '{api.get_document_info().title}'\n")

    # 1. Everything in one transaction: one undo step in Revit, all-or-nothing.
    with api.transaction("Tag walls"):
        for index, wall in enumerate(walls, start=1):
            kind = "Exterior" if wall.name.startswith("Exterior") else "Interior"
            wall.set_parameter_value("Mark", f"W-{index:03d}")
            wall.set_parameter_value("Comments", kind)
    print(f"Tagged {len(walls)} walls (Mark + Comments) in one transaction:")
    show(current_walls(api))

    # 2. An exception inside the block rolls every change back.
    print("\nRunning an update that fails part-way ...")
    try:
        faulty_update(api)
    except ValueError as error:
        print(f"  caught: {error} -> transaction rolled back")

    walls = current_walls(api)
    show(walls)
    leaked = [
        w
        for w in walls
        if w.get_parameter_value("Comments", use_cache=False) == "SHOULD NOT PERSIST"
    ]
    if leaked:
        raise RuntimeError(f"{len(leaked)} walls kept changes after rollback")
    print("\nRollback verified: no wall kept the faulty value.")


if __name__ == "__main__":
    main()
