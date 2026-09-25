"""Streaming alarm rules for building sensors.

Pure Python/pandas; nothing here touches Revit.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

COMFORT_LIMITS: dict[str, tuple[float | None, float | None]] = {
    "temperature_c": (18.0, 26.0),
    "co2_ppm": (None, 1000.0),
    "humidity_pct": (25.0, 65.0),
}

SCALE_FLOORS: dict[str, float] = {
    "temperature_c": 0.1,
    "co2_ppm": 5.0,
    "humidity_pct": 0.5,
}
DEFAULT_FLOOR: float = 1e-6


@dataclass(frozen=True)
class Alarm:
    """One alarm raised by :class:`StreamingAnomalyDetector`."""

    timestamp: pd.Timestamp
    sensor_id: str
    metric: str
    value: float
    kind: str
    detail: str


class StreamingAnomalyDetector:
    """Comfort-limit rules plus a robust step-change detector, per sensor.

    Threshold alarms fire whenever a value is outside :data:`COMFORT_LIMITS`.
    Anomaly alarms fire when the change since the sensor's previous reading
    is far outside the recent distribution of changes (robust z-score from
    the median and MAD of the last ``window`` changes). Working on changes
    rather than levels means normal daily ramps (CO2 rising as people arrive)
    are not flagged, while sudden jumps (a failed damper, a stuck valve, a
    dislodged sensor) are.
    """

    def __init__(
        self,
        window: int = 36,
        z_threshold: float = 8.0,
        min_history: int = 12,
        limits: dict[str, tuple[float | None, float | None]] | None = None,
    ) -> None:
        self.window = window
        self.z_threshold = z_threshold
        self.min_history = min_history
        self.limits = limits if limits is not None else COMFORT_LIMITS
        self._changes: dict[tuple[str, str], deque[float]] = {}
        self._last: dict[tuple[str, str], float] = {}

    def update(self, reading: Mapping[str, Any]) -> list[Alarm]:
        """Process one reading (``timestamp``, ``sensor_id`` and metric values)."""
        alarms: list[Alarm] = []
        timestamp = pd.Timestamp(reading["timestamp"])
        sensor_id = str(reading["sensor_id"])

        for metric, (lower, upper) in self.limits.items():
            raw = reading.get(metric)
            if raw is None:
                continue
            value = float(raw)
            if math.isnan(value):
                continue

            if lower is not None and value < lower:
                alarms.append(
                    Alarm(
                        timestamp,
                        sensor_id,
                        metric,
                        value,
                        "threshold",
                        f"below {lower}",
                    )
                )
            elif upper is not None and value > upper:
                alarms.append(
                    Alarm(
                        timestamp,
                        sensor_id,
                        metric,
                        value,
                        "threshold",
                        f"above {upper}",
                    )
                )

            key = (sensor_id, metric)
            previous = self._last.get(key)
            self._last[key] = value
            if previous is None:
                continue
            change = value - previous
            changes = self._changes.setdefault(key, deque(maxlen=self.window))
            if len(changes) >= self.min_history:
                history = np.asarray(changes)
                median = float(np.median(history))
                mad = float(np.median(np.abs(history - median)))
                scale = max(1.4826 * mad, SCALE_FLOORS.get(metric, DEFAULT_FLOOR))
                z = (change - median) / scale
                if abs(z) > self.z_threshold:
                    alarms.append(
                        Alarm(
                            timestamp,
                            sensor_id,
                            metric,
                            value,
                            "anomaly",
                            f"step {change:+.1f}, robust z={z:.1f}",
                        )
                    )
                    # Keep the jump out of the baseline of normal changes.
                    continue
            changes.append(change)

        return alarms

    def process(self, readings: pd.DataFrame) -> list[Alarm]:
        """Run :meth:`update` over every row, in order."""
        alarms: list[Alarm] = []
        for row in readings.to_dict("records"):
            alarms.extend(self.update(row))
        return alarms


def summarize_alarms(alarms: list[Alarm]) -> pd.DataFrame:
    """Count alarms per sensor, metric and kind."""
    if not alarms:
        return pd.DataFrame(
            columns=["sensor_id", "metric", "kind", "count", "first_seen", "last_seen"]
        )

    records = []
    for alarm in alarms:
        records.append(
            {
                "sensor_id": alarm.sensor_id,
                "metric": alarm.metric,
                "kind": alarm.kind,
                "timestamp": alarm.timestamp,
            }
        )

    df = pd.DataFrame(records)
    grouped = df.groupby(["sensor_id", "metric", "kind"], sort=True)
    result = grouped.agg(
        count=("timestamp", "size"),
        first_seen=("timestamp", "min"),
        last_seen=("timestamp", "max"),
    ).reset_index()

    # Ensure correct column order
    result = result[["sensor_id", "metric", "kind", "count", "first_seen", "last_seen"]]
    result.index = pd.RangeIndex(len(result))
    return result


def latest_by_sensor(readings: pd.DataFrame) -> pd.DataFrame:
    """The most recent reading of each sensor, indexed by ``sensor_id``."""
    if readings.empty:
        return pd.DataFrame(columns=readings.columns).set_index("sensor_id")

    # Sort by timestamp to ensure latest is last
    sorted_df = readings.sort_values("timestamp")
    # Group by sensor_id and take the last row in each group
    latest = sorted_df.groupby("sensor_id", sort=False).tail(1)
    # Set sensor_id as index and sort by index
    result = latest.set_index("sensor_id").sort_index()
    return result
