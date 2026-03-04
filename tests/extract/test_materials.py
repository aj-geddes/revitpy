"""
Unit tests for MaterialTakeoff functionality.
"""

import pytest

from revitpy.extract.exceptions import ExtractionError
from revitpy.extract.materials import MaterialTakeoff
from revitpy.extract.types import MaterialQuantity

from .conftest import MockElement


class TestMaterialTakeoff:
    """Test MaterialTakeoff functionality."""

    def test_extract_materials_from_elements(self, sample_elements):
        """Test extracting material data from elements with materials."""
        takeoff = MaterialTakeoff()
        materials = takeoff.extract(sample_elements)

        # 3 concrete elements + 1 glass element have material_name
        names = [m.material_name for m in materials]
        assert "Concrete" in names
        assert "Glass" in names
        assert len(materials) == 4

    def test_extract_skips_elements_without_material(self):
        """Test that elements without material_name are skipped."""
        elements = [
            MockElement(id=1, name="NoMat", category="Walls"),
        ]
        takeoff = MaterialTakeoff()
        materials = takeoff.extract(elements)

        assert len(materials) == 0

    def test_extract_material_quantities(self, sample_elements):
        """Test that material quantity values are correctly extracted."""
        takeoff = MaterialTakeoff()
        materials = takeoff.extract(sample_elements)

        # Find the first concrete entry (Wall-001)
        wall_concrete = [m for m in materials if m.material_name == "Concrete"][0]

        assert wall_concrete.volume == 5.0
        assert wall_concrete.area == 25.0
        assert wall_concrete.mass == 12000.0

    def test_extract_material_category(self, sample_elements):
        """Test that element category is propagated to material."""
        takeoff = MaterialTakeoff()
        materials = takeoff.extract(sample_elements)

        glass_mat = [m for m in materials if m.material_name == "Glass"][0]
        assert glass_mat.category == "Windows"

    def test_aggregate_materials(self, sample_elements):
        """Test aggregating materials by name."""
        takeoff = MaterialTakeoff()
        raw = takeoff.extract(sample_elements)
        aggregated = takeoff.aggregate(raw)

        # Should reduce 3 Concrete entries to 1
        concrete = [m for m in aggregated if m.material_name == "Concrete"]
        assert len(concrete) == 1

        # Summed values: 5+6+20=31 volume, 25+30+100=155 area
        assert concrete[0].volume == 31.0
        assert concrete[0].area == 155.0
        assert concrete[0].mass == 74400.0

    def test_aggregate_preserves_single_materials(self, sample_elements):
        """Test that single-entry materials survive aggregation."""
        takeoff = MaterialTakeoff()
        raw = takeoff.extract(sample_elements)
        aggregated = takeoff.aggregate(raw)

        glass = [m for m in aggregated if m.material_name == "Glass"]
        assert len(glass) == 1
        assert glass[0].area == 2.5

    def test_aggregate_empty_list(self):
        """Test aggregating an empty list."""
        takeoff = MaterialTakeoff()
        result = takeoff.aggregate([])
        assert result == []

    def test_classify_unifformat(self, sample_elements):
        """Test classification with UniFormat system."""
        takeoff = MaterialTakeoff()
        raw = takeoff.extract(sample_elements)
        aggregated = takeoff.aggregate(raw)
        classified = takeoff.classify(aggregated, system="UniFormat")

        concrete = [m for m in classified if m.material_name == "Concrete"][0]
        assert concrete.classification_code == "A1010"
        assert concrete.classification_system == "UniFormat"

        glass = [m for m in classified if m.material_name == "Glass"][0]
        assert glass.classification_code == "B2020"

    def test_classify_masterformat(self, sample_elements):
        """Test classification with MasterFormat system."""
        takeoff = MaterialTakeoff()
        raw = takeoff.extract(sample_elements)
        aggregated = takeoff.aggregate(raw)
        classified = takeoff.classify(aggregated, system="MasterFormat")

        concrete = [m for m in classified if m.material_name == "Concrete"][0]
        assert concrete.classification_code == "03 00 00"
        assert concrete.classification_system == "MasterFormat"

    def test_classify_unknown_material(self):
        """Test that unknown materials get empty classification code."""
        takeoff = MaterialTakeoff()
        materials = [
            MaterialQuantity(material_name="ExoticAlloy", category="Custom", volume=1.0)
        ]
        classified = takeoff.classify(materials, system="UniFormat")

        assert classified[0].classification_code == ""
        assert classified[0].classification_system == ""

    def test_classify_partial_match(self):
        """Test that partial material name matches work."""
        takeoff = MaterialTakeoff()
        materials = [
            MaterialQuantity(
                material_name="Reinforced Concrete",
                category="Walls",
                volume=10.0,
            )
        ]
        classified = takeoff.classify(materials, system="UniFormat")

        # "concrete" is in "reinforced concrete"
        assert classified[0].classification_code == "A1010"

    def test_extract_fallback_to_generic_attrs(self):
        """Test that extraction falls back to generic volume/area attrs."""
        element = MockElement(
            id=10,
            name="GenericWall",
            category="Walls",
            material_name="Steel",
            area=50.0,
            volume=10.0,
        )
        takeoff = MaterialTakeoff()
        materials = takeoff.extract([element])

        assert len(materials) == 1
        # Falls back to generic area/volume since material_area/material_volume are None
        assert materials[0].area == 50.0
        assert materials[0].volume == 10.0

    def test_extract_with_context(self):
        """Test that context is stored correctly."""
        ctx = object()
        takeoff = MaterialTakeoff(context=ctx)
        assert takeoff._context is ctx

    def test_material_quantity_dataclass(self):
        """Test MaterialQuantity dataclass defaults."""
        mat = MaterialQuantity(material_name="Test", category="Cat")
        assert mat.volume == 0.0
        assert mat.area == 0.0
        assert mat.mass == 0.0
        assert mat.classification_code == ""
        assert mat.classification_system == ""
