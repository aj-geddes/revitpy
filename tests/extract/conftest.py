"""
Pytest configuration and fixtures for extraction layer tests.
"""

import tempfile
from pathlib import Path
from typing import Any

import pytest

from revitpy.extract.types import (
    AggregationLevel,
    CostSource,
    QuantityItem,
    QuantityType,
)


class MockElement:
    """Mock Revit element with quantity and material attributes."""

    def __init__(
        self,
        *,
        id: int = 1,
        name: str = "Element",
        category: str = "Walls",
        level: str = "Level 1",
        system: str = "",
        area: float | None = None,
        volume: float | None = None,
        length: float | None = None,
        weight: float | None = None,
        material_name: str | None = None,
        material_volume: float | None = None,
        material_area: float | None = None,
        material_mass: float | None = None,
    ):
        self.id = id
        self.name = name
        self.category = category
        self.level = level
        self.system = system
        self.area = area
        self.volume = volume
        self.length = length
        self.weight = weight
        self.material_name = material_name
        self.material_volume = material_volume
        self.material_area = material_area
        self.material_mass = material_mass


@pytest.fixture
def sample_elements() -> list[MockElement]:
    """Provide a list of mock elements with various quantity attributes."""
    return [
        MockElement(
            id=1,
            name="Wall-001",
            category="Walls",
            level="Level 1",
            system="Structure",
            area=25.0,
            volume=5.0,
            length=10.0,
            material_name="Concrete",
            material_volume=5.0,
            material_area=25.0,
            material_mass=12000.0,
        ),
        MockElement(
            id=2,
            name="Wall-002",
            category="Walls",
            level="Level 1",
            system="Structure",
            area=30.0,
            volume=6.0,
            length=12.0,
            material_name="Concrete",
            material_volume=6.0,
            material_area=30.0,
            material_mass=14400.0,
        ),
        MockElement(
            id=3,
            name="Floor-001",
            category="Floors",
            level="Level 1",
            system="Structure",
            area=100.0,
            volume=20.0,
            material_name="Concrete",
            material_volume=20.0,
            material_area=100.0,
            material_mass=48000.0,
        ),
        MockElement(
            id=4,
            name="Room-101",
            category="Rooms",
            level="Level 2",
            area=50.0,
            volume=150.0,
        ),
        MockElement(
            id=5,
            name="Window-001",
            category="Windows",
            level="Level 2",
            area=2.5,
            material_name="Glass",
            material_area=2.5,
        ),
    ]


@pytest.fixture
def sample_quantities() -> list[QuantityItem]:
    """Provide a list of pre-built QuantityItem instances."""
    return [
        QuantityItem(
            element_id=1,
            element_name="Wall-001",
            category="Walls",
            quantity_type=QuantityType.AREA,
            value=25.0,
            unit="m2",
            level="Level 1",
            system="Structure",
        ),
        QuantityItem(
            element_id=2,
            element_name="Wall-002",
            category="Walls",
            quantity_type=QuantityType.AREA,
            value=30.0,
            unit="m2",
            level="Level 1",
            system="Structure",
        ),
        QuantityItem(
            element_id=3,
            element_name="Floor-001",
            category="Floors",
            quantity_type=QuantityType.AREA,
            value=100.0,
            unit="m2",
            level="Level 1",
            system="Structure",
        ),
        QuantityItem(
            element_id=1,
            element_name="Wall-001",
            category="Walls",
            quantity_type=QuantityType.VOLUME,
            value=5.0,
            unit="m3",
            level="Level 1",
            system="Structure",
        ),
        QuantityItem(
            element_id=4,
            element_name="Room-101",
            category="Rooms",
            quantity_type=QuantityType.VOLUME,
            value=150.0,
            unit="m3",
            level="Level 2",
        ),
    ]


@pytest.fixture
def mock_cost_database() -> dict[str, float]:
    """Provide a cost database mapping categories to unit costs."""
    return {
        "Walls": 150.0,
        "Floors": 200.0,
        "Rooms": 0.0,
        "Windows": 500.0,
        "Doors": 350.0,
        "Roofs": 180.0,
    }


@pytest.fixture
def tmp_export_dir() -> Path:
    """Provide a temporary directory for export tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
