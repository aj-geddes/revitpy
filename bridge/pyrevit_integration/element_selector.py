"""
Element selection utilities for PyRevit integration.
"""

from collections.abc import Callable
from enum import Enum
from typing import Any

# PyRevit imports (these would be available in PyRevit environment)
try:
    from Autodesk.Revit.DB import (
        BuiltInCategory,
        BuiltInParameter,
        Element,
        ElementFilter,
        FilteredElementCollector,
        Transaction,
    )
    from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
    from pyrevit import UI, revit
    from pyrevit.framework import List as PyRevitList

    PYREVIT_AVAILABLE = True
except ImportError:
    # For development/testing outside PyRevit
    PYREVIT_AVAILABLE = False


class SelectionMode(Enum):
    """Element selection modes."""

    INTERACTIVE = "interactive"
    FILTERED = "filtered"
    PREDEFINED = "predefined"
    ALL_OF_CATEGORY = "all_of_category"


class ElementSelector:
    """
    Utility class for selecting Revit elements in PyRevit scripts.

    This class provides various methods to select elements that will be
    sent to RevitPy for analysis.
    """

    def __init__(self, doc=None):
        """Initialize element selector."""
        self.doc = doc or (revit.doc if PYREVIT_AVAILABLE else None)
        self.selected_elements: list[Any] = []
        self.selection_filters: dict[str, Callable] = {}

        # Statistics
        self.selection_stats = {
            "total_selections": 0,
            "elements_by_category": {},
            "last_selection_count": 0,
        }

    def select_elements_interactively(
        self,
        message: str = "Select elements for RevitPy analysis",
        allow_multiple: bool = True,
        element_filter: Callable | None = None,
    ) -> list[Any]:
        """
        Allow user to interactively select elements.

        Args:
            message: Message to display during selection
            allow_multiple: Whether to allow multiple element selection
            element_filter: Optional filter function for valid elements

        Returns:
            List of selected elements
        """
        if not PYREVIT_AVAILABLE:
            raise RuntimeError("Interactive selection requires PyRevit environment")

        try:
            # Create selection filter if provided
            selection_filter = None
            if element_filter:
                selection_filter = self._create_selection_filter(element_filter)

            # Perform selection
            if allow_multiple:
                # Multiple element selection
                selection = revit.uidoc.Selection.PickObjects(
                    ObjectType.Element, selection_filter, message
                )
                elements = [self.doc.GetElement(ref.ElementId) for ref in selection]
            else:
                # Single element selection
                selection = revit.uidoc.Selection.PickObject(
                    ObjectType.Element, selection_filter, message
                )
                elements = [self.doc.GetElement(selection.ElementId)]

            # Update selection
            self.selected_elements = elements
            self._update_selection_stats(elements)

            return elements

        except Exception as e:
            UI.TaskDialog.Show("Selection Error", f"Failed to select elements: {e}")
            return []

    def select_elements_by_category(
        self,
        categories: str | list[str],
        additional_filters: list[Callable] | None = None,
    ) -> list[Any]:
        """
        Select all elements of specified categories.

        Args:
            categories: Category name(s) to select
            additional_filters: Additional filter functions

        Returns:
            List of selected elements
        """
        if not PYREVIT_AVAILABLE:
            raise RuntimeError("Category selection requires PyRevit environment")

        try:
            # Ensure categories is a list
            if isinstance(categories, str):
                categories = [categories]

            elements = []

            for category_name in categories:
                # Get built-in category
                builtin_category = self._get_builtin_category(category_name)
                if builtin_category is None:
                    continue

                # Collect elements
                collector = FilteredElementCollector(self.doc).OfCategory(
                    builtin_category
                )

                # Apply additional filters
                if additional_filters:
                    for filter_func in additional_filters:
                        collector = collector.Where(lambda e: filter_func(e))

                # Add to elements list
                category_elements = list(collector.ToElements())
                elements.extend(category_elements)

            # Update selection
            self.selected_elements = elements
            self._update_selection_stats(elements)

            return elements

        except Exception as e:
            print(f"Failed to select elements by category: {e}")
            return []

    def select_elements_by_parameters(
        self, parameter_filters: dict[str, Any], categories: list[str] | None = None
    ) -> list[Any]:
        """
        Select elements based on parameter values.

        Args:
            parameter_filters: Dictionary of parameter name -> value filters
            categories: Optional list of categories to limit search

        Returns:
            List of selected elements
        """
        if not PYREVIT_AVAILABLE:
            raise RuntimeError("Parameter selection requires PyRevit environment")

        try:
            # Start with all elements or specific categories
            if categories:
                elements = self.select_elements_by_category(categories)
            else:
                collector = FilteredElementCollector(
                    self.doc
                ).WhereElementIsNotElementType()
                elements = list(collector.ToElements())

            # Apply parameter filters
            filtered_elements = []

            for element in elements:
                matches_all_filters = True

                for param_name, expected_value in parameter_filters.items():
                    param_value = self._get_parameter_value(element, param_name)

                    if not self._matches_parameter_filter(param_value, expected_value):
                        matches_all_filters = False
                        break

                if matches_all_filters:
                    filtered_elements.append(element)

            # Update selection
            self.selected_elements = filtered_elements
            self._update_selection_stats(filtered_elements)

            return filtered_elements

        except Exception as e:
            print(f"Failed to select elements by parameters: {e}")
            return []

    def select_elements_by_ids(self, element_ids: list[int | str]) -> list[Any]:
        """
        Select elements by their IDs.

        Args:
            element_ids: List of element IDs

        Returns:
            List of selected elements
        """
        if not PYREVIT_AVAILABLE:
            raise RuntimeError("ID selection requires PyRevit environment")

        try:
            elements = []

            for element_id in element_ids:
                if isinstance(element_id, str):
                    element_id = int(element_id)

                element = self.doc.GetElement(element_id)
                if element is not None:
                    elements.append(element)

            # Update selection
            self.selected_elements = elements
            self._update_selection_stats(elements)

            return elements

        except Exception as e:
            print(f"Failed to select elements by IDs: {e}")
            return []

    def get_selected_elements(self) -> list[Any]:
        """Get currently selected elements."""
        return self.selected_elements.copy()

    def get_current_selection(self) -> list[Any]:
        """Get elements currently selected in Revit UI."""
        if not PYREVIT_AVAILABLE:
            return []

        try:
            selection = revit.uidoc.Selection.GetElementIds()
            elements = [self.doc.GetElement(element_id) for element_id in selection]
            return [e for e in elements if e is not None]
        except:
            return []

    def filter_elements_by_type(
        self, elements: list[Any], element_types: list[str]
    ) -> list[Any]:
        """Filter elements by their type names."""
        filtered = []

        for element in elements:
            element_type = type(element).__name__
            if element_type in element_types:
                filtered.append(element)

        return filtered

    def group_elements_by_category(
        self, elements: list[Any] | None = None
    ) -> dict[str, list[Any]]:
        """Group elements by their categories."""
        if elements is None:
            elements = self.selected_elements

        grouped = {}

        for element in elements:
            try:
                category_name = element.Category.Name if element.Category else "Unknown"
                if category_name not in grouped:
                    grouped[category_name] = []
                grouped[category_name].append(element)
            except:
                if "Unknown" not in grouped:
                    grouped["Unknown"] = []
                grouped["Unknown"].append(element)

        return grouped

    def create_element_summary(
        self, elements: list[Any] | None = None
    ) -> dict[str, Any]:
        """Create a summary of selected elements."""
        if elements is None:
            elements = self.selected_elements

        # Group by category
        by_category = self.group_elements_by_category(elements)

        # Create summary
        summary = {
            "total_count": len(elements),
            "categories": {
                category: len(element_list)
                for category, element_list in by_category.items()
            },
            "element_types": {},
            "has_parameters": 0,
            "has_geometry": 0,
        }

        # Analyze element types and properties
        for element in elements:
            element_type = type(element).__name__
            summary["element_types"][element_type] = (
                summary["element_types"].get(element_type, 0) + 1
            )

            # Check for parameters
            try:
                if hasattr(element, "Parameters") and len(list(element.Parameters)) > 0:
                    summary["has_parameters"] += 1
            except:
                pass

            # Check for geometry
            try:
                if hasattr(element, "Geometry") and element.Geometry is not None:
                    summary["has_geometry"] += 1
            except:
                pass

        return summary

    def validate_elements_for_analysis(
        self, elements: list[Any] | None = None, analysis_type: str | None = None
    ) -> dict[str, Any]:
        """
        Validate elements for RevitPy analysis.

        Args:
            elements: Elements to validate (uses selected if None)
            analysis_type: Type of analysis to validate for

        Returns:
            Validation results
        """
        if elements is None:
            elements = self.selected_elements

        validation = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "element_count": len(elements),
            "estimated_processing_time": self._estimate_processing_time(
                elements, analysis_type
            ),
        }

        # Basic validation
        if not elements:
            validation["valid"] = False
            validation["errors"].append("No elements selected for analysis")
            return validation

        # Check element types
        unsupported_types = []
        elements_with_geometry = 0
        elements_with_parameters = 0

        for element in elements:
            try:
                # Check if element has required properties
                if hasattr(element, "Geometry"):
                    elements_with_geometry += 1

                if hasattr(element, "Parameters"):
                    elements_with_parameters += 1

                # Check for potentially problematic element types
                element_type = type(element).__name__
                if element_type in ["Group", "AssemblyInstance"]:
                    validation["warnings"].append(
                        f"Element type {element_type} may need special handling"
                    )

            except Exception:
                unsupported_types.append(type(element).__name__)

        # Analysis-specific validation
        if analysis_type:
            analysis_validation = self._validate_for_analysis_type(
                elements, analysis_type
            )
            validation["warnings"].extend(analysis_validation.get("warnings", []))
            validation["errors"].extend(analysis_validation.get("errors", []))
            if analysis_validation.get("valid") is False:
                validation["valid"] = False

        # Add summary information
        validation["summary"] = {
            "elements_with_geometry": elements_with_geometry,
            "elements_with_parameters": elements_with_parameters,
            "geometry_percentage": round(
                elements_with_geometry / len(elements) * 100, 1
            ),
            "parameters_percentage": round(
                elements_with_parameters / len(elements) * 100, 1
            ),
        }

        if unsupported_types:
            validation["warnings"].append(
                f"Unsupported element types found: {unsupported_types}"
            )

        return validation

    def _create_selection_filter(self, filter_func: Callable) -> "ISelectionFilter":
        """Create a Revit selection filter from a function."""
        if not PYREVIT_AVAILABLE:
            return None

        class CustomSelectionFilter(ISelectionFilter):
            def __init__(self, filter_function):
                self.filter_function = filter_function

            def AllowElement(self, element):
                try:
                    return self.filter_function(element)
                except:
                    return False

            def AllowReference(self, reference, position):
                return True

        return CustomSelectionFilter(filter_func)

    def _get_builtin_category(self, category_name: str):
        """Get BuiltInCategory from category name."""
        if not PYREVIT_AVAILABLE:
            return None

        # Map common category names to BuiltInCategory values
        category_map = {
            "Walls": BuiltInCategory.OST_Walls,
            "Doors": BuiltInCategory.OST_Doors,
            "Windows": BuiltInCategory.OST_Windows,
            "Floors": BuiltInCategory.OST_Floors,
            "Roofs": BuiltInCategory.OST_Roofs,
            "Columns": BuiltInCategory.OST_Columns,
            "Beams": BuiltInCategory.OST_StructuralFraming,
            "Rooms": BuiltInCategory.OST_Rooms,
            "Spaces": BuiltInCategory.OST_MEPSpaces,
            "Furniture": BuiltInCategory.OST_Furniture,
            "Generic Models": BuiltInCategory.OST_GenericModel,
            "Lighting Fixtures": BuiltInCategory.OST_LightingFixtures,
            "Plumbing Fixtures": BuiltInCategory.OST_PlumbingFixtures,
            "Mechanical Equipment": BuiltInCategory.OST_MechanicalEquipment,
            "Electrical Equipment": BuiltInCategory.OST_ElectricalEquipment,
        }

        return category_map.get(category_name)

    def _get_parameter_value(self, element: Any, parameter_name: str):
        """Get parameter value from element."""
        try:
            # Try by parameter name
            param = element.LookupParameter(parameter_name)
            if param is not None:
                if param.StorageType.ToString() == "String":
                    return param.AsString()
                elif param.StorageType.ToString() == "Integer":
                    return param.AsInteger()
                elif param.StorageType.ToString() == "Double":
                    return param.AsDouble()
                elif param.StorageType.ToString() == "ElementId":
                    return param.AsElementId()

            # Try built-in parameters
            try:
                builtin_param = getattr(BuiltInParameter, parameter_name, None)
                if builtin_param is not None:
                    param = element.get_Parameter(builtin_param)
                    if param is not None:
                        return param.AsValueString()
            except:
                pass

            return None

        except Exception:
            return None

    def _matches_parameter_filter(self, param_value: Any, expected_value: Any) -> bool:
        """Check if parameter value matches filter criteria."""
        if param_value is None:
            return expected_value is None

        # Handle different comparison types
        if isinstance(expected_value, dict):
            # Advanced filter with operators
            operator = expected_value.get("operator", "equals")
            value = expected_value.get("value")

            if operator == "equals":
                return param_value == value
            elif operator == "not_equals":
                return param_value != value
            elif operator == "greater_than":
                return param_value > value
            elif operator == "less_than":
                return param_value < value
            elif operator == "contains":
                return str(value).lower() in str(param_value).lower()
            elif operator == "starts_with":
                return str(param_value).lower().startswith(str(value).lower())

        else:
            # Simple equality check
            return param_value == expected_value

    def _validate_for_analysis_type(
        self, elements: list[Any], analysis_type: str
    ) -> dict[str, Any]:
        """Validate elements for specific analysis type."""
        validation = {"valid": True, "warnings": [], "errors": []}

        # Analysis-specific validation rules
        if analysis_type == "energy_performance":
            # Check for rooms, walls, windows, doors
            required_categories = ["Rooms", "Walls", "Windows", "Doors"]
            element_categories = [e.Category.Name for e in elements if e.Category]

            missing_categories = [
                cat for cat in required_categories if cat not in element_categories
            ]
            if missing_categories:
                validation["warnings"].append(
                    f"Energy analysis may be incomplete without: {missing_categories}"
                )

        elif analysis_type == "structural_analysis":
            # Check for structural elements
            structural_categories = [
                "Columns",
                "Beams",
                "Structural Foundations",
                "Floors",
            ]
            element_categories = [e.Category.Name for e in elements if e.Category]

            has_structural = any(
                cat in element_categories for cat in structural_categories
            )
            if not has_structural:
                validation["warnings"].append(
                    "No structural elements found for structural analysis"
                )

        elif analysis_type == "space_optimization":
            # Check for rooms or spaces
            space_categories = ["Rooms", "Spaces"]
            element_categories = [e.Category.Name for e in elements if e.Category]

            has_spaces = any(cat in element_categories for cat in space_categories)
            if not has_spaces:
                validation["errors"].append(
                    "Space optimization requires Room or Space elements"
                )
                validation["valid"] = False

        return validation

    def _estimate_processing_time(
        self, elements: list[Any], analysis_type: str | None
    ) -> str:
        """Estimate processing time for elements."""
        element_count = len(elements)

        # Basic time estimation based on element count
        if element_count < 10:
            base_time = "< 1 minute"
        elif element_count < 100:
            base_time = "1-5 minutes"
        elif element_count < 1000:
            base_time = "5-30 minutes"
        else:
            base_time = "> 30 minutes"

        # Adjust based on analysis type
        if analysis_type in ["energy_performance", "structural_analysis"]:
            return f"{base_time} (complex analysis)"
        elif analysis_type in ["clash_detection", "space_optimization"]:
            return f"{base_time} (intensive computation)"
        else:
            return base_time

    def _update_selection_stats(self, elements: list[Any]):
        """Update selection statistics."""
        self.selection_stats["total_selections"] += 1
        self.selection_stats["last_selection_count"] = len(elements)

        # Count by category
        for element in elements:
            try:
                category_name = element.Category.Name if element.Category else "Unknown"
                self.selection_stats["elements_by_category"][category_name] = (
                    self.selection_stats["elements_by_category"].get(category_name, 0)
                    + 1
                )
            except:
                self.selection_stats["elements_by_category"]["Unknown"] = (
                    self.selection_stats["elements_by_category"].get("Unknown", 0) + 1
                )

    def get_selection_statistics(self) -> dict[str, Any]:
        """Get selection statistics."""
        return self.selection_stats.copy()
