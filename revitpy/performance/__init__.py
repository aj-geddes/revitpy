"""
RevitPy Performance Optimization Framework

This module provides comprehensive performance optimization and benchmarking
capabilities for the RevitPy Python framework, designed to meet enterprise
performance targets:

- Startup time ≤1 second for Python framework initialization
- API latency ≤1ms for simple operations, ≤100ms for complex operations
- Memory usage ≤50MB idle, ≤500MB peak under load
- Support for 10,000+ elements without performance degradation
- Zero memory leaks over 24-hour continuous operation

Key Components:
- PerformanceOptimizer: Core optimization engine with caching and pooling
- BenchmarkSuite: Comprehensive benchmarking and regression detection
- MemoryManager: Advanced memory management and leak detection
- AdaptiveCache / ObjectPool: Caching and pooling used by the optimizer
- MetricsCollector: Performance metrics collection and analysis
"""

from .benchmarks import BenchmarkConfiguration, BenchmarkRunner, BenchmarkSuite
from .memory import MemoryLeakDetector, MemoryManager
from .monitoring import AlertingSystem, MetricsCollector, PerformanceMonitor
from .optimizer import (
    AdaptiveCache,
    ObjectPool,
    OptimizationConfig,
    PerformanceOptimizer,
)

__all__ = [
    # Core optimization
    "PerformanceOptimizer",
    "OptimizationConfig",
    "AdaptiveCache",
    "ObjectPool",
    # Benchmarking
    "BenchmarkSuite",
    "BenchmarkRunner",
    "BenchmarkConfiguration",
    # Memory management
    "MemoryManager",
    "MemoryLeakDetector",
    # Metrics and monitoring
    "MetricsCollector",
    "PerformanceMonitor",
    "AlertingSystem",
]

# Performance targets as specified in requirements
PERFORMANCE_TARGETS = {
    "startup_time_ms": 1000,  # Python framework initialization
    "api_latency_simple_ms": 1,
    "api_latency_complex_ms": 100,
    "memory_idle_mb": 50,
    "memory_peak_mb": 500,
    "max_elements": 10000,
    "max_concurrent_sessions": 100,
    "cache_hit_ratio_min": 0.85,
    "throughput_ops_per_sec": 10000,
}

# Global performance optimizer instance
_global_optimizer = None


def get_global_optimizer() -> PerformanceOptimizer:
    """Get or create the global performance optimizer instance."""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = PerformanceOptimizer()
    return _global_optimizer


def initialize_performance_framework(
    config: OptimizationConfig = None,
) -> PerformanceOptimizer:
    """Initialize the RevitPy performance framework with optional configuration."""
    global _global_optimizer
    _global_optimizer = PerformanceOptimizer(config)
    return _global_optimizer


def cleanup_performance_framework():
    """Cleanup the performance framework and release resources."""
    global _global_optimizer
    if _global_optimizer:
        _global_optimizer.cleanup()
        _global_optimizer = None
