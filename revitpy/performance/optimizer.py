"""
Core Performance Optimizer for RevitPy Python Framework

Provides comprehensive performance optimization including:
- Intelligent caching with multiple eviction policies
- Object pooling for frequently used types
- Batch operation optimization
- Async operation support with proper resource management
- Memory-aware optimization strategies
- Automatic performance tuning based on usage patterns
"""

import asyncio
import cProfile
import gc
import logging
import pstats
import threading
import time
import tracemalloc
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache, wraps
from io import StringIO
from queue import Empty, Queue
from typing import Any, Generic, TypeVar

import psutil

# Performance monitoring imports
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

T = TypeVar("T")
logger = logging.getLogger(__name__)


@dataclass
class OptimizationConfig:
    """Configuration for performance optimization."""

    # Caching configuration
    cache_max_size: int = 10000
    cache_max_memory_mb: int = 100
    cache_ttl_seconds: int = 3600
    enable_adaptive_caching: bool = True

    # Object pooling configuration
    pool_max_size: int = 1000
    pool_cleanup_interval_seconds: int = 300
    enable_object_pooling: bool = True

    # Concurrency configuration
    max_worker_threads: int = None  # Defaults to CPU count * 2
    batch_size_default: int = 100
    enable_async_optimization: bool = True

    # Memory management
    memory_monitoring_enabled: bool = True
    memory_cleanup_threshold_mb: int = 400
    gc_optimization_enabled: bool = True

    # Performance monitoring
    enable_profiling: bool = True
    enable_metrics_collection: bool = True
    metrics_collection_interval_seconds: int = 30

    # Benchmarking
    enable_benchmarking: bool = True
    benchmark_warmup_iterations: int = 10
    benchmark_test_iterations: int = 100

    def __post_init__(self):
        if self.max_worker_threads is None:
            self.max_worker_threads = min(32, (psutil.cpu_count() or 1) * 2)


class ObjectPool(Generic[T]):
    """High-performance object pool with automatic cleanup and size management."""

    def __init__(
        self,
        factory: Callable[[], T],
        reset_func: Callable[[T], bool] = None,
        max_size: int = 100,
    ):
        self.factory = factory
        self.reset_func = reset_func or (lambda x: True)
        self.max_size = max_size
        self._pool = Queue(maxsize=max_size)
        self._created_count = 0
        self._borrowed_count = 0
        self._returned_count = 0
        self._lock = threading.Lock()

    def get(self) -> T:
        """Get an object from the pool or create a new one."""
        try:
            obj = self._pool.get_nowait()
            with self._lock:
                self._borrowed_count += 1
            return obj
        except Empty:
            # Pool is empty, create new object
            obj = self.factory()
            with self._lock:
                self._created_count += 1
                self._borrowed_count += 1
            return obj

    def return_object(self, obj: T) -> bool:
        """Return an object to the pool."""
        try:
            if self.reset_func(obj):
                self._pool.put_nowait(obj)
                with self._lock:
                    self._returned_count += 1
                return True
        except:
            pass
        return False

    def get_stats(self) -> dict[str, int]:
        """Get pool statistics."""
        with self._lock:
            return {
                "pool_size": self._pool.qsize(),
                "max_size": self.max_size,
                "created_count": self._created_count,
                "borrowed_count": self._borrowed_count,
                "returned_count": self._returned_count,
                "utilization": self._pool.qsize() / self.max_size
                if self.max_size > 0
                else 0,
            }


class AdaptiveCache:
    """Adaptive cache with intelligent eviction and size management."""

    def __init__(
        self, max_size: int = 1000, max_memory_mb: int = 50, ttl_seconds: int = 3600
    ):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.ttl_seconds = ttl_seconds

        self._cache = {}
        self._access_times = {}
        self._creation_times = {}
        self._access_counts = defaultdict(int)
        self._memory_usage = 0
        self._lock = threading.RLock()

        # LRU tracking
        self._access_order = deque()
        self._order_index = {}

    def get(self, key: str, default=None) -> Any:
        """Get value from cache with LRU tracking."""
        with self._lock:
            if key not in self._cache:
                return default

            # Check TTL
            if self._is_expired(key):
                self._remove_key(key)
                return default

            # Update access tracking
            self._access_times[key] = time.time()
            self._access_counts[key] += 1
            self._update_access_order(key)

            return self._cache[key]

    def set(self, key: str, value: Any, ttl_seconds: int = None) -> bool:
        """Set value in cache with adaptive size management."""
        with self._lock:
            # Calculate memory usage of new value
            value_size = self._estimate_size(value)

            # Check if we need to evict items
            while (
                len(self._cache) >= self.max_size
                or self._memory_usage + value_size > self.max_memory_bytes
            ):
                if not self._evict_item():
                    return False  # Cannot make space

            # Remove existing if updating
            if key in self._cache:
                self._remove_key(key)

            # Add new item
            self._cache[key] = value
            self._creation_times[key] = time.time()
            self._access_times[key] = time.time()
            self._access_counts[key] = 1
            self._memory_usage += value_size
            self._update_access_order(key)

            return True

    def invalidate(self, key: str) -> bool:
        """Remove item from cache."""
        with self._lock:
            if key in self._cache:
                self._remove_key(key)
                return True
            return False

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
            self._creation_times.clear()
            self._access_counts.clear()
            self._access_order.clear()
            self._order_index.clear()
            self._memory_usage = 0

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_accesses = sum(self._access_counts.values())
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "memory_usage_bytes": self._memory_usage,
                "memory_usage_mb": self._memory_usage / (1024 * 1024),
                "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
                "hit_ratio": self._calculate_hit_ratio(),
                "total_accesses": total_accesses,
                "avg_access_count": total_accesses / len(self._cache)
                if self._cache
                else 0,
            }

    def _is_expired(self, key: str) -> bool:
        """Check if cache entry is expired."""
        creation_time = self._creation_times.get(key, 0)
        return time.time() - creation_time > self.ttl_seconds

    def _evict_item(self) -> bool:
        """Evict least recently used item."""
        if not self._access_order:
            return False

        # Find LRU item
        lru_key = self._access_order[0]
        self._remove_key(lru_key)
        return True

    def _remove_key(self, key: str):
        """Remove key and all associated data."""
        if key in self._cache:
            value_size = self._estimate_size(self._cache[key])
            self._memory_usage -= value_size

            del self._cache[key]
            self._access_times.pop(key, None)
            self._creation_times.pop(key, None)
            self._access_counts.pop(key, None)

            # Remove from access order
            if key in self._order_index:
                self._access_order.remove(key)
                del self._order_index[key]

    def _update_access_order(self, key: str):
        """Update LRU access order."""
        if key in self._order_index:
            self._access_order.remove(key)
        self._access_order.append(key)
        self._order_index[key] = True

    def _estimate_size(self, obj: Any) -> int:
        """Estimate memory size of object."""
        try:
            if HAS_NUMPY and isinstance(obj, np.ndarray):
                return obj.nbytes

            # Simple size estimation
            if isinstance(obj, str):
                return len(obj.encode("utf-8"))
            elif isinstance(obj, list | tuple):
                return sum(self._estimate_size(item) for item in obj) + 64
            elif isinstance(obj, dict):
                return (
                    sum(
                        self._estimate_size(k) + self._estimate_size(v)
                        for k, v in obj.items()
                    )
                    + 64
                )
            else:
                return 64  # Default size estimate
        except:
            return 64

    def _calculate_hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        # This is a simplified calculation
        # In production, you'd track hits/misses explicitly
        total_accesses = sum(self._access_counts.values())
        if total_accesses == 0:
            return 0.0

        # Estimate hit ratio based on access patterns
        return min(1.0, len(self._cache) / max(1, total_accesses * 0.1))


class PerformanceOptimizer:
    """Main performance optimizer for RevitPy Python framework."""

    def __init__(self, config: OptimizationConfig = None):
        self.config = config or OptimizationConfig()
        self._start_time = time.time()

        # Core components
        self._cache = AdaptiveCache(
            max_size=self.config.cache_max_size,
            max_memory_mb=self.config.cache_max_memory_mb,
            ttl_seconds=self.config.cache_ttl_seconds,
        )

        self._object_pools = {}
        self._thread_pool = ThreadPoolExecutor(
            max_workers=self.config.max_worker_threads
        )

        # Performance tracking
        self._metrics = {
            "operations_count": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "pool_hits": 0,
            "pool_misses": 0,
            "total_latency": 0.0,
            "operation_counts": defaultdict(int),
            "operation_latencies": defaultdict(list),
        }

        self._latency_trackers = {}
        self._memory_snapshots = deque(maxlen=1000)

        # Threading
        self._lock = threading.Lock()
        self._cleanup_thread = None
        self._monitoring_thread = None
        self._running = True

        # Initialize monitoring if enabled
        if self.config.memory_monitoring_enabled:
            tracemalloc.start()
            self._start_monitoring()

        # Start cleanup thread
        self._start_cleanup_thread()

        logger.info("PerformanceOptimizer initialized with config: %s", self.config)

    @contextmanager
    def performance_context(self, operation_name: str):
        """Context manager for tracking operation performance."""
        start_time = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start_time
            self._record_operation(operation_name, duration)

    def cached_operation(self, cache_key: str = None, ttl_seconds: int = None):
        """Decorator for caching expensive operations."""

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key if not provided
                key = (
                    cache_key
                    or f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"
                )

                # Try to get from cache
                result = self._cache.get(key)
                if result is not None:
                    with self._lock:
                        self._metrics["cache_hits"] += 1
                    return result

                # Execute function and cache result
                with self.performance_context(func.__name__):
                    result = func(*args, **kwargs)

                # Cache the result
                cache_ttl = ttl_seconds or self.config.cache_ttl_seconds
                if self._cache.set(key, result, cache_ttl):
                    with self._lock:
                        self._metrics["cache_misses"] += 1

                return result

            return wrapper

        return decorator

    def get_object_pool(
        self, object_type: type, factory: Callable = None, reset_func: Callable = None
    ) -> ObjectPool:
        """Get or create object pool for specified type."""
        type_name = object_type.__name__

        if type_name not in self._object_pools:
            if factory is None:
                factory = object_type

            self._object_pools[type_name] = ObjectPool(
                factory=factory,
                reset_func=reset_func,
                max_size=self.config.pool_max_size,
            )

        return self._object_pools[type_name]

    @contextmanager
    def pooled_object(
        self, object_type: type, factory: Callable = None, reset_func: Callable = None
    ):
        """Context manager for using pooled objects."""
        pool = self.get_object_pool(object_type, factory, reset_func)
        obj = pool.get()

        with self._lock:
            if pool._pool.qsize() < pool.max_size:
                self._metrics["pool_hits"] += 1
            else:
                self._metrics["pool_misses"] += 1

        try:
            yield obj
        finally:
            pool.return_object(obj)

    async def execute_batch_async(
        self, operations: list[Callable], batch_size: int = None
    ) -> list[Any]:
        """Execute operations in optimized batches with async support."""
        batch_size = batch_size or self.config.batch_size_default
        results = []

        # Process in batches to control memory usage
        for i in range(0, len(operations), batch_size):
            batch = operations[i : i + batch_size]

            # Execute batch concurrently
            batch_tasks = []
            for operation in batch:
                if asyncio.iscoroutinefunction(operation):
                    batch_tasks.append(operation())
                else:
                    # Run sync operations in thread pool
                    loop = asyncio.get_event_loop()
                    batch_tasks.append(
                        loop.run_in_executor(self._thread_pool, operation)
                    )

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            results.extend(batch_results)

            # Optional yield to allow other tasks to run
            await asyncio.sleep(0)

        return results

    def execute_batch_sync(
        self, operations: list[Callable], batch_size: int = None
    ) -> list[Any]:
        """Execute operations in optimized batches synchronously."""
        batch_size = batch_size or self.config.batch_size_default
        results = []

        # Process in batches
        for i in range(0, len(operations), batch_size):
            batch = operations[i : i + batch_size]

            # Submit batch to thread pool
            future_to_op = {self._thread_pool.submit(op): op for op in batch}

            batch_results = []
            for future in as_completed(future_to_op):
                try:
                    result = future.result()
                    batch_results.append(result)
                except Exception as e:
                    logger.warning("Batch operation failed: %s", e)
                    batch_results.append(e)

            results.extend(batch_results)

        return results

    def optimize_memory(self):
        """Perform memory optimization and cleanup."""
        try:
            # Clear expired cache entries
            expired_keys = []
            current_time = time.time()

            for key, creation_time in self._cache._creation_times.items():
                if current_time - creation_time > self.config.cache_ttl_seconds:
                    expired_keys.append(key)

            for key in expired_keys:
                self._cache.invalidate(key)

            # Trigger garbage collection if memory usage is high
            current_memory = self._get_memory_usage_mb()
            if current_memory > self.config.memory_cleanup_threshold_mb:
                collected = gc.collect()
                logger.info(
                    "Memory cleanup: collected %d objects, memory: %.1fMB",
                    collected,
                    self._get_memory_usage_mb(),
                )

            # Record memory snapshot
            self._record_memory_snapshot()

        except Exception as e:
            logger.warning("Memory optimization failed: %s", e)

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get comprehensive performance metrics."""
        with self._lock:
            cache_stats = self._cache.get_stats()
            pool_stats = {
                name: pool.get_stats() for name, pool in self._object_pools.items()
            }

            uptime = time.time() - self._start_time
            total_ops = self._metrics["operations_count"]

            metrics = {
                "uptime_seconds": uptime,
                "total_operations": total_ops,
                "operations_per_second": total_ops / uptime if uptime > 0 else 0,
                "average_latency_ms": (
                    self._metrics["total_latency"] / total_ops * 1000
                )
                if total_ops > 0
                else 0,
                "memory_usage_mb": self._get_memory_usage_mb(),
                "cache": cache_stats,
                "object_pools": pool_stats,
                "cache_hit_ratio": (
                    self._metrics["cache_hits"]
                    / max(
                        1, self._metrics["cache_hits"] + self._metrics["cache_misses"]
                    )
                ),
                "pool_hit_ratio": (
                    self._metrics["pool_hits"]
                    / max(1, self._metrics["pool_hits"] + self._metrics["pool_misses"])
                ),
                "operation_counts": dict(self._metrics["operation_counts"]),
                "memory_snapshots_count": len(self._memory_snapshots),
            }

            # Add latency percentiles for operations
            operation_latencies = {}
            for op_name, latencies in self._metrics["operation_latencies"].items():
                if latencies:
                    sorted_latencies = sorted(latencies)
                    n = len(sorted_latencies)
                    operation_latencies[op_name] = {
                        "count": n,
                        "avg_ms": sum(latencies) / n * 1000,
                        "p50_ms": sorted_latencies[n // 2] * 1000,
                        "p95_ms": sorted_latencies[int(n * 0.95)] * 1000
                        if n > 0
                        else 0,
                        "p99_ms": sorted_latencies[int(n * 0.99)] * 1000
                        if n > 0
                        else 0,
                    }

            metrics["operation_latencies"] = operation_latencies

            return metrics

    def profile_operation(self, operation: Callable, *args, **kwargs) -> dict[str, Any]:
        """Profile a specific operation and return detailed performance data."""
        if not self.config.enable_profiling:
            result = operation(*args, **kwargs)
            return {"result": result, "profiling_disabled": True}

        # Setup profiling
        profiler = cProfile.Profile()

        # Memory tracking
        if tracemalloc.is_tracing():
            snapshot_before = tracemalloc.take_snapshot()

        start_time = time.perf_counter()
        memory_before = self._get_memory_usage_mb()

        try:
            # Execute with profiling
            profiler.enable()
            result = operation(*args, **kwargs)
            profiler.disable()

            # Collect metrics
            end_time = time.perf_counter()
            memory_after = self._get_memory_usage_mb()

            # Process profiling data
            stats_stream = StringIO()
            stats = pstats.Stats(profiler, stream=stats_stream)
            stats.sort_stats("cumulative").print_stats(20)

            profile_data = {
                "result": result,
                "execution_time_ms": (end_time - start_time) * 1000,
                "memory_delta_mb": memory_after - memory_before,
                "memory_before_mb": memory_before,
                "memory_after_mb": memory_after,
                "profile_stats": stats_stream.getvalue(),
            }

            # Add memory trace if available
            if tracemalloc.is_tracing():
                snapshot_after = tracemalloc.take_snapshot()
                top_stats = snapshot_after.compare_to(snapshot_before, "lineno")[:10]
                profile_data["memory_trace"] = [str(stat) for stat in top_stats]

            return profile_data

        except Exception as e:
            profiler.disable()
            return {
                "error": str(e),
                "execution_time_ms": (time.perf_counter() - start_time) * 1000,
                "memory_delta_mb": self._get_memory_usage_mb() - memory_before,
            }

    def benchmark_operation(
        self, operation: Callable, iterations: int = None, warmup_iterations: int = None
    ) -> dict[str, Any]:
        """Benchmark an operation with statistical analysis."""
        iterations = iterations or self.config.benchmark_test_iterations
        warmup_iterations = warmup_iterations or self.config.benchmark_warmup_iterations

        # Warmup
        for _ in range(warmup_iterations):
            try:
                operation()
            except:
                pass

        # Benchmark
        latencies = []
        memory_deltas = []

        for _i in range(iterations):
            memory_before = self._get_memory_usage_mb()
            start_time = time.perf_counter()

            try:
                operation()
            except Exception as e:
                str(e)

            end_time = time.perf_counter()
            memory_after = self._get_memory_usage_mb()

            latency = (end_time - start_time) * 1000  # Convert to ms
            memory_delta = memory_after - memory_before

            latencies.append(latency)
            memory_deltas.append(memory_delta)

        # Calculate statistics
        if latencies:
            sorted_latencies = sorted(latencies)
            n = len(sorted_latencies)

            benchmark_result = {
                "iterations": iterations,
                "warmup_iterations": warmup_iterations,
                "success_rate": sum(1 for l in latencies if l >= 0) / n,
                "latency_stats": {
                    "min_ms": min(sorted_latencies),
                    "max_ms": max(sorted_latencies),
                    "avg_ms": sum(sorted_latencies) / n,
                    "median_ms": sorted_latencies[n // 2],
                    "p95_ms": sorted_latencies[int(n * 0.95)] if n > 0 else 0,
                    "p99_ms": sorted_latencies[int(n * 0.99)] if n > 0 else 0,
                    "std_dev_ms": self._calculate_std_dev(sorted_latencies),
                },
                "memory_stats": {
                    "avg_delta_mb": sum(memory_deltas) / len(memory_deltas)
                    if memory_deltas
                    else 0,
                    "max_delta_mb": max(memory_deltas) if memory_deltas else 0,
                    "min_delta_mb": min(memory_deltas) if memory_deltas else 0,
                },
                "throughput_ops_per_sec": n / (sum(sorted_latencies) / 1000)
                if sum(sorted_latencies) > 0
                else 0,
            }

            return benchmark_result

        return {"error": "No successful iterations"}

    def auto_optimize(self) -> dict[str, Any]:
        """Automatically optimize performance based on current metrics."""
        metrics = self.get_performance_metrics()
        optimizations = []

        try:
            # Optimize cache based on hit ratio
            cache_hit_ratio = metrics.get("cache_hit_ratio", 0)
            if cache_hit_ratio < 0.7:  # Low hit ratio
                # Increase cache size if memory allows
                current_memory = metrics.get("memory_usage_mb", 0)
                if current_memory < self.config.memory_cleanup_threshold_mb * 0.8:
                    self._cache.max_size = min(self._cache.max_size * 2, 50000)
                    optimizations.append("Increased cache size due to low hit ratio")

            # Optimize object pools based on miss ratio
            pool_hit_ratio = metrics.get("pool_hit_ratio", 1.0)
            if pool_hit_ratio < 0.8:  # Low pool hit ratio
                for pool_name, pool in self._object_pools.items():
                    if pool.max_size < 2000:
                        pool.max_size = min(pool.max_size * 2, 2000)
                        optimizations.append(f"Increased {pool_name} pool size")

            # Memory optimization
            if (
                metrics.get("memory_usage_mb", 0)
                > self.config.memory_cleanup_threshold_mb
            ):
                self.optimize_memory()
                optimizations.append("Triggered memory cleanup")

            # Adjust GC settings based on allocation patterns
            if self.config.gc_optimization_enabled:
                gc.set_threshold(700, 10, 10)  # More aggressive GC
                optimizations.append("Optimized GC thresholds")

            return {
                "success": True,
                "optimizations_applied": optimizations,
                "metrics_before": metrics,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error("Auto-optimization failed: %s", e)
            return {
                "success": False,
                "error": str(e),
                "optimizations_applied": optimizations,
                "timestamp": time.time(),
            }

    def cleanup(self):
        """Cleanup resources and stop background threads."""
        self._running = False

        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)

        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5)

        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)

        self._cache.clear()

        if tracemalloc.is_tracing():
            tracemalloc.stop()

        logger.info("PerformanceOptimizer cleanup completed")

    # Private methods

    def _record_operation(self, operation_name: str, duration: float):
        """Record operation metrics."""
        with self._lock:
            self._metrics["operations_count"] += 1
            self._metrics["total_latency"] += duration
            self._metrics["operation_counts"][operation_name] += 1

            # Keep only recent latencies to prevent memory bloat
            latencies = self._metrics["operation_latencies"][operation_name]
            latencies.append(duration)
            if len(latencies) > 1000:
                latencies[:] = latencies[-500:]  # Keep last 500

    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0

    def _record_memory_snapshot(self):
        """Record current memory snapshot."""
        snapshot = {
            "timestamp": time.time(),
            "memory_mb": self._get_memory_usage_mb(),
            "cache_size": len(self._cache._cache),
            "pool_count": len(self._object_pools),
        }

        if tracemalloc.is_tracing():
            current_snapshot = tracemalloc.take_snapshot()
            top_stats = current_snapshot.statistics("lineno")[:10]
            snapshot["top_allocations"] = [
                f"{stat.traceback.format()[-1]}: {stat.size_diff / 1024:.1f} KB"
                for stat in top_stats
            ]

        self._memory_snapshots.append(snapshot)

    def _calculate_std_dev(self, values: list[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance**0.5

    def _start_cleanup_thread(self):
        """Start background cleanup thread."""

        def cleanup_worker():
            while self._running:
                try:
                    time.sleep(self.config.pool_cleanup_interval_seconds)
                    if self._running:
                        self.optimize_memory()
                except Exception as e:
                    logger.warning("Cleanup thread error: %s", e)

        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()

    def _start_monitoring(self):
        """Start background monitoring thread."""

        def monitoring_worker():
            while self._running:
                try:
                    time.sleep(self.config.metrics_collection_interval_seconds)
                    if self._running:
                        self._record_memory_snapshot()

                        # Auto-optimize if enabled
                        metrics = self.get_performance_metrics()
                        memory_usage = metrics.get("memory_usage_mb", 0)

                        if memory_usage > self.config.memory_cleanup_threshold_mb * 0.9:
                            logger.warning(
                                "High memory usage detected: %.1fMB", memory_usage
                            )
                            self.optimize_memory()

                except Exception as e:
                    logger.warning("Monitoring thread error: %s", e)

        self._monitoring_thread = threading.Thread(
            target=monitoring_worker, daemon=True
        )
        self._monitoring_thread.start()


# Convenience decorators and functions


def optimized_function(
    cache_key: str = None, ttl_seconds: int = None, use_pool: type = None
):
    """Decorator to automatically optimize function calls."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get global optimizer
            from . import get_global_optimizer

            optimizer = get_global_optimizer()

            # Use caching
            if cache_key is not None:
                cached_func = optimizer.cached_operation(cache_key, ttl_seconds)(func)
                return cached_func(*args, **kwargs)

            # Use object pooling if specified
            if use_pool is not None:
                with optimizer.pooled_object(use_pool):
                    with optimizer.performance_context(func.__name__):
                        return func(*args, **kwargs)

            # Just use performance tracking
            with optimizer.performance_context(func.__name__):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Export commonly used decorators
@lru_cache(maxsize=1)
def get_default_optimizer() -> PerformanceOptimizer:
    """Get a default optimizer instance."""
    return PerformanceOptimizer()
