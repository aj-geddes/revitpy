"""
Tests for the IFC element mapper.
"""

from types import SimpleNamespace

import pytest

from revitpy.ifc.exceptions import IfcExportError, IfcImportError
from revitpy.ifc.mapper import IfcElementMapper
from revitpy.ifc.types import IfcMapping


class TestIfcElementMapper:
    """Tests for IfcElementMapper."""

    def test_default_mappings_loaded(self):
        """Mapper should load default mappings on init."""
        mapper = IfcElementMapper()
        assert mapper.get_ifc_type("WallElement") == "IfcWall"
        assert mapper.get_ifc_type("RoomElement") == "IfcSpace"
        assert mapper.get_ifc_type("DoorElement") == "IfcDoor"
        assert mapper.get_ifc_type("WindowElement") == "IfcWindow"

    def test_reverse_mapping(self):
        """Mapper should support reverse lookup from IFC to RevitPy type."""
        mapper = IfcElementMapper()
        assert mapper.get_revitpy_type("IfcWall") == "WallElement"
        assert mapper.get_revitpy_type("IfcSpace") == "RoomElement"
        assert mapper.get_revitpy_type("IfcDoor") == "DoorElement"

    def test_unmapped_type_returns_none(self):
        """Mapper should return None for unknown types."""
        mapper = IfcElementMapper()
        assert mapper.get_ifc_type("UnknownElement") is None
        assert mapper.get_revitpy_type("IfcUnknown") is None

    def test_register_custom_mapping(self):
        """Mapper should accept custom type registrations."""
        mapper = IfcElementMapper()
        mapper.register_mapping(
            "CurtainWallElement",
            "IfcCurtainWall",
            property_map={"panel_count": "PanelCount"},
        )

        assert mapper.get_ifc_type("CurtainWallElement") == "IfcCurtainWall"
        assert mapper.get_revitpy_type("IfcCurtainWall") == "CurtainWallElement"

        mapping = mapper.get_mapping("CurtainWallElement")
        assert mapping is not None
        assert mapping.property_map == {"panel_count": "PanelCount"}

    def test_register_unidirectional_mapping(self):
        """Unidirectional mappings should not appear in reverse registry."""
        mapper = IfcElementMapper()
        mapper.register_mapping(
            "SpecialElement",
            "IfcBuildingElementProxy",
            bidirectional=False,
        )

        assert mapper.get_ifc_type("SpecialElement") == "IfcBuildingElementProxy"
        # Should not override any existing reverse mapping
        assert mapper.get_revitpy_type("IfcBuildingElementProxy") is None

    def test_override_existing_mapping(self):
        """Registering a mapping for an existing type should override it."""
        mapper = IfcElementMapper()
        mapper.register_mapping("WallElement", "IfcWallStandardCase")

        assert mapper.get_ifc_type("WallElement") == "IfcWallStandardCase"

    def test_get_mapping_returns_ifc_mapping(self, sample_ifc_mapping):
        """get_mapping should return an IfcMapping dataclass."""
        mapper = IfcElementMapper()
        mapping = mapper.get_mapping("WallElement")
        assert isinstance(mapping, IfcMapping)
        assert mapping.revitpy_type == "WallElement"
        assert mapping.ifc_entity_type == "IfcWall"

    def test_registered_types_property(self):
        """registered_types should list all RevitPy type names."""
        mapper = IfcElementMapper()
        types = mapper.registered_types
        assert "WallElement" in types
        assert "DoorElement" in types

    def test_registered_ifc_types_property(self):
        """registered_ifc_types should list all IFC entity type names."""
        mapper = IfcElementMapper()
        ifc_types = mapper.registered_ifc_types
        assert "IfcWall" in ifc_types
        assert "IfcDoor" in ifc_types

    def test_from_ifc_unmapped_raises_import_error(self):
        """from_ifc should raise IfcImportError for unmapped types."""
        mapper = IfcElementMapper()
        entity = SimpleNamespace(GlobalId="abc-123", Name="Unknown")
        entity.is_a = lambda: "IfcUnknownEntity"

        with pytest.raises(IfcImportError):
            mapper.from_ifc(entity)

    def test_from_ifc_with_explicit_target_type(self):
        """from_ifc should accept an explicit target_type."""
        mapper = IfcElementMapper()
        entity = SimpleNamespace(GlobalId="abc-123", Name="MyWall")
        entity.is_a = lambda: "IfcWallStandardCase"

        result = mapper.from_ifc(entity, target_type="WallElement")
        assert result["type"] == "WallElement"
        assert result["global_id"] == "abc-123"
        assert result["name"] == "MyWall"

    def test_from_ifc_applies_property_map(self):
        """from_ifc should apply reverse property mappings."""
        mapper = IfcElementMapper()
        mapper.register_mapping(
            "WallElement",
            "IfcWall",
            property_map={"height": "Height"},
        )

        entity = SimpleNamespace(GlobalId="g-1", Name="W1", Height=3.0)
        entity.is_a = lambda: "IfcWall"

        result = mapper.from_ifc(entity)
        assert result["height"] == 3.0

    def test_bidirectional_round_trip(self):
        """Mapping should work consistently in both directions."""
        mapper = IfcElementMapper()
        for revit_type, ifc_type in IfcElementMapper._DEFAULT_MAPPINGS.items():
            assert mapper.get_ifc_type(revit_type) == ifc_type
            assert mapper.get_revitpy_type(ifc_type) == revit_type
