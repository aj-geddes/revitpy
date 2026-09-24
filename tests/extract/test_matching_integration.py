"""
Tests for deterministic scored matching in cost lookup, material
classification, and element-name fallback in quantity extraction.
"""

from __future__ import annotations

from typing import Any

import pytest

from revitpy.extract.costs import CostEstimator
from revitpy.extract.materials import MaterialTakeoff
from revitpy.extract.quantities import QuantityExtractor
from revitpy.extract.types import MaterialQuantity, QuantityItem, QuantityType


def _qty(category: str) -> QuantityItem:
    return QuantityItem(
        element_id=1,
        element_name="Element",
        category=category,
        quantity_type=QuantityType.AREA,
        value=10.0,
        unit="m2",
    )


class _Elem:
    def __init__(self, *, id: Any = None, name: Any = None, area: float = 5.0):
        self.id = id
        self.name = name
        self.category = "Walls"
        self.level = "Level 1"
        self.system = ""
        self.area = area


class _ElemWithoutName:
    def __init__(self, *, id: Any, area: float = 5.0):
        self.id = id
        self.area = area


class TestCostMatching:
    DB = {"Walls": 100.0, "Curtain Walls": 400.0, "Doors": 50.0}

    def test_exact_match(self):
        item = CostEstimator(self.DB).estimate([_qty("Curtain Walls")]).items[0]

        assert item.unit_cost == 400.0
        assert item.matched_key == "Curtain Walls"
        assert item.match_type == "exact"
        assert item.match_confidence == 1.0

    def test_case_insensitive_is_exact(self):
        item = CostEstimator(self.DB).estimate([_qty("walls")]).items[0]

        assert item.unit_cost == 100.0
        assert item.matched_key == "Walls"
        assert item.match_type == "exact"

    def test_longest_key_wins_within_same_span(self):
        item = (
            CostEstimator(self.DB).estimate([_qty("Exterior Curtain Walls")]).items[0]
        )

        assert item.unit_cost == 400.0
        assert item.matched_key == "Curtain Walls"
        assert item.match_type == "token"
        assert item.match_confidence < 1.0

    def test_compound_name_is_deterministic_and_low_confidence(self):
        db1 = {"Aluminum": 900.0, "Timber": 300.0}
        db2 = {"Timber": 300.0, "Aluminum": 900.0}
        query = [_qty("Aluminum-Clad Timber Window")]

        item1 = CostEstimator(db1).estimate(query).items[0]
        item2 = CostEstimator(db2).estimate(query).items[0]

        assert item1.unit_cost == item2.unit_cost == 300.0
        assert item1.match_confidence == item2.match_confidence
        assert item1.match_confidence < 0.5

    def test_unmatched_category_is_skipped(self):
        summary = CostEstimator(self.DB).estimate([_qty("Plumbing")])

        assert summary.items == []
        assert summary.total_cost == 0.0


class TestClassificationMatching:
    def test_compound_name(self):
        result = MaterialTakeoff().classify(
            [MaterialQuantity("Aluminum-Clad Wood Window", "Windows")],
            system="UniFormat",
        )[0]

        assert result.classification_code == "A1030"
        assert result.classification_match == "token"
        assert result.classification_confidence is not None
        assert result.classification_confidence < 0.5

    def test_compound_name_masterformat(self):
        result = MaterialTakeoff().classify(
            [MaterialQuantity("Aluminum-Clad Wood Window", "Windows")],
            system="MasterFormat",
        )[0]

        assert result.classification_code == "06 00 00"

    def test_exact_name(self):
        result = MaterialTakeoff().classify([MaterialQuantity("Wood", "Framing")])[0]

        assert result.classification_code == "A1030"
        assert result.classification_match == "exact"
        assert result.classification_confidence == 1.0

    def test_unknown_name(self):
        result = MaterialTakeoff().classify([MaterialQuantity("Unobtanium", "Misc")])[0]

        assert result.classification_code == ""
        assert result.classification_system == ""
        assert result.classification_match == "none"
        assert result.classification_confidence is None


class TestElementNameFallback:
    @pytest.mark.parametrize(
        ("element", "expected"),
        [
            (_Elem(id=None, name=None), "Unknown"),
            (_Elem(id=42, name=None), "42"),
            (_Elem(id=42, name=""), "42"),
            (_Elem(id=1, name="Wall A"), "Wall A"),
            (_ElemWithoutName(id=7), "7"),
            (_ElemWithoutName(id=None), "Unknown"),
        ],
    )
    def test_element_name(self, element, expected):
        items = QuantityExtractor().extract(
            [element], quantity_types=[QuantityType.AREA]
        )

        assert len(items) == 1
        assert items[0].element_name == expected
