"""
Unit tests for CostEstimator functionality.
"""

import csv
import json
from pathlib import Path

import pytest

from revitpy.extract.costs import CostEstimator
from revitpy.extract.exceptions import CostEstimationError
from revitpy.extract.types import (
    AggregationLevel,
    CostSource,
    CostSummary,
    QuantityItem,
    QuantityType,
)


class TestCostEstimator:
    """Test CostEstimator functionality."""

    def test_init_with_dict(self, mock_cost_database):
        """Test initialization with a dict cost database."""
        estimator = CostEstimator(cost_database=mock_cost_database)
        assert estimator.database == mock_cost_database

    def test_init_empty(self):
        """Test initialization without a database."""
        estimator = CostEstimator()
        assert estimator.database == {}

    def test_estimate_basic(self, sample_quantities, mock_cost_database):
        """Test basic cost estimation with known quantities."""
        estimator = CostEstimator(cost_database=mock_cost_database)
        summary = estimator.estimate(sample_quantities)

        assert isinstance(summary, CostSummary)
        assert summary.total_cost > 0
        assert len(summary.items) > 0

    def test_estimate_wall_costs(self, mock_cost_database):
        """Test that wall costs are calculated correctly."""
        quantities = [
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
        ]
        estimator = CostEstimator(cost_database=mock_cost_database)
        summary = estimator.estimate(quantities)

        # 25.0 * 150.0 = 3750.0
        assert summary.total_cost == 3750.0
        assert len(summary.items) == 1
        assert summary.items[0].unit_cost == 150.0
        assert summary.items[0].total_cost == 3750.0

    def test_estimate_by_category(self, sample_quantities, mock_cost_database):
        """Test that costs are aggregated by category."""
        estimator = CostEstimator(cost_database=mock_cost_database)
        summary = estimator.estimate(
            sample_quantities, aggregation=AggregationLevel.CATEGORY
        )

        assert "Walls" in summary.by_category
        assert "Floors" in summary.by_category
        # Walls: (25*150) + (30*150) + (5*150) = 9000
        assert summary.by_category["Walls"] == 9000.0

    def test_estimate_by_system(self, sample_quantities, mock_cost_database):
        """Test that costs are aggregated by system."""
        estimator = CostEstimator(cost_database=mock_cost_database)
        summary = estimator.estimate(sample_quantities)

        assert "Structure" in summary.by_system

    def test_estimate_by_level(self, sample_quantities, mock_cost_database):
        """Test that costs are aggregated by level."""
        estimator = CostEstimator(cost_database=mock_cost_database)
        summary = estimator.estimate(sample_quantities)

        assert "Level 1" in summary.by_level

    def test_estimate_missing_category_skipped(self):
        """Test that quantities with no matching cost entry are skipped."""
        quantities = [
            QuantityItem(
                element_id=1,
                element_name="Unknown",
                category="NonExistentCategory",
                quantity_type=QuantityType.AREA,
                value=10.0,
                unit="m2",
            ),
        ]
        estimator = CostEstimator(cost_database={"Walls": 100.0})
        summary = estimator.estimate(quantities)

        assert summary.total_cost == 0.0
        assert len(summary.items) == 0

    def test_estimate_case_insensitive_match(self):
        """Test that cost lookup is case-insensitive."""
        quantities = [
            QuantityItem(
                element_id=1,
                element_name="Wall",
                category="walls",
                quantity_type=QuantityType.AREA,
                value=10.0,
                unit="m2",
            ),
        ]
        estimator = CostEstimator(cost_database={"Walls": 100.0})
        summary = estimator.estimate(quantities)

        assert summary.total_cost == 1000.0

    def test_estimate_empty_quantities(self, mock_cost_database):
        """Test estimating with empty quantity list."""
        estimator = CostEstimator(cost_database=mock_cost_database)
        summary = estimator.estimate([])

        assert summary.total_cost == 0.0
        assert summary.items == []

    def test_cost_item_source(self, mock_cost_database):
        """Test that cost items have correct source."""
        quantities = [
            QuantityItem(
                element_id=1,
                element_name="Wall",
                category="Walls",
                quantity_type=QuantityType.AREA,
                value=10.0,
                unit="m2",
            ),
        ]
        estimator = CostEstimator(cost_database=mock_cost_database)
        summary = estimator.estimate(quantities)

        assert summary.items[0].source == CostSource.MANUAL

    def test_load_csv_database(self, tmp_export_dir):
        """Test loading cost data from CSV file."""
        csv_path = tmp_export_dir / "costs.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["name", "unit_cost"])
            writer.writeheader()
            writer.writerow({"name": "Walls", "unit_cost": "150.0"})
            writer.writerow({"name": "Floors", "unit_cost": "200.0"})

        estimator = CostEstimator()
        estimator.load_database(csv_path)

        assert estimator.database["Walls"] == 150.0
        assert estimator.database["Floors"] == 200.0

    def test_load_json_database(self, tmp_export_dir):
        """Test loading cost data from JSON file."""
        json_path = tmp_export_dir / "costs.json"
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump({"Walls": 150.0, "Floors": 200.0}, fh)

        estimator = CostEstimator()
        estimator.load_database(json_path)

        assert estimator.database["Walls"] == 150.0
        assert estimator.database["Floors"] == 200.0

    def test_load_json_list_format(self, tmp_export_dir):
        """Test loading cost data from JSON list format."""
        json_path = tmp_export_dir / "costs_list.json"
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(
                [
                    {"name": "Walls", "unit_cost": 150.0},
                    {"name": "Floors", "unit_cost": 200.0},
                ],
                fh,
            )

        estimator = CostEstimator()
        estimator.load_database(json_path)

        assert estimator.database["Walls"] == 150.0

    def test_load_unsupported_format(self, tmp_export_dir):
        """Test that unsupported format raises error."""
        bad_path = tmp_export_dir / "costs.xml"
        bad_path.write_text("<costs/>", encoding="utf-8")

        estimator = CostEstimator()
        with pytest.raises(CostEstimationError):
            estimator.load_database(bad_path)

    def test_load_missing_file(self, tmp_export_dir):
        """Test that missing file raises error."""
        estimator = CostEstimator()
        with pytest.raises(CostEstimationError):
            estimator.load_database(tmp_export_dir / "nonexistent.csv")

    def test_init_with_path(self, tmp_export_dir):
        """Test initialization with a file path."""
        json_path = tmp_export_dir / "costs.json"
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump({"Walls": 100.0}, fh)

        estimator = CostEstimator(cost_database=json_path)
        assert estimator.database["Walls"] == 100.0

    def test_cost_summary_currency(self, mock_cost_database):
        """Test that cost summary has default currency."""
        estimator = CostEstimator(cost_database=mock_cost_database)
        summary = estimator.estimate([])
        assert summary.currency == "USD"
