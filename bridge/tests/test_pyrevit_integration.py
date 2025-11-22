"""
Tests for PyRevit integration components.
"""

from unittest.mock import Mock, patch

import pytest

from ..core.exceptions import BridgeException
from ..pyrevit_integration.analysis_client import AnalysisClient, AnalysisWorkflow
from ..pyrevit_integration.element_selector import ElementSelector
from ..pyrevit_integration.revitpy_bridge import RevitPyBridge
from ..pyrevit_integration.ui_helpers import BridgeUIHelpers


class TestRevitPyBridge:
    """Test main PyRevit bridge interface."""

    @pytest.fixture
    def bridge(self, mock_bridge_config):
        """Create RevitPy bridge for testing."""
        return RevitPyBridge(**mock_bridge_config)

    def test_bridge_initialization(self, bridge):
        """Test bridge initialization."""
        assert bridge is not None
        assert not bridge.is_connected()
        assert bridge.get_statistics()["total_requests"] == 0

    def test_connection_management(self, bridge):
        """Test connection management."""
        with patch.object(bridge, "_establish_connection", return_value=True):
            success = bridge.connect()
            assert success
            assert bridge.is_connected()

        bridge.disconnect()
        assert not bridge.is_connected()

    @pytest.mark.asyncio
    async def test_analysis_execution(
        self, bridge, mock_revit_elements, sample_analysis_result
    ):
        """Test analysis execution."""
        bridge.connected = True

        with patch.object(
            bridge, "_send_analysis_request", return_value=sample_analysis_result
        ):
            result = bridge.execute_analysis(
                mock_revit_elements, "energy_performance", {"include_thermal": True}
            )

            assert result["success"] is True
            assert "results" in result

    def test_connection_error_handling(self, bridge):
        """Test connection error handling."""
        with patch.object(
            bridge, "_establish_connection", side_effect=Exception("Connection failed")
        ):
            success = bridge.connect()
            assert not success
            assert not bridge.is_connected()

    def test_analysis_validation(self, bridge):
        """Test analysis request validation."""
        bridge.connected = True

        # Test with invalid elements
        with pytest.raises(BridgeException):
            bridge.execute_analysis([], "energy_performance", {})

        # Test with invalid analysis type
        with pytest.raises(BridgeException):
            bridge.execute_analysis([Mock()], "", {})

    def test_statistics_tracking(self, bridge):
        """Test statistics tracking."""
        initial_stats = bridge.get_statistics()
        assert initial_stats["total_requests"] == 0

        # Simulate requests
        bridge.statistics.total_requests = 10
        bridge.statistics.successful_requests = 8
        bridge.statistics.failed_requests = 2

        updated_stats = bridge.get_statistics()
        assert updated_stats["total_requests"] == 10
        assert updated_stats["success_rate"] == 0.8

    def test_timeout_handling(self, bridge):
        """Test request timeout handling."""
        bridge.connected = True
        bridge.request_timeout = 0.1  # Very short timeout for testing

        with patch.object(bridge, "_send_analysis_request") as mock_send:
            # Simulate slow response
            import asyncio

            async def slow_response(*args):
                await asyncio.sleep(0.2)  # Longer than timeout
                return {"success": True}

            mock_send.side_effect = slow_response

            result = bridge.execute_analysis([Mock()], "test_analysis", {})
            assert result["success"] is False
            assert "timeout" in result.get("error", "").lower()


class TestElementSelector:
    """Test element selection functionality."""

    @pytest.fixture
    def selector(self):
        """Create element selector for testing."""
        return ElementSelector()

    def test_element_selection_by_category(self, selector):
        """Test selecting elements by category."""
        with patch("pyrevit.revit.doc"):
            # Mock filtered element collector
            mock_collector = Mock()
            mock_elements = [Mock() for _ in range(5)]
            mock_collector.ToElements.return_value = mock_elements

            with patch(
                "pyrevit.revit.FilteredElementCollector", return_value=mock_collector
            ):
                elements = selector.select_elements_by_category(["Walls"])

                assert len(elements) == 5
                mock_collector.OfCategory.assert_called()

    def test_current_selection_retrieval(self, selector):
        """Test retrieving current Revit selection."""
        with patch("pyrevit.revit.get_selection") as mock_get_selection:
            mock_elements = [Mock() for _ in range(3)]
            mock_get_selection.return_value = mock_elements

            selected = selector.get_current_selection()

            assert len(selected) == 3
            mock_get_selection.assert_called_once()

    def test_interactive_element_selection(self, selector, mock_pyrevit_ui):
        """Test interactive element selection with UI."""
        with patch.multiple(
            "pyrevit", UI=mock_pyrevit_ui["UI"], forms=mock_pyrevit_ui["forms"]
        ):
            mock_pyrevit_ui["UI"].TaskDialogResult.Yes = "Yes"
            mock_pyrevit_ui["UI"].TaskDialog.Show.return_value = "Yes"

            # Mock element selection
            mock_elements = [Mock() for _ in range(2)]
            with patch.object(
                selector, "get_current_selection", return_value=mock_elements
            ):
                elements = selector.select_elements_interactively("Select elements")

                assert len(elements) == 2

    def test_element_validation_for_analysis(self, selector, mock_revit_elements):
        """Test validating elements for specific analysis types."""
        # Test valid elements for energy analysis
        validation = selector.validate_elements_for_analysis(
            mock_revit_elements, "energy_performance"
        )

        assert validation["valid"] is True
        assert len(validation["warnings"]) >= 0
        assert len(validation["errors"]) == 0

        # Test with no elements
        empty_validation = selector.validate_elements_for_analysis(
            [], "energy_performance"
        )
        assert empty_validation["valid"] is False
        assert len(empty_validation["errors"]) > 0

    def test_element_summary_creation(self, selector, mock_revit_elements):
        """Test creating element summary."""
        summary = selector.create_element_summary(mock_revit_elements)

        assert "total_count" in summary
        assert "by_category" in summary
        assert summary["total_count"] == len(mock_revit_elements)
        assert len(summary["by_category"]) > 0

    def test_element_filtering(self, selector, mock_revit_elements):
        """Test filtering elements by criteria."""
        # Add some variety to mock elements
        mock_revit_elements[0].Category.Name = "Walls"
        mock_revit_elements[1].Category.Name = "Windows"
        mock_revit_elements[2].Category.Name = "Walls"

        # Filter by category
        walls = selector.filter_elements_by_category(mock_revit_elements, ["Walls"])
        assert len(walls) == 2
        assert all(elem.Category.Name == "Walls" for elem in walls)


class TestBridgeUIHelpers:
    """Test UI helper functionality."""

    @pytest.fixture
    def ui_helpers(self):
        """Create UI helpers instance."""
        return BridgeUIHelpers()

    def test_show_element_summary(self, ui_helpers, mock_pyrevit_ui):
        """Test showing element summary dialog."""
        with patch.multiple(
            "pyrevit", UI=mock_pyrevit_ui["UI"], forms=mock_pyrevit_ui["forms"]
        ):
            element_summary = {
                "total_count": 5,
                "by_category": {"Walls": 3, "Windows": 2},
            }

            ui_helpers.show_element_summary(element_summary)

            mock_pyrevit_ui["UI"].TaskDialog.Show.assert_called()

    def test_show_analysis_results(
        self, ui_helpers, mock_pyrevit_ui, sample_analysis_result
    ):
        """Test showing analysis results dialog."""
        with patch.multiple(
            "pyrevit", UI=mock_pyrevit_ui["UI"], forms=mock_pyrevit_ui["forms"]
        ):
            ui_helpers.show_analysis_results(sample_analysis_result, "Energy Analysis")

            mock_pyrevit_ui["UI"].TaskDialog.Show.assert_called()

    def test_confirm_analysis_execution(self, ui_helpers, mock_pyrevit_ui):
        """Test analysis execution confirmation."""
        with patch.multiple(
            "pyrevit", UI=mock_pyrevit_ui["UI"], forms=mock_pyrevit_ui["forms"]
        ):
            mock_pyrevit_ui["UI"].TaskDialog.Show.return_value = "Yes"
            mock_pyrevit_ui["UI"].TaskDialogResult.Yes = "Yes"

            confirmed = ui_helpers.confirm_analysis_execution(
                "Test Analysis",
                element_count=10,
                estimated_time="30 seconds",
                parameters={},
            )

            assert confirmed is True
            mock_pyrevit_ui["UI"].TaskDialog.Show.assert_called()

    def test_show_connection_status(self, ui_helpers, mock_pyrevit_ui):
        """Test showing connection status."""
        with patch.multiple(
            "pyrevit", UI=mock_pyrevit_ui["UI"], forms=mock_pyrevit_ui["forms"]
        ):
            connection_status = {
                "connected": True,
                "protocol": "websocket",
                "latency": 15.5,
            }

            ui_helpers.show_connection_status(connection_status)

            mock_pyrevit_ui["UI"].TaskDialog.Show.assert_called()

    def test_show_analysis_progress(self, ui_helpers, mock_pyrevit_ui):
        """Test showing analysis progress dialog."""
        with patch.multiple(
            "pyrevit", UI=mock_pyrevit_ui["UI"], forms=mock_pyrevit_ui["forms"]
        ):
            mock_progress = Mock()
            mock_pyrevit_ui["forms"].ProgressWindow.return_value = mock_progress

            progress_dialog = ui_helpers.show_analysis_progress("Test Analysis", 100)

            assert progress_dialog is not None
            mock_pyrevit_ui["forms"].ProgressWindow.assert_called()


class TestAnalysisClient:
    """Test high-level analysis client."""

    @pytest.fixture
    def analysis_client(self, mock_bridge_config):
        """Create analysis client for testing."""
        return AnalysisClient(mock_bridge_config)

    def test_client_initialization(self, analysis_client):
        """Test client initialization."""
        assert analysis_client is not None
        assert hasattr(analysis_client, "workflows")
        assert len(analysis_client.workflows) > 0

    def test_available_workflows(self, analysis_client):
        """Test getting available workflows."""
        workflows = analysis_client.get_available_workflows()

        assert isinstance(workflows, dict)
        assert "energy_performance" in workflows
        assert "space_optimization" in workflows
        assert "structural_analysis" in workflows
        assert "clash_detection" in workflows

    def test_workflow_info_retrieval(self, analysis_client):
        """Test getting workflow information."""
        workflow_info = analysis_client.get_workflow_info("energy_performance")

        assert workflow_info is not None
        assert isinstance(workflow_info, AnalysisWorkflow)
        assert workflow_info.name is not None
        assert len(workflow_info.required_categories) > 0

    def test_energy_analysis_workflow(
        self, analysis_client, mock_revit_elements, sample_analysis_result
    ):
        """Test energy performance analysis workflow."""
        with patch.object(
            analysis_client.bridge,
            "execute_analysis",
            return_value=sample_analysis_result,
        ):
            result = analysis_client.analyze_energy_performance(
                elements=mock_revit_elements, interactive=False
            )

            assert result["success"] is True
            assert "workflow_info" in result

    def test_space_optimization_workflow(self, analysis_client, mock_revit_elements):
        """Test space optimization workflow."""
        optimization_result = {
            "success": True,
            "results": {
                "efficiency_improvement": 0.15,
                "optimized_layout": {"spaces": 5, "furniture": 20},
            },
        }

        with patch.object(
            analysis_client.bridge, "execute_analysis", return_value=optimization_result
        ):
            result = analysis_client.optimize_space_layout(
                elements=mock_revit_elements, interactive=False
            )

            assert result["success"] is True
            assert result["results"]["efficiency_improvement"] == 0.15

    def test_custom_analysis_execution(self, analysis_client, mock_revit_elements):
        """Test custom analysis execution."""
        custom_result = {"success": True, "custom_data": "test"}

        with patch.object(
            analysis_client.bridge, "execute_analysis", return_value=custom_result
        ):
            result = analysis_client.run_custom_analysis(
                "custom_analysis_type",
                elements=mock_revit_elements,
                parameters={"custom_param": "value"},
                interactive=False,
            )

            assert result["success"] is True
            assert result["custom_data"] == "test"

    def test_bridge_connection_test(self, analysis_client):
        """Test bridge connection testing."""
        connection_result = {
            "connected": True,
            "latency": 25.0,
            "protocol": "websocket",
        }

        with patch.object(
            analysis_client.bridge, "test_connection", return_value=connection_result
        ):
            with patch.object(
                analysis_client,
                "test_bridge_connection",
                return_value=connection_result,
            ):
                result = analysis_client.test_bridge_connection()

                assert result["connected"] is True
                assert result["latency"] == 25.0

    def test_element_validation_workflow(self, analysis_client, mock_revit_elements):
        """Test element validation in workflow execution."""
        # Mock element validation to fail
        validation_result = {
            "valid": False,
            "errors": ["Invalid element category for this analysis"],
            "warnings": [],
        }

        with patch.object(
            analysis_client.element_selector,
            "validate_elements_for_analysis",
            return_value=validation_result,
        ):
            result = analysis_client.analyze_energy_performance(
                elements=mock_revit_elements, interactive=False
            )

            assert result["success"] is False
            assert "validation" in result["error"].lower()


class TestAnalysisWorkflow:
    """Test analysis workflow dataclass."""

    def test_workflow_creation(self):
        """Test creating analysis workflow."""
        workflow = AnalysisWorkflow(
            name="Test Workflow",
            description="Test description",
            analysis_type="test_analysis",
            default_parameters={"param1": "value1"},
            required_categories=["Walls", "Windows"],
            estimated_time_per_element=0.5,
        )

        assert workflow.name == "Test Workflow"
        assert workflow.analysis_type == "test_analysis"
        assert len(workflow.required_categories) == 2

    def test_time_estimation(self):
        """Test time estimation functionality."""
        workflow = AnalysisWorkflow(
            name="Test Workflow",
            description="Test description",
            analysis_type="test_analysis",
            default_parameters={},
            required_categories=[],
            estimated_time_per_element=1.5,  # 1.5 seconds per element
        )

        # Test different element counts
        assert "seconds" in workflow.estimate_total_time(30)  # 45 seconds
        assert "minutes" in workflow.estimate_total_time(100)  # 2.5 minutes
        assert "hours" in workflow.estimate_total_time(5000)  # 2+ hours
