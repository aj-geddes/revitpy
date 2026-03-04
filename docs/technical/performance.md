---
layout: page
title: Performance
description: RevitPy performance infrastructure covering optimization strategies, adaptive caching, memory management, benchmark framework, and thread safety patterns.
doc_tier: technical
---

# Performance

This document covers RevitPy's performance infrastructure: targets, optimisation strategies, the adaptive caching layer, memory management, the benchmark framework, and thread safety patterns.

The primary source files are `revitpy/performance/optimizer.py` and `revitpy/performance/benchmarks.py`.

## Performance Targets

Default performance targets are defined in `BenchmarkConfiguration.performance_targets` (in `benchmarks.py`):

| Metric | Target | Unit |
|---|---|---|
| `startup_time_ms` | 1,000 | milliseconds |
| `api_latency_simple_ms` | 1 | milliseconds |
| `api_latency_complex_ms` | 100 | milliseconds |
| `memory_idle_mb` | 50 | megabytes |
| `memory_peak_mb` | 500 | megabytes |
| `cache_hit_ratio` | 0.85 | ratio (0--1) |
| `throughput_ops_per_sec` | 10,000 | operations/second |

These targets can be overridden via `BenchmarkConfiguration` at suite creation time and are validated automatically when the benchmark suite runs with `strict_target_validation` enabled.

## Optimization Strategies

### PerformanceOptimizer

`PerformanceOptimizer` (in `optimizer.py`) is the central optimization coordinator. It provides:

1. **Adaptive caching** with intelligent eviction and size management.
2. **Object pooling** for frequently created/destroyed types.
3. **Batch operation execution** (both sync and async).
4. **Memory monitoring and cleanup**.
5. **Automatic performance tuning** based on runtime metrics.
6. **Operation profiling** with cProfile and tracemalloc integration.

### OptimizationConfig

| Parameter | Default | Description |
|---|---|---|
| `cache_max_size` | 10,000 | Maximum cache entries |
| `cache_max_memory_mb` | 100 | Maximum cache memory |
| `cache_ttl_seconds` | 3,600 | Cache time-to-live |
| `enable_adaptive_caching` | `True` | Auto-adjust cache size |
| `pool_max_size` | 1,000 | Maximum pool size per type |
| `pool_cleanup_interval_seconds` | 300 | Pool cleanup interval |
| `enable_object_pooling` | `True` | Enable object pools |
| `max_worker_threads` | `cpu_count * 2` | Thread pool size (capped at 32) |
| `batch_size_default` | 100 | Default batch size |
| `enable_async_optimization` | `True` | Enable async support |
| `memory_monitoring_enabled` | `True` | Start tracemalloc |
| `memory_cleanup_threshold_mb` | 400 | Trigger GC above this |
| `gc_optimization_enabled` | `True` | Tune GC thresholds |
| `enable_profiling` | `True` | Enable cProfile integration |
| `enable_metrics_collection` | `True` | Collect metrics |
| `metrics_collection_interval_seconds` | 30 | Metrics sampling interval |
| `benchmark_warmup_iterations` | 10 | Warmup runs before benchmark |
| `benchmark_test_iterations` | 100 | Measured benchmark iterations |

### Auto-Optimization

The `auto_optimize()` method inspects current metrics and makes adjustments:

1. **Cache size expansion**: If `cache_hit_ratio < 0.7` and memory usage is below 80% of `memory_cleanup_threshold_mb`, the cache size is doubled (up to `MAX_ADAPTIVE_CACHE_SIZE` = 50,000).
2. **Pool size expansion**: If `pool_hit_ratio < 0.8`, pool sizes are doubled (up to `MAX_ADAPTIVE_POOL_SIZE` = 2,000).
3. **Memory cleanup**: If memory usage exceeds `memory_cleanup_threshold_mb`, triggers `optimize_memory()`.
4. **GC tuning**: Sets garbage collector thresholds to `(700, 10, 10)` for more aggressive collection.

## Caching Architecture

RevitPy has two independent caching layers that serve different purposes.

### ORM Cache (revitpy/orm/cache.py)

Used by `RevitContext`, `QueryBuilder`, and `RelationshipManager`. See the [Data Model](data-model.md#cache-system) document for full details.

Key characteristics:
- **Backend**: `MemoryCache` using `OrderedDict` for LRU ordering.
- **Eviction policies**: LRU, LFU, FIFO, TTL, SIZE_BASED.
- **Dependency tracking**: Bidirectional index for cascade invalidation.
- **Thread safety**: Optional `RLock` per backend and per `CacheManager`.
- **Statistics**: Hit/miss/eviction/invalidation counters with `RLock` protection.

Configuration defaults (from `CacheConfiguration`):

| Parameter | Default |
|---|---|
| `max_size` | 10,000 |
| `max_memory_mb` | 500 |
| `default_ttl_seconds` | 3,600 |
| `eviction_policy` | LRU |
| `cleanup_interval_seconds` | 300 |

### Performance Cache (revitpy/performance/optimizer.py)

The `AdaptiveCache` is a standalone cache used by `PerformanceOptimizer` for caching arbitrary operation results:

- Uses a plain `dict` with separate `_access_times`, `_creation_times`, and `_access_counts` dictionaries.
- LRU tracking via a `deque` for access order.
- TTL-based expiration checked on every `get()`.
- Memory-aware eviction: tracks estimated memory usage per entry and evicts when exceeding `max_memory_bytes`.
- Size estimation logic: strings are measured by UTF-8 byte length; lists/dicts recurse; numpy arrays use `nbytes`; other objects default to `DEFAULT_ESTIMATED_OBJECT_SIZE` (64 bytes).

### Caching Decorator

`PerformanceOptimizer.cached_operation()` provides a decorator for caching function results:

```python
optimizer = PerformanceOptimizer()

@optimizer.cached_operation(cache_key="my_operation", ttl_seconds=600)
def expensive_operation():
    ...
```

The cache key defaults to `f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"` when not explicitly provided.

## Memory Management

### Active Monitoring

When `memory_monitoring_enabled` is `True`:

1. `tracemalloc.start()` is called at optimizer initialization.
2. A background daemon thread samples memory snapshots every `metrics_collection_interval_seconds` (default 30s).
3. If memory exceeds `memory_cleanup_threshold_mb * 0.9` (`MEMORY_WARNING_FACTOR`), a warning is logged and `optimize_memory()` is triggered.

### Memory Cleanup

`optimize_memory()` performs:

1. Evicts expired cache entries by scanning `_creation_times` against the configured TTL.
2. Checks process memory via `psutil.Process().memory_info().rss`.
3. If memory exceeds `memory_cleanup_threshold_mb`, triggers `gc.collect()`.
4. Records a memory snapshot including top 10 tracemalloc allocations.

### Memory Snapshots

The optimizer maintains a rotating buffer of up to 1,000 memory snapshots (`deque(maxlen=1000)`), each containing:

```python
{
    "timestamp": float,
    "memory_mb": float,
    "cache_size": int,
    "pool_count": int,
    "top_allocations": list[str],  # From tracemalloc, if active
}
```

### Object Pooling

`ObjectPool[T]` provides thread-safe object reuse:

- Backed by `queue.Queue(maxsize=max_size)`.
- `get()` returns an object from the pool or creates one via the factory.
- `return_object(obj)` resets the object (via `reset_func`) and returns it to the pool.
- Statistics: `created_count`, `borrowed_count`, `returned_count`, `utilization`.

Usage via context manager:

```python
with optimizer.pooled_object(MyType, factory=MyType, reset_func=reset_my_type) as obj:
    obj.do_work()
# Object is automatically returned to the pool
```

## Benchmark Framework

### BenchmarkSuite

`BenchmarkSuite` (in `benchmarks.py`) orchestrates performance testing:

```python
suite = BenchmarkSuite(BenchmarkConfiguration(
    parallel_execution=True,
    max_workers=4,
    enable_memory_tracking=True,
    enable_memory_leak_detection=True,
    enable_regression_detection=True,
))

results = suite.run_all_benchmarks()
```

### BenchmarkConfiguration

| Parameter | Default | Description |
|---|---|---|
| `parallel_execution` | `True` | Run benchmarks in parallel |
| `max_workers` | 4 | Thread pool size for parallel runs |
| `timeout_seconds` | 300 | Total suite timeout |
| `enable_memory_tracking` | `True` | Use tracemalloc |
| `enable_memory_leak_detection` | `True` | Detect memory leaks |
| `memory_leak_threshold_mb` | 10.0 | Leak detection threshold |
| `enable_regression_detection` | `True` | Compare against baselines |
| `regression_threshold_percent` | 20.0 | Regression alert threshold |
| `baseline_file` | `None` | Path to baseline JSON |
| `save_results` | `True` | Save results to disk |
| `results_directory` | `"benchmark_results"` | Output directory |
| `strict_target_validation` | `False` | Fail suite on target miss |

### PerformanceBenchmark

Individual benchmarks are defined as `PerformanceBenchmark` dataclasses:

```python
@dataclass
class PerformanceBenchmark:
    name: str
    target_latency_ms: float
    target_memory_mb: float
    target_throughput_ops_sec: float
    operation: Callable
    setup: Callable | None = None
    teardown: Callable | None = None
    iterations: int = 100
    warmup_iterations: int = 10
    timeout_seconds: float = 30.0
    validate_result: Callable | None = None
```

### BenchmarkResult

Results are returned as named tuples:

```python
BenchmarkResult = namedtuple("BenchmarkResult", [
    "name", "success", "latency_ms", "memory_mb",
    "throughput_ops_sec", "error", "details"
])
```

### Built-in Analyses

The suite includes several automated analyses:

**Regression Detection**: Compares current results against a stored baseline. Thresholds from constants:
- Changes above `HIGH_REGRESSION_SEVERITY_PERCENT` (50%) are flagged as "high" severity.
- Improvements above `IMPROVEMENT_THRESHOLD_PERCENT` (10%) are noted as positive.

**Memory Leak Detection**: Monitors memory growth across iterations. If more than `MEMORY_LEAK_GROWTH_RATIO` (70%) of measurements show growth, a potential leak is flagged. Forced GC runs every `GC_TRIGGER_INTERVAL` (50) operations.

**Scalability Analysis** (when numpy is available): Performs linear regression on element count vs. latency. If R-squared exceeds `LINEAR_SCALING_R_SQUARED_THRESHOLD` (0.8) and slope is below `MAX_LATENCY_SLOPE_PER_ELEMENT` (0.1 ms/element), scaling is assessed as "linear." Without numpy, a simpler ratio-based check flags scaling issues when the average factor exceeds `MAX_SCALING_FACTOR_THRESHOLD` (2.0).

### Profiling Integration

`PerformanceOptimizer.profile_operation()` wraps any callable with:

1. `cProfile.Profile` for call-level timing.
2. `tracemalloc` snapshots before/after for memory delta analysis.
3. Returns detailed profile data including top 20 functions by cumulative time and top 10 memory allocations by line.

### Latency Tracking

Operation latencies are tracked in `_metrics["operation_latencies"]`, a `defaultdict(list)` keyed by operation name. To prevent unbounded growth, latency lists are trimmed to `LATENCY_HISTORY_TRIM_SIZE` (500) when they exceed `MAX_LATENCY_HISTORY_SIZE` (1,000).

Percentile calculations (p50, p95, p99) are computed from sorted latency arrays in `get_performance_metrics()`.

## Thread Safety Patterns

### RLock Usage

The codebase uses `threading.RLock` (reentrant lock) throughout, allowing the same thread to acquire the lock multiple times without deadlock. The pattern is consistent across modules:

```python
# Constructor
self._lock = threading.RLock() if thread_safe else None

# Usage
with self._lock if self._lock else self._no_op():
    # Critical section
```

The `_no_op()` method returns a context manager that does nothing, avoiding lock overhead in single-threaded mode.

### Where RLock is Used

| Component | Location | Protection Scope |
|---|---|---|
| `RevitContext` | `orm/context.py` | Entity set cache, query operations |
| `ChangeTracker` | `orm/change_tracker.py` | All entity state mutations |
| `CacheManager` | `orm/cache.py` | All cache read/write operations |
| `CacheStatistics` | `orm/cache.py` | Hit/miss/eviction counters |
| `MemoryCache` | `orm/cache.py` | OrderedDict and dependency maps |
| `AdaptiveCache` | `performance/optimizer.py` | Cache dict and access tracking |
| `ObjectPool` | `performance/optimizer.py` | Pool statistics counters |
| `PerformanceOptimizer` | `performance/optimizer.py` | Metrics dictionaries |
| `EventDispatcher` | `events/dispatcher.py` | Event queue (uses `RLock`) |
| `EventManager` | `events/manager.py` | Singleton creation (class-level `Lock`) |

### Background Threads

The `PerformanceOptimizer` spawns two daemon threads:

1. **Cleanup thread**: Runs `optimize_memory()` every `pool_cleanup_interval_seconds` (default 300s).
2. **Monitoring thread**: Records memory snapshots and triggers auto-optimization every `metrics_collection_interval_seconds` (default 30s).

Both threads check `self._running` before each iteration and are joined with a 5-second timeout during `cleanup()`.

The `EventDispatcher` spawns a daemon thread for background event processing, using `threading.Event` for shutdown signaling.

### Thread Pool

`PerformanceOptimizer` maintains a `ThreadPoolExecutor` with `max_worker_threads` workers (default: `min(32, cpu_count * 2)`). This pool is used for:

- `execute_batch_sync()`: Submits batch operations to the pool, collecting results via `concurrent.futures.as_completed()`.
- `execute_batch_async()`: Runs synchronous operations in the pool from async code via `loop.run_in_executor()`.

The pool is shut down with `wait=True` during `cleanup()`.
