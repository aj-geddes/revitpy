---
layout: api
title: Performance API
description: Performance API reference documentation
---

# Performance API

The Performance module provides comprehensive tools for optimizing, monitoring, and profiling RevitPy applications.

## Overview

The Performance module includes:

- **Performance optimization**: Automatic and manual optimization techniques
- **Benchmarking**: Measure and compare performance
- **Memory management**: Monitor and optimize memory usage
- **Profiling**: Detailed performance profiling
- **Caching**: Intelligent multi-level caching
- **Monitoring**: Real-time performance monitoring

## Core Classes

### PerformanceOptimizer

Optimizes RevitPy operations automatically.

::: revitpy.performance.PerformanceOptimizer
    options:
      members:
        - optimize_query
        - optimize_transaction
        - analyze_performance
        - get_recommendations

### BenchmarkSuite

Framework for performance benchmarking.

::: revitpy.performance.BenchmarkSuite
    options:
      members:
        - add_benchmark
        - run_benchmarks
        - compare_results
        - generate_report

### MemoryManager

Monitors and manages memory usage.

::: revitpy.performance.MemoryManager
    options:
      members:
        - get_memory_usage
        - track_allocations
        - detect_leaks
        - optimize_memory

### RevitPyProfiler

Detailed performance profiling.

::: revitpy.performance.RevitPyProfiler
    options:
      members:
        - start_profiling
        - stop_profiling
        - get_profile_report
        - export_profile

### IntelligentCacheManager

Advanced caching with smart eviction.

::: revitpy.performance.IntelligentCacheManager
    options:
      members:
        - get
        - set
        - invalidate
        - get_statistics
        - optimize_cache

## Query Optimization

### Automatic Query Optimization

```python
from revitpy.performance import PerformanceOptimizer

def optimized_wall_query():
    """Query with automatic optimization."""
    optimizer = PerformanceOptimizer()

    with RevitContext() as context:
        # Build query
        query = (context.elements
                .of_category('Walls')
                .where(lambda w: w.Height > 10.0)
                .include('WallType')
                .order_by(lambda w: w.Name))

        # Optimize query
        optimized_query = optimizer.optimize_query(query)

        # Execute optimized query
        walls = optimized_query.to_list()

        # Get optimization report
        report = optimizer.get_optimization_report()
        print(f"Query optimized: {report.improvements}")
```

### Query Analysis

```python
from revitpy.performance import QueryAnalyzer

def analyze_query_performance():
    """Analyze query performance."""
    analyzer = QueryAnalyzer()

    with RevitContext() as context:
        query = context.elements.of_category('Walls').where(lambda w: w.Height > 10)

        # Analyze query
        analysis = analyzer.analyze(query)

        print(f"Estimated cost: {analysis.estimated_cost}")
        print(f"Expected results: {analysis.estimated_results}")
        print(f"Recommended indexes: {analysis.recommended_indexes}")

        # Get optimization suggestions
        suggestions = analysis.get_suggestions()
        for suggestion in suggestions:
            print(f"- {suggestion.description}")
```

### Query Caching

```python
from revitpy.performance import QueryCache

def cached_query_example():
    """Use query result caching."""
    cache = QueryCache(max_size=1000, ttl=300)  # 5 minute TTL

    with RevitContext() as context:
        # First query - hits database
        query = context.elements.of_category('Walls')
        cache_key = cache.generate_key(query)

        if cache.has(cache_key):
            walls = cache.get(cache_key)
            print("Retrieved from cache")
        else:
            walls = query.to_list()
            cache.set(cache_key, walls)
            print("Cached query result")

        return walls
```

## Benchmarking

### Simple Benchmark

```python
from revitpy.performance import BenchmarkSuite, benchmark

# Create benchmark suite
suite = BenchmarkSuite(name="Wall Operations")

@benchmark(suite=suite, name="Query Walls", iterations=100)
def benchmark_query_walls():
    """Benchmark wall querying."""
    with RevitContext() as context:
        walls = context.elements.of_category('Walls').to_list()
        return len(walls)

@benchmark(suite=suite, name="Update Walls", iterations=50)
def benchmark_update_walls():
    """Benchmark wall updates."""
    with RevitContext() as context:
        walls = context.elements.of_category('Walls').take(10).to_list()

        with context.transaction("Update") as txn:
            for wall in walls:
                wall.set_parameter('Comments', 'Updated')
            txn.commit()

# Run benchmarks
results = suite.run_all()

# Display results
for result in results:
    print(f"{result.name}:")
    print(f"  Avg time: {result.avg_time:.4f}s")
    print(f"  Min time: {result.min_time:.4f}s")
    print(f"  Max time: {result.max_time:.4f}s")
    print(f"  Std dev: {result.std_dev:.4f}s")
```

### Comparative Benchmarks

```python
from revitpy.performance import compare_benchmarks

def compare_query_approaches():
    """Compare different query approaches."""
    suite = BenchmarkSuite()

    @benchmark(suite=suite, name="Traditional Query")
    def traditional_query():
        with RevitContext() as context:
            walls = list(context.elements.of_category('Walls'))
            filtered = [w for w in walls if w.Height > 10.0]
            sorted_walls = sorted(filtered, key=lambda w: w.Name)
            return sorted_walls

    @benchmark(suite=suite, name="ORM Query")
    def orm_query():
        with RevitContext() as context:
            walls = (context.elements
                    .of_category('Walls')
                    .where(lambda w: w.Height > 10.0)
                    .order_by(lambda w: w.Name)
                    .to_list())
            return walls

    # Run and compare
    results = suite.run_all()
    comparison = compare_benchmarks(results)

    print(f"Winner: {comparison.fastest}")
    print(f"Speed improvement: {comparison.improvement_percentage:.1f}%")
```

### Latency Benchmarks

```python
from revitpy.performance import LatencyBenchmark

def benchmark_api_latency():
    """Benchmark API operation latency."""
    latency_bench = LatencyBenchmark()

    with RevitContext() as context:
        # Measure element access latency
        element_id = 123456

        for i in range(100):
            with latency_bench.measure("get_element"):
                element = context.get_element_by_id(element_id)

        # Get latency statistics
        stats = latency_bench.get_statistics("get_element")

        print(f"Element access latency:")
        print(f"  P50: {stats.p50:.4f}ms")
        print(f"  P95: {stats.p95:.4f}ms")
        print(f"  P99: {stats.p99:.4f}ms")
        print(f"  Max: {stats.max:.4f}ms")
```

## Memory Management

### Memory Monitoring

```python
from revitpy.performance import MemoryManager, MemoryMonitor

def monitor_memory_usage():
    """Monitor memory usage during operations."""
    memory_mgr = MemoryManager()
    monitor = MemoryMonitor()

    # Start monitoring
    monitor.start()

    with RevitContext() as context:
        # Perform memory-intensive operation
        elements = context.elements.of_category('Walls').to_list()

        # Get current memory usage
        current_usage = memory_mgr.get_memory_usage()
        print(f"Current memory: {current_usage.total_mb:.2f} MB")

        # Process elements
        for element in elements:
            process_element(element)

        # Check for memory growth
        final_usage = memory_mgr.get_memory_usage()
        growth = final_usage.total_mb - current_usage.total_mb
        print(f"Memory growth: {growth:.2f} MB")

    # Stop monitoring and get report
    monitor.stop()
    report = monitor.get_report()

    print(f"\nMemory Report:")
    print(f"  Peak memory: {report.peak_mb:.2f} MB")
    print(f"  Average memory: {report.average_mb:.2f} MB")
    print(f"  Allocations: {report.allocation_count}")
```

### Memory Leak Detection

```python
from revitpy.performance import MemoryLeakDetector

def detect_memory_leaks():
    """Detect potential memory leaks."""
    detector = MemoryLeakDetector()

    # Start detection
    detector.start_tracking()

    # Run operation multiple times
    for i in range(100):
        with RevitContext() as context:
            walls = context.elements.of_category('Walls').to_list()
            # Process walls
            pass

    # Check for leaks
    detector.stop_tracking()
    leaks = detector.detect_leaks()

    if leaks:
        print("Potential memory leaks detected:")
        for leak in leaks:
            print(f"  {leak.location}: {leak.size_mb:.2f} MB")
            print(f"    {leak.description}")
    else:
        print("No memory leaks detected")
```

### Memory Optimization

```python
from revitpy.performance import optimize_memory

def memory_efficient_processing():
    """Process elements with memory optimization."""
    with RevitContext() as context:
        # BAD: Loads all elements into memory
        # walls = context.elements.of_category('Walls').to_list()
        # for wall in walls:
        #     process_wall(wall)

        # GOOD: Process elements in batches
        batch_size = 100
        offset = 0

        while True:
            batch = (context.elements
                    .of_category('Walls')
                    .skip(offset)
                    .take(batch_size)
                    .to_list())

            if not batch:
                break

            for wall in batch:
                process_wall(wall)

            # Force garbage collection after batch
            optimize_memory()

            offset += batch_size
```

## Profiling

### Code Profiling

```python
from revitpy.performance import RevitPyProfiler

def profile_operations():
    """Profile code performance."""
    profiler = RevitPyProfiler()

    # Start profiling
    profiler.start()

    with RevitContext() as context:
        # Profile query operation
        with profiler.section("query_walls"):
            walls = context.elements.of_category('Walls').to_list()

        # Profile update operation
        with profiler.section("update_walls"):
            with context.transaction("Update") as txn:
                for wall in walls[:10]:
                    wall.set_parameter('Comments', 'Profiled')
                txn.commit()

    # Stop profiling
    profiler.stop()

    # Get profile report
    report = profiler.get_report()

    print("Profile Report:")
    for section in report.sections:
        print(f"  {section.name}:")
        print(f"    Time: {section.total_time:.4f}s")
        print(f"    Percentage: {section.percentage:.1f}%")
        print(f"    Calls: {section.call_count}")
```

### Function Profiling

```python
from revitpy.performance import profile

@profile(name="Process Wall", report=True)
def process_wall(wall):
    """Function with automatic profiling."""
    # Get wall parameters
    height = wall.get_parameter('Height').AsDouble()
    area = wall.get_parameter('Area').AsDouble()

    # Perform calculations
    volume = area * height

    # Update parameters
    wall.set_parameter('Comments', f'Volume: {volume:.2f}')

    return volume

# Function is automatically profiled when called
# Profile report is generated on completion
```

### Detailed Profiling

```python
from revitpy.performance import DetailedProfiler

def detailed_performance_analysis():
    """Perform detailed performance analysis."""
    profiler = DetailedProfiler()

    with profiler.profile():
        with RevitContext() as context:
            elements = context.elements.of_category('Walls').to_list()

            for element in elements:
                process_element(element)

    # Get detailed report
    report = profiler.get_detailed_report()

    print("Detailed Performance Report:")
    print(f"Total time: {report.total_time:.4f}s")
    print(f"Function calls: {report.function_call_count}")

    # Top slow functions
    print("\nSlowest functions:")
    for func in report.slowest_functions[:10]:
        print(f"  {func.name}: {func.total_time:.4f}s ({func.call_count} calls)")

    # Export detailed report
    profiler.export_report('performance_report.html')
```

## Caching

### Intelligent Caching

```python
from revitpy.performance import IntelligentCacheManager

def use_intelligent_cache():
    """Use intelligent caching with automatic optimization."""
    cache = IntelligentCacheManager(
        max_size_mb=100,  # 100 MB max cache size
        eviction_policy='lru',  # Least Recently Used
        enable_statistics=True
    )

    with RevitContext() as context:
        # Cache element queries
        cache_key = 'walls:all'

        walls = cache.get(cache_key)
        if walls is None:
            walls = context.elements.of_category('Walls').to_list()
            cache.set(cache_key, walls, ttl=300)  # Cache for 5 minutes

        # Get cache statistics
        stats = cache.get_statistics()
        print(f"Cache hit rate: {stats.hit_rate:.2%}")
        print(f"Cache size: {stats.size_mb:.2f} MB")

        # Optimize cache
        cache.optimize()
```

### Multi-Level Caching

```python
from revitpy.performance import MultiLevelCache, MemoryCache, DiskCache

def multi_level_caching():
    """Use multi-level caching strategy."""
    # Create cache hierarchy
    l1_cache = MemoryCache(max_size_mb=50)  # Fast L1 cache
    l2_cache = DiskCache(max_size_mb=500, path='./cache')  # Larger L2 cache

    ml_cache = MultiLevelCache([l1_cache, l2_cache])

    with RevitContext() as context:
        # Try to get from cache hierarchy
        walls = ml_cache.get('walls:all')

        if walls is None:
            # Not in any cache level
            walls = context.elements.of_category('Walls').to_list()
            ml_cache.set('walls:all', walls)
            print("Loaded from database")
        else:
            print(f"Loaded from {ml_cache.get_hit_level()} cache")
```

## Performance Monitoring

### Real-Time Monitoring

```python
from revitpy.performance import PerformanceMonitor

def monitor_application_performance():
    """Monitor application performance in real-time."""
    monitor = PerformanceMonitor()

    # Configure monitoring
    monitor.configure(
        metrics=['cpu', 'memory', 'query_time', 'transaction_time'],
        sample_interval=1.0,  # Sample every second
        alert_threshold={'memory_mb': 1000, 'query_time_ms': 1000}
    )

    # Start monitoring
    monitor.start()

    # Application code
    with RevitContext() as context:
        walls = context.elements.of_category('Walls').to_list()
        # Process walls...

    # Get monitoring data
    metrics = monitor.get_current_metrics()
    print(f"CPU usage: {metrics.cpu_percent:.1f}%")
    print(f"Memory usage: {metrics.memory_mb:.2f} MB")
    print(f"Query time: {metrics.avg_query_time_ms:.2f} ms")

    # Check for alerts
    alerts = monitor.get_alerts()
    for alert in alerts:
        print(f"ALERT: {alert.message}")

    monitor.stop()
```

### Metrics Collection

```python
from revitpy.performance import MetricsCollector

def collect_performance_metrics():
    """Collect and aggregate performance metrics."""
    collector = MetricsCollector()

    with RevitContext() as context:
        for i in range(100):
            # Record query metric
            start = time.time()
            walls = context.elements.of_category('Walls').take(10).to_list()
            duration = time.time() - start

            collector.record('query_time', duration)
            collector.record('element_count', len(walls))

        # Get aggregated metrics
        metrics = collector.get_metrics()

        print(f"Query statistics:")
        print(f"  Average: {metrics['query_time'].average:.4f}s")
        print(f"  Min: {metrics['query_time'].min:.4f}s")
        print(f"  Max: {metrics['query_time'].max:.4f}s")
        print(f"  Total queries: {metrics['query_time'].count}")
```

## Best Practices

1. **Profile before optimizing**: Measure performance to identify bottlenecks
2. **Use appropriate caching**: Cache expensive operations, but manage memory
3. **Batch operations**: Group related operations together
4. **Monitor in production**: Track performance metrics in production
5. **Test performance**: Include performance tests in your test suite
6. **Optimize queries**: Use query optimization tools
7. **Manage memory**: Monitor and optimize memory usage

## Next Steps

- **[Performance Guide](../../guides/performance.md)**: Comprehensive performance guide
- **[ORM Performance](../../guides/orm-performance.md)**: Optimize ORM operations
- **[Async Performance](../../guides/async-performance.md)**: Optimize async operations
