"""Regression tests for element, query, transaction group, extraction and IFC fixes."""

from __future__ import annotations

from typing import Any

import pytest

from revitpy import RevitAPI
from revitpy.api import Door, Element, Room, Wall
from revitpy.api.transaction import TransactionStatus
from revitpy.extract import QuantityExtractor
from revitpy.extract.types import QuantityType
from revitpy.ifc.mapper import IfcElementMapper
from revitpy.testing.mock_revit import MockApplication, MockDocument, MockElement


@pytest.fixture
def model() -> tuple[RevitAPI, MockDocument]:
    app = MockApplication()
    doc = app.CreateDocument()
    api = RevitAPI()
    api.connect(app)
    return api, doc


def raw(element: MockElement, name: str) -> Any:
    return element.GetParameterValue(name).value


class TestMockNumbers:
    def test_numbers_round_trip_as_numbers(self, model: Any) -> None:
        api, doc = model
        el = doc.CreateElement(name="W1", category="Walls")
        el.SetParameterValue("Height", 12.5)
        el.SetParameterValue("Count", 3)
        wrapper = api.get_element_by_id(el.Id.Value)
        assert wrapper.get_parameter_value("Height") == 12.5
        assert isinstance(wrapper.get_parameter_value("Height"), float)
        assert wrapper.get_parameter_value("Count") == 3
        assert isinstance(wrapper.get_parameter_value("Count"), int)


class TestSorting:
    def test_text_sorts_case_insensitively_both_ways(self, model: Any) -> None:
        api, doc = model
        for name in ["B", "a", "C", "d"]:
            doc.CreateElement(name=name, category="Walls")
        descending = api.elements.order_by_descending("Name").execute()
        ascending = api.elements.order_by_ascending("Name").execute()
        assert [e.name for e in descending] == ["d", "C", "B", "a"]
        assert [e.name for e in ascending] == ["a", "B", "C", "d"]

    def test_multi_key_with_mixed_directions(self, model: Any) -> None:
        api, doc = model
        for mark, name in [(2, "B"), (1, "a"), (1, "C"), (2, "d")]:
            doc.CreateElement(name=name, category="Walls").SetParameterValue(
                "Mark", mark
            )
        result = (
            api.elements.order_by_descending("Mark")
            .order_by_ascending("Name")
            .execute()
        )
        assert [(e.get_parameter_value("Mark"), e.name) for e in result] == [
            (2, "B"),
            (2, "d"),
            (1, "a"),
            (1, "C"),
        ]


class TestElementChanges:
    def test_rollback_refreshes_wrappers_from_queries(self, model: Any) -> None:
        api, doc = model
        doc.CreateElement(name="W1", category="Walls")
        wall = api.query(Wall).execute()[0]
        with pytest.raises(RuntimeError):
            with api.transaction("t"):
                wall.set_parameter_value("Comments", "x")
                raise RuntimeError("boom")
        assert wall.get_parameter_value("Comments") == ""
        assert not wall.is_dirty

    def test_discard_restores_unread_value(self, model: Any) -> None:
        api, doc = model
        el = doc.CreateElement(name="W1", category="Walls")
        el.SetParameterValue("Comments", "original")
        wall = api.query(Wall).execute()[0]
        with api.transaction("t"):
            wall.set_parameter_value("Comments", "x")  # never read before
            assert wall.changes == {"Comments": {"old": "original", "new": "x"}}
            wall.discard_changes()
        assert raw(el, "Comments") == "original"
        assert not wall.is_dirty

    def test_repeated_writes_keep_first_old_value(self, model: Any) -> None:
        api, doc = model
        doc.CreateElement(name="W1", category="Walls")
        wall = api.query(Wall).execute()[0]
        with api.transaction("t"):
            wall.set_parameter_value("Comments", "a")
            wall.set_parameter_value("Comments", "b")
            assert wall.changes == {"Comments": {"old": "", "new": "b"}}
            wall.set_parameter_value("Comments", "")
        assert wall.changes == {}
        assert not wall.is_dirty


class TestTransactionGroup:
    def test_commit(self, model: Any) -> None:
        api, doc = model
        el = doc.CreateElement(name="W1", category="Walls")
        group = api.transaction_group("g")
        group.add_transaction()
        group.add_transaction()
        with group:
            api.get_element_by_id(el.Id.Value).set_parameter_value("Comments", "x")
        assert group.status == TransactionStatus.COMMITTED
        assert raw(el, "Comments") == "x"

    def test_rollback(self, model: Any) -> None:
        api, doc = model
        el = doc.CreateElement(name="W1", category="Walls")
        group = api.transaction_group("g")
        group.add_transaction()
        group.add_transaction()
        with pytest.raises(RuntimeError):
            with group:
                api.get_element_by_id(el.Id.Value).set_parameter_value("Comments", "x")
                raise RuntimeError("boom")
        assert group.status == TransactionStatus.ROLLED_BACK
        assert raw(el, "Comments") == ""


class TestQuantityExtraction:
    def test_area_from_parameter_in_square_feet(self, model: Any) -> None:
        api, doc = model
        doc.CreateElement(name="Office", category="Rooms").SetParameterValue(
            "Area", 215.278
        )
        items = QuantityExtractor().extract(api.query(Room).execute())
        area = [i for i in items if i.quantity_type == QuantityType.AREA]
        assert len(area) == 1
        assert area[0].value == pytest.approx(20.0, rel=1e-3)
        assert area[0].unit == "m2"


class TestIfcMapping:
    @pytest.mark.parametrize(
        ("category", "wrapper", "ifc_type"),
        [
            ("Walls", Wall, "IfcWall"),
            ("OST_Doors", Door, "IfcDoor"),
            ("Rooms", Room, "IfcSpace"),
        ],
    )
    def test_wrappers_resolve(
        self, category: str, wrapper: type, ifc_type: str
    ) -> None:
        element = Element.wrap(MockElement(element_id=1, category=category))
        assert isinstance(element, wrapper)
        _, mapping = IfcElementMapper()._resolve_mapping(element)
        assert mapping is not None and mapping.ifc_entity_type == ifc_type

    def test_unknown_category_is_unmapped(self) -> None:
        element = Element.wrap(MockElement(element_id=1, category="Generic"))
        _, mapping = IfcElementMapper()._resolve_mapping(element)
        assert mapping is None

    def test_import_mapping_unchanged(self) -> None:
        assert IfcElementMapper().get_revitpy_type("IfcWall") == "WallElement"
