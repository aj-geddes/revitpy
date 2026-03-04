"""
Unit tests for SustainabilityReporter functionality.
"""

from __future__ import annotations

import json

import pytest

from revitpy.sustainability.exceptions import ReportGenerationError
from revitpy.sustainability.reports import SustainabilityReporter
from revitpy.sustainability.types import (
    BuildingCarbonSummary,
    CertificationSystem,
    ReportFormat,
)


@pytest.fixture
def reporter() -> SustainabilityReporter:
    """Fixture providing a SustainabilityReporter instance."""
    return SustainabilityReporter()


@pytest.fixture
def summary() -> BuildingCarbonSummary:
    """Fixture providing a sample summary for report testing."""
    return BuildingCarbonSummary(
        total_embodied_carbon_kgco2e=417350.0,
        by_material={
            "Concrete": 156000.0,
            "Steel": 243350.0,
            "Timber": 18000.0,
        },
        by_system={
            "Structure": 399350.0,
            "Framing": 18000.0,
        },
        by_level={
            "Level 1": 399350.0,
            "Level 2": 18000.0,
        },
        by_lifecycle_stage={
            "A1": 139116.67,
            "A2": 139116.67,
            "A3": 139116.67,
        },
        material_count=3,
        calculation_date="2025-01-15T00:00:00+00:00",
    )


class TestSustainabilityReporter:
    """Tests for SustainabilityReporter."""

    # --- JSON Tests ---

    def test_to_json_returns_valid_json(self, reporter, summary):
        """Test that to_json returns valid JSON."""
        result = reporter.to_json(summary)

        data = json.loads(result)
        assert "total_embodied_carbon_kgco2e" in data
        assert data["total_embodied_carbon_kgco2e"] == 417350.0

    def test_to_json_includes_all_fields(self, reporter, summary):
        """Test that JSON report includes all summary fields."""
        result = reporter.to_json(summary)
        data = json.loads(result)

        assert "report_type" in data
        assert "by_material" in data
        assert "by_system" in data
        assert "by_level" in data
        assert "by_lifecycle_stage" in data
        assert "material_count" in data

    def test_to_json_writes_file(self, reporter, summary, tmp_path):
        """Test that to_json writes to file when path provided."""
        output = tmp_path / "report.json"
        result = reporter.to_json(summary, path=output)

        assert result == output
        assert output.exists()

        data = json.loads(output.read_text(encoding="utf-8"))
        assert data["total_embodied_carbon_kgco2e"] == 417350.0

    def test_to_json_creates_parent_dirs(self, reporter, summary, tmp_path):
        """Test that to_json creates parent directories."""
        output = tmp_path / "subdir" / "report.json"
        reporter.to_json(summary, path=output)

        assert output.exists()

    # --- CSV Tests ---

    def test_to_csv_returns_string(self, reporter, summary):
        """Test that to_csv returns a CSV string."""
        result = reporter.to_csv(summary)

        assert isinstance(result, str)
        assert "Material" in result
        assert "Concrete" in result
        assert "Steel" in result

    def test_to_csv_has_header(self, reporter, summary):
        """Test that CSV has proper header row."""
        result = reporter.to_csv(summary)
        lines = result.strip().split("\n")

        assert "Material" in lines[0]
        assert "Embodied Carbon" in lines[0]
        assert "Percentage" in lines[0]

    def test_to_csv_includes_total(self, reporter, summary):
        """Test that CSV includes total row."""
        result = reporter.to_csv(summary)

        assert "Total" in result
        assert "417350" in result

    def test_to_csv_writes_file(self, reporter, summary, tmp_path):
        """Test that to_csv writes to file when path provided."""
        output = tmp_path / "report.csv"
        result = reporter.to_csv(summary, path=output)

        assert result == output
        assert output.exists()

        content = output.read_text(encoding="utf-8")
        assert "Concrete" in content

    def test_to_csv_sorted_by_carbon_desc(self, reporter, summary):
        """Test that CSV materials are sorted by carbon descending."""
        result = reporter.to_csv(summary)
        lines = result.strip().split("\n")

        # Skip header, find material rows.
        material_lines = [
            l
            for l in lines[1:]
            if l
            and not l.startswith("Total")
            and not l.startswith("Calculation")
            and not l.startswith("Material Count")
        ]

        # Steel (243350) should be before Concrete (156000).
        steel_idx = next(i for i, l in enumerate(material_lines) if "Steel" in l)
        concrete_idx = next(i for i, l in enumerate(material_lines) if "Concrete" in l)
        assert steel_idx < concrete_idx

    # --- HTML Tests ---

    def test_to_html_returns_html_string(self, reporter, summary):
        """Test that to_html returns an HTML string."""
        result = reporter.to_html(summary)

        assert isinstance(result, str)
        assert "<html" in result
        assert "Sustainability" in result

    def test_to_html_includes_total(self, reporter, summary):
        """Test that HTML report includes total carbon."""
        result = reporter.to_html(summary)

        assert "417350" in result

    def test_to_html_includes_materials(self, reporter, summary):
        """Test that HTML report includes material breakdown."""
        result = reporter.to_html(summary)

        assert "Concrete" in result
        assert "Steel" in result
        assert "Timber" in result

    def test_to_html_has_table(self, reporter, summary):
        """Test that HTML report contains a table."""
        result = reporter.to_html(summary)

        assert "<table>" in result or "<table" in result
        assert "<tr>" in result
        assert "<td>" in result

    def test_to_html_writes_file(self, reporter, summary, tmp_path):
        """Test that to_html writes to file when path provided."""
        output = tmp_path / "report.html"
        result = reporter.to_html(summary, path=output)

        assert result == output
        assert output.exists()

        content = output.read_text(encoding="utf-8")
        assert "<html" in content

    # --- Generate Dispatch Tests ---

    def test_generate_json(self, reporter, summary):
        """Test generate() with JSON format."""
        result = reporter.generate(summary, format=ReportFormat.JSON)

        data = json.loads(result)
        assert "total_embodied_carbon_kgco2e" in data

    def test_generate_csv(self, reporter, summary):
        """Test generate() with CSV format."""
        result = reporter.generate(summary, format=ReportFormat.CSV)

        assert "Material" in result
        assert "Concrete" in result

    def test_generate_html(self, reporter, summary):
        """Test generate() with HTML format."""
        result = reporter.generate(summary, format=ReportFormat.HTML)

        assert "<html" in result

    def test_generate_with_output_path(self, reporter, summary, tmp_path):
        """Test generate() writes to file."""
        output = tmp_path / "report.json"
        reporter.generate(
            summary,
            format=ReportFormat.JSON,
            output_path=output,
        )

        assert output.exists()

    # --- Certification Docs Tests ---

    def test_generate_leed_docs(self, reporter, summary):
        """Test LEED certification document generation."""
        docs = reporter.generate_certification_docs(summary, CertificationSystem.LEED)

        assert docs["certification_system"] == "LEED"
        assert "credits" in docs
        assert "MRc1" in docs["credits"]
        assert "potential_points" in docs["credits"]["MRc1"]

    def test_generate_breeam_docs(self, reporter, summary):
        """Test BREEAM certification document generation."""
        docs = reporter.generate_certification_docs(summary, CertificationSystem.BREEAM)

        assert docs["certification_system"] == "BREEAM"
        assert "credits" in docs
        assert "Mat01" in docs["credits"]

    def test_generate_dgnb_docs(self, reporter, summary):
        """Test DGNB certification document generation."""
        docs = reporter.generate_certification_docs(summary, CertificationSystem.DGNB)

        assert docs["certification_system"] == "DGNB"
        assert "ENV1.1" in docs["credits"]

    def test_generate_greenstar_docs(self, reporter, summary):
        """Test Green Star certification document generation."""
        docs = reporter.generate_certification_docs(
            summary, CertificationSystem.GREENSTAR
        )

        assert docs["certification_system"] == "Green Star"
        assert "Materials" in docs["credits"]

    def test_generate_well_docs(self, reporter, summary):
        """Test WELL certification document generation."""
        docs = reporter.generate_certification_docs(summary, CertificationSystem.WELL)

        assert docs["certification_system"] == "WELL"

    def test_certification_docs_include_materials(self, reporter, summary):
        """Test that certification docs include material list."""
        docs = reporter.generate_certification_docs(summary, CertificationSystem.LEED)

        assert "by_material" in docs
        assert "Concrete" in docs["by_material"]

    def test_certification_docs_include_totals(self, reporter, summary):
        """Test that certification docs include carbon totals."""
        docs = reporter.generate_certification_docs(summary, CertificationSystem.LEED)

        assert docs["total_embodied_carbon_kgco2e"] == 417350.0
        assert docs["material_count"] == 3

    # --- Edge Cases ---

    def test_empty_summary_json(self, reporter):
        """Test JSON report with empty summary."""
        empty = BuildingCarbonSummary(
            total_embodied_carbon_kgco2e=0.0,
            material_count=0,
            calculation_date="2025-01-01",
        )
        result = reporter.to_json(empty)
        data = json.loads(result)

        assert data["total_embodied_carbon_kgco2e"] == 0.0

    def test_empty_summary_csv(self, reporter):
        """Test CSV report with empty summary."""
        empty = BuildingCarbonSummary(
            total_embodied_carbon_kgco2e=0.0,
            material_count=0,
            calculation_date="2025-01-01",
        )
        result = reporter.to_csv(empty)

        assert "Total" in result
        assert "0.00" in result
