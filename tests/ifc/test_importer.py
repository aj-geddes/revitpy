"""
Tests for the IFC importer.
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from revitpy.ifc.exceptions import IfcImportError
from revitpy.ifc.importer import IfcImporter
from revitpy.ifc.types import IfcImportConfig


def _make_mock_ifcopenshell(ifc_file=None):
    """Create a mock ifcopenshell module suitable for sys.modules."""
    mock_ifc = MagicMock()
    if ifc_file is not None:
        mock_ifc.open.return_value = ifc_file
    return mock_ifc


class TestIfcImporter:
    """Tests for IfcImporter."""

    def test_init_defaults(self):
        """Importer should initialise with default mapper and config."""
        importer = IfcImporter()
        assert importer.mapper is not None
        assert importer.config is not None
        assert importer.config.merge_strategy == "replace"

    def test_init_with_custom_config(self):
        """Importer should accept a custom config."""
        config = IfcImportConfig(
            merge_strategy="merge",
            update_existing=False,
            property_mapping={"Name": "display_name"},
        )
        importer = IfcImporter(config=config)
        assert importer.config.merge_strategy == "merge"
        assert importer.config.property_mapping == {"Name": "display_name"}

    def test_import_requires_ifcopenshell(self, tmp_path):
        """import_file should raise ImportError when ifcopenshell is missing."""
        importer = IfcImporter()
        ifc_path = tmp_path / "test.ifc"
        ifc_path.write_text("ISO-10303-21;")

        with patch(
            "revitpy.ifc.importer.require_ifcopenshell",
            side_effect=ImportError("not installed"),
        ):
            with pytest.raises(ImportError):
                importer.import_file(ifc_path)

    def test_import_file_not_found(self, tmp_path):
        """import_file should raise IfcImportError for missing files."""
        importer = IfcImporter()

        with pytest.raises(IfcImportError, match="not found"):
            importer.import_file(tmp_path / "missing.ifc")

    def test_import_file_processes_entities(self, tmp_path):
        """import_file should call from_ifc for each recognized entity."""
        importer = IfcImporter()

        wall_entity = SimpleNamespace(GlobalId="w-1", Name="Wall 1")
        wall_entity.is_a = lambda: "IfcWall"

        door_entity = SimpleNamespace(GlobalId="d-1", Name="Door 1")
        door_entity.is_a = lambda: "IfcDoor"

        mock_ifc_file = MagicMock()

        def by_type_side_effect(entity_type):
            mapping = {
                "IfcWall": [wall_entity],
                "IfcDoor": [door_entity],
            }
            return mapping.get(entity_type, [])

        mock_ifc_file.by_type = MagicMock(side_effect=by_type_side_effect)

        ifc_path = tmp_path / "test.ifc"
        ifc_path.write_text("ISO-10303-21;")

        mock_ifc = _make_mock_ifcopenshell(mock_ifc_file)

        with (
            patch("revitpy.ifc.importer.require_ifcopenshell"),
            patch.dict(sys.modules, {"ifcopenshell": mock_ifc}),
        ):
            results = importer.import_file(ifc_path)

        assert len(results) == 2
        types = {r["type"] for r in results}
        assert "WallElement" in types
        assert "DoorElement" in types

    def test_import_applies_property_mapping(self, tmp_path):
        """import_file should apply config property_mapping overrides."""
        config = IfcImportConfig(
            property_mapping={"name": "display_name"},
        )
        importer = IfcImporter(config=config)

        wall_entity = SimpleNamespace(GlobalId="w-1", Name="Wall 1")
        wall_entity.is_a = lambda: "IfcWall"

        mock_ifc_file = MagicMock()
        mock_ifc_file.by_type = MagicMock(
            side_effect=lambda t: [wall_entity] if t == "IfcWall" else []
        )

        ifc_path = tmp_path / "test.ifc"
        ifc_path.write_text("ISO-10303-21;")

        mock_ifc = _make_mock_ifcopenshell(mock_ifc_file)

        with (
            patch("revitpy.ifc.importer.require_ifcopenshell"),
            patch.dict(sys.modules, {"ifcopenshell": mock_ifc}),
        ):
            results = importer.import_file(ifc_path)

        assert len(results) == 1
        result = results[0]
        assert "display_name" in result
        assert "name" not in result

    def test_import_skips_unmapped_entities(self, tmp_path):
        """import_file should skip entities with no reverse mapping."""
        importer = IfcImporter()

        mock_ifc_file = MagicMock()
        mock_ifc_file.by_type = MagicMock(return_value=[])

        ifc_path = tmp_path / "test.ifc"
        ifc_path.write_text("ISO-10303-21;")

        mock_ifc = _make_mock_ifcopenshell(mock_ifc_file)

        with (
            patch("revitpy.ifc.importer.require_ifcopenshell"),
            patch.dict(sys.modules, {"ifcopenshell": mock_ifc}),
        ):
            results = importer.import_file(ifc_path)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_import_async_delegates(self, tmp_path):
        """import_file_async should delegate to import_file."""
        importer = IfcImporter()
        expected = [{"type": "WallElement", "name": "Test"}]
        importer.import_file = MagicMock(return_value=expected)

        result = await importer.import_file_async(tmp_path / "test.ifc")

        importer.import_file.assert_called_once()
        assert result == expected

    def test_import_open_failure_raises(self, tmp_path):
        """import_file should wrap ifcopenshell.open failures."""
        importer = IfcImporter()
        ifc_path = tmp_path / "corrupt.ifc"
        ifc_path.write_text("NOT-IFC-DATA")

        mock_ifc = MagicMock()
        mock_ifc.open.side_effect = RuntimeError("corrupt file")

        with (
            patch("revitpy.ifc.importer.require_ifcopenshell"),
            patch.dict(sys.modules, {"ifcopenshell": mock_ifc}),
        ):
            with pytest.raises(IfcImportError, match="Failed to open"):
                importer.import_file(ifc_path)
