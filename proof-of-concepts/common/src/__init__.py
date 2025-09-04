"""
Common utilities and mock data for RevitPy Proof-of-Concepts.
"""

from .revitpy_mock import (
    revitpy,
    get_elements,
    get_project_info,
    get_elements_in_view,
    batch_update_parameters_async,
    RevitElement,
    ElementCategory,
    Point3D,
    BoundingBox,
    Parameter
)

from .data_generators import (
    generate_energy_consumption_data,
    generate_sensor_data,
    generate_space_utilization_data,
    generate_structural_loads_data,
    generate_construction_photos_metadata,
    generate_weather_forecast_data
)

__all__ = [
    'revitpy',
    'get_elements',
    'get_project_info', 
    'get_elements_in_view',
    'batch_update_parameters_async',
    'RevitElement',
    'ElementCategory',
    'Point3D',
    'BoundingBox',
    'Parameter',
    'generate_energy_consumption_data',
    'generate_sensor_data',
    'generate_space_utilization_data',
    'generate_structural_loads_data',
    'generate_construction_photos_metadata',
    'generate_weather_forecast_data'
]