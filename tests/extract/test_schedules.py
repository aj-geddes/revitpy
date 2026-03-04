"""
Unit tests for ScheduleBuilder functionality.
"""

import pytest

from revitpy.extract.exceptions import ScheduleError
from revitpy.extract.schedules import ScheduleBuilder
from revitpy.extract.types import ScheduleConfig


@pytest.fixture
def sample_schedule_data():
    """Provide sample tabular data for schedule tests."""
    return [
        {
            "name": "Wall-001",
            "category": "Walls",
            "level": "Level 1",
            "area": 25.0,
            "cost": 3750.0,
        },
        {
            "name": "Wall-002",
            "category": "Walls",
            "level": "Level 2",
            "area": 30.0,
            "cost": 4500.0,
        },
        {
            "name": "Floor-001",
            "category": "Floors",
            "level": "Level 1",
            "area": 100.0,
            "cost": 20000.0,
        },
        {
            "name": "Door-001",
            "category": "Doors",
            "level": "Level 1",
            "area": 2.0,
            "cost": 700.0,
        },
        {
            "name": "Window-001",
            "category": "Windows",
            "level": "Level 2",
            "area": 2.5,
            "cost": 1250.0,
        },
    ]


class TestScheduleBuilder:
    """Test ScheduleBuilder functionality."""

    def test_build_with_no_config(self, sample_schedule_data):
        """Test building with default (empty) config returns data as-is."""
        builder = ScheduleBuilder()
        result = builder.build(sample_schedule_data)

        assert len(result) == len(sample_schedule_data)

    def test_column_projection(self, sample_schedule_data):
        """Test that column config limits output columns."""
        config = ScheduleConfig(columns=["name", "area"])
        builder = ScheduleBuilder(config=config)
        result = builder.build(sample_schedule_data)

        for row in result:
            assert set(row.keys()) == {"name", "area"}

    def test_filter_by_category(self, sample_schedule_data):
        """Test filtering rows by category."""
        config = ScheduleConfig(filters={"category": "Walls"})
        builder = ScheduleBuilder(config=config)
        result = builder.build(sample_schedule_data)

        assert len(result) == 2
        assert all(row["category"] == "Walls" for row in result)

    def test_filter_by_list_values(self, sample_schedule_data):
        """Test filtering rows with a list of acceptable values."""
        config = ScheduleConfig(filters={"category": ["Walls", "Doors"]})
        builder = ScheduleBuilder(config=config)
        result = builder.build(sample_schedule_data)

        assert len(result) == 3
        assert all(row["category"] in ("Walls", "Doors") for row in result)

    def test_filter_no_match(self, sample_schedule_data):
        """Test filtering with no matching rows."""
        config = ScheduleConfig(filters={"category": "Roofs"})
        builder = ScheduleBuilder(config=config)
        result = builder.build(sample_schedule_data)

        assert len(result) == 0

    def test_sort_ascending(self, sample_schedule_data):
        """Test sorting by column ascending."""
        config = ScheduleConfig(sort_by=["area"])
        builder = ScheduleBuilder(config=config)
        result = builder.build(sample_schedule_data)

        areas = [row["area"] for row in result]
        assert areas == sorted(areas)

    def test_sort_descending(self, sample_schedule_data):
        """Test sorting by column descending."""
        config = ScheduleConfig(sort_by=["-area"])
        builder = ScheduleBuilder(config=config)
        result = builder.build(sample_schedule_data)

        areas = [row["area"] for row in result]
        assert areas == sorted(areas, reverse=True)

    def test_sort_multi_column(self, sample_schedule_data):
        """Test sorting by multiple columns."""
        config = ScheduleConfig(sort_by=["category", "name"])
        builder = ScheduleBuilder(config=config)
        result = builder.build(sample_schedule_data)

        categories = [row["category"] for row in result]
        assert categories == sorted(categories)

    def test_add_totals(self, sample_schedule_data):
        """Test adding a totals row."""
        config = ScheduleConfig(
            columns=["name", "area", "cost"],
            include_totals=True,
        )
        builder = ScheduleBuilder(config=config)
        result = builder.build(sample_schedule_data)

        # Should have original rows + 1 total row
        assert len(result) == len(sample_schedule_data) + 1

        totals_row = result[-1]
        assert totals_row["name"] == "TOTAL"
        assert totals_row["area"] == 159.5
        assert totals_row["cost"] == 30200.0

    def test_add_totals_empty_data(self):
        """Test adding totals to empty data."""
        builder = ScheduleBuilder()
        result = builder.add_totals([], ["area"])
        assert result == []

    def test_group_data(self, sample_schedule_data):
        """Test grouping data by column."""
        builder = ScheduleBuilder()
        grouped = builder.group_data(sample_schedule_data, "category")

        assert "Walls" in grouped
        assert "Floors" in grouped
        assert len(grouped["Walls"]) == 2
        assert len(grouped["Floors"]) == 1

    def test_group_data_missing_key(self, sample_schedule_data):
        """Test grouping by non-existent column."""
        builder = ScheduleBuilder()
        grouped = builder.group_data(sample_schedule_data, "nonexistent")

        # All rows should fall into the "Ungrouped" bucket
        assert "Ungrouped" in grouped
        assert len(grouped["Ungrouped"]) == len(sample_schedule_data)

    def test_filter_data_standalone(self, sample_schedule_data):
        """Test filter_data method independently."""
        builder = ScheduleBuilder()
        filtered = builder.filter_data(sample_schedule_data, {"level": "Level 1"})

        assert len(filtered) == 3
        assert all(row["level"] == "Level 1" for row in filtered)

    def test_sort_data_standalone(self, sample_schedule_data):
        """Test sort_data method independently."""
        builder = ScheduleBuilder()
        sorted_data = builder.sort_data(sample_schedule_data, ["name"])

        names = [row["name"] for row in sorted_data]
        assert names == sorted(names)

    def test_build_full_pipeline(self, sample_schedule_data):
        """Test the full build pipeline: filter + sort + project + totals."""
        config = ScheduleConfig(
            columns=["name", "area", "cost"],
            filters={"category": "Walls"},
            sort_by=["-area"],
            include_totals=True,
        )
        builder = ScheduleBuilder(config=config)
        result = builder.build(sample_schedule_data)

        # 2 wall rows + 1 total row
        assert len(result) == 3
        assert result[0]["area"] == 30.0  # Descending
        assert result[1]["area"] == 25.0
        assert result[2]["name"] == "TOTAL"
        assert result[2]["area"] == 55.0

    def test_config_property(self):
        """Test config property access."""
        config = ScheduleConfig(title="My Schedule")
        builder = ScheduleBuilder(config=config)
        assert builder.config.title == "My Schedule"

    def test_build_does_not_mutate_input(self, sample_schedule_data):
        """Test that build does not mutate the input data."""
        original_len = len(sample_schedule_data)
        original_first = dict(sample_schedule_data[0])

        config = ScheduleConfig(
            columns=["name"],
            filters={"category": "Walls"},
        )
        builder = ScheduleBuilder(config=config)
        builder.build(sample_schedule_data)

        assert len(sample_schedule_data) == original_len
        assert sample_schedule_data[0] == original_first
