"""Synthetic data generators for the demos.

These stand in for data a real project would pull from a BMS, energy meters,
badge/occupancy counters, IoT sensors or site cameras. Everything is
deterministic for a given ``seed``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy import cos, pi, sin


def hourly_weather(
    days: int = 365,
    seed: int = 0,
    start: str = "2025-01-01",
    mean_c: float = 11.0,
    amplitude_c: float = 12.0,
) -> pd.DataFrame:
    """Hourly outdoor temperature (C) and global solar irradiance (W/m2)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 24, freq="h", name="timestamp")
    dayofyear = idx.dayofyear.values.astype(float)
    hour = idx.hour.values.astype(float)

    # Seasonal temperature component: coldest mid-January (day ~15), warmest mid-July
    seasonal_temp = mean_c - amplitude_c * cos(2 * pi * (dayofyear - 15) / 365.25)
    # Daily temperature component: peak at 15:00
    daily_temp = 4 * cos(2 * pi * (hour - 15) / 24)
    # Noise
    noise_temp = rng.normal(0, 1.5, size=len(idx))

    outdoor_temp_c = seasonal_temp + daily_temp + noise_temp

    # Solar radiation
    solar_w_m2 = np.zeros(len(idx))
    mask = (hour >= 6) & (hour < 18)
    hour_inside = hour[mask].copy()
    dayofyear_inside = dayofyear[mask].copy()

    # Seasonal solar factor: max at summer solstice (day ~182)
    seasonal_factor = (
        0.6 + 0.4 * (1 - cos(2 * pi * (dayofyear_inside - 15) / 365.25)) / 2
    )
    # Daily solar profile: starts at 6:00, peaks at noon
    daily_factor = sin(pi * (hour_inside - 6) / 12)
    # Cloudiness factor
    cloudiness = rng.uniform(0.5, 1.0, size=mask.sum())

    solar_w_m2[mask] = 800 * daily_factor * seasonal_factor * cloudiness
    solar_w_m2 = np.clip(solar_w_m2, 0, None)

    return pd.DataFrame(
        {"outdoor_temp_c": outdoor_temp_c, "solar_w_m2": solar_w_m2},
        index=idx,
    )


def metered_energy(
    weather: pd.DataFrame,
    ua_w_per_k: float,
    floor_area_m2: float,
    balance_point_c: float = 15.0,
    base_load_w_per_m2: float = 6.0,
    occupied_load_w_per_m2: float = 10.0,
    noise: float = 0.05,
    seed: int = 0,
) -> pd.DataFrame:
    """Hourly metered energy for a building with heat loss ``ua_w_per_k``.

    Heating follows a degree-hour model below ``balance_point_c``; electricity
    is a base load plus an occupied-hours load. Both carry multiplicative noise.
    """
    if ua_w_per_k < 0:
        raise ValueError("ua_w_per_k must be non-negative")
    if floor_area_m2 <= 0:
        raise ValueError("floor_area_m2 must be positive")

    rng = np.random.default_rng(seed)
    idx = weather.index
    outdoor_temp_c = weather["outdoor_temp_c"].values

    # Occupied: weekdays (Mon-Fri) and 8 <= hour < 18
    hour = idx.hour.values
    weekday = idx.weekday.values < 5  # Monday=0, Sunday=6
    occupied = weekday & (hour >= 8) & (hour < 18)

    # Base electricity load
    base_electricity = base_load_w_per_m2 * floor_area_m2 / 1000  # kWh
    # Occupied electricity load
    occupied_electricity = (
        (base_load_w_per_m2 + occupied_load_w_per_m2) * floor_area_m2 / 1000
    )

    # Apply noise and clip at 0
    electricity_noise = rng.normal(1.0, noise, size=len(idx))
    electricity_kwh = np.where(
        occupied,
        occupied_electricity * electricity_noise,
        base_electricity * electricity_noise,
    )
    electricity_kwh = np.clip(electricity_kwh, 0, None)

    # Heating load: UA * max(balance_point - outdoor_temp, 0)
    heating_power_w = ua_w_per_k * np.clip(balance_point_c - outdoor_temp_c, 0, None)
    heating_kwh = heating_power_w / 1000
    heating_noise = rng.normal(1.0, noise, size=len(idx))
    heating_kwh = heating_kwh * heating_noise
    heating_kwh = np.clip(heating_kwh, 0, None)

    total_kwh = electricity_kwh + heating_kwh

    return pd.DataFrame(
        {
            "timestamp": idx,
            "outdoor_temp_c": outdoor_temp_c,
            "occupied": occupied,
            "electricity_kwh": electricity_kwh,
            "heating_kwh": heating_kwh,
            "total_kwh": total_kwh,
        }
    ).set_index("timestamp")


def room_occupancy(
    rooms: pd.DataFrame,
    days: int = 28,
    seed: int = 0,
    start: str = "2025-03-03",
) -> pd.DataFrame:
    """Hourly head counts per room (long format).

    ``rooms`` needs ``room_id`` and ``capacity``; an optional ``profile``
    column ("underused", "typical", "busy") sets the peak occupancy fraction.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 24, freq="h", name="timestamp")
    hour = idx.hour.values.astype(float)
    weekday = idx.weekday.values < 5  # Monday=0, Sunday=6

    # Daily shape by hour: 0 outside 8 <= hour < 18; inside, shape=1 except
    # hours 12,13 -> 0.6; hours 8,17 -> 0.5
    shape = np.where(
        (hour >= 8) & (hour < 18),
        np.where(
            (hour == 12) | (hour == 13),
            0.6,
            np.where((hour == 8) | (hour == 17), 0.5, 1.0),
        ),
        0.0,
    )
    # Weekend factor
    weekday_factor = np.where(weekday, 1.0, 0.03)

    profile_peaks = {"underused": 0.15, "typical": 0.55, "busy": 0.9}
    if "profile" in rooms.columns:
        profiles = rooms["profile"].fillna("typical")
    else:
        profiles = pd.Series("typical", index=rooms.index)

    frames = []
    for room_id, capacity, profile in zip(
        rooms["room_id"], rooms["capacity"], profiles, strict=True
    ):
        peak = profile_peaks.get(profile, profile_peaks["typical"])
        prob = np.clip(peak * shape * weekday_factor, 0, 1)
        occupants = rng.binomial(max(int(capacity), 0), prob)
        frames.append(
            pd.DataFrame(
                {"timestamp": idx, "room_id": int(room_id), "occupants": occupants}
            )
        )

    df = pd.concat(frames, ignore_index=True)
    df["occupants"] = df["occupants"].astype(int)
    return df.sort_values(["room_id", "timestamp"]).reset_index(drop=True)


def sensor_readings(
    sensor_ids: list[str],
    steps: int = 288,
    interval_minutes: int = 5,
    seed: int = 0,
    faults: dict[str, int] | None = None,
    start: str = "2025-03-03 00:00",
) -> pd.DataFrame:
    """Indoor temperature, CO2 and humidity per sensor at a fixed interval.

    ``faults`` maps a sensor id to the step from which it reports an HVAC
    failure (+6 C and +700 ppm CO2).
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=steps, freq=f"{interval_minutes}min")
    # Fractional hour of day.
    h = (idx.hour + idx.minute / 60.0).to_numpy(dtype=float)

    frames = []
    for sid in sensor_ids:
        # Occupied indicator
        occ = ((h >= 8) & (h < 18)).astype(float)

        # Temperature: base + daily variation + noise
        temp = 21.5 + 0.8 * sin(2 * pi * (h - 9) / 24) + rng.normal(0, 0.15, size=steps)

        # CO2: baseline + occupancy-driven variation + noise
        co2 = (
            420
            + occ * 450 * sin(pi * np.clip((h - 8) / 10, 0, 1))
            + rng.normal(0, 12, size=steps)
        )

        # Humidity: base + daily variation + noise
        humidity = 45 + 3 * sin(2 * pi * h / 24) + rng.normal(0, 1.0, size=steps)

        # Apply faults if any
        if faults is not None and sid in faults:
            s = faults[sid]
            if 0 <= s < steps:
                temp[s:] += 6.0
                co2[s:] += 700

        frames.append(
            pd.DataFrame(
                {
                    "timestamp": idx,
                    "sensor_id": sid,
                    "temperature_c": temp,
                    "co2_ppm": co2,
                    "humidity_pct": humidity,
                }
            )
        )

    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values(["timestamp", "sensor_id"]).reset_index(drop=True)
    return df


def facade_photo(
    rows: int,
    cols: int,
    installed: np.ndarray,
    panel_px: int = 32,
    joint_px: int = 3,
    noise_sd: float = 18.0,
    seed: int = 0,
    occlusion: bool = True,
) -> np.ndarray:
    """A rectified grayscale facade elevation with some panels installed.

    Row 0 of ``installed`` (the ground-floor row) is drawn at the bottom of
    the image. Empty cells are dark (60), installed panels bright (190) with
    darker joints (110). Gaussian noise and, optionally, one mid-gray
    occluding rectangle (scaffold, crane) covering 3-8% of the image are
    added.
    """
    installed = np.asarray(installed, dtype=bool)
    if installed.shape != (rows, cols):
        raise ValueError("installed.shape must be (rows, cols)")

    rng = np.random.default_rng(seed)
    height, width = rows * panel_px, cols * panel_px
    img = np.full((height, width), 60.0)

    for r in range(rows):
        top = height - (r + 1) * panel_px  # row 0 at the bottom
        for c in range(cols):
            if not installed[r, c]:
                continue
            left = c * panel_px
            img[top : top + panel_px, left : left + panel_px] = 110.0
            img[
                top + joint_px : top + panel_px - joint_px,
                left + joint_px : left + panel_px - joint_px,
            ] = 190.0

    img += rng.normal(0.0, noise_sd, size=img.shape)

    if occlusion:
        area = rng.uniform(0.03, 0.08) * height * width
        aspect = rng.uniform(0.5, 2.0)
        occ_h = int(np.clip(np.sqrt(area / aspect), 1, height))
        occ_w = int(np.clip(area / occ_h, 1, width))
        y = int(rng.integers(0, height - occ_h + 1))
        x = int(rng.integers(0, width - occ_w + 1))
        img[y : y + occ_h, x : x + occ_w] = 120.0

    return np.clip(img, 0, 255).astype(np.uint8)
