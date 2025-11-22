"""
UI helper functions for PyRevit bridge integration.
"""

import json
import time
from typing import Any

# PyRevit imports (these would be available in PyRevit environment)
try:
    from pyrevit import UI, forms
    from pyrevit.framework import Windows
    from System.Windows.Forms import DialogResult

    PYREVIT_AVAILABLE = True
except ImportError:
    # For development/testing outside PyRevit
    PYREVIT_AVAILABLE = False


class BridgeUIHelpers:
    """UI helper functions for RevitPy bridge integration in PyRevit."""

    @staticmethod
    def show_analysis_selection_dialog(
        available_analyses: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """
        Show dialog for selecting analysis type.

        Args:
            available_analyses: List of available analysis types with metadata

        Returns:
            Selected analysis configuration or None if cancelled
        """
        if not PYREVIT_AVAILABLE:
            # Fallback for non-PyRevit environment
            return BridgeUIHelpers._console_analysis_selection(available_analyses)

        try:
            # Create analysis options
            analysis_options = []
            for analysis in available_analyses:
                option_text = f"{analysis['name']} - {analysis.get('description', '')}"
                analysis_options.append(option_text)

            # Show selection dialog
            selected = forms.SelectFromList.show(
                analysis_options,
                title="Select RevitPy Analysis",
                multiselect=False,
                name_attr=None,
                button_name="Select Analysis",
            )

            if selected:
                # Find the selected analysis
                selected_index = analysis_options.index(selected)
                selected_analysis = available_analyses[selected_index]

                # Show parameter configuration dialog if needed
                if selected_analysis.get("parameters"):
                    parameters = BridgeUIHelpers.show_parameter_dialog(
                        selected_analysis["parameters"]
                    )
                    selected_analysis["configured_parameters"] = parameters

                return selected_analysis

            return None

        except Exception as e:
            UI.TaskDialog.Show("Error", f"Failed to show analysis selection: {e}")
            return None

    @staticmethod
    def show_parameter_dialog(
        parameter_definitions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Show dialog for configuring analysis parameters.

        Args:
            parameter_definitions: List of parameter definitions

        Returns:
            Dictionary of configured parameters
        """
        if not PYREVIT_AVAILABLE:
            return BridgeUIHelpers._console_parameter_input(parameter_definitions)

        try:
            parameters = {}

            # For each parameter, show appropriate input dialog
            for param_def in parameter_definitions:
                param_name = param_def["name"]
                param_type = param_def.get("type", "string")
                param_description = param_def.get("description", "")
                default_value = param_def.get("default")
                required = param_def.get("required", False)

                # Show input dialog based on parameter type
                if param_type == "boolean":
                    result = forms.ask_for_one_item(
                        ["Yes", "No"],
                        default="Yes" if default_value else "No",
                        prompt=f"{param_description}\n\n{param_name}:",
                        title="Parameter Configuration",
                    )
                    parameters[param_name] = (
                        result == "Yes" if result else default_value
                    )

                elif param_type == "choice":
                    choices = param_def.get("choices", [])
                    result = forms.ask_for_one_item(
                        choices,
                        default=default_value,
                        prompt=f"{param_description}\n\n{param_name}:",
                        title="Parameter Configuration",
                    )
                    parameters[param_name] = result if result else default_value

                elif param_type == "number":
                    result = forms.ask_for_string(
                        prompt=f"{param_description}\n\n{param_name}:",
                        default=str(default_value) if default_value is not None else "",
                        title="Parameter Configuration",
                    )
                    try:
                        parameters[param_name] = (
                            float(result) if result else default_value
                        )
                    except ValueError:
                        parameters[param_name] = default_value

                else:  # string type
                    result = forms.ask_for_string(
                        prompt=f"{param_description}\n\n{param_name}:",
                        default=str(default_value) if default_value is not None else "",
                        title="Parameter Configuration",
                    )
                    parameters[param_name] = result if result else default_value

                # Check if required parameter was provided
                if required and (
                    parameters[param_name] is None or parameters[param_name] == ""
                ):
                    UI.TaskDialog.Show(
                        "Required Parameter",
                        f"Parameter '{param_name}' is required for this analysis.",
                    )
                    return {}  # Cancel if required parameter not provided

            return parameters

        except Exception as e:
            UI.TaskDialog.Show("Error", f"Failed to configure parameters: {e}")
            return {}

    @staticmethod
    def show_analysis_progress(
        analysis_type: str, element_count: int
    ) -> "ProgressDialog":
        """
        Show progress dialog for analysis execution.

        Args:
            analysis_type: Type of analysis being performed
            element_count: Number of elements being analyzed

        Returns:
            Progress dialog instance
        """
        if not PYREVIT_AVAILABLE:
            return BridgeUIHelpers._console_progress(analysis_type, element_count)

        try:
            # Create and show progress dialog
            progress_dialog = ProgressDialog(analysis_type, element_count)
            progress_dialog.show()
            return progress_dialog

        except Exception as e:
            print(f"Failed to show progress dialog: {e}")
            return None

    @staticmethod
    def show_analysis_results(results: dict[str, Any], analysis_type: str):
        """
        Show analysis results in a formatted dialog.

        Args:
            results: Analysis results dictionary
            analysis_type: Type of analysis performed
        """
        if not PYREVIT_AVAILABLE:
            BridgeUIHelpers._console_results_display(results, analysis_type)
            return

        try:
            # Format results for display
            formatted_results = BridgeUIHelpers._format_results_for_display(results)

            # Show results dialog
            result_dialog = ResultsDialog(analysis_type, formatted_results)
            result_dialog.show()

        except Exception as e:
            UI.TaskDialog.Show("Error", f"Failed to show results: {e}")

    @staticmethod
    def show_connection_status(status_info: dict[str, Any]):
        """
        Show RevitPy bridge connection status.

        Args:
            status_info: Connection status information
        """
        if not PYREVIT_AVAILABLE:
            print(f"Connection Status: {json.dumps(status_info, indent=2)}")
            return

        try:
            # Format status information
            status_text = []

            if status_info.get("success", False):
                status_text.append("✓ Connected to RevitPy Bridge")
                response_time = status_info.get("response_time_ms", 0)
                status_text.append(f"Response Time: {response_time:.1f} ms")

                if "connection_id" in status_info:
                    status_text.append(f"Connection ID: {status_info['connection_id']}")
            else:
                status_text.append("✗ Failed to connect to RevitPy Bridge")
                error = status_info.get("error", "Unknown error")
                status_text.append(f"Error: {error}")

            # Show status dialog
            UI.TaskDialog.Show("RevitPy Bridge Status", "\n".join(status_text))

        except Exception as e:
            UI.TaskDialog.Show("Error", f"Failed to show connection status: {e}")

    @staticmethod
    def show_element_summary(element_summary: dict[str, Any]):
        """
        Show selected element summary.

        Args:
            element_summary: Element summary information
        """
        if not PYREVIT_AVAILABLE:
            print(f"Element Summary: {json.dumps(element_summary, indent=2)}")
            return

        try:
            # Format summary
            summary_text = []
            summary_text.append(
                f"Total Elements: {element_summary.get('total_count', 0)}"
            )

            # Categories
            categories = element_summary.get("categories", {})
            if categories:
                summary_text.append("\nBy Category:")
                for category, count in categories.items():
                    summary_text.append(f"  • {category}: {count}")

            # Element types
            element_types = element_summary.get("element_types", {})
            if element_types:
                summary_text.append("\nBy Element Type:")
                for elem_type, count in element_types.items():
                    summary_text.append(f"  • {elem_type}: {count}")

            # Properties
            has_params = element_summary.get("has_parameters", 0)
            has_geom = element_summary.get("has_geometry", 0)
            total = element_summary.get("total_count", 0)

            if total > 0:
                summary_text.append("\nProperties:")
                summary_text.append(
                    f"  • Elements with parameters: {has_params} ({has_params/total*100:.1f}%)"
                )
                summary_text.append(
                    f"  • Elements with geometry: {has_geom} ({has_geom/total*100:.1f}%)"
                )

            # Show summary dialog
            UI.TaskDialog.Show("Element Selection Summary", "\n".join(summary_text))

        except Exception as e:
            UI.TaskDialog.Show("Error", f"Failed to show element summary: {e}")

    @staticmethod
    def confirm_analysis_execution(
        analysis_type: str,
        element_count: int,
        estimated_time: str,
        parameters: dict[str, Any],
    ) -> bool:
        """
        Show confirmation dialog before executing analysis.

        Args:
            analysis_type: Type of analysis
            element_count: Number of elements
            estimated_time: Estimated processing time
            parameters: Analysis parameters

        Returns:
            True if user confirms execution
        """
        if not PYREVIT_AVAILABLE:
            response = input(
                f"Execute {analysis_type} on {element_count} elements? (y/n): "
            )
            return response.lower().startswith("y")

        try:
            # Format confirmation message
            message_parts = []
            message_parts.append(f"Analysis Type: {analysis_type}")
            message_parts.append(f"Elements to analyze: {element_count}")
            message_parts.append(f"Estimated time: {estimated_time}")

            if parameters:
                message_parts.append("\nParameters:")
                for param_name, param_value in parameters.items():
                    message_parts.append(f"  • {param_name}: {param_value}")

            message_parts.append("\nDo you want to proceed with the analysis?")

            # Show confirmation dialog
            result = UI.TaskDialog.Show(
                "Confirm Analysis Execution",
                "\n".join(message_parts),
                UI.TaskDialogCommonButtons.Yes | UI.TaskDialogCommonButtons.No,
            )

            return result == UI.TaskDialogResult.Yes

        except Exception as e:
            UI.TaskDialog.Show("Error", f"Failed to show confirmation dialog: {e}")
            return False

    @staticmethod
    def _format_results_for_display(results: dict[str, Any]) -> str:
        """Format analysis results for display."""
        formatted = []

        # Add success/failure status
        if results.get("success", True):
            formatted.append("✓ Analysis completed successfully\n")
        else:
            formatted.append("✗ Analysis failed\n")
            error = results.get("error", "Unknown error")
            formatted.append(f"Error: {error}\n")
            return "\n".join(formatted)

        # Add execution metadata
        if "execution_time" in results:
            formatted.append(f"Execution time: {results['execution_time']:.2f} seconds")

        if "element_count" in results:
            formatted.append(f"Elements processed: {results['element_count']}")

        formatted.append("")  # Empty line

        # Add main results
        data = results.get("data", {})
        for key, value in data.items():
            if isinstance(value, (int, float)):
                if isinstance(value, float):
                    formatted.append(f"{key}: {value:.3f}")
                else:
                    formatted.append(f"{key}: {value}")
            elif isinstance(value, list) and len(value) < 10:
                formatted.append(f"{key}: {', '.join(map(str, value))}")
            elif isinstance(value, dict):
                formatted.append(f"{key}:")
                for subkey, subvalue in value.items():
                    formatted.append(f"  • {subkey}: {subvalue}")
            else:
                formatted.append(f"{key}: {str(value)[:100]}...")

        return "\n".join(formatted)

    @staticmethod
    def _console_analysis_selection(
        available_analyses: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Console fallback for analysis selection."""
        print("\nAvailable Analyses:")
        for i, analysis in enumerate(available_analyses):
            print(f"{i+1}. {analysis['name']} - {analysis.get('description', '')}")

        try:
            selection = int(input("\nSelect analysis (number): ")) - 1
            if 0 <= selection < len(available_analyses):
                return available_analyses[selection]
        except ValueError:
            pass

        return None

    @staticmethod
    def _console_parameter_input(
        parameter_definitions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Console fallback for parameter input."""
        parameters = {}

        for param_def in parameter_definitions:
            param_name = param_def["name"]
            param_description = param_def.get("description", "")
            default_value = param_def.get("default")

            prompt = f"{param_description}\n{param_name}"
            if default_value is not None:
                prompt += f" (default: {default_value})"
            prompt += ": "

            value = input(prompt).strip()
            if not value and default_value is not None:
                value = default_value

            parameters[param_name] = value

        return parameters

    @staticmethod
    def _console_progress(analysis_type: str, element_count: int):
        """Console fallback for progress display."""
        print(f"Executing {analysis_type} on {element_count} elements...")
        return None

    @staticmethod
    def _console_results_display(results: dict[str, Any], analysis_type: str):
        """Console fallback for results display."""
        print(f"\n{analysis_type} Results:")
        print("=" * 50)
        formatted = BridgeUIHelpers._format_results_for_display(results)
        print(formatted)


class ProgressDialog:
    """Progress dialog for long-running analysis operations."""

    def __init__(self, analysis_type: str, element_count: int):
        """Initialize progress dialog."""
        self.analysis_type = analysis_type
        self.element_count = element_count
        self.start_time = time.time()
        self.progress_value = 0
        self.status_message = "Initializing..."

    def show(self):
        """Show the progress dialog."""
        if not PYREVIT_AVAILABLE:
            print(f"Starting {self.analysis_type} analysis...")
            return

        # For now, just show a simple message
        # In a full implementation, this would show a proper progress dialog
        UI.TaskDialog.Show(
            "Analysis Progress",
            f"Executing {self.analysis_type} on {self.element_count} elements...\n"
            f"Please wait while RevitPy processes the data.",
        )

    def update_progress(self, progress: float, message: str = None):
        """Update progress value and message."""
        self.progress_value = progress
        if message:
            self.status_message = message

        if not PYREVIT_AVAILABLE:
            print(f"Progress: {progress:.1f}% - {self.status_message}")

    def close(self):
        """Close the progress dialog."""
        elapsed_time = time.time() - self.start_time
        if not PYREVIT_AVAILABLE:
            print(f"Analysis completed in {elapsed_time:.2f} seconds")


class ResultsDialog:
    """Dialog for displaying analysis results."""

    def __init__(self, analysis_type: str, formatted_results: str):
        """Initialize results dialog."""
        self.analysis_type = analysis_type
        self.formatted_results = formatted_results

    def show(self):
        """Show the results dialog."""
        if not PYREVIT_AVAILABLE:
            print(f"\n{self.analysis_type} Results:")
            print("=" * 50)
            print(self.formatted_results)
            return

        # Show results in a task dialog
        # For larger results, this could use a custom WPF window
        UI.TaskDialog.Show(f"{self.analysis_type} Results", self.formatted_results)
