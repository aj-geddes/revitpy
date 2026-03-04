"""
Tests for the IFC exporter.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from revitpy.ifc.exceptions import IfcExportError
from revitpy.ifc.exporter import IfcExporter
from revitpy.ifc.types import IfcExportConfig, IfcVersion


def _make_mock_ifcopenshell():
    """Create a mock ifcopenshell module suitable for sys.modules."""
    mock_ifc = MagicMock()
    mock_ifc.guid.new.return_value = "test-guid"
    mock_file = MagicMock()
    mock_file.create_entity.return_value = MagicMock()
    mock_file.write = MagicMock()
    mock_ifc.file.return_value = mock_file
    return mock_ifc, mock_file


class TestIfcExporter:
    """Tests for IfcExporter."""

    def test_init_defaults(self):
        """Exporter should initialise with default mapper and config."""
        exporter = IfcExporter()
        assert exporter.mapper is not None
        assert exporter.config is not None
        assert exporter.config.version == IfcVersion.IFC4

    def test_init_with_custom_config(self):
        """Exporter should accept a custom config."""
        config = IfcExportConfig(
            version=IfcVersion.IFC2X3,
            site_name="Test Site",
            building_name="Test Building",
            author="Tester",
        )
        exporter = IfcExporter(config=config)
        assert exporter.config.site_name == "Test Site"
        assert exporter.config.author == "Tester"

    def test_export_empty_elements_raises(self, tmp_path):
        """Exporting an empty list should raise IfcExportError."""
        exporter = IfcExporter()
        with pytest.raises(IfcExportError, match="No elements"):
            exporter.export([], tmp_path / "out.ifc")

    def test_export_requires_ifcopenshell(self, tmp_path, sample_elements):
        """export should raise ImportError when ifcopenshell is missing."""
        exporter = IfcExporter()
        with patch(
            "revitpy.ifc.exporter.require_ifcopenshell",
            side_effect=ImportError("not installed"),
        ):
            with pytest.raises(ImportError):
                exporter.export(sample_elements, tmp_path / "out.ifc")

    def test_export_calls_mapper(self, tmp_path, sample_elements):
        """export should delegate to mapper.to_ifc for each element."""
        mock_ifc, mock_file = _make_mock_ifcopenshell()
        exporter = IfcExporter()
        exporter._mapper.to_ifc = MagicMock(return_value=MagicMock())

        with (
            patch("revitpy.ifc.exporter.require_ifcopenshell"),
            patch.dict(sys.modules, {"ifcopenshell": mock_ifc}),
        ):
            result = exporter.export(
                sample_elements,
                tmp_path / "out.ifc",
                version=IfcVersion.IFC4,
            )

        assert exporter._mapper.to_ifc.call_count == len(sample_elements)
        assert result == tmp_path / "out.ifc"

    def test_export_version_parameter(self, tmp_path, sample_elements):
        """export should pass the correct IFC version."""
        mock_ifc, mock_file = _make_mock_ifcopenshell()
        exporter = IfcExporter()
        exporter._mapper.to_ifc = MagicMock(return_value=MagicMock())

        with (
            patch("revitpy.ifc.exporter.require_ifcopenshell"),
            patch.dict(sys.modules, {"ifcopenshell": mock_ifc}),
        ):
            exporter.export(
                sample_elements,
                tmp_path / "out.ifc",
                version=IfcVersion.IFC2X3,
            )

        mock_ifc.file.assert_called_once_with(schema="IFC2X3")

    def test_export_handles_unmapped_elements(self, tmp_path):
        """export should skip elements that raise IfcExportError in mapper."""
        mock_ifc, mock_file = _make_mock_ifcopenshell()
        exporter = IfcExporter()

        unmapped = SimpleNamespace(id=99, name="Alien", category="AlienElement")
        elements = [unmapped]

        exporter._mapper.to_ifc = MagicMock(side_effect=IfcExportError("unmapped"))

        with (
            patch("revitpy.ifc.exporter.require_ifcopenshell"),
            patch.dict(sys.modules, {"ifcopenshell": mock_ifc}),
        ):
            result = exporter.export(elements, tmp_path / "out.ifc")

        assert result == tmp_path / "out.ifc"

    @pytest.mark.asyncio
    async def test_export_async_delegates(self, tmp_path, sample_elements):
        """export_async should delegate to export via asyncio.to_thread."""
        exporter = IfcExporter()
        exporter.export = MagicMock(return_value=tmp_path / "out.ifc")

        result = await exporter.export_async(
            sample_elements,
            tmp_path / "out.ifc",
        )

        exporter.export.assert_called_once()
        assert result == tmp_path / "out.ifc"

    @pytest.mark.asyncio
    async def test_export_async_progress_callback(self, tmp_path, sample_elements):
        """export_async should invoke the progress callback."""
        exporter = IfcExporter()
        exporter.export = MagicMock(return_value=tmp_path / "out.ifc")

        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        await exporter.export_async(
            sample_elements,
            tmp_path / "out.ifc",
            progress=on_progress,
        )

        assert (0, len(sample_elements)) in progress_calls
        assert (len(sample_elements), len(sample_elements)) in progress_calls
