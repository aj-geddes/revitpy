"""iot_monitor.analysis alarm rules."""

from __future__ import annotations

import numpy as np
import pandas as pd
from iot_monitor.analysis import (
    Alarm,
    StreamingAnomalyDetector,
    latest_by_sensor,
    summarize_alarms,
)


def feed(steps: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-03-03", periods=steps, freq="5min"),
            "sensor_id": "S1",
            "temperature_c": 21.5 + rng.normal(0, 0.15, steps),
            "co2_ppm": 600 + rng.normal(0, 10, steps),
            "humidity_pct": 45 + rng.normal(0, 1, steps),
        }
    )


def test_clean_feed_raises_nothing():
    assert StreamingAnomalyDetector().process(feed()) == []


def test_step_change_raises_one_anomaly_then_thresholds():
    data = feed()
    data.loc[150:, "temperature_c"] += 5.0
    alarms = StreamingAnomalyDetector().process(data)
    anomalies = [a for a in alarms if a.kind == "anomaly"]
    thresholds = [a for a in alarms if a.kind == "threshold"]
    assert len(anomalies) == 1
    assert anomalies[0].metric == "temperature_c"
    assert anomalies[0].timestamp == data.loc[150, "timestamp"]
    assert len(thresholds) == 50
    assert {a.detail for a in thresholds} == {"above 26.0"}


def test_slow_ramp_is_not_an_anomaly():
    data = feed()
    data["co2_ppm"] = np.linspace(600, 950, 200) + np.random.default_rng(1).normal(
        0, 10, 200
    )
    assert StreamingAnomalyDetector().process(data) == []


def test_threshold_rules():
    detector = StreamingAnomalyDetector()
    high = detector.update(
        {"timestamp": "2025-03-03", "sensor_id": "S1", "co2_ppm": 1200.0}
    )
    low = detector.update(
        {"timestamp": "2025-03-03", "sensor_id": "S2", "temperature_c": 16.0}
    )
    assert [(a.kind, a.detail) for a in high] == [("threshold", "above 1000.0")]
    assert [(a.kind, a.detail) for a in low] == [("threshold", "below 18.0")]


def test_nan_metrics_are_skipped():
    reading = {
        "timestamp": "2025-03-03",
        "sensor_id": "S1",
        "humidity_pct": float("nan"),
    }
    assert StreamingAnomalyDetector().update(reading) == []


def test_summarize_alarms():
    empty = summarize_alarms([])
    assert list(empty.columns) == [
        "sensor_id",
        "metric",
        "kind",
        "count",
        "first_seen",
        "last_seen",
    ]
    assert empty.empty
    t = pd.date_range("2025-03-03 10:00", periods=3, freq="5min")
    alarms = [
        Alarm(ts, "S1", "temperature_c", 27.0, "threshold", "above 26.0") for ts in t
    ]
    alarms.append(Alarm(t[0], "S1", "co2_ppm", 1100.0, "threshold", "above 1000.0"))
    summary = summarize_alarms(alarms).set_index("metric")
    assert summary.loc["temperature_c", "count"] == 3
    assert summary.loc["temperature_c", "first_seen"] == t[0]
    assert summary.loc["temperature_c", "last_seen"] == t[2]
    assert summary.loc["co2_ppm", "count"] == 1


def test_latest_by_sensor():
    a, b = feed(5), feed(5, seed=1).assign(sensor_id="S0")
    latest = latest_by_sensor(pd.concat([a, b], ignore_index=True))
    assert list(latest.index) == ["S0", "S1"]
    assert latest.loc["S1", "temperature_c"] == a["temperature_c"].iloc[-1]
