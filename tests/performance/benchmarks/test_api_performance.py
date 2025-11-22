"""Performance benchmarks for RevitPy API operations.

This module contains comprehensive performance tests to ensure RevitPy
meets enterprise performance requirements and to detect regressions.
"""

import asyncio
import gc
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock

import psutil
import pytest

from revitpy.api.wrapper import RevitAPIWrapper
from revitpy.orm.models import Element
from revitpy.orm.session import RevitSession


class TestAPIPerformance:
    """Performance benchmarks for API operations."""

    @pytest.fixture
    def mock_bridge(self):
        """Mock bridge for performance testing."""
        bridge = MagicMock()
        bridge.IsConnected = True
        bridge.CallAsync = AsyncMock()
        return bridge

    @pytest.fixture
    def api_wrapper(self, mock_bridge):
        """API wrapper for performance testing."""
        wrapper = RevitAPIWrapper()
        wrapper._bridge = mock_bridge
        wrapper._connected = True
        return wrapper

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_single_api_call_performance(self, benchmark, api_wrapper):
        """Benchmark single API call performance."""
        api_wrapper._bridge.CallAsync.return_value = (
            '{"id": 12345, "name": "Test Wall"}'
        )

        async def single_call():
            return await api_wrapper.call_api("GetElement", {"elementId": 12345})

        result = benchmark(asyncio.run, single_call())

        # Performance assertions
        assert result["id"] == 12345
        assert benchmark.stats.mean < 0.01  # Less than 10ms per call
        assert benchmark.stats.stddev < 0.005  # Consistent performance

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_batch_api_calls_performance(self, benchmark, api_wrapper):
        """Benchmark batch API call performance."""
        # Setup mock to return different results for each call
        results = [f'{{"id": {i}, "name": "Element {i}"}}' for i in range(100)]
        api_wrapper._bridge.CallAsync.side_effect = results

        calls = [
            {"method": "GetElement", "params": {"elementId": i}} for i in range(100)
        ]

        async def batch_calls():
            return await api_wrapper.batch_call(calls)

        result = benchmark(asyncio.run, batch_calls())

        # Performance assertions
        assert len(result) == 100
        assert benchmark.stats.mean < 0.5  # Less than 500ms for 100 calls

        # Throughput calculation
        throughput = 100 / benchmark.stats.mean
        assert throughput > 200  # More than 200 calls per second

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_concurrent_api_calls_performance(self, benchmark, api_wrapper):
        """Benchmark concurrent API call performance."""
        api_wrapper._bridge.CallAsync.return_value = '{"success": true}'

        async def concurrent_calls():
            tasks = []
            for i in range(50):
                task = api_wrapper.call_api("TestMethod", {"id": i})
                tasks.append(task)

            return await asyncio.gather(*tasks)

        result = benchmark(asyncio.run, concurrent_calls())

        # Performance assertions
        assert len(result) == 50
        assert benchmark.stats.mean < 0.2  # Less than 200ms for 50 concurrent calls

        # Concurrent throughput
        throughput = 50 / benchmark.stats.mean
        assert throughput > 250  # More than 250 calls per second

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_api_call_with_large_payload(self, benchmark, api_wrapper):
        """Benchmark API calls with large payloads."""
        # Create 1MB payload
        large_data = "x" * (1024 * 1024)
        api_wrapper._bridge.CallAsync.return_value = (
            f'{{"data": "{large_data}", "size": 1048576}}'
        )

        async def large_payload_call():
            return await api_wrapper.call_api("ProcessLargeData", {"data": large_data})

        result = benchmark(asyncio.run, large_payload_call())

        # Performance assertions
        assert result["size"] == 1048576
        assert benchmark.stats.mean < 0.1  # Less than 100ms for 1MB payload

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_memory_usage_during_api_calls(
        self, benchmark, api_wrapper, memory_leak_detector
    ):
        """Benchmark memory usage during API operations."""
        api_wrapper._bridge.CallAsync.return_value = '{"id": 1, "data": "test"}'

        memory_leak_detector.start()

        async def memory_test_calls():
            results = []
            for i in range(1000):
                result = await api_wrapper.call_api("GetElement", {"elementId": i})
                results.append(result)
            return results

        result = benchmark(asyncio.run, memory_test_calls())

        # Check for memory leaks
        memory_stats = memory_leak_detector.check()

        assert len(result) == 1000
        assert memory_stats["memory_increase_mb"] < 50  # Less than 50MB increase
        assert benchmark.stats.mean < 2.0  # Less than 2 seconds for 1000 calls


class TestORMPerformance:
    """Performance benchmarks for ORM operations."""

    @pytest.fixture
    def mock_session(self):
        """Mock RevitSession for testing."""
        session = MagicMock(spec=RevitSession)
        session.api_wrapper = MagicMock()
        session.api_wrapper.call_api = AsyncMock()
        return session

    @pytest.fixture
    def sample_element_data(self):
        """Generate sample element data for testing."""
        return [
            {
                "Id": i,
                "Name": f"Wall {i}",
                "Category": "Walls",
                "Parameters": {
                    "Height": 3000.0 + (i * 100),
                    "Width": 200.0,
                    "Area": 15.0 + i,
                    "Volume": 3.0 + (i * 0.1),
                },
            }
            for i in range(1000)
        ]

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_element_creation_performance(
        self, benchmark, mock_session, sample_element_data
    ):
        """Benchmark element creation from data."""

        def create_elements():
            elements = []
            for data in sample_element_data:
                element = Element.from_data(data, session=mock_session)
                elements.append(element)
            return elements

        result = benchmark(create_elements)

        # Performance assertions
        assert len(result) == 1000
        assert benchmark.stats.mean < 0.5  # Less than 500ms for 1000 elements

        # Memory efficiency check
        element_creation_rate = 1000 / benchmark.stats.mean
        assert element_creation_rate > 2000  # More than 2000 elements per second

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_parameter_access_performance(self, benchmark, mock_session):
        """Benchmark parameter access performance."""
        # Create element with many parameters
        element_data = {
            "Id": 1,
            "Name": "Complex Element",
            "Category": "Walls",
            "Parameters": {f"Parameter_{i}": i * 10.0 for i in range(100)},
        }
        element = Element.from_data(element_data, session=mock_session)

        def access_parameters():
            total = 0
            for i in range(100):
                # Access parameters by name
                param_name = f"parameter_{i}"  # lowercase to test attribute access
                value = getattr(element, param_name, 0)
                total += value
            return total

        result = benchmark(access_parameters)

        # Performance assertions
        assert result > 0
        assert benchmark.stats.mean < 0.01  # Less than 10ms for 100 parameter accesses

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_element_modification_performance(self, benchmark, mock_session):
        """Benchmark element modification performance."""
        element_data = {
            "Id": 1,
            "Name": "Test Wall",
            "Category": "Walls",
            "Parameters": {"Height": 3000.0, "Width": 200.0},
        }
        element = Element.from_data(element_data, session=mock_session)

        def modify_element():
            # Modify multiple parameters
            element.height = 3500.0
            element.width = 250.0
            element.name = "Modified Wall"
            return element

        result = benchmark(modify_element)

        # Performance assertions
        assert result.height == 3500.0
        assert result._dirty
        assert benchmark.stats.mean < 0.001  # Less than 1ms for modifications

    @pytest.mark.performance
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_query_performance(self, benchmark, mock_session):
        """Benchmark query execution performance."""
        # Mock query results
        mock_results = [
            {
                "Id": i,
                "Name": f"Wall {i}",
                "Category": "Walls",
                "Parameters": {"Height": 3000.0 + (i * 100)},
            }
            for i in range(100)
        ]
        mock_session.api_wrapper.call_api.return_value = mock_results

        from revitpy.orm.query import QueryBuilder

        async def execute_query():
            query = (
                QueryBuilder(session=mock_session)
                .filter_by_category("Walls")
                .filter_by_parameter("Height", ">", 2500.0)
            )
            return await query.all()

        result = benchmark(asyncio.run, execute_query())

        # Performance assertions
        assert len(result) == 100
        assert benchmark.stats.mean < 0.05  # Less than 50ms for query execution


class TestBridgePerformance:
    """Performance benchmarks for C# bridge operations."""

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_bridge_connection_time(self, benchmark):
        """Benchmark bridge connection time."""

        def establish_connection():
            # This would test actual bridge connection
            # Mocked for now
            time.sleep(0.01)  # Simulate connection time
            return True

        result = benchmark(establish_connection)

        # Performance assertions
        assert result is True
        assert benchmark.stats.mean < 0.1  # Less than 100ms connection time

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_type_conversion_performance(self, benchmark):
        """Benchmark Python-C# type conversion performance."""

        def convert_types():
            # Simulate type conversion operations
            data = {
                "integers": list(range(1000)),
                "floats": [i * 1.5 for i in range(1000)],
                "strings": [f"String {i}" for i in range(1000)],
                "booleans": [i % 2 == 0 for i in range(1000)],
            }

            # Convert to JSON and back (simulating C# conversion)
            import json

            json_str = json.dumps(data)
            converted_back = json.loads(json_str)
            return converted_back

        result = benchmark(convert_types)

        # Performance assertions
        assert len(result["integers"]) == 1000
        assert benchmark.stats.mean < 0.01  # Less than 10ms for type conversion


class TestScalabilityBenchmarks:
    """Scalability benchmarks for enterprise usage."""

    @pytest.mark.performance
    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_high_volume_element_processing(self, benchmark, mock_session):
        """Test performance with high volume of elements."""
        # Generate large dataset
        large_dataset = [
            {
                "Id": i,
                "Name": f"Element {i}",
                "Category": "Walls"
                if i % 3 == 0
                else "Doors"
                if i % 3 == 1
                else "Windows",
                "Parameters": {
                    "Height": 3000.0 + (i * 50),
                    "Width": 200.0 + (i * 10),
                    "Area": 15.0 + (i * 2),
                },
            }
            for i in range(10000)  # 10,000 elements
        ]

        def process_large_dataset():
            elements = []
            total_area = 0

            for data in large_dataset:
                element = Element.from_data(data, session=mock_session)
                elements.append(element)
                total_area += element.area

            return len(elements), total_area

        result = benchmark(process_large_dataset)

        # Performance assertions
        element_count, total_area = result
        assert element_count == 10000
        assert total_area > 0
        assert benchmark.stats.mean < 5.0  # Less than 5 seconds for 10,000 elements

        # Memory efficiency
        elements_per_second = 10000 / benchmark.stats.mean
        assert elements_per_second > 2000  # More than 2,000 elements per second

    @pytest.mark.performance
    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_concurrent_user_simulation(self, benchmark):
        """Simulate multiple concurrent users."""

        def simulate_concurrent_users():
            def user_session():
                # Simulate a user session
                operations = []
                for _ in range(10):
                    # Simulate API calls
                    time.sleep(0.001)  # 1ms per operation
                    operations.append("operation_completed")
                return operations

            # Simulate 50 concurrent users
            with ThreadPoolExecutor(max_workers=50) as executor:
                futures = [executor.submit(user_session) for _ in range(50)]
                results = [future.result() for future in futures]

            return len(results)

        result = benchmark(simulate_concurrent_users)

        # Performance assertions
        assert result == 50
        assert benchmark.stats.mean < 2.0  # Less than 2 seconds for 50 users

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_memory_usage_scaling(self, benchmark, memory_leak_detector):
        """Test memory usage scaling with data size."""
        memory_leak_detector.start()

        def scaling_test():
            datasets = []

            # Create increasingly large datasets
            for size in [100, 500, 1000, 2000]:
                dataset = [
                    {"id": i, "data": f"Data {i}" * 10}  # Variable size data
                    for i in range(size)
                ]
                datasets.append(dataset)

            return datasets

        result = benchmark(scaling_test)

        # Check memory scaling
        memory_stats = memory_leak_detector.check()

        # Performance assertions
        assert len(result) == 4  # 4 different dataset sizes
        assert memory_stats["memory_increase_mb"] < 100  # Less than 100MB increase

        # Memory should scale linearly, not exponentially
        memory_per_mb = memory_stats["memory_increase_mb"] / sum([100, 500, 1000, 2000])
        assert memory_per_mb < 0.01  # Less than 0.01MB per element


@pytest.mark.performance
class TestRegressionBenchmarks:
    """Regression benchmarks to detect performance degradation."""

    @pytest.fixture
    def baseline_metrics(self):
        """Baseline performance metrics for regression testing."""
        return {
            "api_call_mean": 0.008,  # 8ms baseline
            "api_call_stddev": 0.003,  # 3ms stddev baseline
            "element_creation_rate": 2500,  # 2500 elements/sec baseline
            "parameter_access_mean": 0.005,  # 5ms baseline
            "memory_per_element": 0.005,  # 5KB per element baseline
        }

    @pytest.mark.benchmark
    def test_api_call_regression(self, benchmark, api_wrapper, baseline_metrics):
        """Test for API call performance regression."""
        api_wrapper._bridge.CallAsync.return_value = '{"result": "success"}'

        async def api_call():
            return await api_wrapper.call_api("TestMethod", {})

        result = benchmark(asyncio.run, api_call())

        # Regression assertions (allow 20% performance degradation)
        assert benchmark.stats.mean <= baseline_metrics["api_call_mean"] * 1.2
        assert benchmark.stats.stddev <= baseline_metrics["api_call_stddev"] * 1.2

    @pytest.mark.benchmark
    def test_element_creation_regression(
        self, benchmark, mock_session, baseline_metrics
    ):
        """Test for element creation performance regression."""
        element_data = {
            "Id": 1,
            "Name": "Test Element",
            "Category": "Walls",
            "Parameters": {"Height": 3000.0},
        }

        def create_elements():
            elements = []
            for i in range(1000):
                data = element_data.copy()
                data["Id"] = i
                element = Element.from_data(data, session=mock_session)
                elements.append(element)
            return elements

        result = benchmark(create_elements)

        # Calculate creation rate
        creation_rate = 1000 / benchmark.stats.mean

        # Regression assertion (allow 20% performance degradation)
        assert creation_rate >= baseline_metrics["element_creation_rate"] * 0.8


# Utility functions for performance testing
def measure_cpu_usage(func, *args, **kwargs):
    """Measure CPU usage during function execution."""
    process = psutil.Process()
    cpu_before = process.cpu_percent()

    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()

    cpu_after = process.cpu_percent()

    return {
        "result": result,
        "execution_time": end_time - start_time,
        "cpu_usage": cpu_after - cpu_before,
        "memory_usage": process.memory_info().rss,
    }


def measure_memory_usage(func, *args, **kwargs):
    """Measure memory usage during function execution."""
    gc.collect()  # Clean up before measurement

    mem_before = psutil.Process().memory_info().rss
    result = func(*args, **kwargs)
    mem_after = psutil.Process().memory_info().rss

    return {
        "result": result,
        "memory_increase": mem_after - mem_before,
        "memory_before": mem_before,
        "memory_after": mem_after,
    }
