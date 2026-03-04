"""
Unit tests for QuantityExtractor functionality.
"""

import asyncio

import pytest

from revitpy.extract.exceptions import QuantityError
from revitpy.extract.quantities import QuantityExtractor
from revitpy.extract.types import AggregationLevel, QuantityItem, QuantityType


class TestQuantityExtractor:
    """Test QuantityExtractor functionality."""

    def test_extract_all_types_from_wall(self, sample_elements):
        """Test extracting all quantity types from a wall element."""
        extractor = QuantityExtractor()
        wall = sample_elements[0]  # Wall-001: area=25, volume=5, length=10

        items = extractor.extract([wall])

        # Should find area, volume, length, and count
        types_found = {item.quantity_type for item in items}
        assert QuantityType.AREA in types_found
        assert QuantityType.VOLUME in types_found
        assert QuantityType.LENGTH in types_found
        assert QuantityType.COUNT in types_found

    def test_extract_specific_types(self, sample_elements):
        """Test extracting only specific quantity types."""
        extractor = QuantityExtractor()
        items = extractor.extract(sample_elements, quantity_types=[QuantityType.AREA])

        # Every item should be AREA type (or COUNT implicit)
        for item in items:
            assert item.quantity_type == QuantityType.AREA

    def test_extract_area_values(self, sample_elements):
        """Test that extracted area values match element attributes."""
        extractor = QuantityExtractor()
        items = extractor.extract(sample_elements, quantity_types=[QuantityType.AREA])

        area_values = {item.element_name: item.value for item in items}
        assert area_values["Wall-001"] == 25.0
        assert area_values["Wall-002"] == 30.0
        assert area_values["Floor-001"] == 100.0

    def test_extract_volume_values(self, sample_elements):
        """Test that extracted volume values match element attributes."""
        extractor = QuantityExtractor()
        items = extractor.extract(sample_elements, quantity_types=[QuantityType.VOLUME])

        volume_values = {item.element_name: item.value for item in items}
        assert volume_values["Wall-001"] == 5.0
        assert volume_values["Room-101"] == 150.0

    def test_extract_count_implicit(self, sample_elements):
        """Test that COUNT=1 is assigned when element has no count attr."""
        extractor = QuantityExtractor()
        items = extractor.extract(sample_elements, quantity_types=[QuantityType.COUNT])

        # All elements should have count=1
        for item in items:
            assert item.quantity_type == QuantityType.COUNT
            assert item.value == 1.0

        assert len(items) == len(sample_elements)

    def test_extract_populates_metadata(self, sample_elements):
        """Test that element metadata is correctly propagated."""
        extractor = QuantityExtractor()
        items = extractor.extract(
            [sample_elements[0]], quantity_types=[QuantityType.AREA]
        )

        item = items[0]
        assert item.element_id == 1
        assert item.element_name == "Wall-001"
        assert item.category == "Walls"
        assert item.level == "Level 1"
        assert item.system == "Structure"
        assert item.unit == "m2"

    def test_extract_empty_list(self):
        """Test extracting from an empty element list."""
        extractor = QuantityExtractor()
        items = extractor.extract([])
        assert items == []

    def test_extract_element_without_quantities(self):
        """Test extracting from element with no quantity attributes."""
        from tests.extract.conftest import MockElement

        bare_element = MockElement(id=99, name="Bare", category="Other")
        extractor = QuantityExtractor()
        items = extractor.extract([bare_element], quantity_types=[QuantityType.AREA])

        # No area found, so no items returned
        assert len(items) == 0

    def test_extract_grouped_by_category(self, sample_elements):
        """Test grouping extracted items by category."""
        extractor = QuantityExtractor()
        grouped = extractor.extract_grouped(
            sample_elements,
            group_by=AggregationLevel.CATEGORY,
            quantity_types=[QuantityType.AREA],
        )

        assert "Walls" in grouped
        assert "Floors" in grouped
        assert "Rooms" in grouped

        wall_items = grouped["Walls"]
        assert len(wall_items) == 2  # Wall-001 and Wall-002

    def test_extract_grouped_by_level(self, sample_elements):
        """Test grouping extracted items by level."""
        extractor = QuantityExtractor()
        grouped = extractor.extract_grouped(
            sample_elements,
            group_by=AggregationLevel.LEVEL,
            quantity_types=[QuantityType.AREA],
        )

        assert "Level 1" in grouped
        assert "Level 2" in grouped

    def test_extract_grouped_by_system(self, sample_elements):
        """Test grouping extracted items by system."""
        extractor = QuantityExtractor()
        grouped = extractor.extract_grouped(
            sample_elements,
            group_by=AggregationLevel.SYSTEM,
            quantity_types=[QuantityType.AREA],
        )

        assert "Structure" in grouped

    def test_summarize(self, sample_quantities):
        """Test summarizing quantities by type."""
        extractor = QuantityExtractor()
        summary = extractor.summarize(sample_quantities)

        assert summary["area"] == 155.0  # 25 + 30 + 100
        assert summary["volume"] == 155.0  # 5 + 150

    def test_summarize_empty(self):
        """Test summarizing empty list."""
        extractor = QuantityExtractor()
        summary = extractor.summarize([])
        assert summary == {}

    @pytest.mark.asyncio
    async def test_extract_async(self, sample_elements):
        """Test async extraction returns same results as sync."""
        extractor = QuantityExtractor()

        sync_items = extractor.extract(
            sample_elements, quantity_types=[QuantityType.AREA]
        )
        async_items = await extractor.extract_async(
            sample_elements, quantity_types=[QuantityType.AREA]
        )

        assert len(async_items) == len(sync_items)
        for s, a in zip(sync_items, async_items, strict=True):
            assert s.element_id == a.element_id
            assert s.value == a.value

    @pytest.mark.asyncio
    async def test_extract_async_with_progress(self, sample_elements):
        """Test async extraction with progress reporting."""
        extractor = QuantityExtractor()
        progress_calls = []

        def on_progress(current, total):
            progress_calls.append((current, total))

        await extractor.extract_async(
            sample_elements,
            quantity_types=[QuantityType.AREA],
            progress=on_progress,
        )

        assert len(progress_calls) == len(sample_elements)
        # Last call should report all elements processed
        assert progress_calls[-1] == (
            len(sample_elements),
            len(sample_elements),
        )

    def test_extract_with_context(self):
        """Test that context is stored but extraction works without it."""
        ctx = object()
        extractor = QuantityExtractor(context=ctx)
        assert extractor._context is ctx

    def test_quantity_item_dataclass(self):
        """Test QuantityItem dataclass construction."""
        item = QuantityItem(
            element_id=1,
            element_name="Test",
            category="Cat",
            quantity_type=QuantityType.AREA,
            value=10.0,
            unit="m2",
        )
        assert item.element_id == 1
        assert item.value == 10.0
        assert item.level == ""
        assert item.system == ""
