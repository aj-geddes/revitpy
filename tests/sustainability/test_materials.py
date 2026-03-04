"""
Unit tests for MaterialExtractor functionality.
"""

from __future__ import annotations

import pytest

from revitpy.sustainability.exceptions import SustainabilityError
from revitpy.sustainability.materials import MaterialExtractor
from revitpy.sustainability.types import MaterialData


class MockElement:
    """Mock building element for testing material extraction."""

    def __init__(
        self,
        material_name: str = "Concrete",
        category: str = "Structure",
        volume: float = 10.0,
        area: float = 25.0,
        mass: float = 24000.0,
        density: float | None = 2400.0,
        element_id: str = "E001",
        level: str = "Level 1",
        system: str = "Structure",
    ) -> None:
        self.material_name = material_name
        self.category = category
        self.volume = volume
        self.area = area
        self.mass = mass
        self.density = density
        self.element_id = element_id
        self.level = level
        self.system = system


@pytest.fixture
def extractor() -> MaterialExtractor:
    """Fixture providing a MaterialExtractor instance."""
    return MaterialExtractor()


@pytest.fixture
def mock_elements() -> list[MockElement]:
    """Fixture providing a list of mock building elements."""
    return [
        MockElement(
            material_name="Concrete",
            category="Structure",
            volume=100.0,
            area=250.0,
            mass=240000.0,
            density=2400.0,
            element_id="E001",
            level="Level 1",
            system="Structure",
        ),
        MockElement(
            material_name="Steel",
            category="Structure",
            volume=5.0,
            area=50.0,
            mass=39250.0,
            density=7850.0,
            element_id="E002",
            level="Level 1",
            system="Structure",
        ),
        MockElement(
            material_name="Concrete",
            category="Structure",
            volume=80.0,
            area=200.0,
            mass=192000.0,
            density=2400.0,
            element_id="E003",
            level="Level 2",
            system="Structure",
        ),
        MockElement(
            material_name="Glass",
            category="Glazing",
            volume=2.0,
            area=80.0,
            mass=5000.0,
            density=2500.0,
            element_id="E004",
            level="Level 1",
            system="Envelope",
        ),
    ]


class TestMaterialExtractor:
    """Tests for MaterialExtractor."""

    def test_extract_returns_material_data_list(self, extractor, mock_elements):
        """Test that extraction returns a list of MaterialData."""
        result = extractor.extract(mock_elements)

        assert isinstance(result, list)
        assert len(result) == 4
        assert all(isinstance(m, MaterialData) for m in result)

    def test_extract_preserves_material_name(self, extractor, mock_elements):
        """Test that material names are correctly extracted."""
        result = extractor.extract(mock_elements)

        names = [m.name for m in result]
        assert "Concrete" in names
        assert "Steel" in names
        assert "Glass" in names

    def test_extract_preserves_quantities(self, extractor):
        """Test that volume, area, and mass are extracted correctly."""
        elements = [
            MockElement(
                volume=50.0,
                area=120.0,
                mass=120000.0,
            )
        ]
        result = extractor.extract(elements)

        assert result[0].volume_m3 == 50.0
        assert result[0].area_m2 == 120.0
        assert result[0].mass_kg == 120000.0

    def test_extract_computes_mass_from_volume_and_density(self, extractor):
        """Test mass is computed when missing but volume and density exist."""
        elements = [
            MockElement(
                volume=10.0,
                mass=0.0,
                density=2400.0,
            )
        ]
        result = extractor.extract(elements)

        assert result[0].mass_kg == 24000.0

    def test_extract_preserves_level_and_system(self, extractor, mock_elements):
        """Test that level and system attributes are preserved."""
        result = extractor.extract(mock_elements)

        assert result[0].level == "Level 1"
        assert result[0].system == "Structure"

    def test_extract_handles_missing_attributes(self, extractor):
        """Test extraction handles elements with missing attributes."""

        class MinimalElement:
            pass

        result = extractor.extract([MinimalElement()])

        assert len(result) == 1
        assert result[0].name == "Unknown"
        assert result[0].category == "Uncategorized"
        assert result[0].mass_kg == 0.0

    def test_extract_empty_list(self, extractor):
        """Test extraction of an empty element list."""
        result = extractor.extract([])

        assert result == []

    def test_aggregate_sums_quantities(self, extractor, mock_elements):
        """Test that aggregation sums quantities by material name."""
        materials = extractor.extract(mock_elements)
        aggregated = extractor.aggregate(materials)

        concrete = next(m for m in aggregated if m.name == "Concrete")
        assert concrete.volume_m3 == 180.0
        assert concrete.area_m2 == 450.0
        assert concrete.mass_kg == 432000.0

    def test_aggregate_reduces_duplicates(self, extractor, mock_elements):
        """Test that aggregation reduces duplicate material names."""
        materials = extractor.extract(mock_elements)
        aggregated = extractor.aggregate(materials)

        names = [m.name for m in aggregated]
        assert len(names) == len(set(names))
        assert len(aggregated) == 3  # Concrete, Steel, Glass

    def test_aggregate_preserves_unique_materials(self, extractor):
        """Test that unique materials are preserved in aggregation."""
        materials = [
            MaterialData(name="Timber", category="Framing", mass_kg=100.0),
            MaterialData(name="Steel", category="Metals", mass_kg=200.0),
        ]
        aggregated = extractor.aggregate(materials)

        assert len(aggregated) == 2

    def test_classify_adds_unifformat_codes(self, extractor):
        """Test classification with UniFormat codes."""
        materials = [
            MaterialData(name="Concrete Mix", category="Structure"),
            MaterialData(name="Structural Steel", category="Structure"),
            MaterialData(name="Glass Panel", category="Glazing"),
        ]
        classified = extractor.classify(materials, system="UniFormat")

        assert "[B1010]" in classified[0].category
        assert "[B1020]" in classified[1].category
        assert "[B2020]" in classified[2].category

    def test_classify_adds_masterformat_codes(self, extractor):
        """Test classification with MasterFormat codes."""
        materials = [
            MaterialData(name="Concrete Mix", category="Structure"),
            MaterialData(name="Structural Steel", category="Structure"),
        ]
        classified = extractor.classify(materials, system="MasterFormat")

        assert "[03 00 00]" in classified[0].category
        assert "[05 00 00]" in classified[1].category

    def test_classify_preserves_category_for_unknown(self, extractor):
        """Test that unrecognized materials keep their original category."""
        materials = [
            MaterialData(name="ExoticMaterial", category="Special"),
        ]
        classified = extractor.classify(materials)

        assert classified[0].category == "Special"

    def test_classify_does_not_modify_originals(self, extractor):
        """Test that classification returns new objects."""
        materials = [
            MaterialData(name="Concrete", category="Structure"),
        ]
        classified = extractor.classify(materials)

        assert classified[0] is not materials[0]
        assert materials[0].category == "Structure"

    def test_extractor_with_context(self):
        """Test MaterialExtractor initializes with context."""
        context = object()
        extractor = MaterialExtractor(context=context)
        assert extractor._context is context
