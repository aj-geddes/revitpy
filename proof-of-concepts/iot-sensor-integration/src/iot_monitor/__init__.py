"""Stream building-sensor readings, detect faults and push status into rooms.

Inside Revit (RevitPy add-in or Live Server)::

    from iot_monitor import run
    print(run(__revit__, readings=my_readings_dataframe).to_text())

Outside Revit, ``run()`` uses the demo building and a synthetic sensor feed
with one injected fault.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from poc_common import connect, source_label
from poc_common.timeseries import sensor_readings

from .analysis import (
    Alarm,
    StreamingAnomalyDetector,
    latest_by_sensor,
    summarize_alarms,
)
from .model_data import sensor_rooms, write_room_status

__all__ = ["IotReport", "monitor", "replay", "run"]


@dataclass
class IotReport:
    """Results of :func:`run`."""

    source: str
    sensors: int
    readings: int
    alarms: list[Alarm]
    alarm_summary: pd.DataFrame
    latest: pd.DataFrame
    rooms: pd.DataFrame
    written: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def alarmed_sensors(self) -> set[str]:
        return {a.sensor_id for a in self.alarms}

    def to_text(self) -> str:
        lines = [
            f"IoT monitor - {self.source}",
            f"{self.sensors} sensors mapped to rooms, {self.readings} readings processed",
            "",
            f"Alarms ({len(self.alarms)}):",
        ]
        if self.alarm_summary.empty:
            lines.append("  none")
        for r in self.alarm_summary.itertuples():
            room = self.rooms["room"].get(r.sensor_id, "(unmapped)")
            lines.append(
                f"  {r.sensor_id:<7} {room:<22} {r.metric:<14} {r.kind:<9} "
                f"x{r.count:<4} first {pd.Timestamp(r.first_seen):%H:%M}"
            )
        if self.written:
            lines += ["", f"Wrote latest status to Comments on {self.written} rooms."]
        lines += [f"Note: {n}" for n in self.notes]
        return "\n".join(lines)


async def replay(
    readings: pd.DataFrame, interval_s: float = 0.0
) -> AsyncIterator[pd.DataFrame]:
    """Yield readings one timestamp at a time, like a live feed would.

    Swap this for an MQTT / BMS / cloud IoT subscription in a real deployment.
    """
    for _, batch in readings.groupby("timestamp", sort=True):
        yield batch
        await asyncio.sleep(interval_s)


async def monitor(
    stream: AsyncIterator[pd.DataFrame], detector: StreamingAnomalyDetector
) -> tuple[list[Alarm], int]:
    """Consume a stream of reading batches, returning alarms and the count read."""
    alarms: list[Alarm] = []
    count = 0
    async for batch in stream:
        for reading in batch.to_dict("records"):
            alarms.extend(detector.update(reading))
            count += 1
    return alarms, count


def run(
    app: Any | None = None,
    *,
    readings: pd.DataFrame | None = None,
    steps: int = 288,
    seed: int = 0,
    write: bool = True,
) -> IotReport:
    """Run the monitor over a (replayed) sensor feed.

    Args:
        app: ``__revit__`` inside Revit; ``None`` uses the demo model.
        readings: Long-format readings (``timestamp``, ``sensor_id``,
            ``temperature_c``, ``co2_ppm``, ``humidity_pct``). Synthetic when
            omitted, with an HVAC fault injected on one sensor.
        steps: Number of 5-minute steps of synthetic data (288 = one day).
        seed: Seed for the synthetic data.
        write: Write each room's latest reading to ``Comments``.
    """
    api = connect(app)
    source = source_label(api, app)
    notes = []
    rooms = sensor_rooms(api)
    if rooms.empty:
        raise ValueError("No rooms with a 'Sensor ID' parameter")

    if readings is None:
        sensor_ids = sorted(rooms.index)
        faulty = sensor_ids[len(sensor_ids) // 2]
        readings = sensor_readings(
            sensor_ids, steps=steps, seed=seed, faults={faulty: steps * 2 // 3}
        )
        notes.append(f"sensor feed is synthetic; a fault was injected on {faulty}")

    alarms, count = asyncio.run(monitor(replay(readings), StreamingAnomalyDetector()))
    latest = latest_by_sensor(readings)

    report = IotReport(
        source=source,
        sensors=len(rooms),
        readings=count,
        alarms=alarms,
        alarm_summary=summarize_alarms(alarms),
        latest=latest,
        rooms=rooms,
        notes=notes,
    )
    if write:
        report.written = write_room_status(api, rooms, latest, report.alarmed_sensors)
    return report
