"""
Pytest configuration and fixtures for bridge testing.
"""

import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from . import TEST_CONFIG


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return TEST_CONFIG.copy()


@pytest.fixture
def temp_dir():
    """Provide temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_revit_element():
    """Create a mock Revit element for testing."""
    element = Mock()
    element.Id = Mock()
    element.Id.IntegerValue = 12345
    element.Category = Mock()
    element.Category.Name = "Walls"
    element.Name = "Basic Wall"

    # Mock parameters
    element.LookupParameter = Mock(return_value=Mock())
    element.get_Parameter = Mock(return_value=Mock())

    # Mock geometry
    element.get_Geometry = Mock(return_value=[Mock()])

    return element


@pytest.fixture
def mock_revit_elements():
    """Create multiple mock Revit elements."""
    elements = []
    categories = ["Walls", "Windows", "Doors", "Rooms", "Mechanical Equipment"]

    for i, category in enumerate(categories):
        element = Mock()
        element.Id = Mock()
        element.Id.IntegerValue = 10000 + i
        element.Category = Mock()
        element.Category.Name = category
        element.Name = f"Test {category} {i}"
        element.LookupParameter = Mock(return_value=Mock())
        element.get_Parameter = Mock(return_value=Mock())
        element.get_Geometry = Mock(return_value=[Mock()])
        elements.append(element)

    return elements


@pytest.fixture
def sample_element_data():
    """Provide sample element data for serialization testing."""
    return {
        "id": "12345",
        "category": "Walls",
        "name": "Basic Wall",
        "type": "Wall",
        "parameters": {
            "Height": {"value": 3000, "type": "Length", "unit": "mm"},
            "Width": {"value": 200, "type": "Length", "unit": "mm"},
            "Material": {"value": "Concrete", "type": "Text", "unit": None},
        },
        "geometry": {
            "type": "solid",
            "volume": 600000,
            "area": 6000,
            "vertices": [[0, 0, 0], [4000, 0, 0], [4000, 200, 0], [0, 200, 0]],
            "faces": [],
        },
        "location": {"x": 2000, "y": 100, "z": 1500},
        "level": "Level 1",
    }


@pytest.fixture
def sample_analysis_request():
    """Provide sample analysis request data."""
    return {
        "analysis_id": "test_analysis_001",
        "analysis_type": "energy_performance",
        "elements": ["12345", "12346", "12347"],
        "parameters": {
            "include_thermal": True,
            "weather_data": "default",
            "calculation_method": "detailed",
        },
        "timestamp": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_analysis_result():
    """Provide sample analysis result data."""
    return {
        "analysis_id": "test_analysis_001",
        "success": True,
        "results": {
            "overall_rating": "B+",
            "energy_consumption": 150.5,
            "thermal_performance": {"u_value": 0.3, "thermal_bridge_factor": 0.05},
            "elements": {
                "12345": {
                    "rating": "A",
                    "energy_consumption": 45.2,
                    "recommendations": ["Add insulation layer"],
                }
            },
        },
        "metadata": {
            "analysis_duration": 12.5,
            "elements_processed": 3,
            "warnings": [],
            "timestamp": datetime.now().isoformat(),
        },
    }


@pytest.fixture
def mock_bridge_config():
    """Provide mock bridge configuration."""
    return {
        "communication": {
            "default_protocol": "named_pipes",
            "pipe_name": "test_revitpy_bridge",
            "websocket_host": "localhost",
            "websocket_port": 8766,
            "file_exchange_dir": str(TEST_CONFIG["temp_dir"]),
            "connection_timeout": 10,
        },
        "serialization": {
            "compression_enabled": True,
            "batch_size": 50,
            "max_file_size_mb": 10,
            "format_version": "1.0",
        },
        "performance": {
            "enable_caching": True,
            "cache_size_mb": 100,
            "max_concurrent_analyses": 3,
            "progress_update_interval": 1.0,
        },
    }


@pytest.fixture
def mock_pyrevit_ui():
    """Mock PyRevit UI components for testing."""
    ui_mock = Mock()

    # TaskDialog mock
    ui_mock.TaskDialog = Mock()
    ui_mock.TaskDialog.Show = Mock(return_value=Mock())
    ui_mock.TaskDialogResult = Mock()
    ui_mock.TaskDialogResult.Yes = "Yes"
    ui_mock.TaskDialogResult.No = "No"
    ui_mock.TaskDialogCommonButtons = Mock()
    ui_mock.TaskDialogCommonButtons.Yes = "Yes"
    ui_mock.TaskDialogCommonButtons.No = "No"

    # Forms mock
    forms_mock = Mock()
    forms_mock.SelectFromList = Mock()
    forms_mock.GetValueWindow = Mock()
    forms_mock.ProgressWindow = Mock()

    return {"UI": ui_mock, "forms": forms_mock}


@pytest.fixture
def sample_sensor_data():
    """Provide sample IoT sensor data for testing."""
    return [
        {
            "sensor_id": "temp_001",
            "sensor_type": "temperature",
            "timestamp": datetime.now().isoformat(),
            "value": 22.5,
            "unit": "°C",
            "element_id": "12345",
            "location": "center",
            "quality": "good",
        },
        {
            "sensor_id": "humidity_001",
            "sensor_type": "humidity",
            "timestamp": datetime.now().isoformat(),
            "value": 45.0,
            "unit": "%",
            "element_id": "12345",
            "location": "center",
            "quality": "good",
        },
    ]


@pytest.fixture
def performance_test_data():
    """Generate larger dataset for performance testing."""
    elements = []
    for i in range(1000):
        element = {
            "id": f"element_{i:06d}",
            "category": f"Category_{i % 10}",
            "name": f"Element {i}",
            "type": "TestElement",
            "parameters": {
                "param1": {"value": i * 1.5, "type": "Number", "unit": "units"},
                "param2": {"value": f"Value_{i}", "type": "Text", "unit": None},
            },
            "geometry": {
                "type": "box",
                "volume": i * 100,
                "area": i * 10,
                "vertices": [[0, 0, 0], [i, i, i]],
            },
        }
        elements.append(element)

    return elements


# Helper functions for tests


def create_test_file(temp_dir: Path, filename: str, content: str) -> Path:
    """Create a test file with given content."""
    file_path = temp_dir / filename
    file_path.write_text(content)
    return file_path


def create_test_json_file(temp_dir: Path, filename: str, data: dict[str, Any]) -> Path:
    """Create a test JSON file with given data."""
    file_path = temp_dir / filename
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
    return file_path


async def wait_with_timeout(coroutine, timeout: float = 5.0):
    """Wait for coroutine with timeout."""
    return await asyncio.wait_for(coroutine, timeout=timeout)
