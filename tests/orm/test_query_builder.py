"""
Unit tests for QueryBuilder functionality.
"""

from typing import Any
from unittest.mock import Mock

import pytest

from revitpy.orm.cache import CacheManager
from revitpy.orm.exceptions import QueryError
from revitpy.orm.query_builder import LazyQueryExecutor, QueryBuilder, QueryPlan


class MockElement:
    """Mock element for testing."""

    def __init__(
        self, id: int, name: str, category: str = "Wall", level: str = "Level 1"
    ):
        self.id = id
        self.name = name
        self.category = category
        self.level = level


class MockProvider:
    """Mock element provider for testing."""

    def __init__(self, elements: list[MockElement]):
        self.elements = elements

    def get_all_elements(self) -> list[MockElement]:
        return self.elements.copy()

    def get_elements_of_type(self, element_type) -> list[MockElement]:
        return self.elements.copy()

    def get_element_by_id(self, element_id: Any) -> MockElement:
        for element in self.elements:
            if element.id == element_id:
                return element
        return None

    async def get_all_elements_async(self) -> list[MockElement]:
        return self.elements.copy()

    async def get_elements_of_type_async(self, element_type) -> list[MockElement]:
        return self.elements.copy()


@pytest.fixture
def mock_elements():
    """Create mock elements for testing."""
    return [
        MockElement(1, "Wall-1", "Wall", "Level 1"),
        MockElement(2, "Wall-2", "Wall", "Level 2"),
        MockElement(3, "Door-1", "Door", "Level 1"),
        MockElement(4, "Window-1", "Window", "Level 2"),
        MockElement(5, "Wall-3", "Wall", "Level 1"),
    ]


@pytest.fixture
def mock_provider(mock_elements):
    """Create mock provider with test elements."""
    return MockProvider(mock_elements)


@pytest.fixture
def cache_manager():
    """Create cache manager for testing."""
    return CacheManager()


class TestQueryPlan:
    """Test QueryPlan functionality."""

    def test_query_plan_creation(self):
        """Test creating a query plan."""
        plan = QueryPlan()
        assert plan.operations == []
        assert plan.estimated_cost == 0.0
        assert plan.use_index is False
        assert plan.parallel_execution is False

    def test_add_operation(self):
        """Test adding operations to query plan."""
        plan = QueryPlan()
        plan.add_operation("filter", lambda x: x.category == "Wall", 2.0)

        assert len(plan.operations) == 1
        assert plan.operations[0][0] == "filter"
        assert plan.estimated_cost == 2.0

    def test_optimize_query_plan(self):
        """Test query plan optimization."""
        plan = QueryPlan()
        plan.add_operation("select", lambda x: x.name, 1.0)
        plan.add_operation("filter", lambda x: x.category == "Wall", 2.0)

        optimized = plan.optimize()

        # Filters should come before projections
        assert optimized.operations[0][0] == "filter"
        assert optimized.operations[1][0] == "select"
        assert optimized.estimated_cost < plan.estimated_cost


class TestLazyQueryExecutor:
    """Test LazyQueryExecutor functionality."""

    def test_executor_creation(self, mock_provider, cache_manager):
        """Test creating a lazy query executor."""
        executor = LazyQueryExecutor(mock_provider, MockElement, cache_manager)

        assert executor._provider == mock_provider
        assert executor._element_type == MockElement
        assert executor._cache_manager == cache_manager
        assert executor._is_executed is False

    def test_query_hash_generation(self, mock_provider, cache_manager):
        """Test query hash generation."""
        executor = LazyQueryExecutor(mock_provider, MockElement, cache_manager)

        plan = QueryPlan()
        plan.add_operation("filter", lambda x: x.category == "Wall")
        executor.set_query_plan(plan)

        hash1 = executor.query_hash
        hash2 = executor.query_hash

        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hash length

    def test_execute_query(self, mock_provider, mock_elements, cache_manager):
        """Test query execution."""
        executor = LazyQueryExecutor(mock_provider, MockElement, cache_manager)

        plan = QueryPlan()
        plan.add_operation("filter", lambda x: x.category == "Wall")
        executor.set_query_plan(plan)

        results = executor.execute()

        assert len(results) == 3  # 3 walls in mock data
        assert all(elem.category == "Wall" for elem in results)
        assert executor._is_executed is True

    @pytest.mark.asyncio
    async def test_execute_query_async(self, mock_provider, cache_manager):
        """Test async query execution."""
        executor = LazyQueryExecutor(mock_provider, MockElement, cache_manager)

        plan = QueryPlan()
        plan.add_operation("filter", lambda x: x.category == "Wall")
        executor.set_query_plan(plan)

        results = await executor.execute_async()

        assert len(results) == 3
        assert all(elem.category == "Wall" for elem in results)

    @pytest.mark.asyncio
    async def test_execute_streaming(self, mock_provider, cache_manager):
        """Test streaming query execution."""
        executor = LazyQueryExecutor(mock_provider, MockElement, cache_manager)

        plan = QueryPlan()
        executor.set_query_plan(plan)

        batches = []
        async for batch in executor.execute_streaming(batch_size=2):
            batches.append(batch)

        assert len(batches) >= 1
        total_elements = sum(len(batch) for batch in batches)
        assert total_elements == 5  # Total mock elements


class TestQueryBuilder:
    """Test QueryBuilder functionality."""

    def test_query_builder_creation(self, mock_provider, cache_manager):
        """Test creating a query builder."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        assert builder._provider == mock_provider
        assert builder._element_type == MockElement
        assert builder._cache_manager == cache_manager

    def test_where_clause(self, mock_provider, cache_manager):
        """Test where clause functionality."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        filtered = builder.where(lambda x: x.category == "Wall")

        assert isinstance(filtered, QueryBuilder)
        assert filtered is not builder  # Should return new instance

    def test_select_projection(self, mock_provider, cache_manager):
        """Test select projection."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        projected = builder.select(lambda x: x.name)

        assert isinstance(projected, QueryBuilder)
        assert projected._element_type != MockElement  # Type should change

    def test_order_by(self, mock_provider, cache_manager):
        """Test ordering functionality."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        ordered = builder.order_by(lambda x: x.name)

        assert isinstance(ordered, QueryBuilder)
        assert ordered is not builder

    def test_skip_and_take(self, mock_provider, cache_manager):
        """Test skip and take functionality."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        paged = builder.skip(1).take(2)
        results = paged.to_list()

        assert len(results) == 2

    def test_distinct(self, mock_provider, cache_manager):
        """Test distinct functionality."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        distinct = builder.distinct(lambda x: x.category)
        results = distinct.to_list()

        categories = set(elem.category for elem in results)
        assert len(categories) == len(results)  # All should be unique by category

    def test_first(self, mock_provider, cache_manager):
        """Test first operation."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        first = builder.first()

        assert first is not None
        assert hasattr(first, "id")

    def test_first_with_predicate(self, mock_provider, cache_manager):
        """Test first with predicate."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        first_wall = builder.first(lambda x: x.category == "Wall")

        assert first_wall is not None
        assert first_wall.category == "Wall"

    def test_first_or_default(self, mock_provider, cache_manager):
        """Test first_or_default operation."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        # Should find something
        result = builder.first_or_default(lambda x: x.category == "Wall")
        assert result is not None

        # Should return default
        result = builder.first_or_default(
            lambda x: x.category == "NonExistent", "default"
        )
        assert result == "default"

    def test_single(self, mock_provider, cache_manager):
        """Test single operation."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        # Should work for unique elements
        single_door = builder.single(lambda x: x.category == "Door")
        assert single_door.category == "Door"

        # Should fail for multiple elements
        with pytest.raises(QueryError):
            builder.single(lambda x: x.category == "Wall")

    def test_any(self, mock_provider, cache_manager):
        """Test any operation."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        assert builder.any(lambda x: x.category == "Wall") is True
        assert builder.any(lambda x: x.category == "NonExistent") is False
        assert builder.any() is True  # Should have elements

    def test_all(self, mock_provider, cache_manager):
        """Test all operation."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        assert builder.all(lambda x: x.id > 0) is True
        assert builder.all(lambda x: x.category == "Wall") is False

    def test_count(self, mock_provider, cache_manager):
        """Test count operation."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        total_count = builder.count()
        assert total_count == 5

        wall_count = builder.count(lambda x: x.category == "Wall")
        assert wall_count == 3

    def test_to_list(self, mock_provider, cache_manager):
        """Test to_list operation."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        results = builder.to_list()

        assert isinstance(results, list)
        assert len(results) == 5

    def test_to_dict(self, mock_provider, cache_manager):
        """Test to_dict operation."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        result_dict = builder.to_dict(lambda x: x.id)

        assert isinstance(result_dict, dict)
        assert len(result_dict) == 5
        assert all(isinstance(k, int) for k in result_dict.keys())

    def test_group_by(self, mock_provider, cache_manager):
        """Test group_by operation."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        groups = builder.group_by(lambda x: x.category)

        assert isinstance(groups, dict)
        assert "Wall" in groups
        assert "Door" in groups
        assert len(groups["Wall"]) == 3
        assert len(groups["Door"]) == 1

    @pytest.mark.asyncio
    async def test_async_operations(self, mock_provider, cache_manager):
        """Test async query operations."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        # Test async first
        first = await builder.first_async()
        assert first is not None

        # Test async count
        count = await builder.count_async()
        assert count == 5

        # Test async any
        has_walls = await builder.any_async(lambda x: x.category == "Wall")
        assert has_walls is True

        # Test async to_list
        results = await builder.to_list_async()
        assert len(results) == 5

    def test_chained_operations(self, mock_provider, cache_manager):
        """Test chaining multiple query operations."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        results = (
            builder.where(lambda x: x.category == "Wall")
            .order_by(lambda x: x.name)
            .skip(1)
            .take(2)
            .to_list()
        )

        assert len(results) == 2
        assert all(elem.category == "Wall" for elem in results)

    def test_lazy_evaluation(self, mock_provider, cache_manager):
        """Test that queries are evaluated lazily."""
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        # These operations should not execute immediately
        filtered = builder.where(lambda x: x.category == "Wall")
        ordered = filtered.order_by(lambda x: x.name)

        # Only when we call a terminal operation should it execute
        results = ordered.to_list()
        assert len(results) == 3

    def test_caching_integration(self, mock_provider):
        """Test integration with caching system."""
        cache_manager = CacheManager()
        builder = QueryBuilder(mock_provider, MockElement, cache_manager)

        # First execution should populate cache
        results1 = builder.to_list()

        # Second execution should use cache
        results2 = builder.to_list()

        assert results1 == results2
        assert len(results1) == 5

    def test_error_handling(self, cache_manager):
        """Test error handling in query execution."""
        # Provider that raises an exception
        failing_provider = Mock()
        failing_provider.get_all_elements.side_effect = Exception("Provider error")
        failing_provider.get_elements_of_type.side_effect = Exception("Provider error")

        builder = QueryBuilder(failing_provider, MockElement, cache_manager)

        with pytest.raises(QueryError):
            builder.to_list()

    def test_empty_results(self, cache_manager):
        """Test handling of empty result sets."""
        empty_provider = MockProvider([])
        builder = QueryBuilder(empty_provider, MockElement, cache_manager)

        assert builder.count() == 0
        assert builder.any() is False
        assert builder.to_list() == []

        with pytest.raises(QueryError):
            builder.first()

        assert builder.first_or_default() is None


class TestQueryBuilderFactory:
    """Test query builder factory functions."""

    def test_query_factory(self, mock_provider):
        """Test query factory function."""
        from revitpy.orm.query_builder import query

        builder = query(mock_provider)

        assert isinstance(builder, QueryBuilder)
        assert builder._provider == mock_provider

    def test_typed_query_factory(self, mock_provider):
        """Test typed query factory function."""
        from revitpy.orm.query_builder import query_of_type

        builder = query_of_type(mock_provider, MockElement)

        assert isinstance(builder, QueryBuilder)
        assert builder._element_type == MockElement

    @pytest.mark.asyncio
    async def test_async_query_factory(self, mock_provider):
        """Test async query factory function."""
        from revitpy.orm.query_builder import async_query

        builder = await async_query(mock_provider)

        assert isinstance(builder, QueryBuilder)
        assert builder._provider == mock_provider


if __name__ == "__main__":
    pytest.main([__file__])
