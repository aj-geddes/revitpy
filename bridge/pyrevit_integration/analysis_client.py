"""
High-level analysis client for PyRevit integration.

This module provides a simple, high-level interface for PyRevit scripts
to execute common analysis workflows with RevitPy.
"""

from dataclasses import dataclass
from typing import Any

from .element_selector import ElementSelector
from .revitpy_bridge import RevitPyBridge
from .ui_helpers import BridgeUIHelpers


@dataclass
class AnalysisWorkflow:
    """Represents a complete analysis workflow."""

    name: str
    description: str
    analysis_type: str
    default_parameters: dict[str, Any]
    required_categories: list[str]
    estimated_time_per_element: float  # seconds

    def estimate_total_time(self, element_count: int) -> str:
        """Estimate total processing time."""
        total_seconds = element_count * self.estimated_time_per_element

        if total_seconds < 60:
            return f"{total_seconds:.0f} seconds"
        elif total_seconds < 3600:
            return f"{total_seconds/60:.1f} minutes"
        else:
            return f"{total_seconds/3600:.1f} hours"


class AnalysisClient:
    """
    High-level client for executing RevitPy analysis workflows.

    This class provides pre-configured workflows for common analysis tasks,
    making it easy for PyRevit scripts to leverage RevitPy capabilities.

    Example Usage:
        # Simple energy analysis
        client = AnalysisClient()
        results = client.analyze_energy_performance()

        # Custom analysis with specific elements
        walls = select_walls()
        results = client.analyze_thermal_performance(walls)
    """

    def __init__(self, bridge_config: dict[str, Any] | None = None):
        """Initialize analysis client."""
        self.bridge = RevitPyBridge(**(bridge_config or {}))
        self.element_selector = ElementSelector()

        # Pre-configured workflows
        self.workflows = {
            "energy_performance": AnalysisWorkflow(
                name="Building Energy Performance",
                description="Analyze energy efficiency of building elements including thermal performance, insulation values, and energy consumption patterns",
                analysis_type="energy_performance",
                default_parameters={
                    "include_thermal": True,
                    "weather_data": "default",
                    "calculation_method": "detailed",
                },
                required_categories=["Walls", "Windows", "Doors", "Roofs", "Floors"],
                estimated_time_per_element=0.5,
            ),
            "space_optimization": AnalysisWorkflow(
                name="Space Layout Optimization",
                description="Optimize space layout using ML algorithms to maximize efficiency and user satisfaction",
                analysis_type="space_optimization",
                default_parameters={
                    "optimization_goal": "efficiency",
                    "algorithm": "genetic_algorithm",
                    "iterations": 100,
                },
                required_categories=["Rooms", "Spaces", "Furniture"],
                estimated_time_per_element=2.0,
            ),
            "structural_analysis": AnalysisWorkflow(
                name="Structural Analysis",
                description="Perform structural analysis including load calculations, stress analysis, and safety factor verification",
                analysis_type="structural_analysis",
                default_parameters={
                    "load_combinations": "standard",
                    "safety_factor": 1.5,
                    "analysis_type": "linear",
                },
                required_categories=[
                    "Structural Columns",
                    "Structural Framing",
                    "Floors",
                    "Structural Foundations",
                ],
                estimated_time_per_element=1.0,
            ),
            "clash_detection": AnalysisWorkflow(
                name="Advanced Clash Detection",
                description="Detect clashes between building elements using advanced 3D geometry analysis",
                analysis_type="clash_detection",
                default_parameters={
                    "tolerance": 0.01,
                    "clash_types": ["hard_clash", "soft_clash"],
                    "priority_levels": True,
                },
                required_categories=[
                    "Mechanical Equipment",
                    "Electrical Equipment",
                    "Plumbing Fixtures",
                    "Ducts",
                    "Pipes",
                ],
                estimated_time_per_element=0.3,
            ),
            "thermal_analysis": AnalysisWorkflow(
                name="Thermal Performance Analysis",
                description="Detailed thermal analysis including heat transfer, thermal bridging, and condensation risk",
                analysis_type="thermal_analysis",
                default_parameters={
                    "include_thermal_bridging": True,
                    "condensation_analysis": True,
                    "precision": "high",
                },
                required_categories=["Walls", "Windows", "Doors", "Roofs"],
                estimated_time_per_element=0.8,
            ),
            "daylight_analysis": AnalysisWorkflow(
                name="Daylight and Solar Analysis",
                description="Analyze daylight penetration, solar heat gain, and shading effects",
                analysis_type="daylight_analysis",
                default_parameters={
                    "sky_model": "cie_overcast",
                    "include_solar_gains": True,
                    "time_periods": "annual",
                },
                required_categories=["Windows", "Skylights", "Curtain Walls", "Rooms"],
                estimated_time_per_element=1.5,
            ),
        }

    def analyze_energy_performance(
        self,
        elements: list[Any] | None = None,
        parameters: dict[str, Any] | None = None,
        interactive: bool = True,
    ) -> dict[str, Any]:
        """
        Perform energy performance analysis on building elements.

        Args:
            elements: Elements to analyze (auto-select if None)
            parameters: Analysis parameters (use defaults if None)
            interactive: Show UI dialogs for configuration

        Returns:
            Analysis results including efficiency ratings and recommendations
        """
        return self._execute_workflow(
            "energy_performance", elements, parameters, interactive
        )

    def optimize_space_layout(
        self,
        elements: list[Any] | None = None,
        parameters: dict[str, Any] | None = None,
        interactive: bool = True,
    ) -> dict[str, Any]:
        """
        Optimize space layout using ML algorithms.

        Args:
            elements: Space elements to optimize (auto-select if None)
            parameters: Optimization parameters
            interactive: Show UI dialogs for configuration

        Returns:
            Optimization results with layout suggestions and efficiency improvements
        """
        return self._execute_workflow(
            "space_optimization", elements, parameters, interactive
        )

    def analyze_structural_performance(
        self,
        elements: list[Any] | None = None,
        parameters: dict[str, Any] | None = None,
        interactive: bool = True,
    ) -> dict[str, Any]:
        """
        Perform structural analysis on building elements.

        Args:
            elements: Structural elements to analyze (auto-select if None)
            parameters: Analysis parameters
            interactive: Show UI dialogs for configuration

        Returns:
            Structural analysis results including stress, deflection, and safety factors
        """
        return self._execute_workflow(
            "structural_analysis", elements, parameters, interactive
        )

    def detect_clashes(
        self,
        elements: list[Any] | None = None,
        parameters: dict[str, Any] | None = None,
        interactive: bool = True,
    ) -> dict[str, Any]:
        """
        Perform advanced clash detection between elements.

        Args:
            elements: Elements to check for clashes (auto-select if None)
            parameters: Clash detection parameters
            interactive: Show UI dialogs for configuration

        Returns:
            Clash detection results with detailed clash reports
        """
        return self._execute_workflow(
            "clash_detection", elements, parameters, interactive
        )

    def analyze_thermal_performance(
        self,
        elements: list[Any] | None = None,
        parameters: dict[str, Any] | None = None,
        interactive: bool = True,
    ) -> dict[str, Any]:
        """
        Perform detailed thermal performance analysis.

        Args:
            elements: Building envelope elements to analyze (auto-select if None)
            parameters: Thermal analysis parameters
            interactive: Show UI dialogs for configuration

        Returns:
            Thermal analysis results including heat transfer and condensation risk
        """
        return self._execute_workflow(
            "thermal_analysis", elements, parameters, interactive
        )

    def analyze_daylight_performance(
        self,
        elements: list[Any] | None = None,
        parameters: dict[str, Any] | None = None,
        interactive: bool = True,
    ) -> dict[str, Any]:
        """
        Perform daylight and solar analysis.

        Args:
            elements: Windows, skylights, and spaces to analyze (auto-select if None)
            parameters: Daylight analysis parameters
            interactive: Show UI dialogs for configuration

        Returns:
            Daylight analysis results with illumination levels and solar gains
        """
        return self._execute_workflow(
            "daylight_analysis", elements, parameters, interactive
        )

    def run_custom_analysis(
        self,
        analysis_type: str,
        elements: list[Any] | None = None,
        parameters: dict[str, Any] | None = None,
        interactive: bool = True,
    ) -> dict[str, Any]:
        """
        Run a custom analysis type not covered by pre-configured workflows.

        Args:
            analysis_type: Custom analysis type identifier
            elements: Elements to analyze
            parameters: Analysis parameters
            interactive: Show UI dialogs for configuration

        Returns:
            Analysis results
        """
        try:
            # Get elements if not provided
            if elements is None:
                if interactive:
                    elements = self.element_selector.select_elements_interactively(
                        f"Select elements for {analysis_type} analysis"
                    )
                else:
                    elements = self.element_selector.get_current_selection()

            if not elements:
                return {"success": False, "error": "No elements selected for analysis"}

            # Show element summary if interactive
            if interactive:
                element_summary = self.element_selector.create_element_summary(elements)
                BridgeUIHelpers.show_element_summary(element_summary)

            # Get parameters if interactive
            if interactive and parameters is None:
                # For custom analysis, we don't have predefined parameters
                # Could show a generic parameter input dialog
                parameters = {}

            parameters = parameters or {}

            # Execute analysis
            return self.bridge.execute_analysis(elements, analysis_type, parameters)

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_workflow(
        self,
        workflow_name: str,
        elements: list[Any] | None,
        parameters: dict[str, Any] | None,
        interactive: bool,
    ) -> dict[str, Any]:
        """Execute a pre-configured workflow."""
        try:
            workflow = self.workflows[workflow_name]

            # Get elements if not provided
            if elements is None:
                elements = self._get_workflow_elements(workflow, interactive)

            if not elements:
                return {"success": False, "error": "No elements selected for analysis"}

            # Validate elements for workflow
            validation = self.element_selector.validate_elements_for_analysis(
                elements, workflow.analysis_type
            )

            if not validation["valid"]:
                error_msg = (
                    f"Element validation failed: {'; '.join(validation['errors'])}"
                )
                if interactive:
                    BridgeUIHelpers.show_analysis_results(
                        {"success": False, "error": error_msg}, workflow.name
                    )
                return {"success": False, "error": error_msg}

            # Show warnings if interactive
            if interactive and validation["warnings"]:
                warning_msg = "\n".join(validation["warnings"])
                print(f"Warnings: {warning_msg}")

            # Prepare parameters
            final_parameters = workflow.default_parameters.copy()
            if parameters:
                final_parameters.update(parameters)

            # Show configuration if interactive
            if interactive:
                self.element_selector.create_element_summary(elements)
                estimated_time = workflow.estimate_total_time(len(elements))

                # Show confirmation dialog
                confirmed = BridgeUIHelpers.confirm_analysis_execution(
                    workflow.name, len(elements), estimated_time, final_parameters
                )

                if not confirmed:
                    return {"success": False, "error": "Analysis cancelled by user"}

                # Show progress dialog
                BridgeUIHelpers.show_analysis_progress(workflow.name, len(elements))

            # Execute analysis
            try:
                results = self.bridge.execute_analysis(
                    elements, workflow.analysis_type, final_parameters
                )

                # Add workflow metadata to results
                if isinstance(results, dict):
                    results["workflow_info"] = {
                        "workflow_name": workflow.name,
                        "description": workflow.description,
                        "element_count": len(elements),
                        "parameters_used": final_parameters,
                    }

                # Show results if interactive
                if interactive:
                    BridgeUIHelpers.show_analysis_results(results, workflow.name)

                return results

            except Exception as e:
                error_result = {"success": False, "error": str(e)}
                if interactive:
                    BridgeUIHelpers.show_analysis_results(error_result, workflow.name)
                return error_result

        except KeyError:
            return {"success": False, "error": f"Unknown workflow: {workflow_name}"}
        except Exception as e:
            return {"success": False, "error": f"Workflow execution failed: {e}"}

    def _get_workflow_elements(
        self, workflow: AnalysisWorkflow, interactive: bool
    ) -> list[Any]:
        """Get elements for a workflow."""
        if interactive:
            # Try to auto-select based on required categories
            elements = []
            for category in workflow.required_categories:
                category_elements = self.element_selector.select_elements_by_category(
                    [category]
                )
                elements.extend(category_elements)

            if elements:
                # Show summary and ask for confirmation
                element_summary = self.element_selector.create_element_summary(elements)
                BridgeUIHelpers.show_element_summary(element_summary)

                # Allow user to modify selection if needed
                use_auto_selection = BridgeUIHelpers.confirm_analysis_execution(
                    f"Auto-selected elements for {workflow.name}",
                    len(elements),
                    workflow.estimate_total_time(len(elements)),
                    {},
                )

                if not use_auto_selection:
                    # Let user select manually
                    elements = self.element_selector.select_elements_interactively(
                        f"Select elements for {workflow.name}"
                    )
            else:
                # Manual selection
                elements = self.element_selector.select_elements_interactively(
                    f"Select elements for {workflow.name}"
                )
        else:
            # Non-interactive: use current selection or auto-select
            elements = self.element_selector.get_current_selection()

            if not elements:
                # Try auto-selection based on categories
                for category in workflow.required_categories:
                    category_elements = (
                        self.element_selector.select_elements_by_category([category])
                    )
                    elements.extend(category_elements)

        return elements

    def get_available_workflows(self) -> dict[str, AnalysisWorkflow]:
        """Get all available pre-configured workflows."""
        return self.workflows.copy()

    def get_workflow_info(self, workflow_name: str) -> AnalysisWorkflow | None:
        """Get information about a specific workflow."""
        return self.workflows.get(workflow_name)

    def test_bridge_connection(self) -> dict[str, Any]:
        """Test connection to RevitPy bridge."""
        connection_test = self.bridge.test_connection()
        BridgeUIHelpers.show_connection_status(connection_test)
        return connection_test

    def get_bridge_statistics(self) -> dict[str, Any]:
        """Get bridge usage statistics."""
        return self.bridge.get_statistics()


# Convenience functions for quick workflow execution
def analyze_energy_performance(
    elements: list[Any] | None = None, **kwargs
) -> dict[str, Any]:
    """Quick energy performance analysis."""
    client = AnalysisClient()
    return client.analyze_energy_performance(elements, **kwargs)


def optimize_spaces(elements: list[Any] | None = None, **kwargs) -> dict[str, Any]:
    """Quick space optimization."""
    client = AnalysisClient()
    return client.optimize_space_layout(elements, **kwargs)


def detect_clashes(elements: list[Any] | None = None, **kwargs) -> dict[str, Any]:
    """Quick clash detection."""
    client = AnalysisClient()
    return client.detect_clashes(elements, **kwargs)


def analyze_structure(elements: list[Any] | None = None, **kwargs) -> dict[str, Any]:
    """Quick structural analysis."""
    client = AnalysisClient()
    return client.analyze_structural_performance(elements, **kwargs)


def analyze_thermal(elements: list[Any] | None = None, **kwargs) -> dict[str, Any]:
    """Quick thermal analysis."""
    client = AnalysisClient()
    return client.analyze_thermal_performance(elements, **kwargs)


def analyze_daylight(elements: list[Any] | None = None, **kwargs) -> dict[str, Any]:
    """Quick daylight analysis."""
    client = AnalysisClient()
    return client.analyze_daylight_performance(elements, **kwargs)
