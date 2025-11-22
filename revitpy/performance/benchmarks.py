"""
Comprehensive Benchmarking Infrastructure for RevitPy

Provides extensive benchmarking capabilities including:
- Startup time benchmarking
- API latency benchmarking across different operation types
- Memory usage and leak detection benchmarks
- Scalability testing with various element counts
- Regression detection and performance baseline management
- Automated performance target validation
"""

import gc
import json
import logging
import statistics
import time
import tracemalloc
from collections import namedtuple
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger(__name__)

BenchmarkResult = namedtuple(
    "BenchmarkResult",
    [
        "name",
        "success",
        "latency_ms",
        "memory_mb",
        "throughput_ops_sec",
        "error",
        "details",
    ],
)


@dataclass
class PerformanceBenchmark:
    """Individual performance benchmark configuration and results."""

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

    # Results
    results: list[BenchmarkResult] = field(default_factory=list)
    passed: bool = False
    error: str | None = None


@dataclass
class BenchmarkConfiguration:
    """Configuration for benchmark suite execution."""

    # Execution settings
    parallel_execution: bool = True
    max_workers: int = 4
    timeout_seconds: float = 300.0

    # Memory settings
    enable_memory_tracking: bool = True
    enable_memory_leak_detection: bool = True
    memory_leak_threshold_mb: float = 10.0

    # Regression settings
    enable_regression_detection: bool = True
    regression_threshold_percent: float = 20.0
    baseline_file: str | None = None

    # Output settings
    save_results: bool = True
    results_directory: str = "benchmark_results"
    detailed_profiling: bool = False

    # Target validation
    strict_target_validation: bool = False
    performance_targets: dict[str, float] = field(
        default_factory=lambda: {
            "startup_time_ms": 1000,
            "api_latency_simple_ms": 1,
            "api_latency_complex_ms": 100,
            "memory_idle_mb": 50,
            "memory_peak_mb": 500,
            "cache_hit_ratio": 0.85,
            "throughput_ops_per_sec": 10000,
        }
    )


class BenchmarkSuite:
    """Comprehensive benchmark suite for RevitPy performance testing."""

    def __init__(self, config: BenchmarkConfiguration = None):
        self.config = config or BenchmarkConfiguration()
        self.benchmarks: list[PerformanceBenchmark] = []
        self.baseline_results: dict[str, dict] = {}
        self.results_history: list[dict] = []

        # Performance tracking
        self.start_time = None
        self.end_time = None
        self.total_runtime = 0.0

        # Memory tracking
        self.memory_snapshots = []
        self.initial_memory = 0.0

        # Load baseline if available
        self._load_baseline()

        # Initialize standard benchmarks
        self._initialize_standard_benchmarks()

    def add_benchmark(self, benchmark: PerformanceBenchmark):
        """Add a custom benchmark to the suite."""
        self.benchmarks.append(benchmark)
        logger.info("Added benchmark: %s", benchmark.name)

    def run_all_benchmarks(self) -> dict[str, Any]:
        """Run all benchmarks in the suite."""
        logger.info("Starting benchmark suite with %d benchmarks", len(self.benchmarks))

        self.start_time = time.time()
        self.initial_memory = self._get_memory_usage()

        if self.config.enable_memory_tracking:
            tracemalloc.start()
            self._take_memory_snapshot("benchmark_start")

        # Initialize results
        all_results = {
            "timestamp": self.start_time,
            "config": self.config.__dict__,
            "benchmarks": {},
            "summary": {},
            "regression_analysis": {},
            "memory_analysis": {},
        }

        try:
            # Run benchmarks
            if self.config.parallel_execution:
                benchmark_results = self._run_benchmarks_parallel()
            else:
                benchmark_results = self._run_benchmarks_sequential()

            all_results["benchmarks"] = benchmark_results

            # Analyze results
            all_results["summary"] = self._analyze_results(benchmark_results)

            # Regression detection
            if self.config.enable_regression_detection:
                all_results["regression_analysis"] = self._detect_regressions(
                    benchmark_results
                )

            # Memory analysis
            if self.config.enable_memory_tracking:
                all_results["memory_analysis"] = self._analyze_memory_usage()

            # Save results
            if self.config.save_results:
                self._save_results(all_results)

        except Exception as e:
            logger.error("Benchmark suite execution failed: %s", e)
            all_results["error"] = str(e)
            all_results["success"] = False

        finally:
            self.end_time = time.time()
            self.total_runtime = self.end_time - self.start_time

            if self.config.enable_memory_tracking:
                self._take_memory_snapshot("benchmark_end")
                tracemalloc.stop()

        all_results["total_runtime_seconds"] = self.total_runtime
        logger.info("Benchmark suite completed in %.2f seconds", self.total_runtime)

        return all_results

    def run_startup_benchmarks(self) -> dict[str, Any]:
        """Run startup-specific benchmarks."""
        startup_benchmarks = [b for b in self.benchmarks if "startup" in b.name.lower()]

        if not startup_benchmarks:
            return {"error": "No startup benchmarks defined"}

        results = {}
        for benchmark in startup_benchmarks:
            result = self._run_single_benchmark(benchmark)
            results[benchmark.name] = result

        return {
            "startup_benchmarks": results,
            "meets_startup_target": all(
                r.get("latency_ms", float("inf"))
                <= self.config.performance_targets["startup_time_ms"]
                for r in results.values()
                if r.get("success")
            ),
        }

    def run_api_latency_benchmarks(self) -> dict[str, Any]:
        """Run API latency benchmarks for different operation types."""
        api_benchmarks = [b for b in self.benchmarks if "api" in b.name.lower()]

        results = {}
        for benchmark in api_benchmarks:
            result = self._run_single_benchmark(benchmark)
            results[benchmark.name] = result

        # Categorize results
        simple_operations = {k: v for k, v in results.items() if "simple" in k.lower()}
        complex_operations = {
            k: v for k, v in results.items() if "complex" in k.lower()
        }

        return {
            "simple_operations": simple_operations,
            "complex_operations": complex_operations,
            "meets_simple_target": all(
                r.get("latency_ms", float("inf"))
                <= self.config.performance_targets["api_latency_simple_ms"]
                for r in simple_operations.values()
                if r.get("success")
            ),
            "meets_complex_target": all(
                r.get("latency_ms", float("inf"))
                <= self.config.performance_targets["api_latency_complex_ms"]
                for r in complex_operations.values()
                if r.get("success")
            ),
        }

    def run_scalability_benchmarks(
        self, element_counts: list[int] = None
    ) -> dict[str, Any]:
        """Run scalability benchmarks with varying element counts."""
        element_counts = element_counts or [100, 1000, 5000, 10000, 50000]

        scalability_results = {}

        for count in element_counts:
            logger.info("Running scalability test with %d elements", count)

            # Create scalability benchmark for this element count
            scalability_benchmark = PerformanceBenchmark(
                name=f"scalability_{count}_elements",
                target_latency_ms=self.config.performance_targets[
                    "api_latency_complex_ms"
                ],
                target_memory_mb=self.config.performance_targets["memory_peak_mb"],
                target_throughput_ops_sec=1000,  # Adjusted for element count
                operation=lambda: self._simulate_element_processing(count),
                iterations=10,  # Fewer iterations for large datasets
                warmup_iterations=3,
            )

            result = self._run_single_benchmark(scalability_benchmark)
            scalability_results[f"{count}_elements"] = result

        # Analyze scalability trends
        analysis = self._analyze_scalability_trends(scalability_results, element_counts)

        return {
            "scalability_results": scalability_results,
            "scalability_analysis": analysis,
            "meets_scalability_target": analysis.get("linear_scaling", False),
        }

    def run_memory_leak_detection(
        self, duration_minutes: float = 10.0
    ) -> dict[str, Any]:
        """Run extended memory leak detection benchmark."""
        if not self.config.enable_memory_leak_detection:
            return {"skipped": "Memory leak detection disabled"}

        logger.info("Starting memory leak detection for %.1f minutes", duration_minutes)

        if not tracemalloc.is_tracing():
            tracemalloc.start()

        initial_snapshot = tracemalloc.take_snapshot()
        initial_memory = self._get_memory_usage()

        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        memory_samples = []
        operation_count = 0

        try:
            while time.time() < end_time:
                # Perform various operations that might leak memory
                self._perform_memory_test_operations()
                operation_count += 1

                # Sample memory every 30 seconds
                if operation_count % 100 == 0:
                    current_memory = self._get_memory_usage()
                    memory_samples.append(
                        {
                            "timestamp": time.time() - start_time,
                            "memory_mb": current_memory,
                            "operations": operation_count,
                        }
                    )

                time.sleep(0.1)  # Brief pause

        except KeyboardInterrupt:
            logger.info("Memory leak detection interrupted by user")

        final_snapshot = tracemalloc.take_snapshot()
        final_memory = self._get_memory_usage()

        # Analyze memory growth
        memory_growth = final_memory - initial_memory
        has_leak = memory_growth > self.config.memory_leak_threshold_mb

        # Get top memory differences
        top_stats = final_snapshot.compare_to(initial_snapshot, "lineno")[:10]

        leak_analysis = {
            "duration_minutes": duration_minutes,
            "operations_performed": operation_count,
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "memory_growth_mb": memory_growth,
            "has_potential_leak": has_leak,
            "leak_threshold_mb": self.config.memory_leak_threshold_mb,
            "memory_samples": memory_samples,
            "top_memory_differences": [str(stat) for stat in top_stats],
            "growth_rate_mb_per_hour": (memory_growth / duration_minutes) * 60
            if duration_minutes > 0
            else 0,
        }

        if has_leak:
            logger.warning(
                "Potential memory leak detected: %.2fMB growth over %.1f minutes",
                memory_growth,
                duration_minutes,
            )
        else:
            logger.info("No significant memory leaks detected")

        return leak_analysis

    def validate_performance_targets(self) -> dict[str, Any]:
        """Validate that all benchmarks meet their performance targets."""
        validation_results = {
            "overall_pass": True,
            "target_validations": {},
            "failed_targets": [],
            "summary": {},
        }

        # Check each benchmark against its targets
        for benchmark in self.benchmarks:
            if not benchmark.results:
                continue

            latest_result = benchmark.results[-1]
            target_validations = {}

            # Latency validation
            latency_pass = latest_result.latency_ms <= benchmark.target_latency_ms
            target_validations["latency"] = {
                "target_ms": benchmark.target_latency_ms,
                "actual_ms": latest_result.latency_ms,
                "pass": latency_pass,
            }

            # Memory validation
            memory_pass = latest_result.memory_mb <= benchmark.target_memory_mb
            target_validations["memory"] = {
                "target_mb": benchmark.target_memory_mb,
                "actual_mb": latest_result.memory_mb,
                "pass": memory_pass,
            }

            # Throughput validation
            throughput_pass = (
                latest_result.throughput_ops_sec >= benchmark.target_throughput_ops_sec
            )
            target_validations["throughput"] = {
                "target_ops_sec": benchmark.target_throughput_ops_sec,
                "actual_ops_sec": latest_result.throughput_ops_sec,
                "pass": throughput_pass,
            }

            benchmark_pass = latency_pass and memory_pass and throughput_pass

            validation_results["target_validations"][benchmark.name] = {
                "overall_pass": benchmark_pass,
                "validations": target_validations,
            }

            if not benchmark_pass:
                validation_results["overall_pass"] = False
                validation_results["failed_targets"].append(benchmark.name)

        # Summary statistics
        total_benchmarks = len(validation_results["target_validations"])
        passed_benchmarks = sum(
            1
            for v in validation_results["target_validations"].values()
            if v["overall_pass"]
        )

        validation_results["summary"] = {
            "total_benchmarks": total_benchmarks,
            "passed_benchmarks": passed_benchmarks,
            "failed_benchmarks": total_benchmarks - passed_benchmarks,
            "pass_rate": passed_benchmarks / total_benchmarks
            if total_benchmarks > 0
            else 0,
        }

        return validation_results

    # Private methods

    def _initialize_standard_benchmarks(self):
        """Initialize standard RevitPy benchmarks."""

        # Startup benchmarks
        self.add_benchmark(
            PerformanceBenchmark(
                name="python_framework_startup",
                target_latency_ms=self.config.performance_targets["startup_time_ms"],
                target_memory_mb=self.config.performance_targets["memory_idle_mb"],
                target_throughput_ops_sec=1,
                operation=self._simulate_framework_startup,
                iterations=10,
                warmup_iterations=2,
            )
        )

        # API latency benchmarks - Simple operations
        self.add_benchmark(
            PerformanceBenchmark(
                name="api_simple_element_access",
                target_latency_ms=self.config.performance_targets[
                    "api_latency_simple_ms"
                ],
                target_memory_mb=10,
                target_throughput_ops_sec=self.config.performance_targets[
                    "throughput_ops_per_sec"
                ],
                operation=self._simulate_simple_element_access,
                iterations=1000,
                warmup_iterations=100,
            )
        )

        # API latency benchmarks - Complex operations
        self.add_benchmark(
            PerformanceBenchmark(
                name="api_complex_geometry_analysis",
                target_latency_ms=self.config.performance_targets[
                    "api_latency_complex_ms"
                ],
                target_memory_mb=50,
                target_throughput_ops_sec=100,
                operation=self._simulate_complex_geometry_analysis,
                iterations=50,
                warmup_iterations=10,
            )
        )

        # Cache performance
        self.add_benchmark(
            PerformanceBenchmark(
                name="cache_performance",
                target_latency_ms=0.1,  # Sub-millisecond cache access
                target_memory_mb=20,
                target_throughput_ops_sec=50000,
                operation=self._simulate_cache_operations,
                iterations=10000,
                warmup_iterations=1000,
            )
        )

        # Memory efficiency
        self.add_benchmark(
            PerformanceBenchmark(
                name="memory_efficiency",
                target_latency_ms=100,
                target_memory_mb=self.config.performance_targets["memory_peak_mb"],
                target_throughput_ops_sec=1000,
                operation=self._simulate_memory_intensive_operations,
                iterations=100,
                warmup_iterations=10,
            )
        )

    def _run_benchmarks_parallel(self) -> dict[str, Any]:
        """Run benchmarks in parallel using thread pool."""
        results = {}

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all benchmarks
            future_to_benchmark = {
                executor.submit(self._run_single_benchmark, benchmark): benchmark
                for benchmark in self.benchmarks
            }

            # Collect results
            for future in as_completed(
                future_to_benchmark, timeout=self.config.timeout_seconds
            ):
                benchmark = future_to_benchmark[future]
                try:
                    result = future.result()
                    results[benchmark.name] = result
                except Exception as e:
                    logger.error("Benchmark %s failed: %s", benchmark.name, e)
                    results[benchmark.name] = {
                        "success": False,
                        "error": str(e),
                        "latency_ms": float("inf"),
                        "memory_mb": 0,
                        "throughput_ops_sec": 0,
                    }

        return results

    def _run_benchmarks_sequential(self) -> dict[str, Any]:
        """Run benchmarks sequentially."""
        results = {}

        for benchmark in self.benchmarks:
            logger.info("Running benchmark: %s", benchmark.name)
            result = self._run_single_benchmark(benchmark)
            results[benchmark.name] = result

        return results

    def _run_single_benchmark(self, benchmark: PerformanceBenchmark) -> dict[str, Any]:
        """Run a single benchmark and return results."""
        logger.debug("Starting benchmark: %s", benchmark.name)

        # Setup
        if benchmark.setup:
            try:
                benchmark.setup()
            except Exception as e:
                logger.error("Benchmark setup failed for %s: %s", benchmark.name, e)
                return {"success": False, "error": f"Setup failed: {e}"}

        # Warmup
        for _ in range(benchmark.warmup_iterations):
            try:
                benchmark.operation()
            except:
                pass  # Ignore warmup errors

        # Force garbage collection before measurement
        gc.collect()

        # Measurement
        latencies = []
        memory_usages = []
        errors = []

        initial_memory = self._get_memory_usage()
        start_time = time.time()

        for i in range(benchmark.iterations):
            iteration_start = time.perf_counter()
            iteration_memory_start = self._get_memory_usage()

            try:
                result = benchmark.operation()

                # Validate result if validator provided
                if benchmark.validate_result and not benchmark.validate_result(result):
                    errors.append(f"Iteration {i}: Result validation failed")
                    continue

                success = True
                error = None

            except Exception as e:
                success = False
                error = str(e)
                errors.append(f"Iteration {i}: {error}")
                continue

            iteration_end = time.perf_counter()
            iteration_memory_end = self._get_memory_usage()

            latency_ms = (iteration_end - iteration_start) * 1000
            memory_delta = iteration_memory_end - iteration_memory_start

            latencies.append(latency_ms)
            memory_usages.append(iteration_memory_end)

            # Check timeout
            if time.time() - start_time > benchmark.timeout_seconds:
                logger.warning(
                    "Benchmark %s timed out after %d iterations", benchmark.name, i + 1
                )
                break

        end_time = time.time()
        final_memory = self._get_memory_usage()

        # Teardown
        if benchmark.teardown:
            try:
                benchmark.teardown()
            except Exception as e:
                logger.warning(
                    "Benchmark teardown failed for %s: %s", benchmark.name, e
                )

        # Calculate statistics
        if latencies:
            success_rate = (len(latencies) - len(errors)) / len(latencies)

            result = {
                "success": len(errors) == 0,
                "iterations": len(latencies),
                "success_rate": success_rate,
                "errors": errors[:10],  # Limit error list
                "latency_ms": statistics.mean(latencies),
                "latency_median_ms": statistics.median(latencies),
                "latency_p95_ms": self._percentile(latencies, 95),
                "latency_p99_ms": self._percentile(latencies, 99),
                "latency_std_ms": statistics.stdev(latencies)
                if len(latencies) > 1
                else 0,
                "memory_mb": final_memory,
                "memory_delta_mb": final_memory - initial_memory,
                "memory_peak_mb": max(memory_usages) if memory_usages else final_memory,
                "throughput_ops_sec": len(latencies) / (end_time - start_time),
                "total_duration_sec": end_time - start_time,
                "meets_latency_target": statistics.mean(latencies)
                <= benchmark.target_latency_ms,
                "meets_memory_target": final_memory <= benchmark.target_memory_mb,
                "meets_throughput_target": (len(latencies) / (end_time - start_time))
                >= benchmark.target_throughput_ops_sec,
            }

            # Store result in benchmark
            benchmark_result = BenchmarkResult(
                name=benchmark.name,
                success=result["success"],
                latency_ms=result["latency_ms"],
                memory_mb=result["memory_mb"],
                throughput_ops_sec=result["throughput_ops_sec"],
                error=errors[0] if errors else None,
                details=result,
            )
            benchmark.results.append(benchmark_result)
            benchmark.passed = result["success"] and all(
                [
                    result["meets_latency_target"],
                    result["meets_memory_target"],
                    result["meets_throughput_target"],
                ]
            )

            return result

        else:
            error_result = {
                "success": False,
                "error": "No successful iterations",
                "errors": errors,
                "latency_ms": float("inf"),
                "memory_mb": final_memory,
                "throughput_ops_sec": 0,
            }

            benchmark.error = error_result["error"]
            return error_result

    def _analyze_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """Analyze benchmark results and generate summary."""
        total_benchmarks = len(results)
        successful_benchmarks = sum(
            1 for r in results.values() if r.get("success", False)
        )

        # Calculate aggregate metrics
        latencies = [
            r["latency_ms"]
            for r in results.values()
            if r.get("success") and "latency_ms" in r
        ]
        memory_usage = [
            r["memory_mb"]
            for r in results.values()
            if r.get("success") and "memory_mb" in r
        ]
        throughputs = [
            r["throughput_ops_sec"]
            for r in results.values()
            if r.get("success") and "throughput_ops_sec" in r
        ]

        summary = {
            "total_benchmarks": total_benchmarks,
            "successful_benchmarks": successful_benchmarks,
            "failed_benchmarks": total_benchmarks - successful_benchmarks,
            "success_rate": successful_benchmarks / total_benchmarks
            if total_benchmarks > 0
            else 0,
            "overall_pass": successful_benchmarks == total_benchmarks,
        }

        if latencies:
            summary["latency_stats"] = {
                "avg_ms": statistics.mean(latencies),
                "median_ms": statistics.median(latencies),
                "p95_ms": self._percentile(latencies, 95),
                "p99_ms": self._percentile(latencies, 99),
                "min_ms": min(latencies),
                "max_ms": max(latencies),
            }

        if memory_usage:
            summary["memory_stats"] = {
                "avg_mb": statistics.mean(memory_usage),
                "median_mb": statistics.median(memory_usage),
                "peak_mb": max(memory_usage),
                "min_mb": min(memory_usage),
            }

        if throughputs:
            summary["throughput_stats"] = {
                "avg_ops_sec": statistics.mean(throughputs),
                "median_ops_sec": statistics.median(throughputs),
                "peak_ops_sec": max(throughputs),
                "min_ops_sec": min(throughputs),
            }

        # Performance target analysis
        target_analysis = {}
        for target_name, target_value in self.config.performance_targets.items():
            relevant_results = []

            if "latency" in target_name and latencies:
                relevant_results = [l for l in latencies if l <= target_value]
                target_analysis[target_name] = {
                    "target": target_value,
                    "meeting_target_count": len(relevant_results),
                    "total_count": len(latencies),
                    "compliance_rate": len(relevant_results) / len(latencies),
                }
            elif "memory" in target_name and memory_usage:
                relevant_results = [m for m in memory_usage if m <= target_value]
                target_analysis[target_name] = {
                    "target": target_value,
                    "meeting_target_count": len(relevant_results),
                    "total_count": len(memory_usage),
                    "compliance_rate": len(relevant_results) / len(memory_usage),
                }
            elif "throughput" in target_name and throughputs:
                relevant_results = [t for t in throughputs if t >= target_value]
                target_analysis[target_name] = {
                    "target": target_value,
                    "meeting_target_count": len(relevant_results),
                    "total_count": len(throughputs),
                    "compliance_rate": len(relevant_results) / len(throughputs),
                }

        summary["target_analysis"] = target_analysis

        return summary

    def _detect_regressions(self, current_results: dict[str, Any]) -> dict[str, Any]:
        """Detect performance regressions compared to baseline."""
        if not self.baseline_results:
            return {"message": "No baseline available for regression detection"}

        regressions = []
        improvements = []

        for benchmark_name, current_result in current_results.items():
            if not current_result.get("success"):
                continue

            baseline_result = self.baseline_results.get(benchmark_name)
            if not baseline_result:
                continue

            # Compare latency
            current_latency = current_result.get("latency_ms", 0)
            baseline_latency = baseline_result.get("latency_ms", 0)

            if baseline_latency > 0:
                latency_change_percent = (
                    (current_latency - baseline_latency) / baseline_latency
                ) * 100

                if latency_change_percent > self.config.regression_threshold_percent:
                    regressions.append(
                        {
                            "benchmark": benchmark_name,
                            "metric": "latency_ms",
                            "baseline": baseline_latency,
                            "current": current_latency,
                            "change_percent": latency_change_percent,
                            "severity": "high"
                            if latency_change_percent > 50
                            else "medium",
                        }
                    )
                elif latency_change_percent < -10:  # 10% improvement
                    improvements.append(
                        {
                            "benchmark": benchmark_name,
                            "metric": "latency_ms",
                            "baseline": baseline_latency,
                            "current": current_latency,
                            "improvement_percent": -latency_change_percent,
                        }
                    )

            # Compare memory usage
            current_memory = current_result.get("memory_mb", 0)
            baseline_memory = baseline_result.get("memory_mb", 0)

            if baseline_memory > 0:
                memory_change_percent = (
                    (current_memory - baseline_memory) / baseline_memory
                ) * 100

                if memory_change_percent > self.config.regression_threshold_percent:
                    regressions.append(
                        {
                            "benchmark": benchmark_name,
                            "metric": "memory_mb",
                            "baseline": baseline_memory,
                            "current": current_memory,
                            "change_percent": memory_change_percent,
                            "severity": "high"
                            if memory_change_percent > 50
                            else "medium",
                        }
                    )

        return {
            "regressions_detected": len(regressions) > 0,
            "regressions": regressions,
            "improvements": improvements,
            "regression_count": len(regressions),
            "improvement_count": len(improvements),
        }

    def _analyze_memory_usage(self) -> dict[str, Any]:
        """Analyze memory usage throughout benchmark execution."""
        if not self.memory_snapshots:
            return {"message": "No memory snapshots available"}

        memory_values = [snapshot["memory_mb"] for snapshot in self.memory_snapshots]

        analysis = {
            "snapshot_count": len(self.memory_snapshots),
            "initial_memory_mb": memory_values[0] if memory_values else 0,
            "final_memory_mb": memory_values[-1] if memory_values else 0,
            "peak_memory_mb": max(memory_values) if memory_values else 0,
            "min_memory_mb": min(memory_values) if memory_values else 0,
            "memory_growth_mb": (memory_values[-1] - memory_values[0])
            if len(memory_values) >= 2
            else 0,
            "snapshots": self.memory_snapshots,
        }

        # Detect potential memory leaks
        if len(memory_values) >= 3:
            # Check if memory is consistently growing
            growth_trend = []
            for i in range(1, len(memory_values)):
                growth_trend.append(memory_values[i] - memory_values[i - 1])

            positive_growth_count = sum(1 for g in growth_trend if g > 0)
            potential_leak = (
                positive_growth_count / len(growth_trend)
            ) > 0.7  # 70% of measurements show growth

            analysis["potential_memory_leak"] = potential_leak
            analysis["growth_trend"] = growth_trend

        return analysis

    def _analyze_scalability_trends(
        self, scalability_results: dict[str, Any], element_counts: list[int]
    ) -> dict[str, Any]:
        """Analyze scalability trends across different element counts."""

        # Extract latencies and throughputs for trend analysis
        data_points = []
        for count in element_counts:
            key = f"{count}_elements"
            if key in scalability_results and scalability_results[key].get("success"):
                result = scalability_results[key]
                data_points.append(
                    {
                        "element_count": count,
                        "latency_ms": result.get("latency_ms", 0),
                        "throughput_ops_sec": result.get("throughput_ops_sec", 0),
                        "memory_mb": result.get("memory_mb", 0),
                    }
                )

        if len(data_points) < 2:
            return {"error": "Insufficient data points for trend analysis"}

        # Calculate scaling factors
        analysis = {"data_points": data_points, "scaling_analysis": {}}

        # Analyze latency scaling
        latencies = [dp["latency_ms"] for dp in data_points]
        element_counts_actual = [dp["element_count"] for dp in data_points]

        # Simple linear regression to check if scaling is approximately linear
        if HAS_NUMPY:
            import numpy as np

            # Latency vs element count
            latency_slope, latency_intercept = np.polyfit(
                element_counts_actual, latencies, 1
            )
            latency_r_squared = np.corrcoef(element_counts_actual, latencies)[0, 1] ** 2

            # Throughput vs element count
            throughputs = [dp["throughput_ops_sec"] for dp in data_points]
            throughput_slope, throughput_intercept = np.polyfit(
                element_counts_actual, throughputs, 1
            )
            throughput_r_squared = (
                np.corrcoef(element_counts_actual, throughputs)[0, 1] ** 2
            )

            analysis["scaling_analysis"] = {
                "latency_scaling": {
                    "slope_ms_per_element": float(latency_slope),
                    "r_squared": float(latency_r_squared),
                    "linear_scaling": latency_r_squared > 0.8,  # Good linear fit
                },
                "throughput_scaling": {
                    "slope_ops_per_element": float(throughput_slope),
                    "r_squared": float(throughput_r_squared),
                    "scales_with_load": throughput_slope > 0,
                },
            }

            # Overall scaling assessment
            linear_scaling = (
                latency_r_squared > 0.8
                and latency_slope < 0.1  # Less than 0.1ms per element
                and throughput_slope >= 0
            )  # Throughput doesn't decrease

            analysis["linear_scaling"] = linear_scaling
            analysis["scaling_quality"] = "excellent" if linear_scaling else "poor"

        else:
            # Simple analysis without numpy
            latency_ratios = []
            for i in range(1, len(data_points)):
                prev_dp = data_points[i - 1]
                curr_dp = data_points[i]

                element_ratio = curr_dp["element_count"] / prev_dp["element_count"]
                latency_ratio = curr_dp["latency_ms"] / max(
                    prev_dp["latency_ms"], 0.001
                )

                latency_ratios.append(
                    latency_ratio / element_ratio
                )  # How much latency increases relative to element increase

            avg_scaling_factor = (
                statistics.mean(latency_ratios) if latency_ratios else 1.0
            )
            linear_scaling = (
                avg_scaling_factor < 2.0
            )  # Latency increases less than 2x relative to element count

            analysis["scaling_analysis"] = {
                "average_scaling_factor": avg_scaling_factor,
                "linear_scaling": linear_scaling,
            }
            analysis["linear_scaling"] = linear_scaling
            analysis["scaling_quality"] = "good" if linear_scaling else "poor"

        return analysis

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        if HAS_PSUTIL:
            try:
                process = psutil.Process()
                return process.memory_info().rss / 1024 / 1024
            except:
                pass

        # Fallback to basic method
        try:
            import resource

            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except:
            return 0.0

    def _take_memory_snapshot(self, label: str):
        """Take a memory snapshot with label."""
        snapshot = {
            "label": label,
            "timestamp": time.time(),
            "memory_mb": self._get_memory_usage(),
        }

        if tracemalloc.is_tracing():
            current_snapshot = tracemalloc.take_snapshot()
            top_stats = current_snapshot.statistics("lineno")[:10]
            snapshot["top_allocations"] = [str(stat) for stat in top_stats]

        self.memory_snapshots.append(snapshot)

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (percentile / 100.0) * (len(sorted_data) - 1)

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower_index = int(index)
            upper_index = lower_index + 1
            if upper_index >= len(sorted_data):
                return sorted_data[-1]

            weight = index - lower_index
            return (
                sorted_data[lower_index] * (1 - weight)
                + sorted_data[upper_index] * weight
            )

    def _load_baseline(self):
        """Load baseline results from file."""
        if not self.config.baseline_file:
            return

        try:
            baseline_path = Path(self.config.baseline_file)
            if baseline_path.exists():
                with open(baseline_path) as f:
                    baseline_data = json.load(f)
                    self.baseline_results = baseline_data.get("benchmarks", {})
                    logger.info("Loaded baseline from %s", baseline_path)
        except Exception as e:
            logger.warning("Failed to load baseline: %s", e)

    def _save_results(self, results: dict[str, Any]):
        """Save benchmark results to file."""
        try:
            results_dir = Path(self.config.results_directory)
            results_dir.mkdir(exist_ok=True)

            timestamp = time.strftime(
                "%Y%m%d_%H%M%S", time.localtime(results["timestamp"])
            )
            results_file = results_dir / f"benchmark_results_{timestamp}.json"

            with open(results_file, "w") as f:
                json.dump(results, f, indent=2, default=str)

            logger.info("Saved benchmark results to %s", results_file)

            # Also save as latest baseline
            baseline_file = results_dir / "baseline.json"
            with open(baseline_file, "w") as f:
                json.dump(results, f, indent=2, default=str)

        except Exception as e:
            logger.error("Failed to save results: %s", e)

    # Simulation methods for testing (these would be replaced with actual RevitPy operations)

    def _simulate_framework_startup(self):
        """Simulate Python framework startup."""
        # Simulate initialization work
        time.sleep(0.01)  # 10ms base startup time

        # Simulate module imports and initialization
        dummy_modules = [f"module_{i}" for i in range(10)]
        for module in dummy_modules:
            time.sleep(0.001)  # 1ms per module

        return "framework_initialized"

    def _simulate_simple_element_access(self):
        """Simulate simple element property access."""
        # Very fast operation - just property access
        element_data = {"id": 12345, "name": "Wall_001", "height": 10.0}
        return element_data.get("height")

    def _simulate_complex_geometry_analysis(self):
        """Simulate complex geometry analysis operation."""
        # Simulate computational work
        time.sleep(0.01)  # 10ms base computation

        # Simulate geometry calculations
        points = [(i, i * 2, i * 3) for i in range(100)]
        result = sum(x + y + z for x, y, z in points)

        return result

    def _simulate_cache_operations(self):
        """Simulate cache access operations."""
        # Very fast cache-like operation
        cache = {"key1": "value1", "key2": "value2"}
        return cache.get("key1", "default")

    def _simulate_memory_intensive_operations(self):
        """Simulate memory-intensive operations."""
        # Create and manipulate some data structures
        data = [list(range(1000)) for _ in range(10)]
        processed = [[x * 2 for x in sublist] for sublist in data]
        result = sum(sum(sublist) for sublist in processed)

        # Clean up
        del data
        del processed

        return result

    def _simulate_element_processing(self, element_count: int):
        """Simulate processing a specific number of elements."""
        # Simulate processing time that scales with element count
        base_time = 0.001  # 1ms base
        per_element_time = 0.00001  # 0.01ms per element

        total_time = base_time + (per_element_time * element_count)
        time.sleep(min(total_time, 1.0))  # Cap at 1 second

        # Simulate memory usage that scales with element count
        elements = [
            {"id": i, "data": f"element_{i}"} for i in range(min(element_count, 10000))
        ]

        result = len(elements)
        del elements

        return result

    def _perform_memory_test_operations(self):
        """Perform various operations for memory leak testing."""
        # Create temporary objects
        temp_data = []
        for i in range(100):
            temp_data.append(
                {
                    "id": i,
                    "data": [j for j in range(100)],
                    "metadata": {"created": time.time(), "processed": False},
                }
            )

        # Process data
        for item in temp_data:
            item["metadata"]["processed"] = True
            item["processed_data"] = [x * 2 for x in item["data"]]

        # Clean up (this should prevent memory leaks)
        del temp_data

        # Force garbage collection occasionally
        if hasattr(self, "_gc_counter"):
            self._gc_counter += 1
        else:
            self._gc_counter = 1

        if self._gc_counter % 50 == 0:
            gc.collect()


class BenchmarkRunner:
    """High-level benchmark runner with reporting capabilities."""

    def __init__(self, config: BenchmarkConfiguration = None):
        self.config = config or BenchmarkConfiguration()
        self.suite = BenchmarkSuite(self.config)

    def run_performance_validation(self) -> dict[str, Any]:
        """Run complete performance validation suite."""
        logger.info("Starting comprehensive performance validation")

        validation_results = {
            "timestamp": time.time(),
            "overall_success": True,
            "test_results": {},
        }

        try:
            # Run full benchmark suite
            benchmark_results = self.suite.run_all_benchmarks()
            validation_results["test_results"]["comprehensive_benchmarks"] = (
                benchmark_results
            )

            # Run startup benchmarks
            startup_results = self.suite.run_startup_benchmarks()
            validation_results["test_results"]["startup_benchmarks"] = startup_results

            # Run API latency benchmarks
            api_results = self.suite.run_api_latency_benchmarks()
            validation_results["test_results"]["api_latency_benchmarks"] = api_results

            # Run scalability tests
            scalability_results = self.suite.run_scalability_benchmarks()
            validation_results["test_results"]["scalability_benchmarks"] = (
                scalability_results
            )

            # Run memory leak detection
            memory_leak_results = self.suite.run_memory_leak_detection(
                duration_minutes=5.0
            )
            validation_results["test_results"]["memory_leak_detection"] = (
                memory_leak_results
            )

            # Validate performance targets
            target_validation = self.suite.validate_performance_targets()
            validation_results["test_results"]["target_validation"] = target_validation

            # Determine overall success
            validation_results["overall_success"] = all(
                [
                    benchmark_results.get("summary", {}).get("overall_pass", False),
                    startup_results.get("meets_startup_target", False),
                    api_results.get("meets_simple_target", False),
                    api_results.get("meets_complex_target", False),
                    scalability_results.get("meets_scalability_target", False),
                    not memory_leak_results.get("has_potential_leak", True),
                    target_validation.get("overall_pass", False),
                ]
            )

        except Exception as e:
            logger.error("Performance validation failed: %s", e)
            validation_results["overall_success"] = False
            validation_results["error"] = str(e)

        # Generate summary report
        validation_results["summary"] = self._generate_validation_summary(
            validation_results
        )

        logger.info(
            "Performance validation completed. Overall success: %s",
            validation_results["overall_success"],
        )

        return validation_results

    def _generate_validation_summary(
        self, validation_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate a summary of validation results."""
        summary = {
            "overall_success": validation_results["overall_success"],
            "test_categories": {},
            "key_metrics": {},
            "recommendations": [],
        }

        test_results = validation_results.get("test_results", {})

        # Analyze each test category
        for category, results in test_results.items():
            if isinstance(results, dict):
                category_success = results.get(
                    "overall_success", results.get("success", False)
                )
                summary["test_categories"][category] = {
                    "success": category_success,
                    "details": self._extract_key_details(results),
                }

        # Extract key metrics
        if "comprehensive_benchmarks" in test_results:
            comp_results = test_results["comprehensive_benchmarks"]
            if "summary" in comp_results:
                summary["key_metrics"] = comp_results["summary"]

        # Generate recommendations
        summary["recommendations"] = self._generate_recommendations(validation_results)

        return summary

    def _extract_key_details(self, results: dict[str, Any]) -> dict[str, Any]:
        """Extract key details from test results."""
        details = {}

        # Common patterns to extract
        if "latency_ms" in results:
            details["latency_ms"] = results["latency_ms"]
        if "memory_mb" in results:
            details["memory_mb"] = results["memory_mb"]
        if "throughput_ops_sec" in results:
            details["throughput_ops_sec"] = results["throughput_ops_sec"]
        if "success_rate" in results:
            details["success_rate"] = results["success_rate"]

        return details

    def _generate_recommendations(
        self, validation_results: dict[str, Any]
    ) -> list[str]:
        """Generate performance improvement recommendations."""
        recommendations = []

        test_results = validation_results.get("test_results", {})

        # Analyze benchmark results for recommendations
        if "comprehensive_benchmarks" in test_results:
            benchmark_results = test_results["comprehensive_benchmarks"]
            summary = benchmark_results.get("summary", {})

            # Latency recommendations
            latency_stats = summary.get("latency_stats", {})
            if latency_stats.get("p95_ms", 0) > 100:
                recommendations.append(
                    "Consider optimizing high-latency operations (P95 > 100ms)"
                )

            # Memory recommendations
            memory_stats = summary.get("memory_stats", {})
            if memory_stats.get("peak_mb", 0) > 400:
                recommendations.append(
                    "High memory usage detected - consider memory optimization"
                )

            # Success rate recommendations
            if summary.get("success_rate", 1.0) < 0.95:
                recommendations.append(
                    "Improve operation reliability - success rate below 95%"
                )

        # Memory leak recommendations
        if "memory_leak_detection" in test_results:
            leak_results = test_results["memory_leak_detection"]
            if leak_results.get("has_potential_leak", False):
                recommendations.append(
                    "Potential memory leak detected - review object lifecycle management"
                )

        # Scalability recommendations
        if "scalability_benchmarks" in test_results:
            scalability_results = test_results["scalability_benchmarks"]
            if not scalability_results.get("meets_scalability_target", False):
                recommendations.append(
                    "Improve scalability - performance degrades significantly with load"
                )

        if not recommendations:
            recommendations.append(
                "All performance metrics are within acceptable ranges"
            )

        return recommendations
