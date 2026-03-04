"""
Unit tests for SpeckleTypeMapper.
"""

import pytest

from revitpy.interop.exceptions import TypeMappingError
from revitpy.interop.mapper import SpeckleTypeMapper
from revitpy.interop.types import MappingStatus

# ---------------------------------------------------------------------------
# Lightweight mock element classes
# ---------------------------------------------------------------------------


class WallElement:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class PipeElement:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class UnknownWidget:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestSpeckleTypeMapper:
    """Test bidirectional type mapping between RevitPy and Speckle."""

    @pytest.fixture
    def mapper(self):
        """Create a fresh mapper instance."""
        return SpeckleTypeMapper()

    # ------------------------------------------------------------------
    # Default mappings
    # ------------------------------------------------------------------

    def test_default_mappings_populated(self, mapper):
        """Default mappings should be registered on init."""
        assert "WallElement" in mapper.registered_types
        assert "RoomElement" in mapper.registered_types
        assert "DoorElement" in mapper.registered_types

    def test_default_speckle_types_populated(self, mapper):
        """Reverse registry should contain default Speckle types."""
        speckle_types = mapper.registered_speckle_types
        assert "Objects.BuiltElements.Wall:Wall" in speckle_types
        assert "Objects.BuiltElements.Room:Room" in speckle_types

    def test_get_mapping_returns_mapping(self, mapper):
        """get_mapping should return a TypeMapping for known types."""
        mapping = mapper.get_mapping("WallElement")
        assert mapping is not None
        assert mapping.revitpy_type == "WallElement"
        assert mapping.speckle_type == "Objects.BuiltElements.Wall:Wall"
        assert mapping.status == MappingStatus.MAPPED

    def test_get_mapping_returns_none_for_unknown(self, mapper):
        """get_mapping should return None for unknown types."""
        assert mapper.get_mapping("UnknownElement") is None

    # ------------------------------------------------------------------
    # Custom registrations
    # ------------------------------------------------------------------

    def test_register_custom_mapping(self, mapper):
        """Registering a custom mapping should update the registry."""
        mapper.register_mapping(
            "PipeElement",
            "Objects.BuiltElements.Pipe:Pipe",
            property_map={"diameter": "diameter"},
        )
        mapping = mapper.get_mapping("PipeElement")
        assert mapping is not None
        assert mapping.speckle_type == "Objects.BuiltElements.Pipe:Pipe"
        assert mapping.property_map == {"diameter": "diameter"}

    def test_register_mapping_overrides_default(self, mapper):
        """Re-registering an existing type should override it."""
        mapper.register_mapping(
            "WallElement",
            "Objects.BuiltElements.Wall:CustomWall",
        )
        mapping = mapper.get_mapping("WallElement")
        assert mapping.speckle_type == "Objects.BuiltElements.Wall:CustomWall"

    def test_register_updates_reverse_registry(self, mapper):
        """Registering a mapping should also update reverse lookups."""
        mapper.register_mapping(
            "DuctElement",
            "Objects.BuiltElements.Duct:Duct",
        )
        assert "Objects.BuiltElements.Duct:Duct" in mapper.registered_speckle_types

    # ------------------------------------------------------------------
    # to_speckle
    # ------------------------------------------------------------------

    def test_to_speckle_converts_element(self, mapper):
        """to_speckle should produce a Speckle-compatible dict."""
        wall = WallElement(id="wall-1", name="Wall A", height=10)

        result = mapper.to_speckle(wall)

        assert result["speckle_type"] == "Objects.BuiltElements.Wall:Wall"
        assert result["id"] == "wall-1"
        assert result["name"] == "Wall A"

    def test_to_speckle_with_property_map(self, mapper):
        """to_speckle should apply explicit property mappings."""
        mapper.register_mapping(
            "PipeElement",
            "Objects.BuiltElements.Pipe:Pipe",
            property_map={"pipe_diameter": "diameter"},
        )
        pipe = PipeElement(id="pipe-1", name="Pipe A", pipe_diameter=0.15)

        result = mapper.to_speckle(pipe)
        assert result["diameter"] == 0.15

    def test_to_speckle_raises_for_unmapped(self, mapper):
        """to_speckle should raise TypeMappingError for unknown types."""
        obj = UnknownWidget(id="x")

        with pytest.raises(TypeMappingError, match="No Speckle mapping"):
            mapper.to_speckle(obj)

    # ------------------------------------------------------------------
    # from_speckle
    # ------------------------------------------------------------------

    def test_from_speckle_converts_object(self, mapper):
        """from_speckle should produce a RevitPy-compatible dict."""
        speckle_obj = {
            "id": "wall-1",
            "name": "Wall A",
            "speckle_type": "Objects.BuiltElements.Wall:Wall",
            "height": 10,
        }

        result = mapper.from_speckle(speckle_obj)
        assert result["type"] == "WallElement"
        assert result["id"] == "wall-1"
        assert result["name"] == "Wall A"

    def test_from_speckle_with_target_type(self, mapper):
        """from_speckle should use the given target_type."""
        speckle_obj = {
            "id": "wall-1",
            "name": "Wall A",
            "speckle_type": "SomeCustomType",
            "height": 10,
        }

        result = mapper.from_speckle(speckle_obj, target_type="WallElement")
        assert result["type"] == "WallElement"

    def test_from_speckle_raises_for_unmapped(self, mapper):
        """from_speckle should raise TypeMappingError for unknown types."""
        speckle_obj = {
            "id": "x",
            "speckle_type": "Objects.Custom.Unknown:Unknown",
        }

        with pytest.raises(TypeMappingError, match="No RevitPy mapping"):
            mapper.from_speckle(speckle_obj)

    # ------------------------------------------------------------------
    # Unmapped fallback
    # ------------------------------------------------------------------

    def test_get_unmapped_status(self, mapper):
        """get_unmapped_status should return a TypeMapping with UNMAPPED."""
        mapping = mapper.get_unmapped_status("NonExistent")
        assert mapping.revitpy_type == "NonExistent"
        assert mapping.speckle_type == ""
        assert mapping.status == MappingStatus.UNMAPPED
