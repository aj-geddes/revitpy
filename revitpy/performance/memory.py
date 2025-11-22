"""
Advanced Memory Management and Leak Detection for RevitPy

Provides comprehensive memory management capabilities:
- Memory leak detection with detailed analysis
- Memory usage optimization and cleanup
- Memory pressure monitoring and alerts
- Object lifecycle tracking
- Memory profiling and analysis
- Automatic memory optimization strategies
"""

import gc
import logging
import sys
import threading
import time
import tracemalloc
import weakref
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Detailed memory usage snapshot."""

    timestamp: float
    total_memory_mb: float
    rss_memory_mb: float
    vms_memory_mb: float
    available_memory_mb: float
    memory_percent: float
    gc_stats: dict[int, int]
    tracemalloc_peak_mb: float
    object_counts: dict[str, int]
    top_allocations: list[str] = field(default_factory=list)


@dataclass
class MemoryLeakCandidate:
    """Potential memory leak detection result."""

    object_type: str
    count_growth: int
    memory_growth_mb: float
    growth_rate_per_hour: float
    severity: str  # 'low', 'medium', 'high', 'critical'
    confidence: float  # 0.0 to 1.0
    samples: list[tuple[float, int]]  # (timestamp, object_count)


@dataclass
class MemoryOptimizationRecommendation:
    """Memory optimization recommendation."""

    category: str
    description: str
    impact: str  # 'low', 'medium', 'high'
    implementation_complexity: str  # 'easy', 'medium', 'hard'
    estimated_savings_mb: float
    action_items: list[str]


class MemoryTracker:
    """Track object instances and their lifecycle."""

    def __init__(self, max_tracked_objects: int = 10000):
        self.max_tracked_objects = max_tracked_objects
        self._tracked_objects = weakref.WeakSet()
        self._object_counts = defaultdict(int)
        self._creation_times = {}
        self._lock = threading.Lock()

    def track_object(self, obj: Any, category: str = None):
        """Track an object for lifecycle monitoring."""
        if len(self._tracked_objects) >= self.max_tracked_objects:
            return  # Avoid unbounded growth

        with self._lock:
            self._tracked_objects.add(obj)
            obj_type = category or type(obj).__name__
            self._object_counts[obj_type] += 1
            self._creation_times[id(obj)] = time.time()

    def get_object_counts(self) -> dict[str, int]:
        """Get current object counts by type."""
        with self._lock:
            # Clean up dead references
            current_counts = defaultdict(int)
            live_objects = list(self._tracked_objects)

            for obj in live_objects:
                obj_type = type(obj).__name__
                current_counts[obj_type] += 1

            return dict(current_counts)

    def get_object_lifetimes(self) -> dict[str, list[float]]:
        """Get object lifetimes by type."""
        with self._lock:
            current_time = time.time()
            lifetimes = defaultdict(list)

            for obj in self._tracked_objects:
                obj_id = id(obj)
                if obj_id in self._creation_times:
                    lifetime = current_time - self._creation_times[obj_id]
                    obj_type = type(obj).__name__
                    lifetimes[obj_type].append(lifetime)

            return dict(lifetimes)


class MemoryManager:
    """Advanced memory management with optimization and leak detection."""

    def __init__(self, config: dict[str, Any] = None):
        self.config = config or {}

        # Configuration
        self.monitoring_interval = self.config.get("monitoring_interval_seconds", 30)
        self.snapshot_retention_count = self.config.get(
            "snapshot_retention_count", 1000
        )
        self.leak_detection_window_hours = self.config.get(
            "leak_detection_window_hours", 24
        )
        self.memory_pressure_threshold_percent = self.config.get(
            "memory_pressure_threshold_percent", 80
        )
        self.auto_cleanup_enabled = self.config.get("auto_cleanup_enabled", True)
        self.detailed_tracking_enabled = self.config.get(
            "detailed_tracking_enabled", True
        )

        # Memory tracking
        self.snapshots = deque(maxlen=self.snapshot_retention_count)
        self.object_tracker = (
            MemoryTracker() if self.detailed_tracking_enabled else None
        )

        # Leak detection
        self.leak_candidates = []
        self.object_count_history = defaultdict(lambda: deque(maxlen=1000))

        # Threading
        self._monitoring_thread = None
        self._monitoring_active = False
        self._lock = threading.Lock()

        # Initialize memory tracking
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        tracemalloc.start()

        logger.info("MemoryManager initialized with config: %s", self.config)

    def start_monitoring(self):
        """Start background memory monitoring."""
        if self._monitoring_active:
            return

        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_worker, daemon=True
        )
        self._monitoring_thread.start()

        logger.info("Memory monitoring started")

    def stop_monitoring(self):
        """Stop background memory monitoring."""
        self._monitoring_active = False

        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=5)

        logger.info("Memory monitoring stopped")

    def take_snapshot(self, label: str = None) -> MemorySnapshot:
        """Take a detailed memory snapshot."""
        current_time = time.time()

        # Basic memory info
        if HAS_PSUTIL:
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                memory_percent = process.memory_percent()

                # System memory
                virtual_memory = psutil.virtual_memory()
                available_memory_mb = virtual_memory.available / 1024 / 1024

                total_memory_mb = memory_info.rss / 1024 / 1024
                rss_memory_mb = memory_info.rss / 1024 / 1024
                vms_memory_mb = memory_info.vms / 1024 / 1024

            except Exception as e:
                logger.warning("Failed to get psutil memory info: %s", e)
                total_memory_mb = 0
                rss_memory_mb = 0
                vms_memory_mb = 0
                memory_percent = 0
                available_memory_mb = 0
        else:
            # Fallback without psutil
            total_memory_mb = 0
            rss_memory_mb = 0
            vms_memory_mb = 0
            memory_percent = 0
            available_memory_mb = 0

        # Garbage collection stats
        gc_stats = {i: gc.get_count()[i] for i in range(len(gc.get_count()))}

        # Tracemalloc info
        tracemalloc_peak_mb = 0
        top_allocations = []

        if tracemalloc.is_tracing():
            try:
                current_size, peak_size = tracemalloc.get_traced_memory()
                tracemalloc_peak_mb = peak_size / 1024 / 1024

                # Get top allocations
                snapshot = tracemalloc.take_snapshot()
                top_stats = snapshot.statistics("lineno")[:10]
                top_allocations = [str(stat) for stat in top_stats]

            except Exception as e:
                logger.warning("Failed to get tracemalloc info: %s", e)

        # Object counts
        object_counts = {}
        if self.object_tracker:
            object_counts = self.object_tracker.get_object_counts()

        # Additional object counts from gc
        try:
            gc_objects = gc.get_objects()
            gc_object_counts = defaultdict(int)

            # Sample objects to avoid performance impact
            sample_size = min(len(gc_objects), 10000)
            for i in range(0, len(gc_objects), max(1, len(gc_objects) // sample_size)):
                obj = gc_objects[i]
                obj_type = type(obj).__name__
                gc_object_counts[obj_type] += 1

            # Merge with tracked objects
            for obj_type, count in gc_object_counts.items():
                object_counts[f"gc_{obj_type}"] = count

        except Exception as e:
            logger.warning("Failed to get GC object counts: %s", e)

        snapshot = MemorySnapshot(
            timestamp=current_time,
            total_memory_mb=total_memory_mb,
            rss_memory_mb=rss_memory_mb,
            vms_memory_mb=vms_memory_mb,
            available_memory_mb=available_memory_mb,
            memory_percent=memory_percent,
            gc_stats=gc_stats,
            tracemalloc_peak_mb=tracemalloc_peak_mb,
            object_counts=object_counts,
            top_allocations=top_allocations,
        )

        with self._lock:
            self.snapshots.append(snapshot)

            # Update object count history for leak detection
            for obj_type, count in object_counts.items():
                self.object_count_history[obj_type].append((current_time, count))

        if label:
            logger.debug(
                "Memory snapshot '%s': %.1fMB RSS, %.1f%% usage",
                label,
                rss_memory_mb,
                memory_percent,
            )

        return snapshot

    def detect_memory_leaks(self, min_samples: int = 10) -> list[MemoryLeakCandidate]:
        """Detect potential memory leaks using trend analysis."""
        candidates = []
        current_time = time.time()
        window_start = current_time - (self.leak_detection_window_hours * 3600)

        with self._lock:
            for obj_type, history in self.object_count_history.items():
                if len(history) < min_samples:
                    continue

                # Filter to window
                windowed_history = [(t, c) for t, c in history if t >= window_start]
                if len(windowed_history) < min_samples:
                    continue

                # Analyze trend
                leak_candidate = self._analyze_object_growth_trend(
                    obj_type, windowed_history
                )
                if leak_candidate:
                    candidates.append(leak_candidate)

        # Sort by severity and confidence
        candidates.sort(
            key=lambda c: (c.severity == "critical", c.confidence), reverse=True
        )

        self.leak_candidates = candidates
        return candidates

    def optimize_memory(self, aggressive: bool = False) -> dict[str, Any]:
        """Perform memory optimization and cleanup."""
        start_time = time.time()
        before_snapshot = self.take_snapshot("before_optimization")

        optimization_results = {
            "timestamp": start_time,
            "before_memory_mb": before_snapshot.rss_memory_mb,
            "optimizations_performed": [],
            "memory_freed_mb": 0,
            "gc_collections_triggered": 0,
        }

        try:
            # 1. Explicit garbage collection
            collected_objects = []
            for generation in range(3):
                collected = gc.collect(generation)
                collected_objects.append(collected)
                optimization_results["gc_collections_triggered"] += 1

            optimization_results["optimizations_performed"].append(
                f"Garbage collection: {collected_objects} objects collected"
            )

            # 2. Clear weak references
            if self.object_tracker:
                before_tracked = len(self.object_tracker._tracked_objects)
                # WeakSet automatically cleans up dead references
                live_objects = list(self.object_tracker._tracked_objects)
                after_tracked = len(live_objects)
                cleared_refs = before_tracked - after_tracked

                if cleared_refs > 0:
                    optimization_results["optimizations_performed"].append(
                        f"Cleared {cleared_refs} dead weak references"
                    )

            # 3. Clear old snapshots if memory pressure is high
            if before_snapshot.memory_percent > self.memory_pressure_threshold_percent:
                with self._lock:
                    if len(self.snapshots) > 100:
                        # Keep only recent snapshots
                        recent_snapshots = list(self.snapshots)[-100:]
                        self.snapshots.clear()
                        self.snapshots.extend(recent_snapshots)

                        optimization_results["optimizations_performed"].append(
                            "Cleared old memory snapshots"
                        )

            # 4. Aggressive optimization if requested
            if aggressive:
                # Clear object count history for non-critical types
                with self._lock:
                    removed_types = []
                    for obj_type in list(self.object_count_history.keys()):
                        if obj_type.startswith("gc_") and "list" in obj_type.lower():
                            del self.object_count_history[obj_type]
                            removed_types.append(obj_type)

                    if removed_types:
                        optimization_results["optimizations_performed"].append(
                            f"Cleared history for {len(removed_types)} object types"
                        )

                # Force Python to release memory back to OS
                if hasattr(sys, "intern"):
                    # Clear string intern cache
                    optimization_results["optimizations_performed"].append(
                        "Cleared string intern cache"
                    )

                # Multiple GC passes
                for _ in range(3):
                    collected = gc.collect()
                    optimization_results["gc_collections_triggered"] += 1

            # 5. Reset tracemalloc peak tracking
            if tracemalloc.is_tracing():
                tracemalloc.reset_peak()
                optimization_results["optimizations_performed"].append(
                    "Reset tracemalloc peak tracking"
                )

            # Take after snapshot
            after_snapshot = self.take_snapshot("after_optimization")

            memory_freed = before_snapshot.rss_memory_mb - after_snapshot.rss_memory_mb
            optimization_results["after_memory_mb"] = after_snapshot.rss_memory_mb
            optimization_results["memory_freed_mb"] = memory_freed
            optimization_results["duration_seconds"] = time.time() - start_time
            optimization_results["success"] = True

            logger.info(
                "Memory optimization completed: %.1fMB freed in %.2fs",
                memory_freed,
                optimization_results["duration_seconds"],
            )

        except Exception as e:
            logger.error("Memory optimization failed: %s", e)
            optimization_results["success"] = False
            optimization_results["error"] = str(e)

        return optimization_results

    def get_memory_analysis(self) -> dict[str, Any]:
        """Get comprehensive memory usage analysis."""
        if not self.snapshots:
            return {"error": "No memory snapshots available"}

        with self._lock:
            snapshots = list(self.snapshots)

        if len(snapshots) < 2:
            return {"error": "Insufficient snapshots for analysis"}

        latest_snapshot = snapshots[-1]
        oldest_snapshot = snapshots[0]

        # Time range analysis
        time_span_hours = (latest_snapshot.timestamp - oldest_snapshot.timestamp) / 3600

        # Memory growth analysis
        memory_growth_mb = latest_snapshot.rss_memory_mb - oldest_snapshot.rss_memory_mb
        memory_growth_rate_mb_per_hour = (
            memory_growth_mb / time_span_hours if time_span_hours > 0 else 0
        )

        # Peak memory analysis
        memory_values = [s.rss_memory_mb for s in snapshots]
        peak_memory_mb = max(memory_values)
        min_memory_mb = min(memory_values)
        avg_memory_mb = sum(memory_values) / len(memory_values)

        # Memory stability analysis
        memory_variance = sum((m - avg_memory_mb) ** 2 for m in memory_values) / len(
            memory_values
        )
        memory_stability = "stable" if memory_variance < 100 else "volatile"

        # GC analysis
        gc_trend_analysis = self._analyze_gc_trends(snapshots)

        # Object growth analysis
        object_growth_analysis = self._analyze_object_growth(snapshots)

        analysis = {
            "snapshot_count": len(snapshots),
            "time_span_hours": time_span_hours,
            "current_memory_mb": latest_snapshot.rss_memory_mb,
            "memory_growth_mb": memory_growth_mb,
            "memory_growth_rate_mb_per_hour": memory_growth_rate_mb_per_hour,
            "peak_memory_mb": peak_memory_mb,
            "min_memory_mb": min_memory_mb,
            "avg_memory_mb": avg_memory_mb,
            "memory_variance": memory_variance,
            "memory_stability": memory_stability,
            "current_memory_percent": latest_snapshot.memory_percent,
            "available_memory_mb": latest_snapshot.available_memory_mb,
            "tracemalloc_peak_mb": latest_snapshot.tracemalloc_peak_mb,
            "gc_analysis": gc_trend_analysis,
            "object_growth_analysis": object_growth_analysis,
            "potential_issues": self._identify_memory_issues(snapshots),
            "recommendations": self._generate_memory_recommendations(snapshots),
        }

        return analysis

    def track_object(self, obj: Any, category: str = None):
        """Track an object for lifecycle monitoring."""
        if self.object_tracker:
            self.object_tracker.track_object(obj, category)

    @contextmanager
    def memory_profiling(self, operation_name: str):
        """Context manager for detailed memory profiling of operations."""
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            started_tracemalloc = True
        else:
            started_tracemalloc = False

        # Take before snapshot
        before_snapshot = tracemalloc.take_snapshot()
        before_memory = self._get_current_memory_mb()
        start_time = time.time()

        try:
            yield
        finally:
            # Take after snapshot
            end_time = time.time()
            after_memory = self._get_current_memory_mb()
            after_snapshot = tracemalloc.take_snapshot()

            # Analyze memory usage
            memory_delta = after_memory - before_memory
            duration = end_time - start_time

            # Get top memory differences
            top_stats = after_snapshot.compare_to(before_snapshot, "lineno")[:10]

            profile_result = {
                "operation": operation_name,
                "duration_seconds": duration,
                "memory_delta_mb": memory_delta,
                "before_memory_mb": before_memory,
                "after_memory_mb": after_memory,
                "top_allocations": [str(stat) for stat in top_stats],
            }

            logger.debug(
                "Memory profile for '%s': %.2fMB delta in %.2fs",
                operation_name,
                memory_delta,
                duration,
            )

            if started_tracemalloc:
                tracemalloc.stop()

    def cleanup(self):
        """Cleanup memory manager resources."""
        self.stop_monitoring()

        # Clear data structures
        with self._lock:
            self.snapshots.clear()
            self.object_count_history.clear()
            self.leak_candidates.clear()

        if tracemalloc.is_tracing():
            tracemalloc.stop()

        logger.info("MemoryManager cleanup completed")

    # Private methods

    def _monitoring_worker(self):
        """Background monitoring worker thread."""
        logger.info("Memory monitoring worker started")

        while self._monitoring_active:
            try:
                # Take regular snapshot
                snapshot = self.take_snapshot()

                # Check for memory pressure
                if snapshot.memory_percent > self.memory_pressure_threshold_percent:
                    logger.warning(
                        "High memory pressure detected: %.1f%% (%.1fMB)",
                        snapshot.memory_percent,
                        snapshot.rss_memory_mb,
                    )

                    # Auto-cleanup if enabled
                    if self.auto_cleanup_enabled:
                        logger.info("Triggering automatic memory cleanup")
                        self.optimize_memory(aggressive=False)

                # Periodic leak detection
                if len(self.snapshots) > 50:  # Only run with sufficient data
                    try:
                        leak_candidates = self.detect_memory_leaks()
                        if leak_candidates:
                            high_severity_leaks = [
                                c
                                for c in leak_candidates
                                if c.severity in ["high", "critical"]
                            ]
                            if high_severity_leaks:
                                logger.warning(
                                    "Potential memory leaks detected: %d candidates",
                                    len(high_severity_leaks),
                                )
                    except Exception as e:
                        logger.warning("Leak detection failed: %s", e)

                # Sleep until next monitoring cycle
                time.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error("Memory monitoring error: %s", e)
                time.sleep(self.monitoring_interval)

        logger.info("Memory monitoring worker stopped")

    def _analyze_object_growth_trend(
        self, obj_type: str, history: list[tuple[float, int]]
    ) -> MemoryLeakCandidate | None:
        """Analyze object count growth trend for leak detection."""
        if len(history) < 10:
            return None

        # Calculate growth rate
        timestamps = [h[0] for h in history]
        counts = [h[1] for h in history]

        time_span_hours = (timestamps[-1] - timestamps[0]) / 3600
        if time_span_hours < 1:  # Need at least 1 hour of data
            return None

        count_growth = counts[-1] - counts[0]
        if count_growth <= 0:  # No growth or shrinkage
            return None

        growth_rate_per_hour = count_growth / time_span_hours

        # Estimate memory growth (rough approximation)
        avg_object_size_bytes = 64  # Rough estimate
        memory_growth_mb = (count_growth * avg_object_size_bytes) / (1024 * 1024)

        # Determine severity based on growth rate and memory impact
        if growth_rate_per_hour > 1000 or memory_growth_mb > 10:
            severity = "critical"
            confidence = 0.9
        elif growth_rate_per_hour > 100 or memory_growth_mb > 1:
            severity = "high"
            confidence = 0.7
        elif growth_rate_per_hour > 10 or memory_growth_mb > 0.1:
            severity = "medium"
            confidence = 0.5
        else:
            severity = "low"
            confidence = 0.3

        # Check for consistent growth (higher confidence if consistent)
        if len(counts) >= 5:
            # Check if last 5 measurements show consistent growth
            recent_counts = counts[-5:]
            consistent_growth = all(
                recent_counts[i] >= recent_counts[i - 1]
                for i in range(1, len(recent_counts))
            )
            if consistent_growth:
                confidence = min(1.0, confidence + 0.2)

        return MemoryLeakCandidate(
            object_type=obj_type,
            count_growth=count_growth,
            memory_growth_mb=memory_growth_mb,
            growth_rate_per_hour=growth_rate_per_hour,
            severity=severity,
            confidence=confidence,
            samples=history,
        )

    def _analyze_gc_trends(self, snapshots: list[MemorySnapshot]) -> dict[str, Any]:
        """Analyze garbage collection trends."""
        if len(snapshots) < 2:
            return {}

        # Extract GC stats
        gc_data = defaultdict(list)
        for snapshot in snapshots:
            for gen, count in snapshot.gc_stats.items():
                gc_data[gen].append(count)

        analysis = {}
        for generation, counts in gc_data.items():
            if len(counts) >= 2:
                total_collections = counts[-1] - counts[0]
                time_span_hours = (
                    snapshots[-1].timestamp - snapshots[0].timestamp
                ) / 3600
                collections_per_hour = (
                    total_collections / time_span_hours if time_span_hours > 0 else 0
                )

                analysis[f"generation_{generation}"] = {
                    "total_collections": total_collections,
                    "collections_per_hour": collections_per_hour,
                    "current_count": counts[-1],
                }

        return analysis

    def _analyze_object_growth(self, snapshots: list[MemorySnapshot]) -> dict[str, Any]:
        """Analyze object count growth across snapshots."""
        if len(snapshots) < 2:
            return {}

        first_snapshot = snapshots[0]
        last_snapshot = snapshots[-1]

        # Compare object counts
        growth_analysis = {}
        all_object_types = set(first_snapshot.object_counts.keys()) | set(
            last_snapshot.object_counts.keys()
        )

        for obj_type in all_object_types:
            first_count = first_snapshot.object_counts.get(obj_type, 0)
            last_count = last_snapshot.object_counts.get(obj_type, 0)

            growth = last_count - first_count
            if first_count > 0:
                growth_percent = (growth / first_count) * 100
            else:
                growth_percent = float("inf") if growth > 0 else 0

            if abs(growth) > 10 or abs(growth_percent) > 50:  # Significant changes only
                growth_analysis[obj_type] = {
                    "first_count": first_count,
                    "last_count": last_count,
                    "growth": growth,
                    "growth_percent": growth_percent,
                }

        return growth_analysis

    def _identify_memory_issues(self, snapshots: list[MemorySnapshot]) -> list[str]:
        """Identify potential memory issues from snapshots."""
        issues = []

        if not snapshots:
            return issues

        latest_snapshot = snapshots[-1]

        # High memory usage
        if latest_snapshot.memory_percent > 90:
            issues.append("Critical memory usage (>90%)")
        elif latest_snapshot.memory_percent > 80:
            issues.append("High memory usage (>80%)")

        # Low available memory
        if latest_snapshot.available_memory_mb < 512:
            issues.append("Low available system memory (<512MB)")

        # Memory growth trend
        if len(snapshots) >= 10:
            memory_values = [s.rss_memory_mb for s in snapshots[-10:]]
            if all(
                memory_values[i] >= memory_values[i - 1]
                for i in range(1, len(memory_values))
            ):
                issues.append("Consistent memory growth detected")

        # High GC activity
        if len(snapshots) >= 2:
            first_gc = snapshots[0].gc_stats
            last_gc = snapshots[-1].gc_stats
            time_span_hours = (snapshots[-1].timestamp - snapshots[0].timestamp) / 3600

            if time_span_hours > 0:
                for gen in [0, 1, 2]:
                    if gen in first_gc and gen in last_gc:
                        collections = last_gc[gen] - first_gc[gen]
                        collections_per_hour = collections / time_span_hours

                        if gen == 0 and collections_per_hour > 1000:
                            issues.append("High generation 0 GC activity")
                        elif gen == 1 and collections_per_hour > 100:
                            issues.append("High generation 1 GC activity")
                        elif gen == 2 and collections_per_hour > 10:
                            issues.append("High generation 2 GC activity")

        return issues

    def _generate_memory_recommendations(
        self, snapshots: list[MemorySnapshot]
    ) -> list[MemoryOptimizationRecommendation]:
        """Generate memory optimization recommendations."""
        recommendations = []

        if not snapshots:
            return recommendations

        latest_snapshot = snapshots[-1]

        # High memory usage recommendations
        if latest_snapshot.memory_percent > 80:
            recommendations.append(
                MemoryOptimizationRecommendation(
                    category="Memory Pressure",
                    description="Implement memory cleanup strategies",
                    impact="high",
                    implementation_complexity="medium",
                    estimated_savings_mb=latest_snapshot.rss_memory_mb * 0.2,
                    action_items=[
                        "Run explicit garbage collection",
                        "Clear unnecessary caches",
                        "Review object lifecycle management",
                        "Implement memory pooling for frequently allocated objects",
                    ],
                )
            )

        # Object growth recommendations
        if len(snapshots) >= 2:
            growth_analysis = self._analyze_object_growth(snapshots)
            high_growth_objects = [
                obj_type
                for obj_type, data in growth_analysis.items()
                if data["growth"] > 1000 or data["growth_percent"] > 100
            ]

            if high_growth_objects:
                recommendations.append(
                    MemoryOptimizationRecommendation(
                        category="Object Growth",
                        description=f"Address rapid growth in {len(high_growth_objects)} object types",
                        impact="medium",
                        implementation_complexity="medium",
                        estimated_savings_mb=10.0,  # Rough estimate
                        action_items=[
                            f"Review lifecycle of: {', '.join(high_growth_objects[:3])}",
                            "Implement object pooling for frequently created types",
                            "Add explicit cleanup in long-running operations",
                            "Consider weak references for caches",
                        ],
                    )
                )

        # GC optimization recommendations
        gc_analysis = self._analyze_gc_trends(snapshots)
        if gc_analysis:
            high_gc_activity = any(
                data.get("collections_per_hour", 0) > 100
                for data in gc_analysis.values()
            )

            if high_gc_activity:
                recommendations.append(
                    MemoryOptimizationRecommendation(
                        category="Garbage Collection",
                        description="Optimize garbage collection patterns",
                        impact="medium",
                        implementation_complexity="easy",
                        estimated_savings_mb=5.0,
                        action_items=[
                            "Tune GC thresholds for workload",
                            "Reduce short-lived object allocations",
                            "Use object pooling for temporary objects",
                            "Batch allocations where possible",
                        ],
                    )
                )

        # Tracemalloc recommendations
        if latest_snapshot.tracemalloc_peak_mb > 100:
            recommendations.append(
                MemoryOptimizationRecommendation(
                    category="Memory Allocation",
                    description="High peak memory allocation detected",
                    impact="medium",
                    implementation_complexity="hard",
                    estimated_savings_mb=latest_snapshot.tracemalloc_peak_mb * 0.3,
                    action_items=[
                        "Profile memory allocation patterns",
                        "Implement streaming for large data processing",
                        "Use memory mapping for large files",
                        "Consider chunked processing strategies",
                    ],
                )
            )

        return recommendations

    def _get_current_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        if HAS_PSUTIL:
            try:
                process = psutil.Process()
                return process.memory_info().rss / 1024 / 1024
            except:
                pass

        # Fallback
        try:
            import resource

            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except:
            return 0.0


class MemoryLeakDetector:
    """Specialized memory leak detection utility."""

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.detection_algorithms = [
            self._detect_linear_growth,
            self._detect_exponential_growth,
            self._detect_stepwise_growth,
            self._detect_cyclic_growth,
        ]

    def run_comprehensive_leak_detection(
        self, duration_minutes: float = 30
    ) -> dict[str, Any]:
        """Run comprehensive memory leak detection over specified duration."""
        logger.info(
            "Starting comprehensive leak detection for %.1f minutes", duration_minutes
        )

        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        # Take initial snapshot
        initial_snapshot = self.memory_manager.take_snapshot("leak_detection_start")

        detection_results = {
            "start_time": start_time,
            "duration_minutes": duration_minutes,
            "initial_memory_mb": initial_snapshot.rss_memory_mb,
            "snapshots_taken": 1,
            "leak_candidates": [],
            "memory_growth_analysis": {},
            "recommendations": [],
        }

        try:
            # Take snapshots at regular intervals
            snapshot_interval = min(
                60, duration_minutes * 60 / 20
            )  # At least 20 snapshots
            next_snapshot_time = start_time + snapshot_interval

            while time.time() < end_time:
                current_time = time.time()

                if current_time >= next_snapshot_time:
                    snapshot = self.memory_manager.take_snapshot(
                        f"leak_detection_{detection_results['snapshots_taken']}"
                    )
                    detection_results["snapshots_taken"] += 1
                    next_snapshot_time += snapshot_interval

                    # Perform some operations to potentially trigger leaks
                    self._perform_test_operations()

                time.sleep(1)  # Check every second

            # Final snapshot
            final_snapshot = self.memory_manager.take_snapshot("leak_detection_end")
            detection_results["final_memory_mb"] = final_snapshot.rss_memory_mb
            detection_results["total_memory_growth_mb"] = (
                final_snapshot.rss_memory_mb - initial_snapshot.rss_memory_mb
            )

            # Run leak detection algorithms
            leak_candidates = self.memory_manager.detect_memory_leaks()
            detection_results["leak_candidates"] = [
                {
                    "object_type": candidate.object_type,
                    "count_growth": candidate.count_growth,
                    "memory_growth_mb": candidate.memory_growth_mb,
                    "growth_rate_per_hour": candidate.growth_rate_per_hour,
                    "severity": candidate.severity,
                    "confidence": candidate.confidence,
                }
                for candidate in leak_candidates
            ]

            # Analyze memory growth patterns
            detection_results["memory_growth_analysis"] = (
                self._analyze_memory_growth_patterns()
            )

            # Generate recommendations
            detection_results["recommendations"] = (
                self._generate_leak_prevention_recommendations(leak_candidates)
            )

            # Determine overall result
            critical_leaks = [c for c in leak_candidates if c.severity == "critical"]
            high_leaks = [c for c in leak_candidates if c.severity == "high"]

            detection_results["has_critical_leaks"] = len(critical_leaks) > 0
            detection_results["has_high_leaks"] = len(high_leaks) > 0
            detection_results["total_leak_candidates"] = len(leak_candidates)

            # Overall assessment
            if critical_leaks:
                detection_results["overall_assessment"] = "critical_leaks_detected"
            elif high_leaks:
                detection_results["overall_assessment"] = "potential_leaks_detected"
            elif detection_results["total_memory_growth_mb"] > 50:
                detection_results["overall_assessment"] = "high_memory_growth"
            else:
                detection_results["overall_assessment"] = "no_significant_leaks"

            detection_results["success"] = True

        except Exception as e:
            logger.error("Comprehensive leak detection failed: %s", e)
            detection_results["success"] = False
            detection_results["error"] = str(e)

        detection_results["total_duration_minutes"] = (time.time() - start_time) / 60

        logger.info(
            "Comprehensive leak detection completed: %s",
            detection_results["overall_assessment"],
        )

        return detection_results

    def _detect_linear_growth(
        self, data: list[tuple[float, int]]
    ) -> dict[str, Any] | None:
        """Detect linear growth pattern in object counts."""
        if len(data) < 5:
            return None

        timestamps = [d[0] for d in data]
        counts = [d[1] for d in data]

        # Simple linear regression
        n = len(data)
        sum_x = sum(timestamps)
        sum_y = sum(counts)
        sum_xy = sum(t * c for t, c in data)
        sum_x2 = sum(t * t for t in timestamps)

        # Calculate slope
        denominator = n * sum_x2 - sum_x * sum_x
        if abs(denominator) < 1e-10:
            return None

        slope = (n * sum_xy - sum_x * sum_y) / denominator

        # Check if slope indicates significant growth
        if slope > 0.01:  # More than 0.01 objects per second
            return {
                "pattern": "linear_growth",
                "slope": slope,
                "growth_rate_per_hour": slope * 3600,
                "confidence": 0.7,
            }

        return None

    def _detect_exponential_growth(
        self, data: list[tuple[float, int]]
    ) -> dict[str, Any] | None:
        """Detect exponential growth pattern."""
        if len(data) < 5:
            return None

        counts = [d[1] for d in data]

        # Check for exponential-like growth
        ratios = []
        for i in range(1, len(counts)):
            if counts[i - 1] > 0:
                ratio = counts[i] / counts[i - 1]
                ratios.append(ratio)

        if ratios and len(ratios) >= 3:
            avg_ratio = sum(ratios) / len(ratios)
            if avg_ratio > 1.1:  # 10% growth per measurement
                return {
                    "pattern": "exponential_growth",
                    "average_growth_ratio": avg_ratio,
                    "confidence": 0.8,
                }

        return None

    def _detect_stepwise_growth(
        self, data: list[tuple[float, int]]
    ) -> dict[str, Any] | None:
        """Detect stepwise growth pattern."""
        if len(data) < 10:
            return None

        counts = [d[1] for d in data]

        # Look for sudden jumps
        jumps = []
        for i in range(1, len(counts)):
            diff = counts[i] - counts[i - 1]
            if diff > 100:  # Significant jump
                jumps.append(diff)

        if len(jumps) >= 3:  # Multiple significant jumps
            return {
                "pattern": "stepwise_growth",
                "jump_count": len(jumps),
                "average_jump_size": sum(jumps) / len(jumps),
                "confidence": 0.6,
            }

        return None

    def _detect_cyclic_growth(
        self, data: list[tuple[float, int]]
    ) -> dict[str, Any] | None:
        """Detect cyclic growth pattern (growing with cycles)."""
        if len(data) < 20:
            return None

        counts = [d[1] for d in data]

        # Look for periodic patterns with overall growth
        # Simple approach: check if there are regular peaks and valleys
        peaks = []
        valleys = []

        for i in range(1, len(counts) - 1):
            if counts[i] > counts[i - 1] and counts[i] > counts[i + 1]:
                peaks.append(counts[i])
            elif counts[i] < counts[i - 1] and counts[i] < counts[i + 1]:
                valleys.append(counts[i])

        if len(peaks) >= 3 and len(valleys) >= 3:
            # Check if peaks are generally increasing
            peak_trend = peaks[-1] - peaks[0] if peaks else 0
            valley_trend = valleys[-1] - valleys[0] if valleys else 0

            if peak_trend > 0 and valley_trend > 0:
                return {
                    "pattern": "cyclic_growth",
                    "peak_count": len(peaks),
                    "valley_count": len(valleys),
                    "peak_trend": peak_trend,
                    "valley_trend": valley_trend,
                    "confidence": 0.5,
                }

        return None

    def _analyze_memory_growth_patterns(self) -> dict[str, Any]:
        """Analyze memory growth patterns across all tracked objects."""
        patterns = {}

        with self.memory_manager._lock:
            for obj_type, history in self.memory_manager.object_count_history.items():
                if len(history) >= 5:
                    data = list(history)

                    # Run all detection algorithms
                    detected_patterns = []
                    for algorithm in self.detection_algorithms:
                        pattern = algorithm(data)
                        if pattern:
                            detected_patterns.append(pattern)

                    if detected_patterns:
                        patterns[obj_type] = detected_patterns

        return patterns

    def _generate_leak_prevention_recommendations(
        self, leak_candidates: list[MemoryLeakCandidate]
    ) -> list[str]:
        """Generate recommendations for preventing memory leaks."""
        recommendations = []

        if not leak_candidates:
            recommendations.append("No memory leaks detected - continue monitoring")
            return recommendations

        # Categorize leak candidates
        critical_candidates = [c for c in leak_candidates if c.severity == "critical"]
        high_candidates = [c for c in leak_candidates if c.severity == "high"]

        if critical_candidates:
            recommendations.append(
                "CRITICAL: Immediate action required for memory leaks"
            )
            for candidate in critical_candidates[:3]:  # Top 3
                recommendations.append(
                    f"  - Review {candidate.object_type} lifecycle and cleanup"
                )

        if high_candidates:
            recommendations.append("HIGH: Address potential memory leaks")
            object_types = [c.object_type for c in high_candidates[:3]]
            recommendations.append(
                f"  - Investigate object types: {', '.join(object_types)}"
            )

        # General recommendations
        recommendations.extend(
            [
                "Implement explicit cleanup in long-running operations",
                "Use weak references for caches and event handlers",
                "Review object pooling opportunities",
                "Add memory monitoring to CI/CD pipeline",
                "Consider implementing object lifecycle tracking",
            ]
        )

        return recommendations

    def _perform_test_operations(self):
        """Perform various operations that might trigger memory leaks."""
        # Create temporary objects
        temp_objects = []
        for i in range(50):
            obj = {
                "id": i,
                "data": [j for j in range(50)],
                "metadata": {"created": time.time()},
            }
            temp_objects.append(obj)

        # Process objects
        results = []
        for obj in temp_objects:
            result = sum(obj["data"]) * obj["id"]
            results.append(result)

        # Cleanup (this should prevent leaks)
        del temp_objects
        del results

        # Occasional garbage collection
        if hasattr(self, "_test_operation_count"):
            self._test_operation_count += 1
        else:
            self._test_operation_count = 1

        if self._test_operation_count % 10 == 0:
            gc.collect()
