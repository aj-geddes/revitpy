"""ORM layer: validated models, LINQ-style queries, change tracking, unit of work.

Demonstrates:
    1. pydantic element models (``create_wall`` / ``create_room``) and the
       ``ValidationError.validation_errors`` you get for bad input
    2. ``RevitContext`` queries (``where`` / ``order_by`` / ``count``) and
       aggregation on an ``ElementSet``
    3. recording changes with a ``ChangeTracker``
    4. persisting them with ``save_changes_async()`` through an ``IUnitOfWork``
       that writes to Revit inside a transaction
    5. ``ctx.transaction()`` discarding pending changes when something fails

Run it:
    * locally, against an in-memory demo model:  ``python examples/orm_usage.py``
    * inside Revit: RevitPy ribbon -> Run Script -> pick this file.
      Note: step 4 really writes ``Comments`` on three walls (use Undo to revert).
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from revitpy import RevitAPI
from revitpy.api import Wall
from revitpy.orm import (
    ElementSet,
    RevitContext,
    ValidationError,
    create_room,
    create_wall,
)
from revitpy.orm.change_tracker import ChangeTracker
from revitpy.orm.types import ChangeSet

# The ORM tracks element properties by their Python names; these are the Revit
# parameters behind the ones this example changes.
PARAMETER_NAMES = {"comments": "Comments", "mark": "Mark"}


def build_demo_model() -> Any:
    """Build a MockApplication with sample data (used outside Revit)."""
    from revitpy.testing.mock_revit import MockApplication

    app = MockApplication()
    doc = app.CreateDocument()
    for index in range(6):
        wall = doc.CreateElement(name=f"Wall {index + 1:02d}", category="Walls")
        wall.SetParameterValue("Level", f"Level {index % 2 + 1}")
        wall.SetParameterValue("Height", 10.0 + index * 2.0)
        wall.SetParameterValue("Family", "Basic Wall")
    return app


def get_revit_app() -> Any:
    """Return Revit's UIApplication inside Revit, else a demo model."""
    try:
        return __revit__  # noqa: F821 - injected by the RevitPy host / pyRevit
    except NameError:
        from loguru import logger

        logger.remove()
        # ctx.transaction() logs the (expected) failure in step 5 at ERROR level.
        logger.add(sys.stderr, level="CRITICAL")
        print("Not running inside Revit - using an in-memory demo model.\n")
        return build_demo_model()


def as_float(value: Any) -> float:
    """Convert a parameter value to float (the mock model stores numbers as text)."""
    try:
        return float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


class RevitUnitOfWork:
    """``IUnitOfWork`` that applies modified properties as Revit parameters.

    The ORM hands every pending change to ``register_*`` and then calls
    ``commit``/``commit_async``; all writes happen in one Revit transaction.
    Creating and deleting elements is out of scope for this example.
    """

    def __init__(self, api: RevitAPI) -> None:
        self.api = api
        self.dirty: list[ChangeSet] = []
        self.ignored: list[ChangeSet] = []
        self.writes = 0
        self.rolled_back = False

    def register_new(self, entity: ChangeSet) -> None:
        self.ignored.append(entity)

    def register_dirty(self, entity: ChangeSet) -> None:
        self.dirty.append(entity)

    def register_removed(self, entity: ChangeSet) -> None:
        self.ignored.append(entity)

    def register_clean(self, entity: ChangeSet) -> None:
        pass

    def commit(self) -> None:
        with self.api.transaction("ORM save"):
            for change in self.dirty:
                element = self.api.get_element_by_id(int(change.entity_id))
                if element is None:
                    continue
                for name, value in change.current_values.items():
                    element.set_parameter_value(PARAMETER_NAMES.get(name, name), value)
                    self.writes += 1
        self.dirty.clear()
        self.ignored.clear()

    def rollback(self) -> None:
        self.dirty.clear()
        self.ignored.clear()
        self.rolled_back = True

    async def commit_async(self) -> None:
        self.commit()

    async def rollback_async(self) -> None:
        self.rollback()


def read_comments(api: RevitAPI, wall: Any) -> Any:
    """Read Comments straight from the model (bypassing wrapper caches)."""
    element = api.get_element_by_id(wall.id.value)
    return element.get_parameter_value("Comments", use_cache=False)


def validated_models() -> None:
    print("== 1. Validated element models ==")
    wall = create_wall(id=1, height=10.0, length=20.0, width=0.5, name="Demo wall")
    print(f"  {wall.name}: area={wall.area} sq ft, volume={wall.volume} cu ft")

    bad_inputs = {
        "wall with negative height": lambda: create_wall(
            id=2, height=-5.0, length=20.0, width=0.5
        ),
        "wall with 9 hr fire rating": lambda: create_wall(
            id=3, height=10.0, length=20.0, width=0.5, fire_rating=9
        ),
        "room number with a space": lambda: create_room(
            id=4, number="10 1", area=250.0
        ),
    }
    for label, build in bad_inputs.items():
        try:
            build()
        except ValidationError as error:
            print(f"  rejected {label}: {error.validation_errors}")


def main() -> None:
    api = RevitAPI()
    api.connect(get_revit_app())

    validated_models()

    unit_of_work = RevitUnitOfWork(api)
    tracker = ChangeTracker()
    with RevitContext(
        api.active_document, change_tracker=tracker, unit_of_work=unit_of_work
    ) as ctx:
        print("\n== 2. Querying ==")
        print(f"  walls: {ctx.count(Wall)}")
        tall = (
            ctx.all(Wall)
            .where(lambda w: as_float(w.get_parameter_value("Height")) >= 14)
            .order_by(lambda w: w.name)
            .to_list()
        )
        print(f"  walls >= 14 ft: {', '.join(w.name for w in tall) or '(none)'}")

        walls = ElementSet(ctx.all(Wall).to_list(), element_type=Wall, lazy=False)
        if len(walls):
            height = walls.sum(lambda w: as_float(w.get_parameter_value("Height")))
            average = walls.average(lambda w: as_float(w.get_parameter_value("Height")))
            print(f"  total height {height:.1f} ft, average {average:.1f} ft")
            by_level = walls.group_by(lambda w: w.get_parameter_value("Level"))
            for level, group in by_level.items():
                print(f"  level {level}: {len(group)} walls")

        print("\n== 3. Change tracking ==")
        targets = ctx.all(Wall).order_by(lambda w: w.name).take(3).to_list()
        for wall in targets:
            tracker.track_property_change(
                wall, "comments", wall.comments, f"Reviewed ({wall.name})"
            )
        print(f"  has_changes={ctx.has_changes}, change_count={ctx.change_count}")
        if targets:
            state = ctx.get_entity_state(targets[0])
            print(f"  state of {targets[0].name}: {state.value}")

        print("\n== 4. Async save through the unit of work ==")
        saved = asyncio.run(ctx.as_async().save_changes_async())
        print(f"  saved {saved} entities, {unit_of_work.writes} parameter writes")
        print(f"  has_changes={ctx.has_changes}")
        for wall in targets:
            value = read_comments(api, wall)
            if value != f"Reviewed ({wall.name})":
                raise RuntimeError(f"{wall.name}: Comments not saved (got {value!r})")
            print(f"  {wall.name}: Comments = {value!r}")

        print("\n== 5. Failed ORM transaction discards pending changes ==")
        if targets:
            first = targets[0]
            before = read_comments(api, first)
            try:
                with ctx.transaction():
                    tracker.track_property_change(first, "comments", before, "nope")
                    raise RuntimeError("validation failed downstream")
            except RuntimeError as error:
                print(f"  caught: {error}")
            print(f"  unit of work rolled back: {unit_of_work.rolled_back}")
            print(f"  has_changes={ctx.has_changes}")
            after = read_comments(api, first)
            if after != before:
                raise RuntimeError(f"{first.name}: Comments changed to {after!r}")
            print(f"  {first.name}: Comments still {after!r}")


if __name__ == "__main__":
    main()
