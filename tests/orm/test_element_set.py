"""
Unit tests for ElementSet functionality.
"""

from unittest.mock import Mock

import pytest

from revitpy.orm.element_set import AsyncElementSet, ElementSet
from revitpy.orm.exceptions import QueryError


class MockElement:
    """Mock element for testing."""

    def __init__(
        self, id: int, name: str, category: str = "Wall", level: str = "Level 1"
    ):
        self.id = id
        self.name = name
        self.category = category
        self.level = level

    def __eq__(self, other):
        return isinstance(other, MockElement) and self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return (
            f"MockElement(id={self.id}, name='{self.name}', category='{self.category}')"
        )


@pytest.fixture
def sample_elements():
    """Create sample elements for testing."""
    return [
        MockElement(1, "Wall-1", "Wall", "Level 1"),
        MockElement(2, "Wall-2", "Wall", "Level 2"),
        MockElement(3, "Door-1", "Door", "Level 1"),
        MockElement(4, "Window-1", "Window", "Level 2"),
        MockElement(5, "Wall-3", "Wall", "Level 1"),
    ]


class TestElementSet:
    """Test ElementSet functionality."""

    def test_creation_with_elements(self, sample_elements):
        """Test creating ElementSet with initial elements."""
        element_set = ElementSet(sample_elements, lazy=False)

        assert len(element_set) == 5
        assert element_set.count() == 5
        assert not element_set._lazy
        assert element_set._is_materialized

    def test_creation_lazy(self):
        """Test creating lazy ElementSet."""
        element_set = ElementSet(lazy=True)

        assert element_set._lazy
        assert not element_set._is_materialized

    def test_indexing(self, sample_elements):
        """Test indexing operations."""
        element_set = ElementSet(sample_elements, lazy=False)

        # Single index
        first_element = element_set[0]
        assert first_element.id == 1

        # Slice
        subset = element_set[1:3]
        assert isinstance(subset, ElementSet)
        assert len(subset) == 2
        assert subset[0].id == 2
        assert subset[1].id == 3

    def test_iteration(self, sample_elements):
        """Test iteration over ElementSet."""
        element_set = ElementSet(sample_elements, lazy=False)

        ids = [elem.id for elem in element_set]
        assert ids == [1, 2, 3, 4, 5]

    def test_contains(self, sample_elements):
        """Test membership testing."""
        element_set = ElementSet(sample_elements, lazy=False)

        assert sample_elements[0] in element_set
        assert MockElement(99, "NotInSet") not in element_set

    def test_boolean_conversion(self, sample_elements):
        """Test boolean conversion."""
        element_set = ElementSet(sample_elements, lazy=False)
        empty_set = ElementSet([], lazy=False)

        assert bool(element_set) is True
        assert bool(empty_set) is False

    def test_repr(self, sample_elements):
        """Test string representation."""
        element_set = ElementSet(sample_elements, element_type=MockElement, lazy=False)

        repr_str = repr(element_set)
        assert "ElementSet<MockElement>[5]" in repr_str

    def test_where_filtering(self, sample_elements):
        """Test where clause filtering."""
        element_set = ElementSet(sample_elements, lazy=False)

        walls = element_set.where(lambda x: x.category == "Wall")

        assert isinstance(walls, ElementSet)
        assert walls.count() == 3
        assert all(elem.category == "Wall" for elem in walls)

    def test_select_projection(self, sample_elements):
        """Test select projection."""
        element_set = ElementSet(sample_elements, lazy=False)

        names = element_set.select(lambda x: x.name)
        name_list = names.to_list()

        assert len(name_list) == 5
        assert "Wall-1" in name_list
        assert "Door-1" in name_list

    def test_order_by(self, sample_elements):
        """Test ordering."""
        element_set = ElementSet(sample_elements, lazy=False)

        ordered = element_set.order_by(lambda x: x.name)
        names = [elem.name for elem in ordered]

        assert names == sorted(names)

    def test_order_by_descending(self, sample_elements):
        """Test descending order."""
        element_set = ElementSet(sample_elements, lazy=False)

        ordered = element_set.order_by_descending(lambda x: x.id)
        ids = [elem.id for elem in ordered]

        assert ids == [5, 4, 3, 2, 1]

    def test_skip_and_take(self, sample_elements):
        """Test skip and take operations."""
        element_set = ElementSet(sample_elements, lazy=False)

        middle = element_set.skip(1).take(3)

        assert len(middle) == 3
        assert middle[0].id == 2
        assert middle[2].id == 4

    def test_distinct(self, sample_elements):
        """Test distinct operation."""
        # Add duplicate categories
        elements_with_duplicates = sample_elements + [
            MockElement(6, "Wall-4", "Wall", "Level 2"),
            MockElement(7, "Door-2", "Door", "Level 2"),
        ]

        element_set = ElementSet(elements_with_duplicates, lazy=False)

        distinct_by_category = element_set.distinct(lambda x: x.category)
        categories = {elem.category for elem in distinct_by_category}

        assert len(categories) == len(distinct_by_category.to_list())
        assert categories == {"Wall", "Door", "Window"}

    def test_first_operations(self, sample_elements):
        """Test first, first_or_default operations."""
        element_set = ElementSet(sample_elements, lazy=False)

        # first()
        first = element_set.first()
        assert first.id == 1

        # first(predicate)
        first_door = element_set.first(lambda x: x.category == "Door")
        assert first_door.category == "Door"

        # first_or_default()
        first_default = element_set.first_or_default(
            lambda x: x.category == "NonExistent", default=None
        )
        assert first_default is None

    def test_last_operations(self, sample_elements):
        """Test last, last_or_default operations."""
        element_set = ElementSet(sample_elements, lazy=False)

        # last()
        last = element_set.last()
        assert last.id == 5

        # last(predicate)
        last_wall = element_set.last(lambda x: x.category == "Wall")
        assert last_wall.id == 5  # Wall-3 is the last wall

        # last_or_default()
        last_default = element_set.last_or_default(
            lambda x: x.category == "NonExistent", default=None
        )
        assert last_default is None

    def test_single_operations(self, sample_elements):
        """Test single, single_or_default operations."""
        element_set = ElementSet(sample_elements, lazy=False)

        # single() with unique result
        single_door = element_set.single(lambda x: x.category == "Door")
        assert single_door.category == "Door"

        # single() with multiple results should raise error
        with pytest.raises(QueryError):
            element_set.single(lambda x: x.category == "Wall")

        # single() with no results should raise error
        with pytest.raises(QueryError):
            element_set.single(lambda x: x.category == "NonExistent")

        # single_or_default()
        single_default = element_set.single_or_default(
            lambda x: x.category == "NonExistent", default=None
        )
        assert single_default is None

    def test_any_and_all(self, sample_elements):
        """Test any and all operations."""
        element_set = ElementSet(sample_elements, lazy=False)

        # any()
        assert element_set.any() is True
        assert element_set.any(lambda x: x.category == "Wall") is True
        assert element_set.any(lambda x: x.category == "NonExistent") is False

        # all()
        assert element_set.all(lambda x: x.id > 0) is True
        assert element_set.all(lambda x: x.category == "Wall") is False

    def test_count_operation(self, sample_elements):
        """Test count operation."""
        element_set = ElementSet(sample_elements, lazy=False)

        assert element_set.count() == 5
        assert element_set.count(lambda x: x.category == "Wall") == 3
        assert element_set.count(lambda x: x.category == "NonExistent") == 0

    def test_to_list(self, sample_elements):
        """Test to_list operation."""
        element_set = ElementSet(sample_elements, lazy=False)

        result_list = element_set.to_list()

        assert isinstance(result_list, list)
        assert len(result_list) == 5
        assert result_list == sample_elements

    def test_to_dict(self, sample_elements):
        """Test to_dict operation."""
        element_set = ElementSet(sample_elements, lazy=False)

        id_dict = element_set.to_dict(lambda x: x.id)

        assert isinstance(id_dict, dict)
        assert len(id_dict) == 5
        assert id_dict[1].name == "Wall-1"
        assert id_dict[3].name == "Door-1"

    def test_to_lookup(self, sample_elements):
        """Test to_lookup operation."""
        element_set = ElementSet(sample_elements, lazy=False)

        category_lookup = element_set.to_lookup(lambda x: x.category)

        assert isinstance(category_lookup, dict)
        assert len(category_lookup["Wall"]) == 3
        assert len(category_lookup["Door"]) == 1
        assert len(category_lookup["Window"]) == 1

    def test_group_by(self, sample_elements):
        """Test group_by operation."""
        element_set = ElementSet(sample_elements, lazy=False)

        groups = element_set.group_by(lambda x: x.category)

        assert isinstance(groups, dict)
        assert isinstance(groups["Wall"], ElementSet)
        assert groups["Wall"].count() == 3
        assert groups["Door"].count() == 1

    def test_aggregation_operations(self, sample_elements):
        """Test sum, average, min, max operations."""
        element_set = ElementSet(sample_elements, lazy=False)

        # sum()
        id_sum = element_set.sum(lambda x: x.id)
        assert id_sum == sum(elem.id for elem in sample_elements)

        # average()
        id_average = element_set.average(lambda x: x.id)
        assert id_average == sum(elem.id for elem in sample_elements) / len(
            sample_elements
        )

        # min() and max()
        min_elem = element_set.min(lambda x: x.id)
        max_elem = element_set.max(lambda x: x.id)
        assert min_elem.id == 1
        assert max_elem.id == 5

    def test_set_operations(self, sample_elements):
        """Test union, intersect, except operations."""
        set1 = ElementSet(sample_elements[:3], lazy=False)  # Elements 1, 2, 3
        set2 = ElementSet(sample_elements[2:], lazy=False)  # Elements 3, 4, 5

        # union()
        union_set = set1.union(set2)
        assert union_set.count() == 5  # All unique elements

        # intersect()
        intersect_set = set1.intersect(set2)
        assert intersect_set.count() == 1  # Only element 3 is common
        assert intersect_set.first().id == 3

        # except_elements()
        except_set = set1.except_elements(set2)
        assert except_set.count() == 2  # Elements 1, 2
        ids = [elem.id for elem in except_set]
        assert 1 in ids and 2 in ids

    def test_include_relationships(self, sample_elements):
        """Test include operation for relationships."""
        element_set = ElementSet(sample_elements, lazy=False)

        included = element_set.include("related_rooms")

        assert isinstance(included, ElementSet)
        assert "related_rooms" in included._relationships

    def test_batch_update(self, sample_elements):
        """Test batch update operation."""
        element_set = ElementSet(sample_elements, lazy=False)

        updates = {"level": "New Level"}
        updated_count = element_set.batch_update(updates)

        # Should update 5 properties (1 per element)
        assert updated_count == 5
        assert all(elem.level == "New Level" for elem in element_set)

    def test_for_each(self, sample_elements):
        """Test for_each operation."""
        element_set = ElementSet(sample_elements, lazy=False)

        processed_ids = []
        element_set.for_each(lambda x: processed_ids.append(x.id))

        assert processed_ids == [1, 2, 3, 4, 5]

    def test_empty_set(self):
        """Test operations on empty ElementSet."""
        empty_set = ElementSet.empty(MockElement)

        assert len(empty_set) == 0
        assert empty_set.count() == 0
        assert empty_set.any() is False
        assert empty_set.to_list() == []

        with pytest.raises(QueryError):
            empty_set.first()

        assert empty_set.first_or_default() is None

    def test_lazy_evaluation_with_query_builder(self):
        """Test lazy evaluation with QueryBuilder integration."""
        # Mock QueryBuilder that tracks execution
        mock_builder = Mock()
        mock_builder.to_list.return_value = [MockElement(1, "Test")]

        element_set = ElementSet(lazy=True, query_builder=mock_builder)

        # Operations should not execute the query yet
        filtered = element_set.where(lambda x: x.id > 0)
        assert not mock_builder.to_list.called

        # Only when materializing should the query execute
        filtered.to_list()
        assert mock_builder.where.called

    def test_chained_operations(self, sample_elements):
        """Test chaining multiple operations."""
        element_set = ElementSet(sample_elements, lazy=False)

        result = (
            element_set.where(lambda x: x.category in ["Wall", "Door"])
            .order_by(lambda x: x.name)
            .skip(1)
            .take(2)
        )

        result_list = result.to_list()
        assert len(result_list) == 2
        # Should be ordered and filtered
        names = [elem.name for elem in result_list]
        assert names == sorted(names)


class TestAsyncElementSet:
    """Test AsyncElementSet functionality."""

    def test_creation(self, sample_elements):
        """Test creating AsyncElementSet."""
        sync_set = ElementSet(sample_elements, lazy=False)
        async_set = AsyncElementSet(sync_set)

        assert async_set._element_set == sync_set

    @pytest.mark.asyncio
    async def test_async_operations(self, sample_elements):
        """Test async query operations."""
        sync_set = ElementSet(sample_elements, lazy=False)
        async_set = AsyncElementSet(sync_set)

        # first_async()
        first = await async_set.first_async()
        assert first.id == 1

        # count_async()
        count = await async_set.count_async()
        assert count == 5

        # any_async()
        has_walls = await async_set.any_async(lambda x: x.category == "Wall")
        assert has_walls is True

        # to_list_async()
        results = await async_set.to_list_async()
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_async_iteration(self, sample_elements):
        """Test async iteration."""
        sync_set = ElementSet(sample_elements, lazy=False)
        async_set = AsyncElementSet(sync_set)

        ids = []
        async for elem in async_set:
            ids.append(elem.id)

        assert ids == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_for_each_async(self, sample_elements):
        """Test async for_each operation."""
        sync_set = ElementSet(sample_elements, lazy=False)
        async_set = AsyncElementSet(sync_set)

        processed_ids = []

        async def process_element(elem):
            processed_ids.append(elem.id)

        await async_set.for_each_async(process_element)

        assert processed_ids == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_batch_update_async(self, sample_elements):
        """Test async batch update."""
        sync_set = ElementSet(sample_elements, lazy=False)
        async_set = AsyncElementSet(sync_set)

        updates = {"level": "Async Level"}
        updated_count = await async_set.batch_update_async(updates)

        assert updated_count == 5

    def test_sync_bridge(self, sample_elements):
        """Test conversion between sync and async sets."""
        sync_set = ElementSet(sample_elements, lazy=False)

        # to async
        async_set = AsyncElementSet.from_sync(sync_set)
        assert async_set._element_set == sync_set

        # back to sync
        sync_again = async_set.to_sync()
        assert sync_again == sync_set


if __name__ == "__main__":
    pytest.main([__file__])
