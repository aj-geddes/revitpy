"""
Performance benchmarks and regression tests for the RevitPy ORM layer.

These tests ensure the ORM meets the performance requirements:
- <100ms response time for complex queries on 10,000+ elements
- <10ms response time for simple property access
- Support for millions of elements with pagination
"""

import pytest
import time
import asyncio
import statistics
from typing import List, Dict, Any
from unittest.mock import Mock
from contextlib import contextmanager

# Import comprehensive performance system
try:
    from revitpy.performance import (
        PerformanceOptimizer, OptimizationConfig,
        MemoryManager, BenchmarkSuite, PERFORMANCE_TARGETS
    )
    HAS_PERFORMANCE_SYSTEM = True
except ImportError:
    HAS_PERFORMANCE_SYSTEM = False

from revitpy.orm.query_builder import QueryBuilder
from revitpy.orm.element_set import ElementSet, AsyncElementSet
from revitpy.orm.validation import WallElement, RoomElement, DoorElement
from revitpy.orm.cache import CacheManager, CacheConfiguration
from revitpy.orm.change_tracker import ChangeTracker
from revitpy.orm.relationships import RelationshipManager
from revitpy.orm.context import RevitContext, ContextConfiguration
from revitpy.orm.types import QueryMode, CachePolicy


class PerformanceElementProvider:
    """High-performance element provider for benchmarking."""
    
    def __init__(self, element_count: int = 10000):
        self.element_count = element_count
        self._elements = None
        self._type_mapping = {}
    
    def _generate_elements(self):
        """Generate test elements for benchmarking."""
        if self._elements is not None:
            return
        
        self._elements = []
        
        # Generate walls (70% of elements)
        wall_count = int(self.element_count * 0.7)
        for i in range(wall_count):
            wall = WallElement(
                id=i,
                name=f"Wall_{i:06d}",
                height=8 + (i % 20) * 0.5,  # Heights 8-18
                length=10 + (i % 50) * 0.2,  # Lengths 10-20
                width=0.2 + (i % 10) * 0.05,  # Widths 0.2-0.65
                category="Walls",
                structural=(i % 4 == 0),  # 25% structural
                fire_rating=(i % 5)  # 0-4 hour ratings
            )
            self._elements.append(wall)
        
        # Generate rooms (20% of elements)
        room_count = int(self.element_count * 0.2)
        for i in range(room_count):
            room_id = wall_count + i
            room = RoomElement(
                id=room_id,
                number=f"{100 + (i // 100):03d}{chr(65 + (i % 26))}",
                name=f"Room_{i:04d}",
                area=100 + (i % 500) * 2,  # Areas 100-1100
                perimeter=40 + (i % 100) * 0.5,  # Perimeters 40-90
                volume=(100 + (i % 500) * 2) * 10,  # Volume = area * 10
                department=f"Dept_{i % 10}",
                occupancy=1 + (i % 20)  # 1-20 people
            )
            self._elements.append(room)
        
        # Generate doors (10% of elements) 
        door_count = self.element_count - wall_count - room_count
        for i in range(door_count):
            door_id = wall_count + room_count + i
            door = DoorElement(
                id=door_id,
                name=f"Door_{i:04d}",
                width=2.5 + (i % 4) * 0.5,  # Widths 2.5-4
                height=6.5 + (i % 3) * 0.5,  # Heights 6.5-7.5
                material=f"Material_{i % 5}",
                fire_rating=(i % 4) * 0.75,  # 0, 0.75, 1.5, 2.25 hour ratings
                hand="Left" if i % 2 == 0 else "Right"
            )
            self._elements.append(door)
        
        # Create type mapping for efficient lookups
        self._type_mapping = {}
        for element in self._elements:
            element_type = type(element)
            if element_type not in self._type_mapping:
                self._type_mapping[element_type] = []
            self._type_mapping[element_type].append(element)
    
    def get_all_elements(self) -> List[Any]:
        self._generate_elements()
        return self._elements
    
    def get_elements_of_type(self, element_type: Any) -> List[Any]:
        self._generate_elements()
        return self._type_mapping.get(element_type, [])
    
    def get_element_by_id(self, element_id: Any) -> Any:
        self._generate_elements()
        # Optimized lookup by ID
        if 0 <= element_id < len(self._elements):
            return self._elements[element_id]
        return None
    
    async def get_all_elements_async(self) -> List[Any]:
        return self.get_all_elements()
    
    async def get_elements_of_type_async(self, element_type: Any) -> List[Any]:
        return self.get_elements_of_type(element_type)
    
    async def get_element_by_id_async(self, element_id: Any) -> Any:
        return self.get_element_by_id(element_id)


@contextmanager
def measure_time():
    """Context manager to measure execution time."""
    start_time = time.perf_counter()
    yield lambda: time.perf_counter() - start_time
    

class TestQueryPerformance:
    """Test query performance benchmarks."""
    
    def setup_method(self):
        """Setup large dataset for performance testing."""
        self.provider = PerformanceElementProvider(element_count=10000)
        
        # High-performance cache configuration
        cache_config = CacheConfiguration(
            max_size=50000,
            max_memory_mb=1000,
            enable_statistics=True
        )
        self.cache_manager = CacheManager(cache_config)
    
    def test_simple_query_performance_requirement(self):
        """Test that simple queries meet <10ms requirement."""
        query = QueryBuilder(
            self.provider,
            WallElement,
            self.cache_manager,
            QueryMode.LAZY
        )
        
        # Warm up
        query.first()
        
        # Measure multiple runs
        times = []
        for _ in range(10):
            with measure_time() as get_time:
                result = query.first()
            
            times.append(get_time() * 1000)  # Convert to milliseconds
            assert isinstance(result, WallElement)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        print(f"Simple query - Average: {avg_time:.2f}ms, Max: {max_time:.2f}ms")
        
        # Performance requirement: <10ms for simple operations
        assert avg_time < 10, f"Simple query too slow: {avg_time:.2f}ms (requirement: <10ms)"
        assert max_time < 20, f"Simple query max time too slow: {max_time:.2f}ms"
    
    def test_complex_query_performance_requirement(self):
        """Test that complex queries meet <100ms requirement on 10,000+ elements."""
        query = QueryBuilder(
            self.provider,
            WallElement,
            self.cache_manager,
            QueryMode.LAZY
        )
        
        # Complex query: filter, join conditions, ordering, aggregation
        def complex_query():
            return (query
                    .where(lambda w: w.height > 10)
                    .where(lambda w: w.width > 0.3)
                    .where(lambda w: w.structural == True)
                    .order_by(lambda w: w.length)
                    .order_by(lambda w: w.height)
                    .take(100)
                    .to_list())
        
        # Warm up
        complex_query()
        
        # Measure multiple runs
        times = []
        for _ in range(5):
            with measure_time() as get_time:
                result = complex_query()
            
            times.append(get_time() * 1000)  # Convert to milliseconds
            assert len(result) <= 100
            assert all(isinstance(wall, WallElement) for wall in result)
            assert all(wall.height > 10 and wall.width > 0.3 and wall.structural for wall in result)
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        print(f"Complex query - Average: {avg_time:.2f}ms, Max: {max_time:.2f}ms")
        
        # Performance requirement: <100ms for complex queries
        assert avg_time < 100, f"Complex query too slow: {avg_time:.2f}ms (requirement: <100ms)"
        assert max_time < 200, f"Complex query max time too slow: {max_time:.2f}ms"
    
    def test_large_result_set_performance(self):
        """Test performance with large result sets."""
        query = QueryBuilder(
            self.provider,
            WallElement,
            self.cache_manager,
            QueryMode.LAZY
        )
        
        # Query that returns large result set
        def large_query():
            return query.where(lambda w: w.height > 8).to_list()
        
        with measure_time() as get_time:
            result = large_query()
        
        time_ms = get_time() * 1000
        result_count = len(result)
        
        print(f"Large result set ({result_count} elements) - Time: {time_ms:.2f}ms")
        
        # Should handle thousands of results efficiently
        assert result_count > 1000
        assert time_ms < 500  # Should complete within 500ms even for large results
    
    @pytest.mark.asyncio
    async def test_async_query_performance(self):
        """Test async query performance."""
        query = QueryBuilder(
            self.provider,
            WallElement,
            self.cache_manager,
            QueryMode.LAZY
        )
        
        # Measure async operations
        times = []
        for _ in range(5):
            with measure_time() as get_time:
                result = await query.where(lambda w: w.height > 12).to_list_async()
            
            times.append(get_time() * 1000)
            assert len(result) > 0
        
        avg_time = statistics.mean(times)
        print(f"Async query - Average: {avg_time:.2f}ms")
        
        # Async should be competitive with sync performance
        assert avg_time < 150, f"Async query too slow: {avg_time:.2f}ms"
    
    def test_query_caching_performance_impact(self):
        """Test performance impact of caching."""
        query = QueryBuilder(
            self.provider,
            WallElement,
            self.cache_manager,
            QueryMode.LAZY
        )
        
        # Clear cache
        self.cache_manager.clear()
        
        # First execution (cache miss)
        with measure_time() as get_time:
            result1 = query.where(lambda w: w.fire_rating > 2).to_list()
        first_time = get_time() * 1000
        
        # Second execution (should benefit from any caching)
        with measure_time() as get_time:
            result2 = query.where(lambda w: w.fire_rating > 2).to_list()
        second_time = get_time() * 1000
        
        print(f"Cache impact - First: {first_time:.2f}ms, Second: {second_time:.2f}ms")
        
        assert len(result1) == len(result2)
        # Second execution should be at least as fast (allowing for variability)
        assert second_time <= first_time * 1.5  # Allow 50% variance


class TestElementSetPerformance:
    """Test ElementSet performance benchmarks."""
    
    def setup_method(self):
        """Setup for ElementSet performance tests."""
        self.provider = PerformanceElementProvider(element_count=5000)
        self.walls = self.provider.get_elements_of_type(WallElement)
    
    def test_element_set_creation_performance(self):
        """Test ElementSet creation performance."""
        with measure_time() as get_time:
            element_set = ElementSet(self.walls, element_type=WallElement, lazy=False)
        
        creation_time = get_time() * 1000
        print(f"ElementSet creation ({len(self.walls)} elements) - Time: {creation_time:.2f}ms")
        
        assert len(element_set) == len(self.walls)
        assert creation_time < 50, f"ElementSet creation too slow: {creation_time:.2f}ms"
    
    def test_element_set_operations_performance(self):
        """Test ElementSet operation performance."""
        element_set = ElementSet(self.walls, element_type=WallElement, lazy=False)
        
        # Test filtering performance
        with measure_time() as get_time:
            tall_walls = element_set.where(lambda w: w.height > 12)
        filter_time = get_time() * 1000
        
        # Test ordering performance  
        with measure_time() as get_time:
            ordered_walls = element_set.order_by(lambda w: w.height)
        sort_time = get_time() * 1000
        
        # Test aggregation performance
        with measure_time() as get_time:
            wall_count = element_set.count()
        count_time = get_time() * 1000
        
        print(f"ElementSet operations - Filter: {filter_time:.2f}ms, Sort: {sort_time:.2f}ms, Count: {count_time:.2f}ms")
        
        assert len(tall_walls) > 0
        assert len(ordered_walls) == len(self.walls)
        assert wall_count == len(self.walls)
        
        # Performance requirements
        assert filter_time < 30, f"Filtering too slow: {filter_time:.2f}ms"
        assert sort_time < 100, f"Sorting too slow: {sort_time:.2f}ms"
        assert count_time < 5, f"Counting too slow: {count_time:.2f}ms"
    
    def test_batch_operations_performance(self):
        """Test batch operation performance."""
        element_set = ElementSet(self.walls[:1000].copy(), element_type=WallElement, lazy=False)
        
        # Test batch update performance
        updates = {"structural": True, "fire_rating": 2}
        
        with measure_time() as get_time:
            updated_count = element_set.batch_update(updates, batch_size=100)
        
        batch_time = get_time() * 1000
        throughput = updated_count / (batch_time / 1000)  # Updates per second
        
        print(f"Batch update - Time: {batch_time:.2f}ms, Throughput: {throughput:.0f} updates/sec")
        
        assert updated_count == len(element_set) * len(updates)
        assert batch_time < 200, f"Batch update too slow: {batch_time:.2f}ms"
        assert throughput > 5000, f"Batch update throughput too low: {throughput:.0f} updates/sec"


class TestCachePerformance:
    """Test cache performance benchmarks."""
    
    def setup_method(self):
        """Setup for cache performance tests."""
        self.cache_config = CacheConfiguration(
            max_size=10000,
            max_memory_mb=100,
            enable_statistics=True
        )
        self.cache_manager = CacheManager(self.cache_config)
    
    def test_cache_set_get_performance(self):
        """Test basic cache set/get performance."""
        from revitpy.orm.cache import create_entity_cache_key
        
        # Test data
        test_elements = [
            WallElement(id=i, height=10, length=20, width=0.5, name=f"Wall {i}")
            for i in range(1000)
        ]
        
        # Measure cache set performance
        with measure_time() as get_time:
            for element in test_elements:
                cache_key = create_entity_cache_key("Wall", element.id)
                self.cache_manager.set(cache_key, element)
        set_time = get_time() * 1000
        
        # Measure cache get performance
        cache_keys = [create_entity_cache_key("Wall", i) for i in range(1000)]
        
        with measure_time() as get_time:
            for cache_key in cache_keys:
                result = self.cache_manager.get(cache_key)
                assert result is not None
        get_time_ms = get_time() * 1000
        
        set_throughput = len(test_elements) / (set_time / 1000)
        get_throughput = len(cache_keys) / (get_time_ms / 1000)
        
        print(f"Cache performance - Set: {set_time:.2f}ms ({set_throughput:.0f}/sec), Get: {get_time_ms:.2f}ms ({get_throughput:.0f}/sec)")
        
        # Performance requirements for cache operations
        assert set_time < 100, f"Cache set too slow: {set_time:.2f}ms"
        assert get_time_ms < 50, f"Cache get too slow: {get_time_ms:.2f}ms"
        assert set_throughput > 5000, f"Cache set throughput too low: {set_throughput:.0f}/sec"
        assert get_throughput > 10000, f"Cache get throughput too low: {get_throughput:.0f}/sec"
    
    def test_cache_invalidation_performance(self):
        """Test cache invalidation performance."""
        from revitpy.orm.cache import create_entity_cache_key
        
        # Populate cache
        for i in range(2000):
            cache_key = create_entity_cache_key("Wall", i)
            element = WallElement(id=i, height=10, length=20, width=0.5)
            self.cache_manager.set(cache_key, element)
        
        # Test pattern-based invalidation
        with measure_time() as get_time:
            invalidated_count = self.cache_manager.invalidate_by_pattern("Wall")
        
        invalidation_time = get_time() * 1000
        invalidation_throughput = invalidated_count / (invalidation_time / 1000)
        
        print(f"Cache invalidation - Time: {invalidation_time:.2f}ms, Count: {invalidated_count}, Throughput: {invalidation_throughput:.0f}/sec")
        
        assert invalidated_count > 0
        assert invalidation_time < 100, f"Cache invalidation too slow: {invalidation_time:.2f}ms"


class TestChangeTrackerPerformance:
    """Test change tracker performance benchmarks."""
    
    def test_change_tracking_performance(self):
        """Test change tracking performance with many entities."""
        change_tracker = ChangeTracker(thread_safe=True)
        
        # Create test elements
        elements = [
            WallElement(id=i, height=10, length=20, width=0.5, name=f"Wall {i}")
            for i in range(1000)
        ]
        
        # Test attachment performance
        with measure_time() as get_time:
            for element in elements:
                change_tracker.attach(element)
        
        attach_time = get_time() * 1000
        attach_throughput = len(elements) / (attach_time / 1000)
        
        # Test change tracking performance
        with measure_time() as get_time:
            for i, element in enumerate(elements):
                element.name = f"Modified Wall {i}"
                change_tracker.track_property_change(element, "name", f"Wall {i}", f"Modified Wall {i}")
        
        track_time = get_time() * 1000
        track_throughput = len(elements) / (track_time / 1000)
        
        print(f"Change tracking - Attach: {attach_time:.2f}ms ({attach_throughput:.0f}/sec), Track: {track_time:.2f}ms ({track_throughput:.0f}/sec)")
        
        assert change_tracker.change_count == len(elements)
        assert attach_time < 200, f"Change tracker attach too slow: {attach_time:.2f}ms"
        assert track_time < 100, f"Change tracking too slow: {track_time:.2f}ms"
        assert attach_throughput > 2000, f"Attach throughput too low: {attach_throughput:.0f}/sec"
        assert track_throughput > 5000, f"Track throughput too low: {track_throughput:.0f}/sec"


class TestIntegratedContextPerformance:
    """Test integrated RevitContext performance."""
    
    def setup_method(self):
        """Setup integrated context for testing."""
        self.provider = PerformanceElementProvider(element_count=5000)
        
        config = ContextConfiguration(
            auto_track_changes=True,
            cache_policy=CachePolicy.MEMORY,
            cache_max_size=10000,
            performance_monitoring=True
        )
        
        self.context = RevitContext(self.provider, config=config)
    
    def test_context_query_performance(self):
        """Test RevitContext query performance."""
        # Test simple queries
        with measure_time() as get_time:
            first_wall = self.context.first(WallElement)
        simple_time = get_time() * 1000
        
        # Test complex queries
        with measure_time() as get_time:
            tall_structural_walls = (self.context.where(WallElement, lambda w: w.height > 12)
                                     .where(lambda w: w.structural == True)
                                     .to_list())
        complex_time = get_time() * 1000
        
        print(f"Context queries - Simple: {simple_time:.2f}ms, Complex: {complex_time:.2f}ms")
        
        assert isinstance(first_wall, WallElement)
        assert len(tall_structural_walls) >= 0
        
        # Performance requirements
        assert simple_time < 15, f"Simple context query too slow: {simple_time:.2f}ms"
        assert complex_time < 150, f"Complex context query too slow: {complex_time:.2f}ms"
    
    def test_context_change_tracking_performance(self):
        """Test RevitContext change tracking performance."""
        # Get some elements
        walls = self.context.all(WallElement).take(500).to_list()
        
        # Test modification tracking
        with measure_time() as get_time:
            for i, wall in enumerate(walls):
                wall.name = f"Modified Wall {i}"
                wall.mark_dirty()
        
        modify_time = get_time() * 1000
        
        # Test save changes (mock operation)
        with measure_time() as get_time:
            # In a real implementation, this would persist changes
            change_count = self.context.change_count
        
        save_time = get_time() * 1000
        
        print(f"Context change tracking - Modify: {modify_time:.2f}ms, Changes: {change_count}, Check: {save_time:.2f}ms")
        
        assert change_count == len(walls)
        assert modify_time < 100, f"Change modification too slow: {modify_time:.2f}ms"
        assert save_time < 10, f"Change count check too slow: {save_time:.2f}ms"
    
    def teardown_method(self):
        """Cleanup after tests."""
        self.context.dispose()


class TestScalabilityBenchmarks:
    """Test scalability with different dataset sizes."""
    
    @pytest.mark.parametrize("element_count", [1000, 5000, 10000, 50000])
    def test_query_scalability(self, element_count):
        """Test query performance scalability."""
        provider = PerformanceElementProvider(element_count=element_count)
        cache_manager = CacheManager()
        
        query = QueryBuilder(provider, WallElement, cache_manager)
        
        # Complex query that should scale linearly
        with measure_time() as get_time:
            result = (query
                      .where(lambda w: w.height > 10)
                      .order_by(lambda w: w.length)
                      .take(100)
                      .to_list())
        
        query_time = get_time() * 1000
        elements_per_ms = element_count / query_time
        
        print(f"Scalability test - Elements: {element_count:,}, Time: {query_time:.2f}ms, Rate: {elements_per_ms:.0f} elements/ms")
        
        assert len(result) <= 100
        
        # Performance should scale reasonably
        if element_count <= 10000:
            assert query_time < 200, f"Query too slow for {element_count} elements: {query_time:.2f}ms"
        else:
            # For very large datasets, allow more time but should still be reasonable
            assert query_time < 1000, f"Query too slow for {element_count} elements: {query_time:.2f}ms"
        
        # Throughput should be maintained
        assert elements_per_ms > 50, f"Processing rate too low: {elements_per_ms:.0f} elements/ms"


@pytest.mark.benchmark
class TestRegressionBenchmarks:
    """Regression tests to ensure performance doesn't degrade."""
    
    def test_baseline_performance_metrics(self):
        """Establish baseline performance metrics."""
        provider = PerformanceElementProvider(element_count=10000)
        cache_manager = CacheManager()
        query = QueryBuilder(provider, WallElement, cache_manager)
        
        # Baseline metrics (these should be maintained or improved)
        baseline_metrics = {
            'simple_query_ms': 10,
            'complex_query_ms': 100,
            'large_result_ms': 500,
            'cache_set_throughput': 5000,
            'cache_get_throughput': 10000
        }
        
        # Simple query
        with measure_time() as get_time:
            query.first()
        simple_time = get_time() * 1000
        
        # Complex query
        with measure_time() as get_time:
            query.where(lambda w: w.height > 10).where(lambda w: w.structural == True).to_list()
        complex_time = get_time() * 1000
        
        print(f"Regression test - Simple: {simple_time:.2f}ms (baseline: {baseline_metrics['simple_query_ms']}ms)")
        print(f"Regression test - Complex: {complex_time:.2f}ms (baseline: {baseline_metrics['complex_query_ms']}ms)")
        
        # Ensure performance hasn't regressed beyond acceptable thresholds
        assert simple_time <= baseline_metrics['simple_query_ms'] * 1.5, f"Simple query regression: {simple_time:.2f}ms"
        assert complex_time <= baseline_metrics['complex_query_ms'] * 1.5, f"Complex query regression: {complex_time:.2f}ms"