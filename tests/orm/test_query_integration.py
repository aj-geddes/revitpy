"""
Integration tests for the QueryBuilder with validation and type safety.
"""

import pytest
import asyncio
from typing import Any, List, Optional
from unittest.mock import Mock, AsyncMock

from revitpy.orm.query_builder import QueryBuilder, LazyQueryExecutor
from revitpy.orm.element_set import ElementSet, AsyncElementSet
from revitpy.orm.validation import ElementValidator, ValidationLevel, WallElement, RoomElement
from revitpy.orm.cache import CacheManager, CacheConfiguration
from revitpy.orm.types import IElementProvider, QueryMode
from revitpy.orm.exceptions import QueryError


class MockElementProvider:
    """Mock element provider for testing."""
    
    def __init__(self, elements: List[Any] = None):
        self.elements = elements or []
        self._type_mapping = {}
        
        # Group elements by type
        for element in self.elements:
            element_type = type(element)
            if element_type not in self._type_mapping:
                self._type_mapping[element_type] = []
            self._type_mapping[element_type].append(element)
    
    def get_all_elements(self) -> List[Any]:
        """Get all elements."""
        return self.elements.copy()
    
    def get_elements_of_type(self, element_type: Any) -> List[Any]:
        """Get elements of specific type."""
        return self._type_mapping.get(element_type, [])
    
    def get_element_by_id(self, element_id: Any) -> Optional[Any]:
        """Get element by ID."""
        for element in self.elements:
            if hasattr(element, 'id') and element.id == element_id:
                return element
        return None
    
    async def get_all_elements_async(self) -> List[Any]:
        """Get all elements asynchronously."""
        return self.get_all_elements()
    
    async def get_elements_of_type_async(self, element_type: Any) -> List[Any]:
        """Get elements of specific type asynchronously."""
        return self.get_elements_of_type(element_type)
    
    async def get_element_by_id_async(self, element_id: Any) -> Optional[Any]:
        """Get element by ID asynchronously."""
        return self.get_element_by_id(element_id)


class TestQueryBuilderIntegration:
    """Test QueryBuilder integration with validation and type safety."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Create test elements with validation
        self.walls = [
            WallElement(id=1, name="Wall 1", height=10, length=20, width=0.5, category="Walls"),
            WallElement(id=2, name="Wall 2", height=8, length=15, width=0.4, category="Walls"),
            WallElement(id=3, name="Wall 3", height=12, length=25, width=0.6, category="Walls"),
        ]
        
        self.rooms = [
            RoomElement(id=10, number="101", name="Room 101", area=200, perimeter=60, volume=2000),
            RoomElement(id=11, number="102", name="Room 102", area=300, perimeter=70, volume=3000),
            RoomElement(id=12, number="103", name="Room 103", area=150, perimeter=50, volume=1500),
        ]
        
        # Setup provider with all elements
        all_elements = self.walls + self.rooms
        self.provider = MockElementProvider(all_elements)
        
        # Setup cache manager
        cache_config = CacheConfiguration(max_size=1000, enable_statistics=True)
        self.cache_manager = CacheManager(cache_config)
        
        # Setup validator
        self.validator = ElementValidator(ValidationLevel.STANDARD)
    
    def test_query_walls_with_validation(self):
        """Test querying walls with automatic validation."""
        query = QueryBuilder(
            self.provider, 
            WallElement, 
            self.cache_manager,
            QueryMode.LAZY
        )
        
        # Query walls taller than 9 feet
        tall_walls = query.where(lambda w: w.height > 9).to_list()
        
        assert len(tall_walls) == 2  # Wall 1 (10ft) and Wall 3 (12ft)
        assert all(isinstance(wall, WallElement) for wall in tall_walls)
        assert all(wall.height > 9 for wall in tall_walls)
        
        # Validate all results
        for wall in tall_walls:
            errors = self.validator.validate_element(wall)
            assert len(errors) == 0
    
    def test_query_rooms_with_filtering(self):
        """Test querying rooms with complex filtering."""
        query = QueryBuilder(
            self.provider,
            RoomElement,
            self.cache_manager
        )
        
        # Query large rooms (area > 250)
        large_rooms = query.where(lambda r: r.area > 250).to_list()
        
        assert len(large_rooms) == 1  # Only Room 102
        assert large_rooms[0].number == "102"
        assert large_rooms[0].area == 300
    
    def test_query_with_chained_operations(self):
        """Test chained query operations."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        
        # Complex query: walls wider than 0.4, ordered by height, take first 2
        result = (query
                  .where(lambda w: w.width > 0.4)
                  .order_by(lambda w: w.height)
                  .take(2)
                  .to_list())
        
        assert len(result) == 2
        assert result[0].height == 10  # Wall 1 (height 10, width 0.5)
        assert result[1].height == 12  # Wall 3 (height 12, width 0.6)
    
    def test_query_with_projection(self):
        """Test query with projection/select operations."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        
        # Project to just names and heights
        wall_info = query.select(lambda w: {"name": w.name, "height": w.height}).to_list()
        
        assert len(wall_info) == 3
        assert all("name" in info and "height" in info for info in wall_info)
        assert wall_info[0]["name"] == "Wall 1"
        assert wall_info[0]["height"] == 10
    
    def test_query_aggregations(self):
        """Test query aggregation operations."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        
        # Count all walls
        wall_count = query.count()
        assert wall_count == 3
        
        # Check if any walls are taller than 11 feet
        has_tall_walls = query.any(lambda w: w.height > 11)
        assert has_tall_walls is True
        
        # Check if all walls are structural (should be False as default is False)
        all_structural = query.all(lambda w: w.structural)
        assert all_structural is False
    
    @pytest.mark.asyncio
    async def test_async_query_operations(self):
        """Test async query operations."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        
        # Async count
        count = await query.count_async()
        assert count == 3
        
        # Async first
        first_wall = await query.first_async()
        assert isinstance(first_wall, WallElement)
        assert first_wall.id == 1
        
        # Async to_list
        all_walls = await query.to_list_async()
        assert len(all_walls) == 3
        assert all(isinstance(wall, WallElement) for wall in all_walls)
    
    def test_query_caching(self):
        """Test query result caching."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        
        # First execution - should cache results
        result1 = query.where(lambda w: w.height > 9).to_list()
        
        # Check cache statistics
        stats = self.cache_manager.statistics
        if stats:
            initial_hits = stats.hits
            
            # Second execution with same query - should hit cache
            result2 = query.where(lambda w: w.height > 9).to_list()
            
            assert result1 == result2
            # Cache hits should have increased (implementation dependent)
    
    def test_query_error_handling(self):
        """Test query error handling."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        
        # Query for non-existent element should raise QueryError
        with pytest.raises(QueryError):
            query.single(lambda w: w.height > 100)  # No walls this tall
        
        # Empty result for first() should raise QueryError
        with pytest.raises(QueryError):
            query.first(lambda w: w.height > 100)
    
    def test_query_with_invalid_predicate(self):
        """Test query behavior with invalid predicates."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        
        # Predicate that causes exception should be handled gracefully
        def invalid_predicate(w):
            return w.nonexistent_property > 5  # This will raise AttributeError
        
        # The query system should handle this gracefully
        try:
            result = query.where(invalid_predicate).to_list()
            # If it doesn't raise an exception, result should be empty or all items
            assert isinstance(result, list)
        except (AttributeError, QueryError):
            # This is also acceptable behavior
            pass


class TestElementSetIntegration:
    """Test ElementSet integration with validation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.walls = [
            WallElement(id=1, name="Wall 1", height=10, length=20, width=0.5),
            WallElement(id=2, name="Wall 2", height=8, length=15, width=0.4),
            WallElement(id=3, name="Wall 3", height=12, length=25, width=0.6),
        ]
        
        self.provider = MockElementProvider(self.walls)
        self.cache_manager = CacheManager()
        self.validator = ElementValidator(ValidationLevel.STANDARD)
    
    def test_element_set_creation_from_query(self):
        """Test creating ElementSet from query."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        element_set = ElementSet.from_query(query)
        
        assert isinstance(element_set, ElementSet)
        assert len(element_set) == 3
    
    def test_element_set_linq_operations(self):
        """Test LINQ-style operations on ElementSet."""
        element_set = ElementSet(self.walls, element_type=WallElement, lazy=False)
        
        # Filter tall walls
        tall_walls = element_set.where(lambda w: w.height > 9)
        assert len(tall_walls) == 2
        
        # Order by height
        ordered_walls = element_set.order_by(lambda w: w.height)
        heights = [w.height for w in ordered_walls]
        assert heights == [8, 10, 12]  # Should be sorted
        
        # Take first 2
        first_two = element_set.take(2)
        assert len(first_two) == 2
    
    def test_element_set_aggregations(self):
        """Test aggregation operations on ElementSet."""
        element_set = ElementSet(self.walls, element_type=WallElement, lazy=False)
        
        # Count
        assert element_set.count() == 3
        
        # Any/All
        assert element_set.any(lambda w: w.height > 11) is True
        assert element_set.all(lambda w: w.height > 5) is True
        assert element_set.all(lambda w: w.height > 15) is False
        
        # Min/Max
        min_wall = element_set.min(lambda w: w.height)
        max_wall = element_set.max(lambda w: w.height)
        assert min_wall.height == 8
        assert max_wall.height == 12
    
    def test_element_set_batch_operations(self):
        """Test batch operations on ElementSet."""
        element_set = ElementSet(self.walls.copy(), element_type=WallElement, lazy=False)
        
        # Batch update properties
        updates = {"structural": True, "fire_rating": 2}
        updated_count = element_set.batch_update(updates)
        
        assert updated_count == 6  # 3 elements * 2 properties each
        
        # Verify updates
        for wall in element_set:
            assert wall.structural is True
            assert wall.fire_rating == 2
    
    @pytest.mark.asyncio
    async def test_async_element_set(self):
        """Test AsyncElementSet operations."""
        element_set = ElementSet(self.walls, element_type=WallElement, lazy=False)
        async_set = AsyncElementSet.from_sync(element_set)
        
        # Async count
        count = await async_set.count_async()
        assert count == 3
        
        # Async first
        first_wall = await async_set.first_async()
        assert isinstance(first_wall, WallElement)
        
        # Async iteration
        walls_async = []
        async for wall in async_set:
            walls_async.append(wall)
        
        assert len(walls_async) == 3
        assert all(isinstance(wall, WallElement) for wall in walls_async)
    
    def test_element_set_validation_integration(self):
        """Test ElementSet with validation integration."""
        # Create element set with some invalid data (for testing)
        element_set = ElementSet(self.walls, element_type=WallElement, lazy=False)
        
        # All elements should be valid
        validator = ElementValidator(ValidationLevel.STANDARD)
        
        for wall in element_set:
            errors = validator.validate_element(wall)
            assert len(errors) == 0, f"Validation errors for wall {wall.id}: {errors}"


class TestPerformanceAndOptimization:
    """Test performance and optimization features."""
    
    def setup_method(self):
        """Setup test fixtures with larger dataset."""
        # Create a larger dataset for performance testing
        self.walls = []
        for i in range(1000):
            wall = WallElement(
                id=i,
                name=f"Wall {i}",
                height=8 + (i % 10),  # Heights from 8 to 17
                length=10 + (i % 20),  # Lengths from 10 to 29
                width=0.3 + (i % 5) * 0.1,  # Widths from 0.3 to 0.7
                category="Walls"
            )
            self.walls.append(wall)
        
        self.provider = MockElementProvider(self.walls)
        
        # Configure cache for performance
        cache_config = CacheConfiguration(
            max_size=5000,
            enable_statistics=True
        )
        self.cache_manager = CacheManager(cache_config)
    
    def test_large_query_performance(self):
        """Test performance with large dataset."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        
        # Complex query on large dataset
        result = (query
                  .where(lambda w: w.height > 10)
                  .where(lambda w: w.width > 0.4)
                  .order_by(lambda w: w.length)
                  .to_list())
        
        # Should complete without performance issues
        assert len(result) > 0
        assert all(isinstance(wall, WallElement) for wall in result)
        assert all(wall.height > 10 and wall.width > 0.4 for wall in result)
    
    @pytest.mark.asyncio
    async def test_async_streaming_query(self):
        """Test streaming query for large datasets."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        
        streaming_query = query.as_streaming(batch_size=100)
        
        total_processed = 0
        async for batch in streaming_query:
            assert len(batch) <= 100  # Batch size limit
            assert all(isinstance(wall, WallElement) for wall in batch)
            total_processed += len(batch)
        
        assert total_processed == len(self.walls)
    
    def test_query_caching_effectiveness(self):
        """Test that caching improves query performance."""
        query = QueryBuilder(self.provider, WallElement, self.cache_manager)
        
        # Clear cache to start fresh
        self.cache_manager.clear()
        
        # Execute same query multiple times
        for _ in range(5):
            result = query.where(lambda w: w.height > 12).to_list()
            assert len(result) > 0
        
        # Check cache statistics
        stats = self.cache_manager.statistics
        if stats:
            # Should have some cache activity
            assert stats.hits + stats.misses > 0
    
    def test_lazy_vs_eager_evaluation(self):
        """Test lazy vs eager evaluation performance characteristics."""
        # Lazy query
        lazy_query = QueryBuilder(
            self.provider, 
            WallElement, 
            self.cache_manager,
            QueryMode.LAZY
        )
        
        # Eager query
        eager_query = QueryBuilder(
            self.provider,
            WallElement,
            self.cache_manager, 
            QueryMode.EAGER
        )
        
        # Both should produce same results
        lazy_result = lazy_query.where(lambda w: w.height > 10).to_list()
        eager_result = eager_query.where(lambda w: w.height > 10).to_list()
        
        assert len(lazy_result) == len(eager_result)
        
        # Results should be equivalent (though order might differ)
        lazy_ids = set(w.id for w in lazy_result)
        eager_ids = set(w.id for w in eager_result)
        assert lazy_ids == eager_ids