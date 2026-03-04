"""
Unit tests for DataExporter functionality.
"""

import json
from pathlib import Path

import pytest

from revitpy.extract.exceptions import ExportError
from revitpy.extract.exporters import _HAS_OPENPYXL, _HAS_PYARROW, DataExporter
from revitpy.extract.types import ExportConfig, ExportFormat


@pytest.fixture
def sample_export_data():
    """Provide sample tabular data for export tests."""
    return [
        {"name": "Wall-001", "area": 25.123456, "cost": 3750.50},
        {"name": "Wall-002", "area": 30.654321, "cost": 4500.75},
        {"name": "Floor-001", "area": 100.0, "cost": 20000.0},
    ]


class TestDataExporter:
    """Test DataExporter functionality."""

    def test_to_csv_creates_file(self, sample_export_data, tmp_export_dir):
        """Test that CSV export creates a file."""
        path = tmp_export_dir / "output.csv"
        exporter = DataExporter()
        result = exporter.to_csv(sample_export_data, path)

        assert result == path
        assert path.exists()

    def test_to_csv_content(self, sample_export_data, tmp_export_dir):
        """Test CSV file content."""
        path = tmp_export_dir / "output.csv"
        exporter = DataExporter()
        exporter.to_csv(sample_export_data, path)

        content = path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        # Header + 3 data rows
        assert len(lines) == 4
        assert "name" in lines[0]
        assert "area" in lines[0]
        assert "Wall-001" in lines[1]

    def test_to_csv_no_headers(self, sample_export_data, tmp_export_dir):
        """Test CSV export without headers."""
        path = tmp_export_dir / "output_no_header.csv"
        exporter = DataExporter()
        exporter.to_csv(sample_export_data, path, include_headers=False)

        content = path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        # 3 data rows only
        assert len(lines) == 3
        assert "name" not in lines[0] or "Wall" in lines[0]

    def test_to_csv_decimal_rounding(self, sample_export_data, tmp_export_dir):
        """Test that floats are rounded in CSV output."""
        path = tmp_export_dir / "output_rounded.csv"
        exporter = DataExporter()
        exporter.to_csv(sample_export_data, path, decimal_places=1)

        content = path.read_text(encoding="utf-8")
        assert "25.1" in content
        assert "25.123456" not in content

    def test_to_csv_empty_data(self, tmp_export_dir):
        """Test CSV export with empty data."""
        path = tmp_export_dir / "empty.csv"
        exporter = DataExporter()
        result = exporter.to_csv([], path)

        assert result == path
        assert path.exists()

    def test_to_csv_requires_path(self, sample_export_data):
        """Test that CSV export raises error without path."""
        exporter = DataExporter()
        with pytest.raises(ExportError):
            exporter.to_csv(sample_export_data, None)

    def test_to_json_creates_file(self, sample_export_data, tmp_export_dir):
        """Test that JSON export creates a file."""
        path = tmp_export_dir / "output.json"
        exporter = DataExporter()
        result = exporter.to_json(sample_export_data, path)

        assert result == path
        assert path.exists()

    def test_to_json_content(self, sample_export_data, tmp_export_dir):
        """Test JSON file content is valid JSON."""
        path = tmp_export_dir / "output.json"
        exporter = DataExporter()
        exporter.to_json(sample_export_data, path)

        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)

        assert len(data) == 3
        assert data[0]["name"] == "Wall-001"

    def test_to_json_decimal_rounding(self, sample_export_data, tmp_export_dir):
        """Test that floats are rounded in JSON output."""
        path = tmp_export_dir / "output_rounded.json"
        exporter = DataExporter()
        exporter.to_json(sample_export_data, path, decimal_places=1)

        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)

        assert data[0]["area"] == 25.1

    def test_to_json_requires_path(self, sample_export_data):
        """Test that JSON export raises error without path."""
        exporter = DataExporter()
        with pytest.raises(ExportError):
            exporter.to_json(sample_export_data, None)

    def test_to_dicts_returns_copy(self, sample_export_data):
        """Test that to_dicts returns a shallow copy."""
        exporter = DataExporter()
        result = exporter.to_dicts(sample_export_data)

        assert result == sample_export_data
        assert result is not sample_export_data
        # Each row should be a new dict
        for orig, copy in zip(sample_export_data, result, strict=True):
            assert orig == copy
            assert orig is not copy

    def test_to_dicts_empty(self):
        """Test to_dicts with empty data."""
        exporter = DataExporter()
        result = exporter.to_dicts([])
        assert result == []

    def test_export_csv_via_config(self, sample_export_data, tmp_export_dir):
        """Test export method with CSV config."""
        config = ExportConfig(
            format=ExportFormat.CSV,
            output_path=tmp_export_dir / "via_config.csv",
        )
        exporter = DataExporter()
        result = exporter.export(sample_export_data, config)

        assert isinstance(result, Path)
        assert result.exists()

    def test_export_json_via_config(self, sample_export_data, tmp_export_dir):
        """Test export method with JSON config."""
        config = ExportConfig(
            format=ExportFormat.JSON,
            output_path=tmp_export_dir / "via_config.json",
        )
        exporter = DataExporter()
        result = exporter.export(sample_export_data, config)

        assert isinstance(result, Path)
        assert result.exists()

    def test_export_dict_via_config(self, sample_export_data):
        """Test export method with DICT config."""
        config = ExportConfig(format=ExportFormat.DICT)
        exporter = DataExporter()
        result = exporter.export(sample_export_data, config)

        assert isinstance(result, list)
        assert len(result) == 3

    def test_export_excel_missing_dep(self, sample_export_data, tmp_export_dir):
        """Test Excel export behavior when openpyxl is absent."""
        if _HAS_OPENPYXL:
            pytest.skip("openpyxl is installed, cannot test missing dep")

        config = ExportConfig(
            format=ExportFormat.EXCEL,
            output_path=tmp_export_dir / "output.xlsx",
        )
        exporter = DataExporter()
        with pytest.raises(ExportError, match="openpyxl"):
            exporter.export(sample_export_data, config)

    def test_export_parquet_missing_dep(self, sample_export_data, tmp_export_dir):
        """Test Parquet export behavior when pyarrow is absent."""
        if _HAS_PYARROW:
            pytest.skip("pyarrow is installed, cannot test missing dep")

        config = ExportConfig(
            format=ExportFormat.PARQUET,
            output_path=tmp_export_dir / "output.parquet",
        )
        exporter = DataExporter()
        with pytest.raises(ExportError, match="pyarrow"):
            exporter.export(sample_export_data, config)

    def test_round_floats(self, sample_export_data):
        """Test the float rounding helper."""
        rounded = DataExporter._round_floats(sample_export_data, 1)

        assert rounded[0]["area"] == 25.1
        assert rounded[1]["area"] == 30.7
        # Non-float values untouched
        assert rounded[0]["name"] == "Wall-001"

    def test_export_config_defaults(self):
        """Test ExportConfig default values."""
        config = ExportConfig()
        assert config.format == ExportFormat.CSV
        assert config.output_path is None
        assert config.include_headers is True
        assert config.decimal_places == 2
        assert config.sheet_name == "Sheet1"
