"""
Intelligent caching system for the RevitPy ORM layer.

This module provides multi-level caching with LRU eviction, intelligent
invalidation, dependency tracking, and performance monitoring.
"""

from __future__ import annotations

import threading
import time
import weakref
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import (
    Any, Dict, List, Optional, Set, Type, TypeVar, Generic, Union,
    Callable, Hashable, Protocol
)
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger

from .types import CacheKey, CacheEntry, CachePolicy, ElementId
from .exceptions import CacheError


T = TypeVar('T')
K = TypeVar('K', bound=Hashable)
V = TypeVar('V')


class EvictionPolicy(Enum):
    """Cache eviction policies."""
    
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In, First Out
    TTL = "ttl"  # Time To Live only
    SIZE_BASED = "size_based"  # Based on memory size


class CacheStatistics:
    """Statistics for cache performance monitoring."""
    
    def __init__(self) -> None:
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._invalidations = 0
        self._memory_usage = 0
        self._start_time = datetime.utcnow()
        self._lock = threading.RLock()
    
    @property
    def hits(self) -> int:
        """Get cache hit count."""
        with self._lock:
            return self._hits
    
    @property
    def misses(self) -> int:
        """Get cache miss count."""
        with self._lock:
            return self._misses
    
    @property
    def hit_rate(self) -> float:
        """Get cache hit rate as percentage."""
        with self._lock:
            total = self._hits + self._misses
            return (self._hits / total * 100) if total > 0 else 0.0
    
    @property
    def evictions(self) -> int:
        """Get eviction count."""
        with self._lock:
            return self._evictions
    
    @property
    def invalidations(self) -> int:
        """Get invalidation count."""
        with self._lock:
            return self._invalidations
    
    @property
    def memory_usage(self) -> int:
        """Get estimated memory usage in bytes."""
        with self._lock:
            return self._memory_usage
    
    @property
    def uptime(self) -> timedelta:
        """Get cache uptime."""
        return datetime.utcnow() - self._start_time
    
    def record_hit(self) -> None:
        """Record a cache hit."""
        with self._lock:
            self._hits += 1
    
    def record_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self._misses += 1
    
    def record_eviction(self) -> None:
        """Record a cache eviction."""
        with self._lock:
            self._evictions += 1
    
    def record_invalidation(self) -> None:
        """Record a cache invalidation."""
        with self._lock:
            self._invalidations += 1
    
    def update_memory_usage(self, delta: int) -> None:
        """Update memory usage by delta bytes."""
        with self._lock:
            self._memory_usage += delta
    
    def reset(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._invalidations = 0
            self._memory_usage = 0
            self._start_time = datetime.utcnow()
    
    def __str__(self) -> str:
        return (
            f"CacheStats(hits={self.hits}, misses={self.misses}, "
            f"hit_rate={self.hit_rate:.1f}%, evictions={self.evictions}, "
            f"memory_usage={self.memory_usage:,} bytes, uptime={self.uptime})"
        )


@dataclass
class CacheConfiguration:
    """Configuration for cache behavior."""
    
    max_size: int = 10000  # Maximum number of entries
    max_memory_mb: int = 500  # Maximum memory usage in MB
    default_ttl_seconds: Optional[int] = 3600  # 1 hour default TTL
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    enable_statistics: bool = True
    cleanup_interval_seconds: int = 300  # 5 minutes
    compression_enabled: bool = False
    thread_safe: bool = True
    
    def __post_init__(self) -> None:
        if self.max_size <= 0:
            raise ValueError("max_size must be positive")
        if self.max_memory_mb <= 0:
            raise ValueError("max_memory_mb must be positive")


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: CacheKey) -> Optional[CacheEntry]:
        """Get cache entry by key."""
        pass
    
    @abstractmethod
    def set(self, key: CacheKey, entry: CacheEntry) -> bool:
        """Set cache entry."""
        pass
    
    @abstractmethod
    def delete(self, key: CacheKey) -> bool:
        """Delete cache entry."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        pass
    
    @abstractmethod
    def keys(self) -> List[CacheKey]:
        """Get all cache keys."""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get number of cached entries."""
        pass


class MemoryCache(CacheBackend):
    """In-memory cache implementation with LRU eviction."""
    
    def __init__(self, config: CacheConfiguration) -> None:
        self._config = config
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._key_dependencies: Dict[str, Set[str]] = {}  # key -> dependent keys
        self._reverse_dependencies: Dict[str, Set[str]] = {}  # dependent -> source keys
        self._lock = threading.RLock() if config.thread_safe else None
        self._last_cleanup = time.time()
    
    def get(self, key: CacheKey) -> Optional[CacheEntry]:
        """Get cache entry by key."""
        with self._lock if self._lock else self._no_op():
            key_str = str(key)
            
            if key_str not in self._cache:
                return None
            
            entry = self._cache[key_str]
            
            # Check expiration
            if entry.is_expired:
                del self._cache[key_str]
                self._cleanup_dependencies(key_str)
                return None
            
            # Update access info
            entry.mark_accessed()
            
            # Move to end for LRU
            if self._config.eviction_policy == EvictionPolicy.LRU:
                self._cache.move_to_end(key_str)
            
            return entry
    
    def set(self, key: CacheKey, entry: CacheEntry) -> bool:
        """Set cache entry."""
        with self._lock if self._lock else self._no_op():
            key_str = str(key)
            
            # Check if we need to evict entries
            self._ensure_capacity()
            
            # Store entry
            self._cache[key_str] = entry
            
            # Track dependencies
            for dep in entry.dependencies:
                if dep not in self._key_dependencies:
                    self._key_dependencies[dep] = set()
                self._key_dependencies[dep].add(key_str)
                
                if key_str not in self._reverse_dependencies:
                    self._reverse_dependencies[key_str] = set()
                self._reverse_dependencies[key_str].add(dep)
            
            # Periodic cleanup
            current_time = time.time()
            if current_time - self._last_cleanup > self._config.cleanup_interval_seconds:
                self._cleanup_expired()
                self._last_cleanup = current_time
            
            return True
    
    def delete(self, key: CacheKey) -> bool:
        """Delete cache entry."""
        with self._lock if self._lock else self._no_op():
            key_str = str(key)
            
            if key_str in self._cache:
                del self._cache[key_str]
                self._cleanup_dependencies(key_str)
                return True
            
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock if self._lock else self._no_op():
            self._cache.clear()
            self._key_dependencies.clear()
            self._reverse_dependencies.clear()
    
    def keys(self) -> List[CacheKey]:
        """Get all cache keys."""
        with self._lock if self._lock else self._no_op():
            # Reconstruct CacheKey objects from stored keys
            result = []
            for key_str in self._cache.keys():
                # Parse key string back to CacheKey
                # This is a simplified implementation
                parts = key_str.split('|')
                if parts:
                    cache_key = CacheKey(entity_type=parts[0])
                    # Additional parsing would happen here
                    result.append(cache_key)
            
            return result
    
    def size(self) -> int:
        """Get number of cached entries."""
        with self._lock if self._lock else self._no_op():
            return len(self._cache)
    
    def invalidate_dependencies(self, dependency: str) -> Set[str]:
        """Invalidate all entries that depend on the given dependency."""
        with self._lock if self._lock else self._no_op():
            invalidated = set()
            
            if dependency in self._key_dependencies:
                dependent_keys = self._key_dependencies[dependency].copy()
                
                for key_str in dependent_keys:
                    if key_str in self._cache:
                        del self._cache[key_str]
                        invalidated.add(key_str)
                        self._cleanup_dependencies(key_str)
            
            return invalidated
    
    def _ensure_capacity(self) -> None:
        """Ensure cache doesn't exceed capacity limits."""
        # Size-based eviction
        while len(self._cache) >= self._config.max_size:
            self._evict_one()
        
        # Memory-based eviction (simplified)
        estimated_memory_mb = len(self._cache) * 0.001  # Rough estimate
        while estimated_memory_mb > self._config.max_memory_mb:
            self._evict_one()
            estimated_memory_mb = len(self._cache) * 0.001
    
    def _evict_one(self) -> None:
        """Evict one entry based on eviction policy."""
        if not self._cache:
            return
        
        if self._config.eviction_policy == EvictionPolicy.LRU:
            # Remove least recently used (first item)
            key_str = next(iter(self._cache))
        elif self._config.eviction_policy == EvictionPolicy.LFU:
            # Remove least frequently used
            key_str = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count
            )
        elif self._config.eviction_policy == EvictionPolicy.FIFO:
            # Remove first in (oldest)
            key_str = next(iter(self._cache))
        else:
            # Default to LRU
            key_str = next(iter(self._cache))
        
        del self._cache[key_str]
        self._cleanup_dependencies(key_str)
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        current_time = datetime.utcnow()
        expired_keys = []
        
        for key_str, entry in self._cache.items():
            if entry.is_expired:
                expired_keys.append(key_str)
        
        for key_str in expired_keys:
            del self._cache[key_str]
            self._cleanup_dependencies(key_str)
    
    def _cleanup_dependencies(self, key_str: str) -> None:
        """Clean up dependency tracking for a removed key."""
        # Remove from reverse dependencies
        if key_str in self._reverse_dependencies:
            for dep in self._reverse_dependencies[key_str]:
                if dep in self._key_dependencies:
                    self._key_dependencies[dep].discard(key_str)
                    if not self._key_dependencies[dep]:
                        del self._key_dependencies[dep]
            del self._reverse_dependencies[key_str]
    
    def _no_op(self):
        """No-op context manager for non-thread-safe mode."""
        return self
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class CacheManager:
    """
    Main cache manager providing high-level caching operations.
    
    Features:
    - Multi-level caching (memory, persistent)
    - Intelligent invalidation based on dependencies
    - Performance monitoring and statistics
    - Thread-safe operations
    - Automatic cleanup and eviction
    """
    
    def __init__(
        self,
        config: Optional[CacheConfiguration] = None,
        backend: Optional[CacheBackend] = None
    ) -> None:
        self._config = config or CacheConfiguration()
        self._backend = backend or MemoryCache(self._config)
        self._statistics = CacheStatistics() if self._config.enable_statistics else None
        self._invalidation_callbacks: List[Callable[[CacheKey], None]] = []
        self._lock = threading.RLock() if self._config.thread_safe else None
    
    @property
    def statistics(self) -> Optional[CacheStatistics]:
        """Get cache statistics."""
        return self._statistics
    
    @property
    def size(self) -> int:
        """Get number of cached entries."""
        return self._backend.size()
    
    def get(self, key: CacheKey) -> Optional[Any]:
        """Get cached value by key."""
        with self._lock if self._lock else self._no_op():
            try:
                entry = self._backend.get(key)
                
                if entry is not None:
                    if self._statistics:
                        self._statistics.record_hit()
                    
                    logger.debug(f"Cache hit: {key}")
                    return entry.data
                else:
                    if self._statistics:
                        self._statistics.record_miss()
                    
                    logger.debug(f"Cache miss: {key}")
                    return None
                    
            except Exception as e:
                logger.error(f"Cache get error for key {key}: {e}")
                if self._statistics:
                    self._statistics.record_miss()
                return None
    
    def set(
        self,
        key: CacheKey,
        value: Any,
        *,
        ttl_seconds: Optional[int] = None,
        dependencies: Optional[Set[str]] = None
    ) -> bool:
        """Set cached value with optional TTL and dependencies."""
        with self._lock if self._lock else self._no_op():
            try:
                # Create cache entry
                entry = CacheEntry(
                    key=key,
                    data=value,
                    ttl_seconds=ttl_seconds or self._config.default_ttl_seconds,
                    dependencies=dependencies or set()
                )
                
                # Store in backend
                success = self._backend.set(key, entry)
                
                if success:
                    logger.debug(f"Cache set: {key}")
                else:
                    logger.warning(f"Cache set failed: {key}")
                
                return success
                
            except Exception as e:
                logger.error(f"Cache set error for key {key}: {e}")
                return False
    
    def delete(self, key: CacheKey) -> bool:
        """Delete cached value by key."""
        with self._lock if self._lock else self._no_op():
            try:
                success = self._backend.delete(key)
                
                if success:
                    if self._statistics:
                        self._statistics.record_invalidation()
                    
                    # Notify callbacks
                    for callback in self._invalidation_callbacks:
                        try:
                            callback(key)
                        except Exception as e:
                            logger.warning(f"Invalidation callback error: {e}")
                    
                    logger.debug(f"Cache delete: {key}")
                
                return success
                
            except Exception as e:
                logger.error(f"Cache delete error for key {key}: {e}")
                return False
    
    def invalidate(self, key: CacheKey) -> bool:
        """Invalidate cached value (alias for delete)."""
        return self.delete(key)
    
    def invalidate_by_dependency(self, dependency: str) -> int:
        """Invalidate all cached values that depend on the given dependency."""
        with self._lock if self._lock else self._no_op():
            try:
                if isinstance(self._backend, MemoryCache):
                    invalidated_keys = self._backend.invalidate_dependencies(dependency)
                    
                    if self._statistics:
                        for _ in invalidated_keys:
                            self._statistics.record_invalidation()
                    
                    # Notify callbacks
                    for key_str in invalidated_keys:
                        # Reconstruct CacheKey for callback
                        cache_key = CacheKey(entity_type=key_str.split('|')[0])
                        for callback in self._invalidation_callbacks:
                            try:
                                callback(cache_key)
                            except Exception as e:
                                logger.warning(f"Invalidation callback error: {e}")
                    
                    logger.debug(f"Invalidated {len(invalidated_keys)} entries for dependency: {dependency}")
                    return len(invalidated_keys)
                
                return 0
                
            except Exception as e:
                logger.error(f"Cache invalidate by dependency error for {dependency}: {e}")
                return 0
    
    def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate cached values matching a pattern."""
        with self._lock if self._lock else self._no_op():
            try:
                keys_to_delete = []
                
                for key in self._backend.keys():
                    if pattern in str(key):
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    self.delete(key)
                
                logger.debug(f"Invalidated {len(keys_to_delete)} entries matching pattern: {pattern}")
                return len(keys_to_delete)
                
            except Exception as e:
                logger.error(f"Cache invalidate by pattern error for {pattern}: {e}")
                return 0
    
    def clear(self) -> None:
        """Clear all cached values."""
        with self._lock if self._lock else self._no_op():
            try:
                self._backend.clear()
                
                if self._statistics:
                    self._statistics.reset()
                
                logger.info("Cache cleared")
                
            except Exception as e:
                logger.error(f"Cache clear error: {e}")
    
    def contains(self, key: CacheKey) -> bool:
        """Check if key exists in cache."""
        return self.get(key) is not None
    
    def keys(self) -> List[CacheKey]:
        """Get all cache keys."""
        with self._lock if self._lock else self._no_op():
            return self._backend.keys()
    
    def add_invalidation_callback(self, callback: Callable[[CacheKey], None]) -> None:
        """Add callback to be called when entries are invalidated."""
        self._invalidation_callbacks.append(callback)
    
    def remove_invalidation_callback(self, callback: Callable[[CacheKey], None]) -> None:
        """Remove invalidation callback."""
        if callback in self._invalidation_callbacks:
            self._invalidation_callbacks.remove(callback)
    
    def get_memory_usage_estimate(self) -> int:
        """Get estimated memory usage in bytes."""
        # This is a simplified implementation
        # In practice, you'd want more accurate memory measurement
        return self.size * 1000  # Rough estimate
    
    def _no_op(self):
        """No-op context manager for non-thread-safe mode."""
        return self
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Utility functions for common cache operations

def create_entity_cache_key(entity_type: str, entity_id: ElementId) -> CacheKey:
    """Create cache key for an entity."""
    return CacheKey(
        entity_type=entity_type,
        entity_id=entity_id
    )


def create_query_cache_key(entity_type: str, query_hash: str) -> CacheKey:
    """Create cache key for a query result."""
    return CacheKey(
        entity_type=entity_type,
        query_hash=query_hash
    )


def create_relationship_cache_key(
    entity_type: str,
    entity_id: ElementId,
    relationship_path: str
) -> CacheKey:
    """Create cache key for a relationship."""
    return CacheKey(
        entity_type=entity_type,
        entity_id=entity_id,
        relationship_path=relationship_path
    )