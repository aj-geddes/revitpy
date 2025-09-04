"""
Real-time Performance Monitoring and Alerting System for RevitPy

Provides comprehensive real-time performance monitoring:
- Real-time metrics collection and analysis
- Performance threshold monitoring and alerting
- Automated performance regression detection
- Performance dashboard data provision
- Historical performance trend analysis
- Predictive performance analytics
"""

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Set
from datetime import datetime, timedelta
import statistics

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger(__name__)

@dataclass
class PerformanceThreshold:
    """Performance threshold configuration."""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison_operator: str = ">"  # >, <, >=, <=, ==, !=
    evaluation_window_seconds: int = 60
    min_samples: int = 3
    enabled: bool = True

@dataclass
class PerformanceAlert:
    """Performance alert data."""
    id: str
    timestamp: float
    metric_name: str
    current_value: float
    threshold_value: float
    severity: str  # 'warning', 'critical'
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False
    resolution_timestamp: Optional[float] = None

@dataclass
class MetricSnapshot:
    """Single metric measurement snapshot."""
    timestamp: float
    metric_name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceTrend:
    """Performance trend analysis result."""
    metric_name: str
    trend_direction: str  # 'improving', 'degrading', 'stable'
    trend_strength: float  # 0.0 to 1.0
    average_change_rate: float
    samples_analyzed: int
    time_period_hours: float
    confidence: float  # 0.0 to 1.0

class MetricsCollector:
    """High-performance metrics collection system."""
    
    def __init__(self, buffer_size: int = 10000):
        self.buffer_size = buffer_size
        self.metrics_buffer = deque(maxlen=buffer_size)
        self.metric_aggregates = defaultdict(lambda: deque(maxlen=1000))
        self.collection_callbacks = []
        self._lock = threading.Lock()
        self._collection_active = False
        self._collection_thread = None
        self.collection_interval = 1.0  # seconds
        
    def start_collection(self):
        """Start background metrics collection."""
        if self._collection_active:
            return
        
        self._collection_active = True
        self._collection_thread = threading.Thread(target=self._collection_worker, daemon=True)
        self._collection_thread.start()
        
        logger.info("Metrics collection started")
    
    def stop_collection(self):
        """Stop background metrics collection."""
        self._collection_active = False
        
        if self._collection_thread and self._collection_thread.is_alive():
            self._collection_thread.join(timeout=5)
        
        logger.info("Metrics collection stopped")
    
    def record_metric(self, metric_name: str, value: float, 
                     tags: Dict[str, str] = None, context: Dict[str, Any] = None):
        """Record a single metric measurement."""
        snapshot = MetricSnapshot(
            timestamp=time.time(),
            metric_name=metric_name,
            value=value,
            tags=tags or {},
            context=context or {}
        )
        
        with self._lock:
            self.metrics_buffer.append(snapshot)
            self.metric_aggregates[metric_name].append(snapshot)
    
    def record_metrics_batch(self, metrics: List[Dict[str, Any]]):
        """Record multiple metrics efficiently."""
        current_time = time.time()
        snapshots = []
        
        for metric in metrics:
            snapshot = MetricSnapshot(
                timestamp=current_time,
                metric_name=metric['name'],
                value=metric['value'],
                tags=metric.get('tags', {}),
                context=metric.get('context', {})
            )
            snapshots.append(snapshot)
        
        with self._lock:
            self.metrics_buffer.extend(snapshots)
            for snapshot in snapshots:
                self.metric_aggregates[snapshot.metric_name].append(snapshot)
    
    def get_metric_history(self, metric_name: str, 
                          time_window_seconds: int = 3600) -> List[MetricSnapshot]:
        """Get metric history for specified time window."""
        cutoff_time = time.time() - time_window_seconds
        
        with self._lock:
            metric_data = self.metric_aggregates.get(metric_name, [])
            return [m for m in metric_data if m.timestamp >= cutoff_time]
    
    def get_metric_statistics(self, metric_name: str, 
                            time_window_seconds: int = 3600) -> Dict[str, float]:
        """Get statistical summary for a metric."""
        history = self.get_metric_history(metric_name, time_window_seconds)
        
        if not history:
            return {}
        
        values = [m.value for m in history]
        
        stats = {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'std_dev': statistics.stdev(values) if len(values) > 1 else 0.0
        }
        
        # Add percentiles
        sorted_values = sorted(values)
        n = len(sorted_values)
        if n > 0:
            stats['p50'] = sorted_values[n // 2]
            stats['p90'] = sorted_values[int(n * 0.9)] if n > 0 else 0
            stats['p95'] = sorted_values[int(n * 0.95)] if n > 0 else 0
            stats['p99'] = sorted_values[int(n * 0.99)] if n > 0 else 0
        
        return stats
    
    def add_collection_callback(self, callback: Callable[[], List[Dict[str, Any]]]):
        """Add a callback function for custom metrics collection."""
        self.collection_callbacks.append(callback)
    
    def _collection_worker(self):
        """Background worker for automatic metrics collection."""
        logger.info("Metrics collection worker started")
        
        while self._collection_active:
            try:
                start_time = time.time()
                
                # Collect system metrics
                system_metrics = self._collect_system_metrics()
                if system_metrics:
                    self.record_metrics_batch(system_metrics)
                
                # Run custom collection callbacks
                for callback in self.collection_callbacks:
                    try:
                        custom_metrics = callback()
                        if custom_metrics:
                            self.record_metrics_batch(custom_metrics)
                    except Exception as e:
                        logger.warning("Custom metrics collection callback failed: %s", e)
                
                # Sleep to maintain collection interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.collection_interval - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error("Metrics collection error: %s", e)
                time.sleep(self.collection_interval)
        
        logger.info("Metrics collection worker stopped")
    
    def _collect_system_metrics(self) -> List[Dict[str, Any]]:
        """Collect standard system performance metrics."""
        metrics = []
        current_time = time.time()
        
        if HAS_PSUTIL:
            try:
                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=None)
                metrics.append({
                    'name': 'system.cpu.percent',
                    'value': cpu_percent,
                    'tags': {'host': 'local'}
                })
                
                # Memory metrics
                memory = psutil.virtual_memory()
                metrics.extend([
                    {
                        'name': 'system.memory.percent',
                        'value': memory.percent,
                        'tags': {'host': 'local'}
                    },
                    {
                        'name': 'system.memory.available_mb',
                        'value': memory.available / 1024 / 1024,
                        'tags': {'host': 'local'}
                    },
                    {
                        'name': 'system.memory.used_mb',
                        'value': memory.used / 1024 / 1024,
                        'tags': {'host': 'local'}
                    }
                ])
                
                # Process metrics
                process = psutil.Process()
                process_memory = process.memory_info()
                
                metrics.extend([
                    {
                        'name': 'process.memory.rss_mb',
                        'value': process_memory.rss / 1024 / 1024,
                        'tags': {'process': 'revitpy'}
                    },
                    {
                        'name': 'process.memory.vms_mb',
                        'value': process_memory.vms / 1024 / 1024,
                        'tags': {'process': 'revitpy'}
                    },
                    {
                        'name': 'process.cpu.percent',
                        'value': process.cpu_percent(),
                        'tags': {'process': 'revitpy'}
                    }
                ])
                
                # Disk I/O metrics
                disk_io = process.io_counters()
                metrics.extend([
                    {
                        'name': 'process.io.read_bytes',
                        'value': disk_io.read_bytes,
                        'tags': {'process': 'revitpy', 'type': 'read'}
                    },
                    {
                        'name': 'process.io.write_bytes',
                        'value': disk_io.write_bytes,
                        'tags': {'process': 'revitpy', 'type': 'write'}
                    }
                ])
                
            except Exception as e:
                logger.warning("Failed to collect system metrics: %s", e)
        
        return metrics

class AlertingSystem:
    """Performance alerting and notification system."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.thresholds: Dict[str, PerformanceThreshold] = {}
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.alert_history = deque(maxlen=1000)
        self.alert_callbacks = []
        
        # Alerting configuration
        self.evaluation_interval = 30  # seconds
        self._alerting_active = False
        self._alerting_thread = None
        self._lock = threading.Lock()
        
        # Initialize default thresholds
        self._initialize_default_thresholds()
    
    def start_alerting(self):
        """Start background alerting system."""
        if self._alerting_active:
            return
        
        self._alerting_active = True
        self._alerting_thread = threading.Thread(target=self._alerting_worker, daemon=True)
        self._alerting_thread.start()
        
        logger.info("Alerting system started")
    
    def stop_alerting(self):
        """Stop background alerting system."""
        self._alerting_active = False
        
        if self._alerting_thread and self._alerting_thread.is_alive():
            self._alerting_thread.join(timeout=5)
        
        logger.info("Alerting system stopped")
    
    def add_threshold(self, threshold: PerformanceThreshold):
        """Add or update a performance threshold."""
        with self._lock:
            self.thresholds[threshold.metric_name] = threshold
        
        logger.info("Added threshold for %s: %s %s (warning: %s, critical: %s)",
                   threshold.metric_name, threshold.comparison_operator,
                   threshold.critical_threshold, threshold.warning_threshold,
                   threshold.critical_threshold)
    
    def remove_threshold(self, metric_name: str):
        """Remove a performance threshold."""
        with self._lock:
            if metric_name in self.thresholds:
                del self.thresholds[metric_name]
                logger.info("Removed threshold for %s", metric_name)
    
    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """Add callback for alert notifications."""
        self.alert_callbacks.append(callback)
    
    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an active alert."""
        with self._lock:
            if alert_id in self.active_alerts:
                self.active_alerts[alert_id].acknowledged = True
                logger.info("Alert %s acknowledged", alert_id)
    
    def resolve_alert(self, alert_id: str):
        """Resolve an active alert."""
        with self._lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved = True
                alert.resolution_timestamp = time.time()
                
                # Move to history
                self.alert_history.append(alert)
                del self.active_alerts[alert_id]
                
                logger.info("Alert %s resolved", alert_id)
    
    def get_active_alerts(self) -> List[PerformanceAlert]:
        """Get all active alerts."""
        with self._lock:
            return list(self.active_alerts.values())
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of alert status."""
        with self._lock:
            active_alerts = list(self.active_alerts.values())
            
            summary = {
                'total_active_alerts': len(active_alerts),
                'critical_alerts': len([a for a in active_alerts if a.severity == 'critical']),
                'warning_alerts': len([a for a in active_alerts if a.severity == 'warning']),
                'unacknowledged_alerts': len([a for a in active_alerts if not a.acknowledged]),
                'recent_alerts_24h': len([a for a in self.alert_history 
                                        if time.time() - a.timestamp < 86400]),
                'alert_rate_per_hour': 0
            }
            
            # Calculate alert rate
            if self.alert_history:
                recent_alerts = [a for a in self.alert_history 
                               if time.time() - a.timestamp < 86400]
                if recent_alerts:
                    summary['alert_rate_per_hour'] = len(recent_alerts) / 24
            
            return summary
    
    def _initialize_default_thresholds(self):
        """Initialize default performance thresholds."""
        default_thresholds = [
            PerformanceThreshold(
                metric_name="system.cpu.percent",
                warning_threshold=80.0,
                critical_threshold=90.0,
                comparison_operator=">",
                evaluation_window_seconds=120
            ),
            PerformanceThreshold(
                metric_name="system.memory.percent",
                warning_threshold=80.0,
                critical_threshold=90.0,
                comparison_operator=">",
                evaluation_window_seconds=180
            ),
            PerformanceThreshold(
                metric_name="process.memory.rss_mb",
                warning_threshold=400.0,
                critical_threshold=500.0,
                comparison_operator=">",
                evaluation_window_seconds=300
            ),
            PerformanceThreshold(
                metric_name="api.latency.p95_ms",
                warning_threshold=100.0,
                critical_threshold=500.0,
                comparison_operator=">",
                evaluation_window_seconds=300
            ),
            PerformanceThreshold(
                metric_name="system.memory.available_mb",
                warning_threshold=512.0,
                critical_threshold=256.0,
                comparison_operator="<",
                evaluation_window_seconds=300
            )
        ]
        
        for threshold in default_thresholds:
            self.add_threshold(threshold)
    
    def _alerting_worker(self):
        """Background worker for alert evaluation."""
        logger.info("Alerting worker started")
        
        while self._alerting_active:
            try:
                start_time = time.time()
                
                # Evaluate all thresholds
                with self._lock:
                    thresholds_to_evaluate = list(self.thresholds.values())
                
                for threshold in thresholds_to_evaluate:
                    if threshold.enabled:
                        self._evaluate_threshold(threshold)
                
                # Check for auto-resolution of alerts
                self._check_alert_auto_resolution()
                
                # Sleep until next evaluation
                elapsed = time.time() - start_time
                sleep_time = max(0, self.evaluation_interval - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error("Alerting evaluation error: %s", e)
                time.sleep(self.evaluation_interval)
        
        logger.info("Alerting worker stopped")
    
    def _evaluate_threshold(self, threshold: PerformanceThreshold):
        """Evaluate a single threshold for alerting."""
        # Get recent metric data
        history = self.metrics_collector.get_metric_history(
            threshold.metric_name, 
            threshold.evaluation_window_seconds
        )
        
        if len(history) < threshold.min_samples:
            return  # Not enough data
        
        # Calculate average value over evaluation window
        values = [m.value for m in history]
        avg_value = statistics.mean(values)
        
        # Evaluate threshold
        alert_triggered = self._evaluate_condition(
            avg_value, 
            threshold.warning_threshold,
            threshold.comparison_operator
        )
        
        critical_triggered = self._evaluate_condition(
            avg_value,
            threshold.critical_threshold,
            threshold.comparison_operator
        )
        
        alert_id = f"{threshold.metric_name}_threshold"
        
        with self._lock:
            existing_alert = self.active_alerts.get(alert_id)
            
            if critical_triggered:
                severity = 'critical'
                threshold_value = threshold.critical_threshold
            elif alert_triggered:
                severity = 'warning'
                threshold_value = threshold.warning_threshold
            else:
                # No alert condition - resolve if exists
                if existing_alert:
                    self.resolve_alert(alert_id)
                return
            
            if not existing_alert or existing_alert.severity != severity:
                # Create new alert or update severity
                alert = PerformanceAlert(
                    id=alert_id,
                    timestamp=time.time(),
                    metric_name=threshold.metric_name,
                    current_value=avg_value,
                    threshold_value=threshold_value,
                    severity=severity,
                    message=f"{threshold.metric_name} {threshold.comparison_operator} {threshold_value} (current: {avg_value:.2f})",
                    context={
                        'evaluation_window_seconds': threshold.evaluation_window_seconds,
                        'samples_count': len(values),
                        'min_value': min(values),
                        'max_value': max(values)
                    }
                )
                
                self.active_alerts[alert_id] = alert
                
                # Notify callbacks
                for callback in self.alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        logger.warning("Alert callback failed: %s", e)
                
                logger.warning("Alert triggered: %s", alert.message)
    
    def _evaluate_condition(self, value: float, threshold: float, operator: str) -> bool:
        """Evaluate threshold condition."""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return abs(value - threshold) < 1e-6
        elif operator == "!=":
            return abs(value - threshold) >= 1e-6
        else:
            logger.warning("Unknown comparison operator: %s", operator)
            return False
    
    def _check_alert_auto_resolution(self):
        """Check if any alerts should be auto-resolved."""
        current_time = time.time()
        auto_resolve_window = 300  # 5 minutes
        
        with self._lock:
            alerts_to_resolve = []
            
            for alert_id, alert in self.active_alerts.items():
                # Check if metric is now within threshold
                threshold = self.thresholds.get(alert.metric_name)
                if not threshold:
                    continue
                
                # Get recent data
                history = self.metrics_collector.get_metric_history(
                    alert.metric_name, 
                    auto_resolve_window
                )
                
                if len(history) >= 3:  # Need some recent data
                    values = [m.value for m in history]
                    avg_value = statistics.mean(values)
                    
                    # Check if within both warning and critical thresholds
                    warning_ok = not self._evaluate_condition(
                        avg_value, threshold.warning_threshold, threshold.comparison_operator
                    )
                    critical_ok = not self._evaluate_condition(
                        avg_value, threshold.critical_threshold, threshold.comparison_operator
                    )
                    
                    if warning_ok and critical_ok:
                        alerts_to_resolve.append(alert_id)
            
            # Resolve alerts
            for alert_id in alerts_to_resolve:
                self.resolve_alert(alert_id)

class PerformanceMonitor:
    """Main performance monitoring system coordinator."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Initialize components
        self.metrics_collector = MetricsCollector(
            buffer_size=self.config.get('metrics_buffer_size', 10000)
        )
        
        self.alerting_system = AlertingSystem(self.metrics_collector)
        
        # Performance optimization integration
        self.performance_optimizer = None
        
        # Trend analysis
        self.trend_analysis_interval = self.config.get('trend_analysis_interval_seconds', 3600)
        self.trend_history = defaultdict(lambda: deque(maxlen=100))
        
        # Dashboard data
        self.dashboard_data = {}
        self.dashboard_update_interval = 30  # seconds
        
        # Monitoring state
        self._monitoring_active = False
        self._trend_analysis_thread = None
        self._dashboard_update_thread = None
        
        logger.info("PerformanceMonitor initialized")
    
    def start_monitoring(self, performance_optimizer=None):
        """Start comprehensive performance monitoring."""
        if self._monitoring_active:
            return
        
        self.performance_optimizer = performance_optimizer
        self._monitoring_active = True
        
        # Start components
        self.metrics_collector.start_collection()
        self.alerting_system.start_alerting()
        
        # Start background threads
        self._trend_analysis_thread = threading.Thread(
            target=self._trend_analysis_worker, daemon=True
        )
        self._trend_analysis_thread.start()
        
        self._dashboard_update_thread = threading.Thread(
            target=self._dashboard_update_worker, daemon=True
        )
        self._dashboard_update_thread.start()
        
        # Add performance optimizer metrics collection
        if self.performance_optimizer:
            self.metrics_collector.add_collection_callback(
                self._collect_optimizer_metrics
            )
        
        # Setup alert notifications
        self.alerting_system.add_alert_callback(self._handle_performance_alert)
        
        logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self._monitoring_active = False
        
        # Stop components
        self.metrics_collector.stop_collection()
        self.alerting_system.stop_alerting()
        
        # Wait for threads
        for thread in [self._trend_analysis_thread, self._dashboard_update_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=5)
        
        logger.info("Performance monitoring stopped")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get current dashboard data."""
        return self.dashboard_data.copy()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        current_time = time.time()
        
        # Get alert summary
        alert_summary = self.alerting_system.get_alert_summary()
        
        # Get key metric statistics
        key_metrics = [
            'system.cpu.percent',
            'system.memory.percent', 
            'process.memory.rss_mb',
            'api.latency.avg_ms',
            'api.latency.p95_ms'
        ]
        
        metric_stats = {}
        for metric in key_metrics:
            stats = self.metrics_collector.get_metric_statistics(metric, 3600)
            if stats:
                metric_stats[metric] = stats
        
        # Get recent trends
        recent_trends = {}
        for metric in key_metrics:
            trend = self._calculate_trend(metric, 24)  # 24 hour trend
            if trend:
                recent_trends[metric] = {
                    'direction': trend.trend_direction,
                    'strength': trend.trend_strength,
                    'confidence': trend.confidence
                }
        
        # Overall health assessment
        health_score = self._calculate_health_score(alert_summary, metric_stats)
        
        summary = {
            'timestamp': current_time,
            'health_score': health_score,
            'alert_summary': alert_summary,
            'key_metrics': metric_stats,
            'trends': recent_trends,
            'monitoring_uptime_hours': self._get_monitoring_uptime_hours(),
            'recommendations': self._generate_performance_recommendations(
                alert_summary, metric_stats, recent_trends
            )
        }
        
        return summary
    
    def analyze_performance_trends(self, time_window_hours: int = 24) -> Dict[str, PerformanceTrend]:
        """Analyze performance trends over specified time window."""
        trends = {}
        
        # Get all metrics that have enough data
        metric_names = set()
        for snapshot in self.metrics_collector.metrics_buffer:
            metric_names.add(snapshot.metric_name)
        
        for metric_name in metric_names:
            trend = self._calculate_trend(metric_name, time_window_hours)
            if trend:
                trends[metric_name] = trend
        
        return trends
    
    def predict_performance_issues(self, prediction_hours: int = 24) -> List[Dict[str, Any]]:
        """Predict potential performance issues based on trends."""
        predictions = []
        
        # Analyze trends for prediction
        trends = self.analyze_performance_trends(time_window_hours=72)  # Use 72h for prediction
        
        for metric_name, trend in trends.items():
            if trend.trend_direction == 'degrading' and trend.confidence > 0.7:
                # Get current value and threshold
                current_stats = self.metrics_collector.get_metric_statistics(metric_name, 3600)
                threshold = self.alerting_system.thresholds.get(metric_name)
                
                if current_stats and threshold:
                    current_value = current_stats['mean']
                    
                    # Predict when threshold might be reached
                    if trend.average_change_rate != 0:
                        if threshold.comparison_operator == ">":
                            threshold_value = threshold.warning_threshold
                            hours_to_threshold = (threshold_value - current_value) / trend.average_change_rate
                        elif threshold.comparison_operator == "<":
                            threshold_value = threshold.warning_threshold
                            hours_to_threshold = (current_value - threshold_value) / abs(trend.average_change_rate)
                        else:
                            continue
                        
                        if 0 < hours_to_threshold <= prediction_hours:
                            predictions.append({
                                'metric_name': metric_name,
                                'predicted_issue': 'threshold_breach',
                                'hours_to_issue': hours_to_threshold,
                                'current_value': current_value,
                                'threshold_value': threshold_value,
                                'confidence': trend.confidence,
                                'recommended_action': f"Monitor {metric_name} closely and consider optimization"
                            })
        
        # Sort by urgency (hours to issue)
        predictions.sort(key=lambda p: p['hours_to_issue'])
        
        return predictions
    
    def _collect_optimizer_metrics(self) -> List[Dict[str, Any]]:
        """Collect metrics from performance optimizer."""
        if not self.performance_optimizer:
            return []
        
        try:
            optimizer_metrics = self.performance_optimizer.get_performance_metrics()
            
            metrics = []
            current_time = time.time()
            
            # Convert optimizer metrics to collector format
            metric_mappings = {
                'total_operations': 'optimizer.operations.total',
                'operations_per_second': 'optimizer.operations.per_second',
                'average_latency_ms': 'optimizer.latency.avg_ms',
                'memory_usage_mb': 'optimizer.memory.usage_mb',
                'cache_hit_ratio': 'optimizer.cache.hit_ratio',
                'pool_hit_ratio': 'optimizer.pool.hit_ratio'
            }
            
            for source_key, metric_name in metric_mappings.items():
                if source_key in optimizer_metrics:
                    metrics.append({
                        'name': metric_name,
                        'value': optimizer_metrics[source_key],
                        'tags': {'component': 'optimizer'}
                    })
            
            # Add operation-specific latencies
            operation_latencies = optimizer_metrics.get('operation_latencies', {})
            for op_name, latency_stats in operation_latencies.items():
                metrics.append({
                    'name': 'optimizer.operation.latency.avg_ms',
                    'value': latency_stats.get('avg_ms', 0),
                    'tags': {'component': 'optimizer', 'operation': op_name}
                })
                
                metrics.append({
                    'name': 'optimizer.operation.latency.p95_ms',
                    'value': latency_stats.get('p95_ms', 0),
                    'tags': {'component': 'optimizer', 'operation': op_name}
                })
            
            return metrics
            
        except Exception as e:
            logger.warning("Failed to collect optimizer metrics: %s", e)
            return []
    
    def _handle_performance_alert(self, alert: PerformanceAlert):
        """Handle performance alerts with potential auto-remediation."""
        logger.warning("Performance alert: %s", alert.message)
        
        # Auto-remediation for specific alerts
        if alert.metric_name == 'process.memory.rss_mb' and alert.severity == 'critical':
            if self.performance_optimizer:
                logger.info("Triggering automatic memory optimization for critical memory alert")
                try:
                    self.performance_optimizer.optimize_memory()
                except Exception as e:
                    logger.error("Auto-remediation failed: %s", e)
        
        elif alert.metric_name == 'system.cpu.percent' and alert.severity == 'critical':
            # Could trigger CPU-intensive operation throttling
            logger.info("High CPU usage detected - consider operation throttling")
    
    def _trend_analysis_worker(self):
        """Background worker for trend analysis."""
        logger.info("Trend analysis worker started")
        
        while self._monitoring_active:
            try:
                start_time = time.time()
                
                # Perform trend analysis for key metrics
                key_metrics = [
                    'system.cpu.percent',
                    'system.memory.percent',
                    'process.memory.rss_mb',
                    'optimizer.latency.avg_ms',
                    'optimizer.cache.hit_ratio'
                ]
                
                for metric_name in key_metrics:
                    trend = self._calculate_trend(metric_name, 24)  # 24 hour trend
                    if trend:
                        self.trend_history[metric_name].append(trend)
                
                # Sleep until next analysis
                elapsed = time.time() - start_time
                sleep_time = max(0, self.trend_analysis_interval - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error("Trend analysis error: %s", e)
                time.sleep(self.trend_analysis_interval)
        
        logger.info("Trend analysis worker stopped")
    
    def _dashboard_update_worker(self):
        """Background worker for dashboard data updates."""
        logger.info("Dashboard update worker started")
        
        while self._monitoring_active:
            try:
                start_time = time.time()
                
                # Update dashboard data
                self.dashboard_data = self._generate_dashboard_data()
                
                # Sleep until next update
                elapsed = time.time() - start_time
                sleep_time = max(0, self.dashboard_update_interval - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error("Dashboard update error: %s", e)
                time.sleep(self.dashboard_update_interval)
        
        logger.info("Dashboard update worker stopped")
    
    def _generate_dashboard_data(self) -> Dict[str, Any]:
        """Generate real-time dashboard data."""
        current_time = time.time()
        
        # Key metrics for dashboard
        key_metrics = {}
        metric_names = [
            'system.cpu.percent',
            'system.memory.percent',
            'process.memory.rss_mb',
            'process.cpu.percent',
            'optimizer.operations.per_second',
            'optimizer.latency.avg_ms',
            'optimizer.cache.hit_ratio'
        ]
        
        for metric_name in metric_names:
            stats = self.metrics_collector.get_metric_statistics(metric_name, 300)  # 5 min window
            if stats:
                key_metrics[metric_name] = {
                    'current': stats['mean'],
                    'min': stats['min'],
                    'max': stats['max'],
                    'trend': self._get_short_term_trend(metric_name)
                }
        
        # Recent metric history for charts (last hour)
        metric_history = {}
        for metric_name in metric_names:
            history = self.metrics_collector.get_metric_history(metric_name, 3600)
            if history:
                # Sample data points for chart (max 60 points)
                if len(history) > 60:
                    step = len(history) // 60
                    sampled_history = history[::step]
                else:
                    sampled_history = history
                
                metric_history[metric_name] = [
                    {'timestamp': m.timestamp, 'value': m.value}
                    for m in sampled_history
                ]
        
        # Alert information
        alert_summary = self.alerting_system.get_alert_summary()
        active_alerts = [
            {
                'id': alert.id,
                'metric': alert.metric_name,
                'severity': alert.severity,
                'message': alert.message,
                'timestamp': alert.timestamp,
                'acknowledged': alert.acknowledged
            }
            for alert in self.alerting_system.get_active_alerts()
        ]
        
        # Performance health score
        health_score = self._calculate_health_score(alert_summary, key_metrics)
        
        return {
            'timestamp': current_time,
            'health_score': health_score,
            'key_metrics': key_metrics,
            'metric_history': metric_history,
            'alert_summary': alert_summary,
            'active_alerts': active_alerts,
            'uptime_hours': self._get_monitoring_uptime_hours()
        }
    
    def _calculate_trend(self, metric_name: str, time_window_hours: int) -> Optional[PerformanceTrend]:
        """Calculate trend for a specific metric."""
        window_seconds = time_window_hours * 3600
        history = self.metrics_collector.get_metric_history(metric_name, window_seconds)
        
        if len(history) < 10:  # Need minimum data points
            return None
        
        # Extract timestamps and values
        timestamps = [m.timestamp for m in history]
        values = [m.value for m in history]
        
        # Simple linear regression for trend
        n = len(history)
        sum_x = sum(timestamps)
        sum_y = sum(values)
        sum_xy = sum(t * v for t, v in zip(timestamps, values))
        sum_x2 = sum(t * t for t in timestamps)
        
        # Calculate slope (trend)
        denominator = n * sum_x2 - sum_x * sum_x
        if abs(denominator) < 1e-10:
            return None
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        # Determine trend direction and strength
        value_range = max(values) - min(values)
        if value_range == 0:
            return None
        
        normalized_slope = abs(slope) / value_range * time_window_hours
        
        if slope > 0:
            trend_direction = 'degrading' if metric_name.endswith('.percent') or 'latency' in metric_name else 'improving'
        elif slope < 0:
            trend_direction = 'improving' if metric_name.endswith('.percent') or 'latency' in metric_name else 'degrading'
        else:
            trend_direction = 'stable'
        
        # Calculate confidence based on data consistency
        variance = sum((v - statistics.mean(values)) ** 2 for v in values) / n
        confidence = min(1.0, normalized_slope / (1 + variance))
        
        trend_strength = min(1.0, normalized_slope)
        
        return PerformanceTrend(
            metric_name=metric_name,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            average_change_rate=slope,
            samples_analyzed=n,
            time_period_hours=time_window_hours,
            confidence=confidence
        )
    
    def _get_short_term_trend(self, metric_name: str) -> str:
        """Get short-term trend (last 15 minutes) for dashboard."""
        trend = self._calculate_trend(metric_name, 0.25)  # 15 minutes
        if trend:
            if trend.trend_strength > 0.1:
                return trend.trend_direction
        return 'stable'
    
    def _calculate_health_score(self, alert_summary: Dict[str, Any], 
                               metric_stats: Dict[str, Any]) -> float:
        """Calculate overall performance health score (0-100)."""
        base_score = 100.0
        
        # Deduct points for alerts
        base_score -= alert_summary.get('critical_alerts', 0) * 30
        base_score -= alert_summary.get('warning_alerts', 0) * 10
        base_score -= alert_summary.get('unacknowledged_alerts', 0) * 5
        
        # Deduct points for poor metrics
        if 'system.cpu.percent' in metric_stats:
            cpu_usage = metric_stats['system.cpu.percent'].get('mean', 0)
            if cpu_usage > 80:
                base_score -= (cpu_usage - 80) * 0.5
        
        if 'system.memory.percent' in metric_stats:
            memory_usage = metric_stats['system.memory.percent'].get('mean', 0)
            if memory_usage > 80:
                base_score -= (memory_usage - 80) * 0.5
        
        # Ensure score is within bounds
        return max(0.0, min(100.0, base_score))
    
    def _get_monitoring_uptime_hours(self) -> float:
        """Get monitoring system uptime in hours."""
        if hasattr(self, '_start_time'):
            return (time.time() - self._start_time) / 3600
        return 0.0
    
    def _generate_performance_recommendations(self, alert_summary: Dict[str, Any],
                                            metric_stats: Dict[str, Any],
                                            trends: Dict[str, Any]) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        # Alert-based recommendations
        if alert_summary.get('critical_alerts', 0) > 0:
            recommendations.append("CRITICAL: Address critical performance alerts immediately")
        
        if alert_summary.get('warning_alerts', 0) > 2:
            recommendations.append("Multiple warning alerts detected - review system performance")
        
        # Metric-based recommendations
        if 'system.memory.percent' in metric_stats:
            memory_usage = metric_stats['system.memory.percent'].get('mean', 0)
            if memory_usage > 85:
                recommendations.append("High memory usage - consider memory optimization")
        
        if 'optimizer.cache.hit_ratio' in metric_stats:
            hit_ratio = metric_stats['optimizer.cache.hit_ratio'].get('mean', 1.0)
            if hit_ratio < 0.8:
                recommendations.append("Low cache hit ratio - review caching strategy")
        
        # Trend-based recommendations
        degrading_trends = [metric for metric, trend in trends.items() 
                          if trend.get('direction') == 'degrading' and trend.get('confidence', 0) > 0.7]
        
        if degrading_trends:
            recommendations.append(f"Performance degradation detected in: {', '.join(degrading_trends[:3])}")
        
        if not recommendations:
            recommendations.append("All performance metrics are within acceptable ranges")
        
        return recommendations