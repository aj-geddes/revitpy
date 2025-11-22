"""
Data generators for creating realistic building datasets for POC demonstrations.
"""

import random
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from .revitpy_mock import get_elements


def generate_energy_consumption_data(days: int = 365) -> pd.DataFrame:
    """Generate realistic energy consumption time series data."""
    base_date = datetime.now() - timedelta(days=days)
    dates = [base_date + timedelta(days=i) for i in range(days)]

    # Seasonal patterns
    seasonal_factor = []
    for date in dates:
        day_of_year = date.timetuple().tm_yday
        # Higher consumption in summer (cooling) and winter (heating)
        seasonal = 1.0 + 0.3 * (np.cos(2 * np.pi * day_of_year / 365) * 0.5)
        seasonal_factor.append(seasonal)

    # Weekly patterns (lower on weekends)
    weekly_factor = []
    for date in dates:
        if date.weekday() < 5:  # Weekday
            weekly_factor.append(random.uniform(0.9, 1.1))
        else:  # Weekend
            weekly_factor.append(random.uniform(0.3, 0.6))

    # Daily patterns (peak during business hours)
    hourly_data = []
    for i, date in enumerate(dates):
        for hour in range(24):
            if 8 <= hour <= 18:  # Business hours
                hourly_multiplier = random.uniform(0.8, 1.2)
            else:
                hourly_multiplier = random.uniform(0.2, 0.5)

            base_consumption = 500  # kWh base load
            consumption = base_consumption * seasonal_factor[i] * weekly_factor[
                i
            ] * hourly_multiplier + random.uniform(-50, 50)  # noise

            hourly_data.append(
                {
                    "timestamp": date.replace(hour=hour),
                    "energy_consumption_kwh": max(
                        consumption, 50
                    ),  # Minimum consumption
                    "outside_temperature": generate_temperature(date, hour),
                    "humidity": random.uniform(30, 70),
                    "occupancy_count": generate_occupancy(hour, date.weekday()),
                    "solar_irradiance": generate_solar_irradiance(hour),
                    "equipment_efficiency": random.uniform(0.75, 0.95),
                }
            )

    return pd.DataFrame(hourly_data)


def generate_temperature(date: datetime, hour: int) -> float:
    """Generate realistic temperature data based on season and time."""
    day_of_year = date.timetuple().tm_yday

    # Seasonal temperature variation (simplified)
    seasonal_temp = 70 + 20 * np.sin(2 * np.pi * (day_of_year - 80) / 365)

    # Daily temperature variation
    daily_temp = 8 * np.sin(2 * np.pi * (hour - 6) / 24)

    # Random variation
    random_variation = random.uniform(-5, 5)

    return seasonal_temp + daily_temp + random_variation


def generate_occupancy(hour: int, weekday: int) -> int:
    """Generate occupancy count based on time and day."""
    if weekday >= 5:  # Weekend
        return random.randint(0, 20)

    if 9 <= hour <= 17:  # Business hours
        return random.randint(150, 300)
    elif 7 <= hour <= 9 or 17 <= hour <= 19:  # Transition hours
        return random.randint(50, 150)
    else:  # Off hours
        return random.randint(0, 30)


def generate_solar_irradiance(hour: int) -> float:
    """Generate solar irradiance based on time of day."""
    if 6 <= hour <= 18:
        # Simplified sine wave for daylight hours
        angle = (hour - 6) / 12 * np.pi
        return 1000 * np.sin(angle) * random.uniform(0.7, 1.0)
    return 0.0


def generate_sensor_data() -> dict[str, Any]:
    """Generate realistic IoT sensor data for building systems."""
    return {
        "hvac": {
            "temperature": random.uniform(68, 78),
            "humidity": random.uniform(40, 60),
            "air_quality": random.uniform(0.7, 1.0),
            "efficiency": random.uniform(0.75, 0.95),
            "power_consumption": random.uniform(50, 200),
            "filter_status": random.choice(["good", "needs_replacement", "critical"]),
        },
        "lighting": {
            "power_consumption": random.uniform(10, 80),
            "occupancy_detected": random.choice([True, False]),
            "daylight_level": random.uniform(100, 1000),
            "efficiency": random.uniform(0.8, 0.95),
        },
        "security": {
            "occupancy_count": random.randint(0, 50),
            "access_events": random.randint(0, 10),
            "alarm_status": random.choice(["normal", "alert", "maintenance"]),
        },
        "environmental": {
            "outside_temperature": random.uniform(45, 95),
            "wind_speed": random.uniform(0, 25),
            "solar_irradiance": random.uniform(0, 1200),
            "rainfall": random.uniform(0, 2),
        },
    }


def generate_space_utilization_data(spaces: list[Any], days: int = 90) -> pd.DataFrame:
    """Generate space utilization data for ML training."""
    utilization_data = []

    base_date = datetime.now() - timedelta(days=days)

    for space in spaces:
        space_type = space.get_parameter("SpaceType")
        area = space.area
        occupancy_capacity = space.get_parameter("Occupancy")

        for day in range(days):
            current_date = base_date + timedelta(days=day)

            # Generate hourly utilization for each space
            for hour in range(24):
                # Base utilization patterns by space type
                if space_type == "Private Office":
                    base_utilization = 0.7 if 9 <= hour <= 17 else 0.1
                elif space_type == "Open Office":
                    base_utilization = 0.6 if 9 <= hour <= 17 else 0.05
                elif space_type == "Meeting Room":
                    # Meeting rooms have periodic spikes
                    base_utilization = 0.4 if hour in [10, 14, 16] else 0.1
                elif space_type == "Conference Room":
                    base_utilization = 0.3 if hour in [9, 11, 14] else 0.05
                else:
                    base_utilization = 0.2 if 9 <= hour <= 17 else 0.05

                # Apply weekend reduction
                if current_date.weekday() >= 5:
                    base_utilization *= 0.2

                # Add random variation
                utilization = base_utilization * random.uniform(0.5, 1.3)
                utilization = max(0, min(1, utilization))  # Clamp to [0,1]

                utilization_data.append(
                    {
                        "space_id": space.id,
                        "space_name": space.name,
                        "space_type": space_type,
                        "area": area,
                        "capacity": occupancy_capacity,
                        "timestamp": current_date.replace(hour=hour),
                        "utilization_ratio": utilization,
                        "actual_occupancy": int(utilization * occupancy_capacity),
                        "temperature": random.uniform(68, 76),
                        "lighting_level": random.uniform(200, 800),
                        "noise_level": random.uniform(35, 60),
                    }
                )

    return pd.DataFrame(utilization_data)


def generate_structural_loads_data() -> dict[str, np.ndarray]:
    """Generate structural load data for analysis."""
    structural_elements = get_elements(category="StructuralFraming")

    loads_data = {
        "element_ids": [elem.id for elem in structural_elements[:50]],  # Limit for demo
        "dead_loads": np.random.uniform(1000, 5000, 50),  # lbs
        "live_loads": np.random.uniform(2000, 8000, 50),  # lbs
        "wind_loads": np.random.uniform(500, 3000, 50),  # lbs
        "seismic_loads": np.random.uniform(800, 4000, 50),  # lbs
        "material_properties": {
            "yield_strength": np.random.uniform(36000, 50000, 50),  # psi
            "modulus_elasticity": np.full(50, 29000000),  # psi (steel)
            "density": np.full(50, 490),  # lb/ft³ (steel)
        },
    }

    return loads_data


def generate_construction_photos_metadata(days: int = 30) -> list[dict[str, Any]]:
    """Generate metadata for construction progress photos."""
    photos_metadata = []
    base_date = datetime.now() - timedelta(days=days)

    construction_phases = [
        "excavation",
        "foundation",
        "structure",
        "envelope",
        "mep_rough",
        "interior",
        "finishes",
        "completion",
    ]

    for day in range(0, days, 2):  # Photos every 2 days
        current_date = base_date + timedelta(days=day)

        # Determine construction phase based on progress
        progress_ratio = day / days
        phase_index = min(
            int(progress_ratio * len(construction_phases)), len(construction_phases) - 1
        )
        current_phase = construction_phases[phase_index]

        for photo_num in range(random.randint(3, 8)):  # 3-8 photos per day
            photos_metadata.append(
                {
                    "photo_id": f"IMG_{current_date.strftime('%Y%m%d')}_{photo_num+1:02d}",
                    "date_taken": current_date,
                    "construction_phase": current_phase,
                    "location": {
                        "floor": random.randint(1, 12),
                        "zone": random.choice(["A", "B", "C", "D"]),
                        "coordinates": {
                            "x": random.uniform(0, 400),
                            "y": random.uniform(0, 200),
                            "z": random.uniform(0, 144),
                        },
                    },
                    "camera_angle": random.choice(
                        ["north", "south", "east", "west", "overhead"]
                    ),
                    "weather_conditions": random.choice(
                        ["clear", "cloudy", "rainy", "sunny"]
                    ),
                    "progress_percentage": progress_ratio * 100 + random.uniform(-5, 5),
                    "elements_visible": random.sample(
                        [
                            "concrete_walls",
                            "steel_beams",
                            "rebar",
                            "formwork",
                            "hvac_ducts",
                            "electrical_conduit",
                            "plumbing",
                            "insulation",
                            "drywall",
                            "windows",
                            "roofing",
                        ],
                        k=random.randint(2, 6),
                    ),
                }
            )

    return photos_metadata


def generate_weather_forecast_data(days: int = 7) -> pd.DataFrame:
    """Generate weather forecast data for energy prediction."""
    forecast_data = []
    base_date = datetime.now()

    for day in range(days):
        current_date = base_date + timedelta(days=day)

        # Seasonal base temperature
        day_of_year = current_date.timetuple().tm_yday
        seasonal_temp = 70 + 20 * np.sin(2 * np.pi * (day_of_year - 80) / 365)

        for hour in range(24):
            # Daily temperature variation
            daily_temp = 10 * np.sin(2 * np.pi * (hour - 6) / 24)
            temperature = seasonal_temp + daily_temp + random.uniform(-3, 3)

            forecast_data.append(
                {
                    "timestamp": current_date.replace(hour=hour),
                    "temperature": temperature,
                    "humidity": random.uniform(30, 80),
                    "cloud_cover": random.uniform(0, 100),
                    "wind_speed": random.uniform(0, 20),
                    "precipitation": random.uniform(0, 0.5)
                    if random.random() < 0.3
                    else 0,
                    "solar_irradiance_forecast": generate_solar_irradiance(hour)
                    * random.uniform(0.8, 1.0),
                    "pressure": random.uniform(29.8, 30.2),  # inHg
                }
            )

    return pd.DataFrame(forecast_data)
