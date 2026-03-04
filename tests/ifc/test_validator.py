"""
Tests for the IDS validator.
"""

import json
from types import SimpleNamespace

import pytest

from revitpy.ifc.exceptions import IdsValidationError
from revitpy.ifc.types import IdsRequirement, IdsValidationResult
from revitpy.ifc.validator import IdsValidator


class TestIdsValidator:
    """Tests for IdsValidator."""

    def test_validate_all_pass(self, sample_elements, sample_ids_requirements):
        """All requirements should pass for well-formed elements."""
        validator = IdsValidator()

        # Filter to wall elements and their specific requirement
        walls = [e for e in sample_elements if e.category == "WallElement"]
        height_req = [
            r for r in sample_ids_requirements if r.name == "Wall height check"
        ]

        results = validator.validate(walls, height_req)

        for result in results:
            assert result.passed is True

    def test_validate_missing_property_fails(self):
        """A required property that is absent should fail."""
        validator = IdsValidator()

        element = SimpleNamespace(id=10, name="Bare Wall", category="WallElement")
        # 'height' is not set on this element

        requirement = IdsRequirement(
            name="Height required",
            entity_type="WallElement",
            property_name="height",
            required=True,
        )

        results = validator.validate([element], [requirement])

        assert len(results) == 1
        assert results[0].passed is False
        assert "missing" in results[0].message.lower()

    def test_validate_wrong_value_fails(self, sample_elements):
        """A property with the wrong value should fail."""
        validator = IdsValidator()

        # The second wall has material="Drywall", requirement expects
        # "Concrete"
        wall = sample_elements[1]  # Interior Wall, material=Drywall
        requirement = IdsRequirement(
            name="Material check",
            entity_type="WallElement",
            property_name="material",
            property_value="Concrete",
            required=True,
        )

        results = validator.validate([wall], [requirement])

        assert len(results) == 1
        assert results[0].passed is False
        assert "Drywall" in results[0].message

    def test_validate_correct_value_passes(self, sample_elements):
        """A property with the correct value should pass."""
        validator = IdsValidator()

        wall = sample_elements[0]  # Exterior Wall, material=Concrete
        requirement = IdsRequirement(
            name="Material check",
            entity_type="WallElement",
            property_name="material",
            property_value="Concrete",
            required=True,
        )

        results = validator.validate([wall], [requirement])

        assert len(results) == 1
        assert results[0].passed is True

    def test_validate_non_applicable_skipped(self, sample_elements):
        """Requirements for different entity types should be skipped."""
        validator = IdsValidator()

        door = sample_elements[2]  # DoorElement
        wall_req = IdsRequirement(
            name="Wall-only check",
            entity_type="WallElement",
            property_name="height",
            required=True,
        )

        results = validator.validate([door], [wall_req])

        assert len(results) == 1
        assert results[0].passed is True
        assert "not applicable" in results[0].message.lower()

    def test_validate_no_property_name_passes(self, sample_elements):
        """A requirement with no property_name should always pass."""
        validator = IdsValidator()

        requirement = IdsRequirement(
            name="Existence check",
            entity_type="WallElement",
        )

        walls = [e for e in sample_elements if e.category == "WallElement"]
        results = validator.validate(walls, [requirement])

        for result in results:
            assert result.passed is True

    def test_validate_multiple_requirements(
        self, sample_elements, sample_ids_requirements
    ):
        """Multiple requirements should all be checked per element."""
        validator = IdsValidator()

        results = validator.validate(sample_elements, sample_ids_requirements)

        # 5 elements x 4 requirements = 20 results
        assert len(results) == 20

    def test_validate_returns_ids_validation_result(self, sample_elements):
        """Each result should be an IdsValidationResult dataclass."""
        validator = IdsValidator()

        requirement = IdsRequirement(
            name="Type check",
            property_name="name",
            required=True,
        )

        results = validator.validate(sample_elements, [requirement])

        for result in results:
            assert isinstance(result, IdsValidationResult)
            assert result.requirement is requirement

    def test_validate_from_file(self, tmp_path, sample_elements):
        """validate_from_file should load requirements from JSON."""
        validator = IdsValidator()

        requirements_data = [
            {
                "name": "Name required",
                "description": "All elements need a name",
                "property_name": "name",
                "required": True,
            }
        ]

        ids_file = tmp_path / "requirements.json"
        ids_file.write_text(json.dumps(requirements_data))

        results = validator.validate_from_file(sample_elements, ids_file)

        assert len(results) == len(sample_elements)
        for result in results:
            assert result.passed is True

    def test_validate_from_file_not_found(self, tmp_path, sample_elements):
        """validate_from_file should raise for missing files."""
        validator = IdsValidator()

        with pytest.raises(IdsValidationError, match="not found"):
            validator.validate_from_file(sample_elements, tmp_path / "missing.json")

    def test_validate_from_file_invalid_json(self, tmp_path, sample_elements):
        """validate_from_file should raise for malformed JSON."""
        validator = IdsValidator()

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json")

        with pytest.raises(IdsValidationError, match="Failed to parse"):
            validator.validate_from_file(sample_elements, bad_file)

    def test_validate_property_exists_no_value_check(self):
        """Property existence without value check should pass when present."""
        validator = IdsValidator()

        element = SimpleNamespace(
            id=1, name="Test", category="TestElement", color="red"
        )
        requirement = IdsRequirement(
            name="Color exists",
            entity_type="TestElement",
            property_name="color",
            required=True,
        )

        results = validator.validate([element], [requirement])
        assert results[0].passed is True
        assert results[0].actual_value == "red"
