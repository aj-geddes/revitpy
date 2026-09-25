# IoT sensor monitor

`python -m iot_monitor` · package `iot_monitor`

## What it does

1. **Maps sensors to rooms.** Reads a `Sensor ID` project parameter from each
   `Room`.
2. **Streams readings.** `replay()` is an async generator that yields readings
   one timestamp at a time, and `monitor()` consumes it with `async for`. In a
   real deployment `replay()` is replaced by an MQTT, BMS or cloud IoT
   subscription (e.g. `aiomqtt`), and the rest stays the same.
3. **Raises alarms** per sensor and metric (`StreamingAnomalyDetector`):
   - *threshold* alarms when temperature leaves 18-26 °C, CO2 exceeds 1000 ppm
     or humidity leaves 25-65%;
   - *anomaly* alarms when the change since the previous reading is far outside
     the recent distribution of changes (robust z-score from the median and MAD
     of the last 36 changes). Working on changes rather than levels keeps normal
     ramps, like CO2 rising as people arrive, from being flagged. Sudden jumps
     such as a failed damper or a stuck valve are caught.
4. **Write-back.** Writes each room's latest reading and ok/ALARM status to
   `Comments` in one transaction.

## Threading in Revit

Revit's API may only be called from Revit's main thread. `run()` finishes the
asyncio loop first and then writes in a normal transaction on the calling
thread. That is the main thread when you use Run Script or the Live Server. A
long-running monitor would run its loop on a background thread and push
updates with `revitpy.revit.host.call_on_revit_thread(...)`. The model must not
be touched directly from the loop.

## Data

With no `readings=` argument, the feed is **synthetic**: one day at 5-minute
intervals per sensor. On one sensor (`S-205` in the demo), temperature steps up
6 °C and CO2 700 ppm at 16:00. The tests check that only that sensor alarms and
that a clean feed raises nothing. Real data is a long DataFrame with
`timestamp`, `sensor_id`, `temperature_c`, `co2_ppm` and `humidity_pct` columns.

## Changed from the original concept

The earlier version described Azure IoT and AWS IoT clients. They were mocks
that never connected to anything, and they were removed. So were `aiohttp` and
the cloud SDK requirements. The detector is plain NumPy/pandas.
