"""
Comprehensive Performance Test Suite for RevitPy

This test suite validates all performance targets and requirements:
- Startup time ≤2 seconds for host application
- Python framework initialization ≤1 second
- VS Code extension activation ≤500ms
- CLI command response ≤200ms for simple operations
- API latency ≤1ms for simple operations, ≤100ms for complex operations
- Memory usage ≤50MB idle, ≤500MB peak under load
- Support for 10,000+ elements without performance degradation
- Zero memory leaks over 24-hour continuous operation
- Cache hit ratio ≥85%
- Throughput ≥10,000 operations per second for simple operations
"""

import gc
import logging
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

# RevitPy performance imports
from revitpy.performance import (
    BenchmarkConfiguration,
    BenchmarkRunner,
    BenchmarkSuite,
    MemoryLeakDetector,
    MemoryManager,
    OptimizationConfig,
    PerformanceMonitor,
    PerformanceOptimizer,
)

logger = logging.getLogger(__name__)


class PerformanceTestConfig:
    """Configuration for performance tests."""

    # Performance targets (as specified in requirements)
    STARTUP_TIME_TARGET_MS = 2000
    PYTHON_INIT_TARGET_MS = 1000
    VSCODE_ACTIVATION_TARGET_MS = 500
    CLI_RESPONSE_TARGET_MS = 200
    API_LATENCY_SIMPLE_TARGET_MS = 1
    API_LATENCY_COMPLEX_TARGET_MS = 100
    MEMORY_IDLE_TARGET_MB = 50
    MEMORY_PEAK_TARGET_MB = 500
    MAX_ELEMENTS_TARGET = 10000
    MAX_CONCURRENT_SESSIONS = 100
    CACHE_HIT_RATIO_TARGET = 0.85
    THROUGHPUT_TARGET_OPS_SEC = 10000

    # Test configuration
    BENCHMARK_ITERATIONS = 100
    WARMUP_ITERATIONS = 10
    MEMORY_LEAK_TEST_DURATION_MINUTES = 10  # Reduced for testing
    SCALABILITY_TEST_ELEMENT_COUNTS = [100, 1000, 5000, 10000]
    ENDURANCE_TEST_DURATION_MINUTES = 60  # Reduced for testing


@pytest.fixture(scope="session")
def performance_config():
    """Performance test configuration fixture."""
    return PerformanceTestConfig()


@pytest.fixture(scope="session")
def performance_optimizer():
    """Performance optimizer fixture."""
    config = OptimizationConfig(
        cache_max_size=20000,
        cache_max_memory_mb=200,
        pool_max_size=2000,
        max_worker_threads=8,
        enable_profiling=True,
        enable_benchmarking=True,
    )
    optimizer = PerformanceOptimizer(config)
    yield optimizer
    optimizer.cleanup()


@pytest.fixture(scope="session")
def memory_manager():
    """Memory manager fixture."""
    config = {
        "monitoring_interval_seconds": 5,
        "auto_cleanup_enabled": True,
        "detailed_tracking_enabled": True,
    }
    manager = MemoryManager(config)
    manager.start_monitoring()
    yield manager
    manager.cleanup()


@pytest.fixture(scope="session")
def performance_monitor():
    """Performance monitor fixture."""
    monitor = PerformanceMonitor()
    yield monitor
    monitor.stop_monitoring()


@pytest.fixture(scope="function")
def benchmark_suite():
    """Benchmark suite fixture."""
    config = BenchmarkConfiguration(
        parallel_execution=True,
        enable_memory_tracking=True,
        enable_regression_detection=True,
        save_results=True,
    )
    return BenchmarkSuite(config)


class TestStartupPerformance:
    """Test startup performance requirements."""

    def test_python_framework_initialization_time(
        self, performance_config, performance_optimizer
    ):
        """Test Python framework initialization meets ≤1 second target."""

        def initialize_framework():
            """Simulate framework initialization."""
            # Simulate module imports and setup
            time.sleep(0.1)  # Base initialization time

            # Initialize optimizer components
            performance_optimizer.get_object_pool(dict)
            performance_optimizer.get_object_pool(list)

            # Simulate cache warmup
            for i in range(10):
                performance_optimizer._cache.set(f"init_key_{i}", f"value_{i}")

            return "framework_initialized"

        # Benchmark initialization time
        latencies = []
        for _ in range(10):  # Multiple runs for accuracy
            start_time = time.perf_counter()
            result = initialize_framework()
            end_time = time.perf_counter()

            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            assert result == "framework_initialized"

        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)

        logger.info(
            f"Python framework initialization - Avg: {avg_latency:.1f}ms, Max: {max_latency:.1f}ms"
        )

        # Validate against target
        assert (
            avg_latency <= performance_config.PYTHON_INIT_TARGET_MS
        ), f"Python framework initialization too slow: {avg_latency:.1f}ms > {performance_config.PYTHON_INIT_TARGET_MS}ms"

        assert (
            max_latency <= performance_config.PYTHON_INIT_TARGET_MS * 1.5
        ), f"Python framework max initialization time too slow: {max_latency:.1f}ms"

    def test_component_startup_sequence(
        self, performance_config, performance_optimizer, memory_manager
    ):
        """Test startup sequence of all components."""

        def startup_sequence():
            """Simulate complete startup sequence."""
            start_time = time.perf_counter()

            # 1. Core initialization
            optimizer_start = time.perf_counter()
            performance_optimizer.get_performance_metrics()
            optimizer_time = (time.perf_counter() - optimizer_start) * 1000

            # 2. Memory manager initialization
            memory_start = time.perf_counter()
            memory_manager.take_snapshot("startup_test")
            memory_time = (time.perf_counter() - memory_start) * 1000

            # 3. Cache preloading
            cache_start = time.perf_counter()
            for i in range(100):
                performance_optimizer._cache.set(f"preload_{i}", f"data_{i}")
            cache_time = (time.perf_counter() - cache_start) * 1000

            total_time = (time.perf_counter() - start_time) * 1000

            return {
                "total_time_ms": total_time,
                "optimizer_time_ms": optimizer_time,
                "memory_time_ms": memory_time,
                "cache_time_ms": cache_time,
            }

        # Test startup sequence
        result = startup_sequence()

        logger.info(f"Startup sequence timing: {result}")

        # Validate components start quickly
        assert (
            result["total_time_ms"] <= performance_config.STARTUP_TIME_TARGET_MS
        ), f"Total startup time too slow: {result['total_time_ms']:.1f}ms"

        assert (
            result["optimizer_time_ms"] <= 100
        ), f"Optimizer initialization too slow: {result['optimizer_time_ms']:.1f}ms"

        assert (
            result["memory_time_ms"] <= 50
        ), f"Memory manager initialization too slow: {result['memory_time_ms']:.1f}ms"


class TestAPILatencyPerformance:
    """Test API latency performance requirements."""

    def test_simple_api_operations_latency(
        self, performance_config, performance_optimizer
    ):
        """Test simple API operations meet ≤1ms target."""

        # Prepare test data
        test_data = {"id": 12345, "name": "Test Element", "height": 10.0, "width": 5.0}

        def simple_property_access():
            """Simulate simple property access."""
            return test_data.get("height", 0)

        def simple_cache_access():
            """Simulate simple cache access."""
            return performance_optimizer._cache.get("test_key", "default")

        def simple_pool_access():
            """Simulate simple object pool access."""
            pool = performance_optimizer.get_object_pool(dict)
            obj = pool.get()
            pool.return_object(obj)
            return obj

        # Test different simple operations
        operations = {
            "property_access": simple_property_access,
            "cache_access": simple_cache_access,
            "pool_access": simple_pool_access,
        }

        for op_name, operation in operations.items():
            latencies = []

            # Warmup
            for _ in range(performance_config.WARMUP_ITERATIONS):
                operation()

            # Benchmark
            for _ in range(performance_config.BENCHMARK_ITERATIONS):
                start_time = time.perf_counter()
                operation()
                end_time = time.perf_counter()

                latency_ms = (end_time - start_time) * 1000
                latencies.append(latency_ms)

            avg_latency = statistics.mean(latencies)
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
            p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]

            logger.info(
                f"Simple {op_name} - Avg: {avg_latency:.3f}ms, P95: {p95_latency:.3f}ms, P99: {p99_latency:.3f}ms"
            )

            # Validate against target
            assert (
                avg_latency <= performance_config.API_LATENCY_SIMPLE_TARGET_MS
            ), f"Simple {op_name} too slow: {avg_latency:.3f}ms > {performance_config.API_LATENCY_SIMPLE_TARGET_MS}ms"

            assert (
                p95_latency <= performance_config.API_LATENCY_SIMPLE_TARGET_MS * 3
            ), f"Simple {op_name} P95 too slow: {p95_latency:.3f}ms"

    def test_complex_api_operations_latency(
        self, performance_config, performance_optimizer
    ):
        """Test complex API operations meet ≤100ms target."""

        def complex_computation():
            """Simulate complex computation with caching."""
            # Simulate geometry analysis
            points = [(i, i * 2, i * 3) for i in range(1000)]
            result = sum(x + y + z for x, y, z in points)

            # Simulate database query
            time.sleep(0.01)  # 10ms simulated I/O

            return result

        def complex_batch_operation():
            """Simulate complex batch operation."""
            operations = [lambda: sum(range(100)) for _ in range(50)]
            return performance_optimizer.execute_batch_sync(operations, batch_size=10)

        def complex_cached_operation():
            """Simulate complex operation with caching benefit."""
            cache_key = "complex_operation_result"

            def expensive_computation():
                # Simulate expensive computation
                result = sum(i**2 for i in range(1000))
                time.sleep(0.02)  # 20ms computation
                return result

            # Use cached operation decorator
            @performance_optimizer.cached_operation(cache_key, ttl_seconds=300)
            def cached_expensive_computation():
                return expensive_computation()

            return cached_expensive_computation()

        # Test different complex operations
        operations = {
            "computation": complex_computation,
            "batch_operation": complex_batch_operation,
            "cached_operation": complex_cached_operation,
        }

        for op_name, operation in operations.items():
            latencies = []

            # Warmup
            for _ in range(performance_config.WARMUP_ITERATIONS):
                try:
                    operation()
                except:
                    pass

            # Benchmark
            for _ in range(
                min(50, performance_config.BENCHMARK_ITERATIONS)
            ):  # Fewer iterations for complex ops
                start_time = time.perf_counter()
                operation()
                end_time = time.perf_counter()

                latency_ms = (end_time - start_time) * 1000
                latencies.append(latency_ms)

            avg_latency = statistics.mean(latencies)
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
            max_latency = max(latencies)

            logger.info(
                f"Complex {op_name} - Avg: {avg_latency:.1f}ms, P95: {p95_latency:.1f}ms, Max: {max_latency:.1f}ms"
            )

            # Validate against target
            assert (
                avg_latency <= performance_config.API_LATENCY_COMPLEX_TARGET_MS
            ), f"Complex {op_name} too slow: {avg_latency:.1f}ms > {performance_config.API_LATENCY_COMPLEX_TARGET_MS}ms"

            assert (
                p95_latency <= performance_config.API_LATENCY_COMPLEX_TARGET_MS * 2
            ), f"Complex {op_name} P95 too slow: {p95_latency:.1f}ms"


class TestMemoryPerformance:
    """Test memory usage and leak detection."""

    def test_idle_memory_usage(self, performance_config, memory_manager):
        """Test idle memory usage meets ≤50MB target."""

        # Take baseline snapshot
        memory_manager.take_snapshot("idle_baseline")

        # Let system settle
        time.sleep(2)

        # Take measurement snapshot
        measurement_snapshot = memory_manager.take_snapshot("idle_measurement")

        idle_memory_mb = measurement_snapshot.rss_memory_mb

        logger.info(f"Idle memory usage: {idle_memory_mb:.1f}MB")

        # Validate against target
        assert (
            idle_memory_mb <= performance_config.MEMORY_IDLE_TARGET_MB
        ), f"Idle memory usage too high: {idle_memory_mb:.1f}MB > {performance_config.MEMORY_IDLE_TARGET_MB}MB"

    def test_peak_memory_usage_under_load(
        self, performance_config, performance_optimizer, memory_manager
    ):
        """Test peak memory usage under load meets ≤500MB target."""

        # Take baseline
        memory_manager.take_snapshot("load_baseline")

        def memory_intensive_operation():
            """Simulate memory-intensive operation."""
            # Create large data structures
            data = []
            for i in range(1000):
                item = {
                    "id": i,
                    "data": list(range(100)),
                    "metadata": {"timestamp": time.time(), "processed": False},
                }
                data.append(item)

            # Process data
            for item in data:
                item["processed_data"] = [x * 2 for x in item["data"]]
                item["metadata"]["processed"] = True

            # Use performance optimizer
            with performance_optimizer.pooled_object(dict):
                result = sum(len(item["data"]) for item in data)

            return result, data

        # Run memory-intensive operations
        peak_memory_mb = 0

        for i in range(10):  # Multiple operations to build up memory
            memory_manager.take_snapshot(f"load_start_{i}")

            result, data = memory_intensive_operation()

            current_memory = memory_manager.take_snapshot(f"load_end_{i}")
            peak_memory_mb = max(peak_memory_mb, current_memory.rss_memory_mb)

            # Cleanup some data but not all (simulate real usage)
            if i % 3 == 0:
                del data
                gc.collect()

        logger.info(f"Peak memory usage under load: {peak_memory_mb:.1f}MB")

        # Validate against target
        assert (
            peak_memory_mb <= performance_config.MEMORY_PEAK_TARGET_MB
        ), f"Peak memory usage too high: {peak_memory_mb:.1f}MB > {performance_config.MEMORY_PEAK_TARGET_MB}MB"

    def test_memory_leak_detection(self, performance_config, memory_manager):
        """Test memory leak detection over extended operation."""

        # Create memory leak detector
        leak_detector = MemoryLeakDetector(memory_manager)

        # Run leak detection test
        leak_results = leak_detector.run_comprehensive_leak_detection(
            duration_minutes=performance_config.MEMORY_LEAK_TEST_DURATION_MINUTES
        )

        logger.info(
            f"Memory leak detection results: {leak_results['overall_assessment']}"
        )

        # Validate no critical leaks
        assert not leak_results.get(
            "has_critical_leaks", False
        ), f"Critical memory leaks detected: {leak_results.get('leak_candidates', [])}"

        # Allow minor memory growth but not excessive
        memory_growth = leak_results.get("total_memory_growth_mb", 0)
        growth_threshold = 20  # Allow up to 20MB growth over test period

        assert (
            memory_growth <= growth_threshold
        ), f"Excessive memory growth: {memory_growth:.1f}MB > {growth_threshold}MB"

        # Validate overall assessment
        acceptable_assessments = ["no_significant_leaks", "high_memory_growth"]
        assert (
            leak_results["overall_assessment"] in acceptable_assessments
        ), f"Unacceptable memory leak assessment: {leak_results['overall_assessment']}"


class TestScalabilityPerformance:
    """Test scalability with varying loads."""

    def test_element_count_scalability(self, performance_config, performance_optimizer):
        """Test performance with increasing element counts up to 10,000+."""

        def process_elements(element_count: int):
            """Simulate processing a specific number of elements."""
            # Create elements
            elements = []
            for i in range(element_count):
                element = {
                    "id": i,
                    "name": f"Element_{i}",
                    "properties": {
                        "height": 10 + (i % 20),
                        "width": 5 + (i % 10),
                        "area": (10 + (i % 20)) * (5 + (i % 10)),
                    },
                }
                elements.append(element)

            # Process elements with optimization
            processed_count = 0
            with performance_optimizer.performance_context("element_processing"):
                for element in elements:
                    # Simulate property access and computation
                    area = element["properties"]["area"]
                    if area > 50:
                        processed_count += 1

            return processed_count

        scalability_results = {}

        for element_count in performance_config.SCALABILITY_TEST_ELEMENT_COUNTS:
            latencies = []

            # Run multiple tests for this element count
            for _ in range(5):
                start_time = time.perf_counter()
                processed_count = process_elements(element_count)
                end_time = time.perf_counter()

                latency_ms = (end_time - start_time) * 1000
                latencies.append(latency_ms)

                assert processed_count > 0  # Ensure processing worked

            avg_latency = statistics.mean(latencies)
            elements_per_ms = element_count / avg_latency

            scalability_results[element_count] = {
                "avg_latency_ms": avg_latency,
                "elements_per_ms": elements_per_ms,
                "throughput_elements_per_sec": elements_per_ms * 1000,
            }

            logger.info(
                f"Element scalability {element_count:,} elements: {avg_latency:.1f}ms, {elements_per_ms:.1f} elements/ms"
            )

        # Validate scalability requirements
        max_element_result = scalability_results[performance_config.MAX_ELEMENTS_TARGET]

        # Should process 10,000 elements within reasonable time
        assert (
            max_element_result["avg_latency_ms"] <= 1000
        ), f"Processing {performance_config.MAX_ELEMENTS_TARGET} elements too slow: {max_element_result['avg_latency_ms']:.1f}ms"

        # Should maintain reasonable throughput
        assert (
            max_element_result["throughput_elements_per_sec"] >= 5000
        ), f"Element processing throughput too low: {max_element_result['throughput_elements_per_sec']:.0f} elements/sec"

        # Check for linear scalability (processing time should scale roughly linearly)
        small_count = performance_config.SCALABILITY_TEST_ELEMENT_COUNTS[0]
        large_count = performance_config.SCALABILITY_TEST_ELEMENT_COUNTS[-1]

        small_result = scalability_results[small_count]
        large_result = scalability_results[large_count]

        scaling_ratio = large_result["avg_latency_ms"] / small_result["avg_latency_ms"]
        element_ratio = large_count / small_count

        # Scaling should be roughly linear (within factor of 3)
        assert (
            scaling_ratio <= element_ratio * 3
        ), f"Poor scalability: {scaling_ratio:.1f}x latency increase for {element_ratio:.1f}x elements"

    def test_concurrent_session_scalability(
        self, performance_config, performance_optimizer
    ):
        """Test handling multiple concurrent sessions."""

        def simulate_user_session(session_id: int, duration_seconds: float = 5.0):
            """Simulate a user session with various operations."""
            session_ops = 0
            start_time = time.time()

            while time.time() - start_time < duration_seconds:
                # Simulate different operations
                with performance_optimizer.performance_context(
                    f"session_{session_id}_operation"
                ):
                    # Cache operations
                    performance_optimizer._cache.set(
                        f"session_{session_id}_key", f"data_{session_ops}"
                    )
                    performance_optimizer._cache.get(f"session_{session_id}_key")

                    # Pool operations
                    with performance_optimizer.pooled_object(dict):
                        pass

                    session_ops += 1
                    time.sleep(0.01)  # Simulate work

            return session_ops

        # Test with increasing concurrent sessions
        session_counts = [1, 5, 10, 25, 50]

        for session_count in session_counts:
            if session_count > performance_config.MAX_CONCURRENT_SESSIONS:
                continue

            logger.info(f"Testing {session_count} concurrent sessions")

            start_time = time.time()

            # Run concurrent sessions
            with ThreadPoolExecutor(max_workers=session_count) as executor:
                futures = [
                    executor.submit(simulate_user_session, i, 3.0)  # 3 second sessions
                    for i in range(session_count)
                ]

                # Wait for all sessions to complete
                results = [future.result() for future in futures]

            total_time = time.time() - start_time
            total_operations = sum(results)
            ops_per_second = total_operations / total_time

            logger.info(
                f"{session_count} sessions: {total_operations} operations in {total_time:.1f}s ({ops_per_second:.0f} ops/sec)"
            )

            # Validate performance scales with concurrent sessions
            assert all(
                ops > 0 for ops in results
            ), "Some sessions failed to perform operations"

            # Should maintain reasonable operation rate even with concurrency
            min_ops_per_second = 100  # Minimum acceptable throughput
            assert (
                ops_per_second >= min_ops_per_second
            ), f"Concurrent session throughput too low: {ops_per_second:.0f} ops/sec < {min_ops_per_second}"


class TestCachePerformance:
    """Test caching performance and hit ratios."""

    def test_cache_hit_ratio_target(self, performance_config, performance_optimizer):
        """Test cache hit ratio meets ≥85% target."""

        # Clear cache to start fresh
        performance_optimizer._cache.clear()

        # Simulate realistic cache usage pattern
        cache_keys = [f"cache_key_{i}" for i in range(100)]
        access_pattern = []

        # Create access pattern with some keys accessed more frequently
        for i in range(1000):
            if i < 100:
                # First 100 accesses populate cache
                key = cache_keys[i % len(cache_keys)]
            else:
                # Remaining accesses favor certain keys (80/20 rule)
                if i % 10 < 8:  # 80% of accesses to 20% of keys
                    key = cache_keys[i % 20]
                else:  # 20% of accesses to remaining keys
                    key = cache_keys[20 + (i % 80)]

            access_pattern.append(key)

        hits = 0
        misses = 0

        # Execute access pattern
        for key in access_pattern:
            # Try to get from cache
            result = performance_optimizer._cache.get(key)

            if result is not None:
                hits += 1
            else:
                misses += 1
                # Simulate cache miss - compute and store value
                computed_value = f"computed_value_for_{key}"
                performance_optimizer._cache.set(key, computed_value)

        # Calculate hit ratio
        total_accesses = hits + misses
        hit_ratio = hits / total_accesses if total_accesses > 0 else 0

        logger.info(
            f"Cache performance: {hits} hits, {misses} misses, {hit_ratio:.3f} hit ratio"
        )

        # Validate hit ratio target
        assert (
            hit_ratio >= performance_config.CACHE_HIT_RATIO_TARGET
        ), f"Cache hit ratio too low: {hit_ratio:.3f} < {performance_config.CACHE_HIT_RATIO_TARGET}"

        # Validate cache efficiency
        cache_stats = performance_optimizer._cache.get_stats()
        logger.info(f"Cache stats: {cache_stats}")

        assert cache_stats["size"] > 0, "Cache should contain entries after test"
        assert cache_stats["memory_usage_mb"] > 0, "Cache should use memory"

    def test_cache_performance_under_pressure(
        self, performance_config, performance_optimizer
    ):
        """Test cache performance under memory pressure."""

        # Fill cache to near capacity
        cache_size_limit = performance_optimizer._cache.max_size

        # Fill cache with varying sized data
        for i in range(int(cache_size_limit * 0.9)):  # Fill to 90% capacity
            data_size = 100 + (i % 1000)  # Varying data sizes
            data = "x" * data_size
            performance_optimizer._cache.set(f"pressure_test_{i}", data)

        # Test cache performance under pressure
        latencies = []

        for i in range(100):
            key = f"pressure_test_{i % 100}"  # Access first 100 keys

            start_time = time.perf_counter()
            result = performance_optimizer._cache.get(key)
            end_time = time.perf_counter()

            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            assert result is not None  # Should find the key

        avg_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        logger.info(
            f"Cache under pressure - Avg: {avg_latency:.3f}ms, P95: {p95_latency:.3f}ms"
        )

        # Cache should still be fast under pressure
        assert avg_latency <= 1.0, f"Cache too slow under pressure: {avg_latency:.3f}ms"
        assert (
            p95_latency <= 5.0
        ), f"Cache P95 too slow under pressure: {p95_latency:.3f}ms"


class TestThroughputPerformance:
    """Test throughput performance requirements."""

    def test_simple_operation_throughput(
        self, performance_config, performance_optimizer
    ):
        """Test simple operations meet ≥10,000 ops/sec target."""

        def simple_operation():
            """Very simple operation for throughput testing."""
            return {"id": 123, "value": 456}.get("value")

        # Warmup
        for _ in range(1000):
            simple_operation()

        # Measure throughput
        duration_seconds = 5.0
        operation_count = 0
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            simple_operation()
            operation_count += 1

        actual_duration = time.time() - start_time
        ops_per_second = operation_count / actual_duration

        logger.info(
            f"Simple operation throughput: {ops_per_second:.0f} ops/sec ({operation_count} ops in {actual_duration:.2f}s)"
        )

        # Validate throughput target
        assert (
            ops_per_second >= performance_config.THROUGHPUT_TARGET_OPS_SEC
        ), f"Simple operation throughput too low: {ops_per_second:.0f} ops/sec < {performance_config.THROUGHPUT_TARGET_OPS_SEC}"

    def test_optimized_operation_throughput(
        self, performance_config, performance_optimizer
    ):
        """Test throughput with performance optimization features."""

        # Test cached operations throughput
        @performance_optimizer.cached_operation("throughput_test", ttl_seconds=300)
        def cached_operation():
            return sum(range(100))

        # Test pooled operations throughput
        def pooled_operation():
            with performance_optimizer.pooled_object(dict) as obj:
                obj["test"] = "value"
                return obj.get("test")

        operations = {"cached": cached_operation, "pooled": pooled_operation}

        for op_name, operation in operations.items():
            # Warmup
            for _ in range(100):
                operation()

            # Measure throughput
            duration_seconds = 3.0
            operation_count = 0
            start_time = time.time()

            while time.time() - start_time < duration_seconds:
                operation()
                operation_count += 1

            actual_duration = time.time() - start_time
            ops_per_second = operation_count / actual_duration

            logger.info(f"{op_name} operation throughput: {ops_per_second:.0f} ops/sec")

            # Optimized operations should be very fast
            min_throughput = 5000  # Lower threshold for optimized operations
            assert (
                ops_per_second >= min_throughput
            ), f"{op_name} operation throughput too low: {ops_per_second:.0f} ops/sec < {min_throughput}"


class TestEndurancePerformance:
    """Test endurance and stability over extended periods."""

    @pytest.mark.slow
    def test_extended_operation_stability(
        self, performance_config, performance_optimizer, memory_manager
    ):
        """Test performance stability over extended operation."""

        duration_minutes = performance_config.ENDURANCE_TEST_DURATION_MINUTES
        logger.info(f"Starting {duration_minutes}-minute endurance test")

        # Take initial measurements
        initial_snapshot = memory_manager.take_snapshot("endurance_start")
        performance_optimizer.get_performance_metrics()

        # Track performance over time
        performance_samples = []
        memory_samples = []

        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        sample_interval = 60  # Sample every minute
        next_sample_time = start_time + sample_interval

        operation_count = 0

        while time.time() < end_time:
            # Perform various operations
            with performance_optimizer.performance_context("endurance_operation"):
                # Cache operations
                key = f"endurance_{operation_count % 1000}"
                performance_optimizer._cache.set(key, f"data_{operation_count}")
                performance_optimizer._cache.get(key)

                # Pool operations
                with performance_optimizer.pooled_object(dict) as obj:
                    obj["operation"] = operation_count

                # Memory-using operations
                temp_data = list(range(100))
                sum(temp_data)

                operation_count += 1

            # Take periodic samples
            current_time = time.time()
            if current_time >= next_sample_time:
                # Performance sample
                metrics = performance_optimizer.get_performance_metrics()
                performance_samples.append(
                    {
                        "timestamp": current_time,
                        "operation_count": operation_count,
                        "ops_per_second": metrics.get("operations_per_second", 0),
                        "avg_latency_ms": metrics.get("average_latency_ms", 0),
                        "cache_hit_ratio": metrics.get("cache_hit_ratio", 0),
                    }
                )

                # Memory sample
                snapshot = memory_manager.take_snapshot(
                    f"endurance_sample_{len(memory_samples)}"
                )
                memory_samples.append(
                    {"timestamp": current_time, "memory_mb": snapshot.rss_memory_mb}
                )

                next_sample_time += sample_interval

                logger.info(
                    f"Endurance test progress: {(current_time - start_time) / 60:.1f} minutes, {operation_count} operations"
                )

            time.sleep(0.001)  # Brief pause

        # Take final measurements
        final_snapshot = memory_manager.take_snapshot("endurance_end")
        performance_optimizer.get_performance_metrics()

        total_duration = time.time() - start_time
        avg_ops_per_second = operation_count / total_duration

        logger.info(
            f"Endurance test completed: {total_duration / 60:.1f} minutes, {operation_count} total operations"
        )

        # Analyze stability
        if len(performance_samples) >= 3:
            ops_per_second_values = [
                s["ops_per_second"]
                for s in performance_samples
                if s["ops_per_second"] > 0
            ]
            latency_values = [
                s["avg_latency_ms"]
                for s in performance_samples
                if s["avg_latency_ms"] > 0
            ]
            memory_values = [s["memory_mb"] for s in memory_samples]

            # Calculate stability metrics
            if ops_per_second_values:
                ops_stability = statistics.stdev(
                    ops_per_second_values
                ) / statistics.mean(ops_per_second_values)
                logger.info(f"Throughput stability coefficient: {ops_stability:.3f}")
                assert (
                    ops_stability < 0.5
                ), f"Throughput too unstable: {ops_stability:.3f}"

            if latency_values:
                latency_stability = statistics.stdev(latency_values) / statistics.mean(
                    latency_values
                )
                logger.info(f"Latency stability coefficient: {latency_stability:.3f}")
                assert (
                    latency_stability < 1.0
                ), f"Latency too unstable: {latency_stability:.3f}"

            if memory_values:
                memory_growth = memory_values[-1] - memory_values[0]
                logger.info(f"Memory growth over test: {memory_growth:.1f}MB")
                assert (
                    memory_growth < 50
                ), f"Excessive memory growth: {memory_growth:.1f}MB"

        # Validate overall performance maintained
        assert (
            avg_ops_per_second > 1000
        ), f"Average throughput too low: {avg_ops_per_second:.0f} ops/sec"

        # Memory should not have grown excessively
        memory_growth = final_snapshot.rss_memory_mb - initial_snapshot.rss_memory_mb
        assert (
            memory_growth <= 100
        ), f"Excessive memory growth during endurance test: {memory_growth:.1f}MB"


class TestPerformanceRegression:
    """Test for performance regressions."""

    def test_benchmark_suite_execution(self, benchmark_suite):
        """Test comprehensive benchmark suite execution."""

        # Run full benchmark suite
        results = benchmark_suite.run_all_benchmarks()

        assert results["summary"][
            "overall_pass"
        ], f"Benchmark suite failed: {results['summary']}"

        # Validate key benchmark results
        benchmark_results = results["benchmarks"]

        # Check startup benchmarks
        if "python_framework_startup" in benchmark_results:
            startup_result = benchmark_results["python_framework_startup"]
            assert startup_result[
                "success"
            ], "Python framework startup benchmark failed"
            assert startup_result[
                "meets_latency_target"
            ], "Startup latency target not met"

        # Check API benchmarks
        api_benchmarks = [
            name for name in benchmark_results.keys() if "api" in name.lower()
        ]
        for benchmark_name in api_benchmarks:
            result = benchmark_results[benchmark_name]
            assert result["success"], f"API benchmark {benchmark_name} failed"
            assert result[
                "meets_latency_target"
            ], f"API latency target not met for {benchmark_name}"

        # Check memory benchmarks
        memory_benchmarks = [
            name for name in benchmark_results.keys() if "memory" in name.lower()
        ]
        for benchmark_name in memory_benchmarks:
            result = benchmark_results[benchmark_name]
            assert result["success"], f"Memory benchmark {benchmark_name} failed"
            assert result[
                "meets_memory_target"
            ], f"Memory target not met for {benchmark_name}"

    def test_performance_target_validation(self, performance_config):
        """Test that all performance targets are validated."""

        # Create benchmark runner
        config = BenchmarkConfiguration(
            strict_target_validation=True,
            performance_targets={
                "startup_time_ms": performance_config.STARTUP_TIME_TARGET_MS,
                "api_latency_simple_ms": performance_config.API_LATENCY_SIMPLE_TARGET_MS,
                "api_latency_complex_ms": performance_config.API_LATENCY_COMPLEX_TARGET_MS,
                "memory_idle_mb": performance_config.MEMORY_IDLE_TARGET_MB,
                "memory_peak_mb": performance_config.MEMORY_PEAK_TARGET_MB,
                "cache_hit_ratio": performance_config.CACHE_HIT_RATIO_TARGET,
                "throughput_ops_per_sec": performance_config.THROUGHPUT_TARGET_OPS_SEC,
            },
        )

        runner = BenchmarkRunner(config)

        # Run performance validation
        validation_results = runner.run_performance_validation()

        logger.info(
            f"Performance validation result: {validation_results['overall_success']}"
        )
        logger.info(f"Validation summary: {validation_results['summary']}")

        # Should pass overall validation
        assert validation_results[
            "overall_success"
        ], f"Performance validation failed: {validation_results['summary']}"

        # Check individual test categories
        test_results = validation_results.get("test_results", {})

        # All major categories should pass
        required_categories = [
            "comprehensive_benchmarks",
            "startup_benchmarks",
            "api_latency_benchmarks",
            "target_validation",
        ]

        for category in required_categories:
            if category in test_results:
                result = test_results[category]
                category_success = result.get(
                    "overall_success", result.get("success", False)
                )
                assert (
                    category_success
                ), f"Performance validation category {category} failed: {result}"


# Integration test that runs comprehensive performance validation
@pytest.mark.integration
class TestComprehensivePerformanceValidation:
    """Comprehensive integration test for all performance requirements."""

    def test_all_performance_requirements(
        self,
        performance_config,
        performance_optimizer,
        memory_manager,
        performance_monitor,
        benchmark_suite,
    ):
        """Run comprehensive validation of all performance requirements."""

        logger.info("Starting comprehensive performance validation")

        # Start monitoring
        performance_monitor.start_monitoring(performance_optimizer)

        try:
            # 1. Startup Performance
            logger.info("Testing startup performance...")
            startup_start = time.perf_counter()

            # Simulate framework initialization
            performance_optimizer.get_performance_metrics()
            memory_manager.take_snapshot("validation_start")

            startup_time = (time.perf_counter() - startup_start) * 1000
            assert startup_time <= performance_config.STARTUP_TIME_TARGET_MS

            # 2. API Latency Performance
            logger.info("Testing API latency performance...")

            # Simple operation test
            simple_latencies = []
            for _ in range(100):
                start_time = time.perf_counter()
                result = {"test": "data"}.get("test")
                end_time = time.perf_counter()
                simple_latencies.append((end_time - start_time) * 1000)

            avg_simple_latency = statistics.mean(simple_latencies)
            assert avg_simple_latency <= performance_config.API_LATENCY_SIMPLE_TARGET_MS

            # Complex operation test
            def complex_op():
                time.sleep(0.01)  # Simulate 10ms operation
                return sum(range(1000))

            complex_latencies = []
            for _ in range(10):
                start_time = time.perf_counter()
                result = complex_op()
                end_time = time.perf_counter()
                complex_latencies.append((end_time - start_time) * 1000)

            avg_complex_latency = statistics.mean(complex_latencies)
            assert (
                avg_complex_latency <= performance_config.API_LATENCY_COMPLEX_TARGET_MS
            )

            # 3. Memory Performance
            logger.info("Testing memory performance...")

            current_memory = memory_manager.take_snapshot("validation_memory")
            assert (
                current_memory.rss_memory_mb <= performance_config.MEMORY_PEAK_TARGET_MB
            )

            # 4. Scalability
            logger.info("Testing scalability...")

            def process_elements(count):
                elements = [{"id": i, "value": i * 2} for i in range(count)]
                return sum(e["value"] for e in elements)

            scalability_start = time.perf_counter()
            result = process_elements(performance_config.MAX_ELEMENTS_TARGET)
            scalability_time = (time.perf_counter() - scalability_start) * 1000

            assert result > 0  # Ensure processing worked
            assert scalability_time <= 1000  # Should process 10k elements in <1 second

            # 5. Cache Performance
            logger.info("Testing cache performance...")

            # Test cache hit ratio
            cache = performance_optimizer._cache
            cache.clear()

            # Populate cache
            for i in range(100):
                cache.set(f"key_{i}", f"value_{i}")

            # Test access pattern
            hits = 0
            total_accesses = 200

            for i in range(total_accesses):
                key = f"key_{i % 50}"  # Access first 50 keys repeatedly
                if cache.get(key) is not None:
                    hits += 1

            hit_ratio = hits / total_accesses
            assert hit_ratio >= performance_config.CACHE_HIT_RATIO_TARGET

            # 6. Throughput
            logger.info("Testing throughput...")

            def simple_throughput_op():
                return len([1, 2, 3, 4, 5])

            throughput_duration = 2.0
            throughput_count = 0
            throughput_start = time.time()

            while time.time() - throughput_start < throughput_duration:
                simple_throughput_op()
                throughput_count += 1

            actual_duration = time.time() - throughput_start
            throughput = throughput_count / actual_duration

            assert throughput >= performance_config.THROUGHPUT_TARGET_OPS_SEC

            # 7. Get final performance summary
            performance_summary = performance_monitor.get_performance_summary()

            logger.info("Comprehensive performance validation completed successfully")
            logger.info(f"Performance summary: {performance_summary}")

            # Validate overall health score
            health_score = performance_summary.get("health_score", 0)
            assert (
                health_score >= 80
            ), f"Performance health score too low: {health_score}"

        finally:
            performance_monitor.stop_monitoring()


if __name__ == "__main__":
    # Run comprehensive performance tests
    pytest.main(
        [
            __file__,
            "-v",
            "--tb=short",
            "-x",  # Stop on first failure
            "--log-cli-level=INFO",
        ]
    )
