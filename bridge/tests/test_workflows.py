"""
Tests for complete workflow functionality.
"""

import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from ..workflows.building_performance_workflow import BuildingPerformanceWorkflow
from ..workflows.real_time_monitoring_workflow import (
    MonitoringAlert,
    RealTimeMonitoringWorkflow,
    SensorReading,
)
from ..workflows.space_optimization_workflow import SpaceOptimizationWorkflow


class TestBuildingPerformanceWorkflow:
    """Test building performance analysis workflow."""

    @pytest.fixture
    def performance_workflow(self):
        """Create building performance workflow for testing."""
        return BuildingPerformanceWorkflow()

    def test_workflow_initialization(self, performance_workflow):
        """Test workflow initialization."""
        assert performance_workflow is not None
        assert hasattr(performance_workflow, "bridge")
        assert hasattr(performance_workflow, "element_selector")

    def test_element_selection_step(self, performance_workflow, mock_revit_elements):
        """Test element selection step."""
        with patch.object(
            performance_workflow.element_selector,
            "select_elements_interactively",
            return_value=mock_revit_elements,
        ):
            elements, categories = performance_workflow._step_1_select_elements(
                interactive=False
            )

            assert len(elements) > 0
            assert len(categories) > 0

    def test_analysis_execution_step(self, performance_workflow, mock_revit_elements):
        """Test analysis execution step."""
        analysis_result = {
            "success": True,
            "results": {
                "overall_rating": "B+",
                "energy_consumption": 150.5,
                "thermal_performance": {"u_value": 0.3},
            },
        }

        with patch.object(
            performance_workflow.bridge,
            "execute_analysis",
            return_value=analysis_result,
        ):
            result = performance_workflow._step_2_execute_analysis(
                mock_revit_elements, {"include_thermal": True}, interactive=False
            )

            assert result["success"] is True
            assert "results" in result

    def test_results_processing_step(self, performance_workflow):
        """Test results processing step."""
        raw_results = {
            "success": True,
            "results": {
                "overall_rating": "B+",
                "elements": {"12345": {"rating": "A", "energy_consumption": 45.2}},
            },
        }

        processed = performance_workflow._step_3_process_results(
            raw_results, interactive=False
        )

        assert processed is not None
        assert "summary" in processed
        assert "recommendations" in processed

    def test_complete_workflow_execution(
        self, performance_workflow, mock_revit_elements
    ):
        """Test complete workflow execution."""
        with patch.multiple(
            performance_workflow,
            _step_1_select_elements=Mock(
                return_value=(mock_revit_elements, ["Walls", "Windows"])
            ),
            _step_2_execute_analysis=Mock(
                return_value={"success": True, "results": {}}
            ),
            _step_3_process_results=Mock(return_value={"summary": "Complete"}),
        ):
            result = performance_workflow.start_performance_workflow(interactive=False)

            assert result["success"] is True
            assert result["elements_analyzed"] > 0

    def test_error_handling_in_workflow(self, performance_workflow):
        """Test error handling during workflow execution."""
        with patch.object(
            performance_workflow,
            "_step_1_select_elements",
            side_effect=Exception("Selection failed"),
        ):
            result = performance_workflow.start_performance_workflow(interactive=False)

            assert result["success"] is False
            assert "error" in result


class TestSpaceOptimizationWorkflow:
    """Test space optimization workflow."""

    @pytest.fixture
    def optimization_workflow(self):
        """Create space optimization workflow for testing."""
        return SpaceOptimizationWorkflow()

    def test_workflow_initialization(self, optimization_workflow):
        """Test workflow initialization."""
        assert optimization_workflow is not None
        assert hasattr(optimization_workflow, "optimization_engine")
        assert len(optimization_workflow.optimization_algorithms) > 0

    def test_space_analysis_step(self, optimization_workflow, mock_revit_elements):
        """Test space analysis step."""
        # Mock room elements
        room_elements = [
            elem for elem in mock_revit_elements if "Room" in str(elem.Category.Name)
        ]

        with patch.object(
            optimization_workflow.element_selector,
            "select_elements_by_category",
            return_value=room_elements,
        ):
            spaces, furniture = optimization_workflow._step_1_analyze_current_layout(
                interactive=False
            )

            assert isinstance(spaces, list)
            assert isinstance(furniture, list)

    def test_optimization_algorithm_selection(self, optimization_workflow):
        """Test optimization algorithm selection."""
        available_algorithms = optimization_workflow._get_available_algorithms()

        assert len(available_algorithms) > 0
        assert "genetic_algorithm" in available_algorithms
        assert "simulated_annealing" in available_algorithms

    def test_genetic_algorithm_optimization(self, optimization_workflow):
        """Test genetic algorithm optimization."""
        mock_spaces = [
            {"id": "room_1", "area": 100, "current_efficiency": 0.7},
            {"id": "room_2", "area": 150, "current_efficiency": 0.6},
        ]

        optimization_params = {
            "algorithm": "genetic_algorithm",
            "population_size": 20,
            "generations": 10,
        }

        result = optimization_workflow._run_genetic_algorithm(
            mock_spaces, optimization_params
        )

        assert result is not None
        assert "best_layout" in result
        assert "efficiency_improvement" in result

    def test_simulated_annealing_optimization(self, optimization_workflow):
        """Test simulated annealing optimization."""
        mock_spaces = [
            {"id": "room_1", "area": 100, "current_efficiency": 0.7},
            {"id": "room_2", "area": 150, "current_efficiency": 0.6},
        ]

        optimization_params = {
            "algorithm": "simulated_annealing",
            "initial_temperature": 100,
            "cooling_rate": 0.95,
        }

        result = optimization_workflow._run_simulated_annealing(
            mock_spaces, optimization_params
        )

        assert result is not None
        assert "optimized_layout" in result
        assert "efficiency_score" in result

    def test_layout_preview_generation(self, optimization_workflow):
        """Test layout preview generation."""
        optimized_layout = {
            "spaces": [{"id": "room_1", "x": 0, "y": 0, "width": 10, "height": 10}],
            "furniture": [{"id": "desk_1", "x": 2, "y": 2, "type": "desk"}],
        }

        preview = optimization_workflow._generate_layout_preview(optimized_layout)

        assert preview is not None
        assert "visualization_data" in preview

    def test_complete_optimization_workflow(
        self, optimization_workflow, mock_revit_elements
    ):
        """Test complete optimization workflow execution."""
        with patch.multiple(
            optimization_workflow,
            _step_1_analyze_current_layout=Mock(return_value=([], [])),
            _step_2_run_optimization=Mock(
                return_value={"efficiency_improvement": 0.15}
            ),
            _step_3_generate_preview=Mock(return_value={"preview_generated": True}),
        ):
            result = optimization_workflow.start_optimization_workflow(
                interactive=False
            )

            assert result["success"] is True
            assert (
                "optimization_completed" in result
                or result.get("efficiency_improvement") is not None
            )


class TestRealTimeMonitoringWorkflow:
    """Test real-time monitoring workflow."""

    @pytest.fixture
    def monitoring_workflow(self):
        """Create real-time monitoring workflow for testing."""
        return RealTimeMonitoringWorkflow()

    def test_workflow_initialization(self, monitoring_workflow):
        """Test workflow initialization."""
        assert monitoring_workflow is not None
        assert hasattr(monitoring_workflow, "sensor_types")
        assert len(monitoring_workflow.sensor_types) > 0
        assert not monitoring_workflow.monitoring_active

    def test_sensor_configuration_step(self, monitoring_workflow, mock_revit_elements):
        """Test sensor configuration step."""
        elements, sensor_config = monitoring_workflow._step_1_configure_monitoring(
            interactive=False
        )

        assert isinstance(elements, list)
        assert isinstance(sensor_config, dict)

    def test_data_source_connection_step(self, monitoring_workflow):
        """Test data source connection step."""
        sensor_config = {
            "room_001": {"temp_sensor": {"type": "temperature", "location": "center"}}
        }

        with patch.multiple(
            monitoring_workflow,
            _connect_to_iot_platform=Mock(return_value=True),
            _connect_to_weather_api=Mock(return_value=True),
            _connect_to_energy_grid=Mock(return_value=True),
        ):
            data_sources = monitoring_workflow._step_2_connect_data_sources(
                sensor_config, interactive=False
            )

            assert len(data_sources) > 0
            assert "iot_sensors" in data_sources

    def test_baseline_establishment_step(
        self, monitoring_workflow, mock_revit_elements
    ):
        """Test baseline establishment step."""
        sensor_config = {
            "12345": {"temp_001": {"type": "temperature", "location": "center"}}
        }

        baselines = monitoring_workflow._step_3_establish_baselines(
            mock_revit_elements, sensor_config, interactive=False
        )

        assert isinstance(baselines, dict)
        assert len(baselines) > 0

    @pytest.mark.asyncio
    async def test_sensor_reading_collection(self, monitoring_workflow):
        """Test sensor reading collection."""
        sensor_config = {
            "12345": {
                "temp_001": {"type": "temperature", "location": "center"},
                "humidity_001": {"type": "humidity", "location": "center"},
            }
        }

        readings = await monitoring_workflow._collect_sensor_readings(sensor_config)

        assert isinstance(readings, list)
        assert len(readings) == 2
        assert all(isinstance(reading, SensorReading) for reading in readings)

    def test_realistic_reading_generation(self, monitoring_workflow):
        """Test realistic sensor reading generation."""
        # Set up baseline
        monitoring_workflow.performance_baselines = {
            "12345": {
                "temp_001": {
                    "sensor_type": "temperature",
                    "baseline_value": 22.0,
                    "variance": 1.0,
                }
            }
        }

        reading = monitoring_workflow._generate_realistic_reading(
            "temp_001", "temperature"
        )

        assert isinstance(reading, float)
        assert 15 <= reading <= 30  # Reasonable temperature range

    @pytest.mark.asyncio
    async def test_anomaly_detection(self, monitoring_workflow, sample_sensor_data):
        """Test anomaly detection functionality."""
        # Convert sample data to SensorReading objects
        readings = []
        for data in sample_sensor_data:
            reading = SensorReading(
                sensor_id=data["sensor_id"],
                sensor_type=data["sensor_type"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                value=data["value"],
                unit=data["unit"],
                element_id=data["element_id"],
                location=data.get("location"),
                quality=data.get("quality", "good"),
            )
            readings.append(reading)

        # Test with extreme values to trigger alerts
        readings[0].value = 50.0  # Extreme temperature

        alerts = await monitoring_workflow._detect_anomalies(readings)

        assert isinstance(alerts, list)
        # Should detect temperature anomaly
        temp_alerts = [
            alert for alert in alerts if "temperature" in alert.description.lower()
        ]
        assert len(temp_alerts) > 0

    @pytest.mark.asyncio
    async def test_parameter_updates(
        self, monitoring_workflow, mock_revit_elements, sample_sensor_data
    ):
        """Test Revit parameter updates."""
        # Convert sample data to SensorReading objects
        readings = []
        for data in sample_sensor_data:
            reading = SensorReading(
                sensor_id=data["sensor_id"],
                sensor_type=data["sensor_type"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                value=data["value"],
                unit=data["unit"],
                element_id=data["element_id"],
                location=data.get("location"),
            )
            readings.append(reading)

        updates_applied = await monitoring_workflow._update_revit_parameters(
            mock_revit_elements, readings
        )

        assert isinstance(updates_applied, int)
        assert updates_applied >= 0

    @pytest.mark.asyncio
    async def test_background_monitoring(
        self, monitoring_workflow, mock_revit_elements
    ):
        """Test background monitoring execution."""
        sensor_config = {
            "12345": {"temp_001": {"type": "temperature", "location": "center"}}
        }

        # Run short monitoring session
        monitoring_task = asyncio.create_task(
            monitoring_workflow._run_background_monitoring(
                mock_revit_elements,
                sensor_config,
                duration=1,  # 1 second
            )
        )

        await monitoring_task

        # Should have completed without error
        assert not monitoring_workflow.monitoring_active

    def test_monitoring_summary(self, monitoring_workflow):
        """Test monitoring session summary."""
        # Set up some mock data
        monitoring_workflow.monitored_elements = {"12345": {}, "12346": {}}
        monitoring_workflow.alerts_active = [
            MonitoringAlert(
                alert_id="test_001",
                alert_type="temperature",
                severity="medium",
                element_id="12345",
                description="Temperature high",
                timestamp=datetime.now(),
                current_value=28.0,
                threshold_value=26.0,
                recommended_action="Check HVAC",
            )
        ]

        summary = monitoring_workflow.get_monitoring_summary()

        assert summary["elements_monitored"] == 2
        assert summary["total_alerts"] == 1
        assert summary["alert_breakdown"]["medium"] == 1

    def test_monitoring_stop(self, monitoring_workflow):
        """Test stopping monitoring workflow."""
        monitoring_workflow.monitoring_active = True

        monitoring_workflow.stop_monitoring()

        assert not monitoring_workflow.monitoring_active


class TestSensorReading:
    """Test SensorReading dataclass."""

    def test_sensor_reading_creation(self):
        """Test creating sensor reading."""
        reading = SensorReading(
            sensor_id="temp_001",
            sensor_type="temperature",
            timestamp=datetime.now(),
            value=22.5,
            unit="°C",
            element_id="12345",
            location="center",
            quality="good",
        )

        assert reading.sensor_id == "temp_001"
        assert reading.sensor_type == "temperature"
        assert reading.value == 22.5
        assert reading.unit == "°C"


class TestMonitoringAlert:
    """Test MonitoringAlert dataclass."""

    def test_monitoring_alert_creation(self):
        """Test creating monitoring alert."""
        alert = MonitoringAlert(
            alert_id="alert_001",
            alert_type="temperature_high",
            severity="high",
            element_id="12345",
            description="Temperature exceeds safe limits",
            timestamp=datetime.now(),
            current_value=35.0,
            threshold_value=30.0,
            recommended_action="Check cooling system",
        )

        assert alert.alert_id == "alert_001"
        assert alert.severity == "high"
        assert alert.current_value == 35.0
        assert alert.threshold_value == 30.0
