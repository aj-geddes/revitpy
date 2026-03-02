---
layout: api
title: Performance API
description: Real-time performance monitoring, metrics collection, alerting, and trend analysis
---

# Performance API

The Performance module provides real-time metrics collection, threshold-based alerting, statistical analysis, and performance trend detection for RevitPy applications.

**Module:** `revitpy.performance.monitoring`

---

## PerformanceThreshold

Configuration for a single performance threshold that triggers alerts.

### Constructor

```python
PerformanceThreshold(
    metric_name: str,
    warning_threshold: float,
    critical_threshold: float,
    comparison_operator: str = ">",
    evaluation_window_seconds: int = 60,
    min_samples: int = 3,
    enabled: bool = True
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric_name` | `str` | | Name of the metric to monitor. |
| `warning_threshold` | `float` | | Value at which a warning alert is raised. |
| `critical_threshold` | `float` | | Value at which a critical alert is raised. |
| `comparison_operator` | `str` | `">"` | Comparison operator (`>`, `<`, `>=`, `<=`, `==`, `!=`). |
| `evaluation_window_seconds` | `int` | `60` | Time window for evaluating the threshold. |
| `min_samples` | `int` | `3` | Minimum number of samples required before alerting. |
| `enabled` | `bool` | `True` | Whether this threshold is active. |

---

## PerformanceAlert

Dataclass representing a triggered performance alert.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique alert identifier. |
| `timestamp` | `float` | Unix timestamp when the alert was created. |
| `metric_name` | `str` | Name of the metric that triggered the alert. |
| `current_value` | `float` | Metric value that triggered the alert. |
| `threshold_value` | `float` | Threshold value that was exceeded. |
| `severity` | `str` | Alert severity: `"warning"` or `"critical"`. |
| `message` | `str` | Human-readable alert message. |
| `context` | `dict[str, Any]` | Additional context data. |
| `acknowledged` | `bool` | Whether the alert has been acknowledged. |
| `resolved` | `bool` | Whether the alert has been resolved. |
| `resolution_timestamp` | `float` or `None` | When the alert was resolved. |

---

## MetricSnapshot

A single metric measurement at a point in time.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `float` | Unix timestamp of the measurement. |
| `metric_name` | `str` | Metric name. |
| `value` | `float` | Measured value. |
| `tags` | `dict[str, str]` | Key-value tags for categorization. |
| `context` | `dict[str, Any]` | Additional context data. |

---

## PerformanceTrend

Result of a performance trend analysis.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `metric_name` | `str` | Name of the analyzed metric. |
| `trend_direction` | `str` | Direction: `"improving"`, `"degrading"`, or `"stable"`. |
| `trend_strength` | `float` | Strength of the trend (0.0 to 1.0). |
| `average_change_rate` | `float` | Average rate of change per sample. |
| `samples_analyzed` | `int` | Number of samples used in the analysis. |
| `time_period_hours` | `float` | Time period covered by the analysis. |
| `confidence` | `float` | Confidence level of the trend (0.0 to 1.0). |

---

## MetricsCollector

High-performance metrics collection system with background collection, buffering, and statistical analysis.

### Constructor

```python
MetricsCollector(buffer_size: int = 10000)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `buffer_size` | `int` | Maximum number of snapshots held in the buffer. Default `10000`. |

### Methods

#### `start_collection()`

Starts a background thread that automatically collects system metrics (CPU, memory, disk I/O) at the configured interval. Also runs any registered collection callbacks.

#### `stop_collection()`

Stops the background collection thread.

#### `record_metric(metric_name, value, tags=None, context=None)`

Records a single metric measurement.

| Parameter | Type | Description |
|-----------|------|-------------|
| `metric_name` | `str` | Name of the metric. |
| `value` | `float` | Measured value. |
| `tags` | `dict[str, str]` or `None` | Optional tags. |
| `context` | `dict[str, Any]` or `None` | Optional context data. |

```python
collector.record_metric("query.duration_ms", 45.2, tags={"query": "walls"})
```

#### `record_metrics_batch(metrics)`

Records multiple metrics efficiently in a single operation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `metrics` | `list[dict[str, Any]]` | List of metric dictionaries with `name`, `value`, and optional `tags` and `context`. |

```python
collector.record_metrics_batch([
    {"name": "query.count", "value": 10},
    {"name": "query.duration_ms", "value": 120.5, "tags": {"type": "walls"}},
])
```

#### `get_metric_history(metric_name, time_window_seconds=3600)`

Returns metric snapshots for the specified time window.

| Parameter | Type | Description |
|-----------|------|-------------|
| `metric_name` | `str` | Metric name. |
| `time_window_seconds` | `int` | Lookback window in seconds. Default `3600` (one hour). |

**Returns:** `list[MetricSnapshot]`

#### `get_metric_statistics(metric_name, time_window_seconds=3600)`

Returns statistical summary for a metric over a time window.

| Parameter | Type | Description |
|-----------|------|-------------|
| `metric_name` | `str` | Metric name. |
| `time_window_seconds` | `int` | Lookback window in seconds. Default `3600`. |

**Returns:** `dict[str, float]` -- Contains `count`, `min`, `max`, `mean`, `median`, `std_dev`, `p50`, `p90`, `p95`, `p99`. Returns an empty dict if no data is available.

```python
stats = collector.get_metric_statistics("query.duration_ms", time_window_seconds=300)
print(f"Mean: {stats['mean']:.2f}ms, P95: {stats['p95']:.2f}ms")
```

#### `add_collection_callback(callback)`

Registers a callback that is called during each collection cycle. The callback should return a list of metric dictionaries.

| Parameter | Type | Description |
|-----------|------|-------------|
| `callback` | `Callable[[], list[dict[str, Any]]]` | Function returning metric dicts. |

```python
def collect_custom_metrics():
    return [{"name": "custom.active_users", "value": get_user_count()}]

collector.add_collection_callback(collect_custom_metrics)
```

### System Metrics

When `psutil` is installed, the background collector automatically records the following metrics:

| Metric Name | Description |
|-------------|-------------|
| `system.cpu.percent` | System CPU usage percentage. |
| `system.memory.percent` | System memory usage percentage. |
| `system.memory.available_mb` | Available system memory in MB. |
| `system.memory.used_mb` | Used system memory in MB. |
| `process.memory.rss_mb` | Process resident set size in MB. |
| `process.memory.vms_mb` | Process virtual memory size in MB. |
| `process.cpu.percent` | Process CPU usage percentage. |
| `process.io.read_bytes` | Process disk read bytes. |
| `process.io.write_bytes` | Process disk write bytes. |

---

## AlertingSystem

Threshold-based alerting system that evaluates metrics against configurable thresholds and raises alerts.

### Constructor

```python
AlertingSystem(metrics_collector: MetricsCollector)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `metrics_collector` | `MetricsCollector` | The metrics collector to evaluate. |

Default thresholds are initialized for `system.cpu.percent` (warning: 80%, critical: 90%) and `system.memory.percent` (warning: 80%, critical: 90%).

### Methods

#### `start_alerting()`

Starts the background alerting thread that periodically evaluates thresholds.

#### `stop_alerting()`

Stops the background alerting thread.

#### `add_threshold(threshold)`

Adds or updates a performance threshold.

| Parameter | Type | Description |
|-----------|------|-------------|
| `threshold` | `PerformanceThreshold` | Threshold configuration. |

```python
alerting.add_threshold(PerformanceThreshold(
    metric_name="query.duration_ms",
    warning_threshold=500.0,
    critical_threshold=1000.0,
    comparison_operator=">",
))
```

#### `remove_threshold(metric_name)`

Removes a threshold by metric name.

#### `add_alert_callback(callback)`

Registers a callback that is called when an alert is triggered.

| Parameter | Type | Description |
|-----------|------|-------------|
| `callback` | `Callable[[PerformanceAlert], None]` | Alert notification function. |

```python
def on_alert(alert):
    print(f"[{alert.severity}] {alert.message}")

alerting.add_alert_callback(on_alert)
```

#### `acknowledge_alert(alert_id)`

Acknowledges an active alert.

#### `resolve_alert(alert_id)`

Resolves an active alert and moves it to the alert history.

#### `get_active_alerts()`

Returns all currently active alerts.

**Returns:** `list[PerformanceAlert]`

#### `get_alert_summary()`

Returns a summary of the current alert status.

**Returns:** `dict[str, Any]` -- Contains `total_active_alerts`, `critical_alerts`, `warning_alerts`, `unacknowledged_alerts`, `recent_alerts_24h`, and `alert_rate_per_hour`.

---

## Usage Examples

### Basic Metrics Collection

```python
from revitpy.performance.monitoring import MetricsCollector

collector = MetricsCollector(buffer_size=5000)
collector.start_collection()

# Record custom metrics
collector.record_metric("walls.processed", 150)
collector.record_metric("query.duration_ms", 85.3, tags={"category": "Walls"})

# Get statistics
stats = collector.get_metric_statistics("query.duration_ms")
if stats:
    print(f"Query stats -- Mean: {stats['mean']:.2f}ms, Max: {stats['max']:.2f}ms")

collector.stop_collection()
```

### Alerting with Custom Thresholds

```python
from revitpy.performance.monitoring import (
    MetricsCollector,
    AlertingSystem,
    PerformanceThreshold,
)

collector = MetricsCollector()
collector.start_collection()

alerting = AlertingSystem(collector)

# Add custom threshold
alerting.add_threshold(PerformanceThreshold(
    metric_name="query.duration_ms",
    warning_threshold=200.0,
    critical_threshold=500.0,
    comparison_operator=">",
    evaluation_window_seconds=120,
    min_samples=5,
))

# Register alert handler
def handle_alert(alert):
    print(f"ALERT [{alert.severity}]: {alert.metric_name} = {alert.current_value}")

alerting.add_alert_callback(handle_alert)

alerting.start_alerting()

# ... application runs ...

# Check alerts
summary = alerting.get_alert_summary()
print(f"Active alerts: {summary['total_active_alerts']}")

for alert in alerting.get_active_alerts():
    print(f"  {alert.metric_name}: {alert.message}")
    alerting.acknowledge_alert(alert.id)

alerting.stop_alerting()
collector.stop_collection()
```

### Custom Collection Callbacks

```python
from revitpy.performance.monitoring import MetricsCollector

collector = MetricsCollector()

def collect_revit_metrics():
    """Custom callback to collect Revit-specific metrics."""
    return [
        {"name": "revit.elements.total", "value": get_element_count()},
        {"name": "revit.transactions.active", "value": get_active_transactions()},
    ]

collector.add_collection_callback(collect_revit_metrics)
collector.start_collection()
```

---

## Best Practices

1. **Start collection early** -- Call `start_collection()` at application startup to capture baseline metrics.
2. **Set meaningful thresholds** -- Tune `warning_threshold` and `critical_threshold` to your workload.
3. **Use tags for categorization** -- Tags help distinguish metrics from different sources or operations.
4. **Handle alerts with callbacks** -- Register alert callbacks for notifications or logging.
5. **Review statistics regularly** -- Use `get_metric_statistics()` to identify performance trends.
6. **Stop collection on shutdown** -- Call `stop_collection()` and `stop_alerting()` to clean up background threads.

---

## Next Steps

- **[Core API]({{ '/reference/api/core/' | relative_url }})**: The `RevitAPI` interface
- **[Async Support]({{ '/reference/api/async/' | relative_url }})**: Async operations with progress monitoring
- **[Testing]({{ '/reference/api/testing/' | relative_url }})**: Test performance-sensitive code
