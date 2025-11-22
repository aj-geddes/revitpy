"""
Unit tests for cache management functionality.
"""

import threading
import time
from datetime import timedelta
from unittest.mock import patch

import pytest

from revitpy.orm.cache import (
    CacheConfiguration,
    CacheEntry,
    CacheManager,
    CacheStatistics,
    EvictionPolicy,
    MemoryCache,
    create_entity_cache_key,
    create_query_cache_key,
    create_relationship_cache_key,
)
from revitpy.orm.types import CacheKey


@pytest.fixture
def cache_config():
    """Create test cache configuration."""
    return CacheConfiguration(
        max_size=100,
        max_memory_mb=10,
        default_ttl_seconds=300,
        eviction_policy=EvictionPolicy.LRU,
        enable_statistics=True,
        thread_safe=True,
    )


@pytest.fixture
def cache_key():
    """Create test cache key."""
    return CacheKey(
        entity_type="TestElement", entity_id="test-123", query_hash="abc123"
    )


@pytest.fixture
def cache_entry():
    """Create test cache entry."""
    key = CacheKey(entity_type="TestElement", entity_id="test-123")
    return CacheEntry(
        key=key, data={"name": "Test Element", "value": 42}, ttl_seconds=300
    )


class TestCacheStatistics:
    """Test cache statistics functionality."""

    def test_initial_statistics(self):
        """Test initial statistics state."""
        stats = CacheStatistics()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0
        assert stats.evictions == 0
        assert stats.invalidations == 0
        assert stats.memory_usage == 0
        assert isinstance(stats.uptime, timedelta)

    def test_record_operations(self):
        """Test recording cache operations."""
        stats = CacheStatistics()

        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        stats.record_eviction()
        stats.record_invalidation()

        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == 66.7  # 2/3 * 100
        assert stats.evictions == 1
        assert stats.invalidations == 1

    def test_memory_tracking(self):
        """Test memory usage tracking."""
        stats = CacheStatistics()

        stats.update_memory_usage(1024)
        assert stats.memory_usage == 1024

        stats.update_memory_usage(-512)
        assert stats.memory_usage == 512

    def test_reset(self):
        """Test statistics reset."""
        stats = CacheStatistics()
        stats.record_hit()
        stats.record_miss()
        stats.update_memory_usage(1024)

        stats.reset()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.memory_usage == 0

    def test_thread_safety(self):
        """Test thread-safe statistics operations."""
        stats = CacheStatistics()

        def worker():
            for _ in range(100):
                stats.record_hit()
                stats.record_miss()

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert stats.hits == 500  # 5 threads * 100 operations
        assert stats.misses == 500


class TestCacheEntry:
    """Test cache entry functionality."""

    def test_entry_creation(self, cache_key):
        """Test creating cache entry."""
        entry = CacheEntry(key=cache_key, data="test data", ttl_seconds=300)

        assert entry.key == cache_key
        assert entry.data == "test data"
        assert entry.ttl_seconds == 300
        assert entry.access_count == 0
        assert not entry.is_expired

    def test_expiration(self, cache_key):
        """Test cache entry expiration."""
        # Entry with very short TTL
        entry = CacheEntry(key=cache_key, data="test data", ttl_seconds=0.1)

        assert not entry.is_expired

        time.sleep(0.2)
        assert entry.is_expired

    def test_no_expiration(self, cache_key):
        """Test cache entry without TTL."""
        entry = CacheEntry(key=cache_key, data="test data", ttl_seconds=None)

        assert not entry.is_expired

        # Even after time passes, should not be expired
        time.sleep(0.1)
        assert not entry.is_expired

    def test_access_tracking(self, cache_key):
        """Test access count tracking."""
        entry = CacheEntry(key=cache_key, data="test data")

        initial_time = entry.accessed_at
        initial_count = entry.access_count

        time.sleep(0.01)
        entry.mark_accessed()

        assert entry.access_count == initial_count + 1
        assert entry.accessed_at > initial_time


class TestMemoryCache:
    """Test memory cache backend."""

    def test_basic_operations(self, cache_config, cache_key, cache_entry):
        """Test basic cache operations."""
        cache = MemoryCache(cache_config)

        # Initially empty
        assert cache.get(cache_key) is None
        assert cache.size() == 0

        # Set entry
        assert cache.set(cache_key, cache_entry) is True
        assert cache.size() == 1

        # Get entry
        retrieved = cache.get(cache_key)
        assert retrieved == cache_entry
        assert retrieved.access_count == 1  # Should be marked as accessed

        # Delete entry
        assert cache.delete(cache_key) is True
        assert cache.get(cache_key) is None
        assert cache.size() == 0

        # Delete non-existent
        assert cache.delete(cache_key) is False

    def test_lru_eviction(self, cache_config):
        """Test LRU eviction policy."""
        # Small cache size for testing eviction
        cache_config.max_size = 3
        cache = MemoryCache(cache_config)

        # Fill cache
        keys = []
        for i in range(3):
            key = CacheKey(entity_type="Test", entity_id=f"test-{i}")
            entry = CacheEntry(key=key, data=f"data-{i}")
            keys.append(key)
            cache.set(key, entry)

        assert cache.size() == 3

        # Access first item to make it recently used
        cache.get(keys[0])

        # Add another item, should evict the second item (LRU)
        new_key = CacheKey(entity_type="Test", entity_id="test-new")
        new_entry = CacheEntry(key=new_key, data="new-data")
        cache.set(new_key, new_entry)

        assert cache.size() == 3
        assert cache.get(keys[0]) is not None  # Recently used, should still be there
        assert cache.get(keys[1]) is None  # Should be evicted
        assert cache.get(keys[2]) is not None  # Should still be there
        assert cache.get(new_key) is not None  # New item should be there

    def test_ttl_expiration(self, cache_config):
        """Test TTL-based expiration."""
        cache = MemoryCache(cache_config)

        key = CacheKey(entity_type="Test", entity_id="test-ttl")
        entry = CacheEntry(key=key, data="test data", ttl_seconds=0.1)

        cache.set(key, entry)
        assert cache.get(key) is not None

        time.sleep(0.2)
        assert cache.get(key) is None  # Should be expired and removed

    def test_dependency_tracking(self, cache_config):
        """Test cache dependency invalidation."""
        cache = MemoryCache(cache_config)

        # Create entries with dependencies
        key1 = CacheKey(entity_type="Test", entity_id="test-1")
        entry1 = CacheEntry(key=key1, data="data-1", dependencies={"dep1", "dep2"})

        key2 = CacheKey(entity_type="Test", entity_id="test-2")
        entry2 = CacheEntry(key=key2, data="data-2", dependencies={"dep2", "dep3"})

        cache.set(key1, entry1)
        cache.set(key2, entry2)

        # Invalidate by dependency
        invalidated = cache.invalidate_dependencies("dep2")

        assert len(invalidated) == 2  # Both entries should be invalidated
        assert cache.get(key1) is None
        assert cache.get(key2) is None

    def test_clear(self, cache_config, cache_key, cache_entry):
        """Test cache clear operation."""
        cache = MemoryCache(cache_config)

        cache.set(cache_key, cache_entry)
        assert cache.size() == 1

        cache.clear()
        assert cache.size() == 0
        assert cache.get(cache_key) is None

    def test_keys(self, cache_config):
        """Test getting all cache keys."""
        cache = MemoryCache(cache_config)

        # Add multiple entries
        keys = []
        for i in range(3):
            key = CacheKey(entity_type="Test", entity_id=f"test-{i}")
            entry = CacheEntry(key=key, data=f"data-{i}")
            keys.append(key)
            cache.set(key, entry)

        retrieved_keys = cache.keys()
        assert len(retrieved_keys) == 3

        # Keys should match (order may vary)
        retrieved_entity_types = {k.entity_type for k in retrieved_keys}
        assert retrieved_entity_types == {"Test"}


class TestCacheManager:
    """Test cache manager functionality."""

    def test_basic_operations(self, cache_config):
        """Test basic cache manager operations."""
        manager = CacheManager(cache_config)

        key = CacheKey(entity_type="Test", entity_id="test-1")
        value = {"name": "Test", "value": 42}

        # Initially empty
        assert manager.get(key) is None
        assert manager.size == 0

        # Set value
        assert manager.set(key, value) is True
        assert manager.size == 1

        # Get value
        retrieved = manager.get(key)
        assert retrieved == value

        # Check contains
        assert manager.contains(key) is True

        # Delete value
        assert manager.delete(key) is True
        assert manager.get(key) is None
        assert manager.size == 0

    def test_ttl_and_dependencies(self, cache_config):
        """Test TTL and dependency features."""
        manager = CacheManager(cache_config)

        key = CacheKey(entity_type="Test", entity_id="test-1")
        value = "test data"
        dependencies = {"entity_123", "relationship_abc"}

        # Set with TTL and dependencies
        manager.set(key, value, ttl_seconds=300, dependencies=dependencies)

        assert manager.get(key) == value

        # Invalidate by dependency
        invalidated_count = manager.invalidate_by_dependency("entity_123")
        assert invalidated_count >= 1
        assert manager.get(key) is None

    def test_pattern_invalidation(self, cache_config):
        """Test pattern-based invalidation."""
        manager = CacheManager(cache_config)

        # Add multiple entries
        for i in range(5):
            key = CacheKey(entity_type="TestEntity", entity_id=f"test-{i}")
            manager.set(key, f"data-{i}")

        key_other = CacheKey(entity_type="OtherEntity", entity_id="other-1")
        manager.set(key_other, "other data")

        # Invalidate by pattern
        invalidated_count = manager.invalidate_by_pattern("TestEntity")

        assert invalidated_count == 5
        assert manager.get(key_other) == "other data"  # Should not be affected

    def test_statistics_integration(self, cache_config):
        """Test statistics integration."""
        manager = CacheManager(cache_config)
        stats = manager.statistics

        assert stats is not None
        assert stats.hits == 0
        assert stats.misses == 0

        key = CacheKey(entity_type="Test", entity_id="test-1")

        # Miss
        manager.get(key)
        assert stats.misses == 1

        # Set and hit
        manager.set(key, "test data")
        manager.get(key)
        assert stats.hits == 1

        # Invalidation
        manager.delete(key)
        assert stats.invalidations == 1

    def test_invalidation_callbacks(self, cache_config):
        """Test invalidation callbacks."""
        manager = CacheManager(cache_config)

        callback_calls = []

        def test_callback(key: CacheKey):
            callback_calls.append(key)

        manager.add_invalidation_callback(test_callback)

        key = CacheKey(entity_type="Test", entity_id="test-1")
        manager.set(key, "test data")
        manager.delete(key)

        assert len(callback_calls) == 1
        assert callback_calls[0] == key

        # Remove callback
        manager.remove_invalidation_callback(test_callback)
        manager.set(key, "test data")
        manager.delete(key)

        assert len(callback_calls) == 1  # Should not increase

    def test_clear(self, cache_config):
        """Test cache clear operation."""
        manager = CacheManager(cache_config)

        # Add some entries
        for i in range(3):
            key = CacheKey(entity_type="Test", entity_id=f"test-{i}")
            manager.set(key, f"data-{i}")

        assert manager.size == 3

        manager.clear()

        assert manager.size == 0
        if manager.statistics:
            assert manager.statistics.hits == 0
            assert manager.statistics.misses == 0

    def test_memory_usage_estimate(self, cache_config):
        """Test memory usage estimation."""
        manager = CacheManager(cache_config)

        initial_usage = manager.get_memory_usage_estimate()

        # Add entries
        for i in range(10):
            key = CacheKey(entity_type="Test", entity_id=f"test-{i}")
            manager.set(key, f"data-{i}")

        final_usage = manager.get_memory_usage_estimate()
        assert final_usage > initial_usage

    def test_thread_safety(self, cache_config):
        """Test thread-safe operations."""
        manager = CacheManager(cache_config)

        def worker(worker_id):
            for i in range(50):
                key = CacheKey(entity_type="Test", entity_id=f"worker-{worker_id}-{i}")
                manager.set(key, f"data-{worker_id}-{i}")
                retrieved = manager.get(key)
                assert retrieved == f"data-{worker_id}-{i}"

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert manager.size == 250  # 5 workers * 50 entries each

    def test_error_handling(self):
        """Test error handling in cache operations."""
        # Test with None backend
        manager = CacheManager()

        # Should handle errors gracefully
        key = CacheKey(entity_type="Test", entity_id="test-1")

        with patch.object(
            manager._backend, "get", side_effect=Exception("Backend error")
        ):
            result = manager.get(key)
            assert result is None  # Should return None on error

        with patch.object(
            manager._backend, "set", side_effect=Exception("Backend error")
        ):
            result = manager.set(key, "test data")
            assert result is False  # Should return False on error


class TestCacheUtilityFunctions:
    """Test cache utility functions."""

    def test_create_entity_cache_key(self):
        """Test entity cache key creation."""
        key = create_entity_cache_key("TestEntity", "test-123")

        assert key.entity_type == "TestEntity"
        assert key.entity_id == "test-123"
        assert key.query_hash is None
        assert key.relationship_path is None

    def test_create_query_cache_key(self):
        """Test query cache key creation."""
        key = create_query_cache_key("TestEntity", "query-hash-123")

        assert key.entity_type == "TestEntity"
        assert key.query_hash == "query-hash-123"
        assert key.entity_id is None
        assert key.relationship_path is None

    def test_create_relationship_cache_key(self):
        """Test relationship cache key creation."""
        key = create_relationship_cache_key("TestEntity", "test-123", "related_items")

        assert key.entity_type == "TestEntity"
        assert key.entity_id == "test-123"
        assert key.relationship_path == "related_items"
        assert key.query_hash is None


class TestCacheKey:
    """Test cache key functionality."""

    def test_cache_key_string_representation(self):
        """Test cache key string conversion."""
        key = CacheKey(
            entity_type="TestEntity",
            entity_id="test-123",
            query_hash="abc123",
            relationship_path="related",
        )

        key_str = str(key)

        assert "TestEntity" in key_str
        assert "test-123" in key_str
        assert "abc123" in key_str
        assert "related" in key_str

    def test_cache_key_minimal(self):
        """Test minimal cache key."""
        key = CacheKey(entity_type="TestEntity")

        key_str = str(key)
        assert key_str == "TestEntity"

    def test_cache_key_equality(self):
        """Test cache key equality."""
        key1 = CacheKey(entity_type="Test", entity_id="123")
        key2 = CacheKey(entity_type="Test", entity_id="123")
        key3 = CacheKey(entity_type="Test", entity_id="456")

        assert key1.entity_type == key2.entity_type
        assert key1.entity_id == key2.entity_id
        assert key1.entity_id != key3.entity_id


if __name__ == "__main__":
    pytest.main([__file__])
