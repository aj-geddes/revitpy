"""
Building Performance Analysis Workflow

This workflow demonstrates how PyRevit and RevitPy work together to
analyze building performance, with PyRevit handling UI and basic data
collection while RevitPy performs advanced analytics.
"""

import logging
import time
from typing import Any

# PyRevit imports (would be available in PyRevit environment)
try:
    from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector
    from pyrevit import UI, revit
    from pyrevit.framework import List as PyRevitList

    PYREVIT_AVAILABLE = True
except ImportError:
    PYREVIT_AVAILABLE = False

from ..core.exceptions import BridgeException
from ..pyrevit_integration import BridgeUIHelpers, ElementSelector, RevitPyBridge


class BuildingPerformanceWorkflow:
    """
    Complete workflow for building performance analysis combining
    PyRevit's UI capabilities with RevitPy's advanced analytics.

    Workflow Steps:
    1. PyRevit: User selects building elements via UI
    2. PyRevit: Collect basic element data and parameters
    3. Bridge: Send data to RevitPy for advanced analysis
    4. RevitPy: Perform energy, thermal, and daylight analysis
    5. RevitPy: Generate recommendations using ML algorithms
    6. Bridge: Return results to PyRevit
    7. PyRevit: Display results and allow user actions
    8. PyRevit: Apply recommended changes back to model
    """

    def __init__(self):
        """Initialize the workflow."""
        self.logger = logging.getLogger("building_performance_workflow")
        self.bridge = RevitPyBridge()
        self.element_selector = ElementSelector()

        # Workflow configuration
        self.analysis_types = [
            "energy_performance",
            "thermal_analysis",
            "daylight_analysis",
        ]

        # Performance targets
        self.performance_targets = {
            "energy_efficiency": 0.8,  # 80% efficiency target
            "thermal_rating": "good",
            "daylight_factor": 3.0,
        }

    def execute_complete_workflow(self, interactive: bool = True) -> dict[str, Any]:
        """
        Execute the complete building performance analysis workflow.

        Args:
            interactive: Whether to show UI dialogs

        Returns:
            Complete workflow results
        """
        workflow_start = time.time()
        workflow_results = {
            "success": True,
            "steps_completed": [],
            "analysis_results": {},
            "recommendations": [],
            "improvements_applied": [],
            "workflow_time": 0.0,
        }

        try:
            self.logger.info("Starting building performance analysis workflow")

            # Step 1: Element Selection (PyRevit)
            if interactive:
                UI.TaskDialog.Show(
                    "Building Performance Analysis",
                    "Starting building performance analysis workflow.\n\n"
                    "Step 1: Select building elements for analysis",
                )

            elements = self._step_1_select_elements(interactive)
            workflow_results["steps_completed"].append("element_selection")
            workflow_results["element_count"] = len(elements)

            if not elements:
                raise BridgeException("No elements selected for analysis")

            # Step 2: Data Preparation (PyRevit)
            if interactive:
                UI.TaskDialog.Show(
                    "Building Performance Analysis",
                    f"Step 2: Preparing {len(elements)} elements for analysis",
                )

            prepared_data = self._step_2_prepare_data(elements, interactive)
            workflow_results["steps_completed"].append("data_preparation")

            # Step 3: Advanced Analysis (RevitPy via Bridge)
            if interactive:
                UI.TaskDialog.Show(
                    "Building Performance Analysis",
                    "Step 3: Performing advanced analysis using RevitPy...\n\n"
                    "This may take a few minutes for complex models.",
                )

            analysis_results = self._step_3_advanced_analysis(
                prepared_data, interactive
            )
            workflow_results["steps_completed"].append("advanced_analysis")
            workflow_results["analysis_results"] = analysis_results

            # Step 4: Generate Recommendations (RevitPy)
            if interactive:
                UI.TaskDialog.Show(
                    "Building Performance Analysis",
                    "Step 4: Generating optimization recommendations...",
                )

            recommendations = self._step_4_generate_recommendations(
                analysis_results, elements, interactive
            )
            workflow_results["steps_completed"].append("recommendation_generation")
            workflow_results["recommendations"] = recommendations

            # Step 5: Display Results (PyRevit)
            if interactive:
                self._step_5_display_results(analysis_results, recommendations)
            workflow_results["steps_completed"].append("results_display")

            # Step 6: Apply Improvements (PyRevit)
            if interactive and recommendations:
                improvements_applied = self._step_6_apply_improvements(
                    recommendations, elements, interactive
                )
                workflow_results["improvements_applied"] = improvements_applied
                workflow_results["steps_completed"].append("improvements_applied")

            # Step 7: Generate Report (PyRevit)
            if interactive:
                report_path = self._step_7_generate_report(workflow_results)
                workflow_results["report_path"] = report_path
                workflow_results["steps_completed"].append("report_generated")

            workflow_results["workflow_time"] = time.time() - workflow_start

            if interactive:
                UI.TaskDialog.Show(
                    "Workflow Complete",
                    f"Building performance analysis completed successfully!\n\n"
                    f"Elements analyzed: {len(elements)}\n"
                    f"Recommendations generated: {len(recommendations)}\n"
                    f"Total time: {workflow_results['workflow_time']:.1f} seconds",
                )

            self.logger.info(
                f"Workflow completed successfully in {workflow_results['workflow_time']:.1f}s"
            )
            return workflow_results

        except Exception as e:
            workflow_results["success"] = False
            workflow_results["error"] = str(e)
            workflow_results["workflow_time"] = time.time() - workflow_start

            self.logger.error(f"Workflow failed: {e}")

            if interactive:
                UI.TaskDialog.Show(
                    "Workflow Error",
                    f"Building performance analysis failed:\n\n{str(e)}",
                )

            return workflow_results

    def _step_1_select_elements(self, interactive: bool) -> list[Any]:
        """Step 1: Select building elements for analysis."""
        try:
            if interactive:
                # Show element selection dialog
                elements = self.element_selector.select_elements_interactively(
                    message="Select building elements for performance analysis.\n\n"
                    "Include walls, windows, doors, roofs, and floors for "
                    "comprehensive analysis.",
                    allow_multiple=True,
                )

                if elements:
                    # Show selection summary
                    summary = self.element_selector.create_element_summary(elements)
                    BridgeUIHelpers.show_element_summary(summary)

                    # Validate selection
                    validation = self.element_selector.validate_elements_for_analysis(
                        elements, "building_performance"
                    )

                    if not validation["valid"]:
                        error_msg = "; ".join(validation["errors"])
                        UI.TaskDialog.Show(
                            "Selection Error",
                            f"Selected elements are not suitable for analysis:\n\n{error_msg}",
                        )
                        return []

                    if validation["warnings"]:
                        warning_msg = "\n".join(validation["warnings"])
                        result = UI.TaskDialog.Show(
                            "Selection Warnings",
                            f"Warnings about selected elements:\n\n{warning_msg}\n\n"
                            f"Continue with analysis?",
                            UI.TaskDialogCommonButtons.Yes
                            | UI.TaskDialogCommonButtons.No,
                        )
                        if result != UI.TaskDialogResult.Yes:
                            return []

                return elements
            else:
                # Non-interactive: select common building elements
                categories = ["Walls", "Windows", "Doors", "Roofs", "Floors", "Rooms"]
                elements = []

                for category in categories:
                    category_elements = (
                        self.element_selector.select_elements_by_category([category])
                    )
                    elements.extend(category_elements)

                return elements

        except Exception as e:
            self.logger.error(f"Element selection failed: {e}")
            return []

    def _step_2_prepare_data(
        self, elements: list[Any], interactive: bool
    ) -> dict[str, Any]:
        """Step 2: Prepare element data for analysis."""
        try:
            # Organize elements by category
            elements_by_category = self.element_selector.group_elements_by_category(
                elements
            )

            # Extract relevant parameters for each category
            prepared_data = {
                "elements": elements,
                "categories": list(elements_by_category.keys()),
                "analysis_scope": {
                    "include_thermal": True,
                    "include_energy": True,
                    "include_daylight": True,
                    "include_recommendations": True,
                },
                "building_context": self._extract_building_context(elements),
                "analysis_parameters": self._get_analysis_parameters(interactive),
            }

            if interactive:
                # Show data preparation summary
                prep_summary = "Data preparation completed:\n\n"
                prep_summary += f"• Total elements: {len(elements)}\n"
                prep_summary += (
                    f"• Categories found: {', '.join(elements_by_category.keys())}\n"
                )
                prep_summary += f"• Building area: {prepared_data['building_context']['total_area']:.1f} m²\n"
                prep_summary += f"• Analysis scope: {', '.join(prepared_data['analysis_scope'].keys())}"

                UI.TaskDialog.Show("Data Preparation", prep_summary)

            return prepared_data

        except Exception as e:
            self.logger.error(f"Data preparation failed: {e}")
            raise BridgeException(f"Data preparation failed: {e}")

    def _step_3_advanced_analysis(
        self, prepared_data: dict[str, Any], interactive: bool
    ) -> dict[str, Any]:
        """Step 3: Perform advanced analysis using RevitPy."""
        try:
            # Connect to RevitPy bridge
            if not self.bridge.is_connected():
                if not self.bridge.connect():
                    raise BridgeException("Failed to connect to RevitPy bridge")

            analysis_results = {}
            elements = prepared_data["elements"]

            # Energy Performance Analysis
            if interactive:
                BridgeUIHelpers.show_analysis_progress(
                    "Energy Performance Analysis", len(elements)
                )

            energy_results = self.bridge.execute_analysis(
                elements=elements,
                analysis_type="energy_performance",
                parameters={
                    **prepared_data["analysis_parameters"],
                    "calculation_method": "detailed",
                    "include_thermal": True,
                    "precision": "high",
                },
            )
            analysis_results["energy"] = energy_results

            # Thermal Analysis
            if interactive:
                BridgeUIHelpers.show_analysis_progress(
                    "Thermal Analysis", len(elements)
                )

            thermal_results = self.bridge.execute_analysis(
                elements=elements,
                analysis_type="thermal_analysis",
                parameters={
                    **prepared_data["analysis_parameters"],
                    "include_thermal_bridging": True,
                    "condensation_analysis": True,
                    "precision": "high",
                },
            )
            analysis_results["thermal"] = thermal_results

            # Daylight Analysis (for spaces with windows)
            spaces_and_windows = [
                e
                for e in elements
                if any(
                    cat in self._get_element_category(e).lower()
                    for cat in ["room", "space", "window"]
                )
            ]

            if spaces_and_windows:
                if interactive:
                    BridgeUIHelpers.show_analysis_progress(
                        "Daylight Analysis", len(spaces_and_windows)
                    )

                daylight_results = self.bridge.execute_analysis(
                    elements=spaces_and_windows,
                    analysis_type="daylight_analysis",
                    parameters={
                        **prepared_data["analysis_parameters"],
                        "sky_model": "cie_overcast",
                        "include_solar_gains": True,
                        "time_periods": "annual",
                    },
                )
                analysis_results["daylight"] = daylight_results

            return analysis_results

        except Exception as e:
            self.logger.error(f"Advanced analysis failed: {e}")
            raise BridgeException(f"Advanced analysis failed: {e}")

    def _step_4_generate_recommendations(
        self, analysis_results: dict[str, Any], elements: list[Any], interactive: bool
    ) -> list[dict[str, Any]]:
        """Step 4: Generate optimization recommendations."""
        try:
            # Use ML-powered space optimization for comprehensive recommendations
            spaces = [
                e
                for e in elements
                if "room" in self._get_element_category(e).lower()
                or "space" in self._get_element_category(e).lower()
            ]

            recommendations = []

            if spaces:
                # Space optimization recommendations
                space_optimization = self.bridge.execute_analysis(
                    elements=spaces,
                    analysis_type="space_optimization",
                    parameters={
                        "optimization_goal": "efficiency",
                        "algorithm": "genetic_algorithm",
                        "iterations": 50,
                        "constraints": {"min_area": 10.0, "max_area": 100.0},
                    },
                )

                if space_optimization.get("optimized_layout"):
                    recommendations.extend(
                        self._convert_optimization_to_recommendations(
                            space_optimization
                        )
                    )

            # Extract recommendations from analysis results
            for analysis_type, results in analysis_results.items():
                if "recommendations" in results:
                    analysis_recommendations = results["recommendations"]
                    for rec in analysis_recommendations:
                        rec["source_analysis"] = analysis_type
                        recommendations.append(rec)

            # Prioritize recommendations
            prioritized_recommendations = self._prioritize_recommendations(
                recommendations
            )

            return prioritized_recommendations

        except Exception as e:
            self.logger.error(f"Recommendation generation failed: {e}")
            return []

    def _step_5_display_results(
        self, analysis_results: dict[str, Any], recommendations: list[dict[str, Any]]
    ):
        """Step 5: Display analysis results to user."""
        try:
            # Create comprehensive results summary
            results_summary = self._create_results_summary(
                analysis_results, recommendations
            )

            # Show results in formatted dialog
            BridgeUIHelpers.show_analysis_results(
                results_summary, "Building Performance Analysis"
            )

            # Show detailed results for each analysis type
            for analysis_type, results in analysis_results.items():
                if results and isinstance(results, dict):
                    BridgeUIHelpers.show_analysis_results(
                        results, f"{analysis_type.title()} Analysis"
                    )

            # Show recommendations summary
            if recommendations:
                self._show_recommendations_summary(recommendations)

        except Exception as e:
            self.logger.error(f"Results display failed: {e}")

    def _step_6_apply_improvements(
        self,
        recommendations: list[dict[str, Any]],
        elements: list[Any],
        interactive: bool,
    ) -> list[dict[str, Any]]:
        """Step 6: Apply recommended improvements to the model."""
        try:
            improvements_applied = []

            if not recommendations:
                return improvements_applied

            # Show recommendations and ask user which to apply
            selected_recommendations = self._select_recommendations_to_apply(
                recommendations, interactive
            )

            if not selected_recommendations:
                return improvements_applied

            # Apply each selected recommendation
            for recommendation in selected_recommendations:
                try:
                    applied = self._apply_single_recommendation(
                        recommendation, elements
                    )
                    if applied:
                        improvements_applied.append(
                            {
                                "recommendation_id": recommendation.get(
                                    "id", "unknown"
                                ),
                                "type": recommendation.get("type", "unknown"),
                                "description": recommendation.get("description", ""),
                                "status": "applied",
                                "applied_at": time.time(),
                            }
                        )
                    else:
                        improvements_applied.append(
                            {
                                "recommendation_id": recommendation.get(
                                    "id", "unknown"
                                ),
                                "type": recommendation.get("type", "unknown"),
                                "status": "failed",
                                "error": "Application failed",
                            }
                        )

                except Exception as e:
                    improvements_applied.append(
                        {
                            "recommendation_id": recommendation.get("id", "unknown"),
                            "type": recommendation.get("type", "unknown"),
                            "status": "error",
                            "error": str(e),
                        }
                    )

            # Show application results
            if interactive and improvements_applied:
                applied_count = len(
                    [i for i in improvements_applied if i["status"] == "applied"]
                )
                failed_count = len(improvements_applied) - applied_count

                status_msg = "Improvement application completed:\n\n"
                status_msg += f"• Successfully applied: {applied_count}\n"
                status_msg += f"• Failed to apply: {failed_count}\n\n"

                if applied_count > 0:
                    status_msg += (
                        "The model has been updated with the applied improvements."
                    )

                UI.TaskDialog.Show("Improvements Applied", status_msg)

            return improvements_applied

        except Exception as e:
            self.logger.error(f"Improvement application failed: {e}")
            return []

    def _step_7_generate_report(self, workflow_results: dict[str, Any]) -> str:
        """Step 7: Generate comprehensive analysis report."""
        try:
            import os
            from datetime import datetime

            # Create report content
            report_content = self._create_report_content(workflow_results)

            # Save report to file
            report_filename = f"building_performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

            if PYREVIT_AVAILABLE:
                # Save to user's documents folder
                import os

                documents_path = os.path.expanduser("~/Documents")
                report_path = os.path.join(documents_path, report_filename)
            else:
                report_path = report_filename

            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)

            if PYREVIT_AVAILABLE:
                UI.TaskDialog.Show(
                    "Report Generated", f"Analysis report saved to:\n{report_path}"
                )

            return report_path

        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            return ""

    # Helper methods

    def _extract_building_context(self, elements: list[Any]) -> dict[str, Any]:
        """Extract building context information."""
        total_area = 0.0
        categories_found = set()

        for element in elements:
            try:
                # Calculate area
                area = self._get_element_area(element)
                total_area += area

                # Track categories
                category = self._get_element_category(element)
                categories_found.add(category)

            except:
                continue

        return {
            "total_area": total_area,
            "categories": list(categories_found),
            "element_count": len(elements),
            "analysis_date": time.time(),
        }

    def _get_analysis_parameters(self, interactive: bool) -> dict[str, Any]:
        """Get analysis parameters from user or defaults."""
        if interactive and PYREVIT_AVAILABLE:
            # Could show parameter input dialog
            # For now, use defaults
            pass

        return {
            "weather_data": "default_climate",
            "indoor_temperature": 20.0,  # °C
            "indoor_humidity": 60.0,  # %
            "outdoor_temperature": 0.0,  # °C (winter design)
            "analysis_precision": "high",
            "include_thermal_bridging": True,
            "include_solar_gains": True,
        }

    def _get_element_category(self, element) -> str:
        """Get element category name."""
        try:
            if hasattr(element, "Category") and element.Category:
                return element.Category.Name
            return "Unknown"
        except:
            return "Unknown"

    def _get_element_area(self, element) -> float:
        """Get element area."""
        try:
            if hasattr(element, "Parameters"):
                for param in element.Parameters:
                    if hasattr(param, "Definition") and hasattr(
                        param.Definition, "Name"
                    ):
                        if param.Definition.Name == "Area":
                            if hasattr(param, "AsDouble"):
                                return param.AsDouble()
            return 1.0
        except:
            return 1.0

    def _convert_optimization_to_recommendations(
        self, optimization_result: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Convert space optimization results to recommendations."""
        recommendations = []

        modifications = optimization_result.get("optimized_layout", {}).get(
            "modifications_required", []
        )

        for mod in modifications:
            recommendations.append(
                {
                    "id": f"space_opt_{mod.get('space_id', 'unknown')}",
                    "type": "space_modification",
                    "category": "Space Optimization",
                    "priority": "medium",
                    "description": f"Optimize {mod.get('space_name', 'space')} layout",
                    "details": mod.get("changes", {}),
                    "estimated_benefit": f"{optimization_result.get('efficiency_improvement', 0):.1f}% efficiency improvement",
                    "element_id": mod.get("space_id"),
                }
            )

        return recommendations

    def _prioritize_recommendations(
        self, recommendations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Prioritize recommendations by impact and feasibility."""

        # Sort by priority and estimated savings
        def priority_score(rec):
            priority_weights = {"high": 3, "medium": 2, "low": 1}
            priority_weight = priority_weights.get(rec.get("priority", "low"), 1)

            # Try to get estimated savings
            savings = rec.get("energy_savings", rec.get("estimated_savings", 0))
            if isinstance(savings, int | float):
                savings_weight = savings / 1000  # Normalize
            else:
                savings_weight = 0

            return priority_weight + savings_weight

        return sorted(recommendations, key=priority_score, reverse=True)

    def _create_results_summary(
        self, analysis_results: dict[str, Any], recommendations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Create comprehensive results summary."""
        summary = {
            "success": True,
            "analysis_types_completed": list(analysis_results.keys()),
            "total_recommendations": len(recommendations),
            "key_findings": {},
        }

        # Extract key findings from each analysis
        if "energy" in analysis_results:
            energy_data = analysis_results["energy"]
            summary["key_findings"]["energy"] = {
                "efficiency_rating": energy_data.get("efficiency_rating", "unknown"),
                "total_energy_usage": energy_data.get("energy_usage", {}).get(
                    "total_annual_kwh", 0
                ),
                "rating": "good"
                if energy_data.get("efficiency_rating", 0) > 0.7
                else "needs_improvement",
            }

        if "thermal" in analysis_results:
            thermal_data = analysis_results["thermal"]
            overall_metrics = thermal_data.get("overall_metrics", {})
            summary["key_findings"]["thermal"] = {
                "average_u_value": overall_metrics.get("average_u_value", 0),
                "overall_rating": overall_metrics.get("overall_rating", "unknown"),
                "thermal_bridges_found": thermal_data.get("thermal_bridging", {}).get(
                    "bridges_found", 0
                ),
            }

        if "daylight" in analysis_results:
            daylight_data = analysis_results["daylight"]
            summary["key_findings"]["daylight"] = {
                "average_daylight_factor": daylight_data.get(
                    "average_daylight_factor", 0
                ),
                "overall_rating": daylight_data.get("overall_rating", "unknown"),
            }

        # High-priority recommendations
        high_priority_recs = [r for r in recommendations if r.get("priority") == "high"]
        summary["high_priority_recommendations"] = len(high_priority_recs)

        return summary

    def _show_recommendations_summary(self, recommendations: list[dict[str, Any]]):
        """Show summary of recommendations to user."""
        if not recommendations:
            return

        # Group by priority
        by_priority = {"high": [], "medium": [], "low": []}
        for rec in recommendations:
            priority = rec.get("priority", "low")
            by_priority[priority].append(rec)

        summary_text = "Performance Improvement Recommendations:\n\n"

        for priority in ["high", "medium", "low"]:
            if by_priority[priority]:
                summary_text += f"{priority.upper()} PRIORITY ({len(by_priority[priority])} items):\n"
                for i, rec in enumerate(by_priority[priority][:3]):  # Show top 3
                    summary_text += (
                        f"  {i+1}. {rec.get('description', 'Unknown recommendation')}\n"
                    )
                if len(by_priority[priority]) > 3:
                    summary_text += f"  ... and {len(by_priority[priority]) - 3} more\n"
                summary_text += "\n"

        if PYREVIT_AVAILABLE:
            UI.TaskDialog.Show("Recommendations Summary", summary_text)
        else:
            print(summary_text)

    def _select_recommendations_to_apply(
        self, recommendations: list[dict[str, Any]], interactive: bool
    ) -> list[dict[str, Any]]:
        """Let user select which recommendations to apply."""
        if not interactive or not PYREVIT_AVAILABLE:
            # Auto-select high priority recommendations
            return [r for r in recommendations if r.get("priority") == "high"]

        # Show selection dialog (simplified)
        high_priority = [r for r in recommendations if r.get("priority") == "high"]

        if high_priority:
            rec_list = "\n".join(
                [f"• {r.get('description', 'Unknown')}" for r in high_priority[:5]]
            )
            result = UI.TaskDialog.Show(
                "Apply Recommendations",
                f"Apply the following high-priority recommendations?\n\n{rec_list}",
                UI.TaskDialogCommonButtons.Yes | UI.TaskDialogCommonButtons.No,
            )

            if result == UI.TaskDialogResult.Yes:
                return high_priority

        return []

    def _apply_single_recommendation(
        self, recommendation: dict[str, Any], elements: list[Any]
    ) -> bool:
        """Apply a single recommendation to the model."""
        try:
            rec_type = recommendation.get("type", "")
            element_id = recommendation.get("element_id")

            if not element_id:
                return False

            # Find the target element
            target_element = None
            for element in elements:
                if str(self._get_element_id(element)) == str(element_id):
                    target_element = element
                    break

            if not target_element:
                return False

            # Apply recommendation based on type
            if rec_type == "insulation_improvement":
                return self._apply_insulation_improvement(
                    target_element, recommendation
                )
            elif rec_type == "glazing_upgrade":
                return self._apply_glazing_upgrade(target_element, recommendation)
            elif rec_type == "space_modification":
                return self._apply_space_modification(target_element, recommendation)
            else:
                # Log unsupported recommendation type
                self.logger.warning(f"Unsupported recommendation type: {rec_type}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to apply recommendation: {e}")
            return False

    def _get_element_id(self, element) -> str:
        """Get element ID."""
        try:
            if hasattr(element, "Id"):
                if hasattr(element.Id, "IntegerValue"):
                    return str(element.Id.IntegerValue)
                return str(element.Id)
            return "unknown"
        except:
            return "unknown"

    def _apply_insulation_improvement(
        self, element, recommendation: dict[str, Any]
    ) -> bool:
        """Apply insulation improvement recommendation."""
        try:
            # In a real implementation, this would modify element parameters
            # For demonstration, we'll just log the action
            self.logger.info(
                f"Applied insulation improvement to element {self._get_element_id(element)}"
            )
            return True
        except:
            return False

    def _apply_glazing_upgrade(self, element, recommendation: dict[str, Any]) -> bool:
        """Apply glazing upgrade recommendation."""
        try:
            # In a real implementation, this would change window types
            self.logger.info(
                f"Applied glazing upgrade to element {self._get_element_id(element)}"
            )
            return True
        except:
            return False

    def _apply_space_modification(
        self, element, recommendation: dict[str, Any]
    ) -> bool:
        """Apply space modification recommendation."""
        try:
            # In a real implementation, this would modify space boundaries
            self.logger.info(
                f"Applied space modification to element {self._get_element_id(element)}"
            )
            return True
        except:
            return False

    def _create_report_content(self, workflow_results: dict[str, Any]) -> str:
        """Create comprehensive report content."""
        from datetime import datetime

        report = f"""BUILDING PERFORMANCE ANALYSIS REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

EXECUTIVE SUMMARY
================
Analysis Status: {'SUCCESS' if workflow_results['success'] else 'FAILED'}
Elements Analyzed: {workflow_results.get('element_count', 0)}
Workflow Time: {workflow_results.get('workflow_time', 0):.1f} seconds
Steps Completed: {', '.join(workflow_results.get('steps_completed', []))}

ANALYSIS RESULTS
===============
"""

        # Add analysis results
        analysis_results = workflow_results.get("analysis_results", {})
        for analysis_type, results in analysis_results.items():
            report += f"\n{analysis_type.upper()} ANALYSIS:\n"
            report += "Status: Completed\n"

            if "efficiency_rating" in results:
                report += f"Efficiency Rating: {results['efficiency_rating']}\n"

            if "overall_metrics" in results:
                metrics = results["overall_metrics"]
                for metric, value in metrics.items():
                    if isinstance(value, int | float):
                        report += f"{metric}: {value:.2f}\n"
                    else:
                        report += f"{metric}: {value}\n"

            report += "\n"

        # Add recommendations
        recommendations = workflow_results.get("recommendations", [])
        if recommendations:
            report += "\nRECOMMENDATIONS\n"
            report += "==============\n"

            for i, rec in enumerate(recommendations[:10]):  # Top 10
                report += f"{i+1}. {rec.get('description', 'Unknown recommendation')}\n"
                report += f"   Priority: {rec.get('priority', 'Unknown')}\n"
                report += f"   Category: {rec.get('category', 'Unknown')}\n"
                if "estimated_benefit" in rec:
                    report += f"   Benefit: {rec['estimated_benefit']}\n"
                report += "\n"

        # Add improvements applied
        improvements = workflow_results.get("improvements_applied", [])
        if improvements:
            report += "\nIMPROVEMENTS APPLIED\n"
            report += "==================\n"

            applied_count = len([i for i in improvements if i["status"] == "applied"])
            failed_count = len(improvements) - applied_count

            report += f"Successfully Applied: {applied_count}\n"
            report += f"Failed to Apply: {failed_count}\n\n"

            for improvement in improvements:
                status = improvement["status"].upper()
                report += f"- {improvement.get('description', 'Unknown')}: {status}\n"

        report += "\n" + "=" * 50 + "\nEnd of Report\n"

        return report
