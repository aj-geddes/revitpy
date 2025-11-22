"""
Custom Element Filters - Advanced filtering utilities for Revit elements.

This module demonstrates advanced filtering techniques:
- Parameter-based filtering
- Geometric filtering
- Combined filter conditions
- Performance-optimized filtering strategies
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

try:
    from revitpy import Element, FilteredElementCollector
    from revitpy.exceptions import RevitPyException
    from revitpy.geometry import XYZ, BoundingBoxXYZ
except ImportError:
    # Mock imports for development/testing
    from .utils import MockElement as Element


class FilterCondition(ABC):
    """Abstract base class for filter conditions."""

    @abstractmethod
    def matches(self, element: Element) -> bool:
        """Check if element matches this condition."""
        pass


class ParameterFilter(FilterCondition):
    """Filter based on parameter values."""

    def __init__(
        self,
        parameter_name: str,
        value: Any,
        comparison: str = "equals",
        case_sensitive: bool = True,
    ):
        """
        Initialize parameter filter.

        Args:
            parameter_name: Name of parameter to check
            value: Value to compare against
            comparison: Comparison type ('equals', 'contains', 'greater', 'less', 'not_equals')
            case_sensitive: Whether string comparisons should be case sensitive
        """
        self.parameter_name = parameter_name
        self.value = value
        self.comparison = comparison.lower()
        self.case_sensitive = case_sensitive
        self.logger = logging.getLogger(__name__)

    def matches(self, element: Element) -> bool:
        """Check if element parameter matches the condition."""
        try:
            param = element.LookupParameter(self.parameter_name)
            if not param or not param.HasValue:
                return False

            param_value = self._get_parameter_value(param)
            if param_value is None:
                return False

            return self._compare_values(param_value, self.value)

        except Exception as e:
            self.logger.debug(
                f"Error checking parameter {self.parameter_name} on element {element.Id}: {e}"
            )
            return False

    def _get_parameter_value(self, parameter) -> Any:
        """Get parameter value based on storage type."""
        try:
            storage_type = parameter.StorageType.ToString()

            if storage_type == "String":
                return parameter.AsString()
            elif storage_type == "Integer":
                return parameter.AsInteger()
            elif storage_type == "Double":
                return parameter.AsDouble()
            elif storage_type == "ElementId":
                return parameter.AsElementId().IntegerValue
            else:
                return parameter.AsValueString()
        except:
            return None

    def _compare_values(self, param_value: Any, target_value: Any) -> bool:
        """Compare parameter value with target value based on comparison type."""
        if self.comparison == "equals":
            return self._equals_comparison(param_value, target_value)
        elif self.comparison == "not_equals":
            return not self._equals_comparison(param_value, target_value)
        elif self.comparison == "contains":
            return self._contains_comparison(param_value, target_value)
        elif self.comparison == "greater":
            return self._numeric_comparison(
                param_value, target_value, lambda x, y: x > y
            )
        elif self.comparison == "less":
            return self._numeric_comparison(
                param_value, target_value, lambda x, y: x < y
            )
        elif self.comparison == "greater_or_equal":
            return self._numeric_comparison(
                param_value, target_value, lambda x, y: x >= y
            )
        elif self.comparison == "less_or_equal":
            return self._numeric_comparison(
                param_value, target_value, lambda x, y: x <= y
            )
        else:
            raise ValueError(f"Unsupported comparison type: {self.comparison}")

    def _equals_comparison(self, param_value: Any, target_value: Any) -> bool:
        """Handle equals comparison with type conversion."""
        if isinstance(param_value, str) and isinstance(target_value, str):
            if not self.case_sensitive:
                return param_value.lower() == target_value.lower()
            return param_value == target_value

        # Try numeric comparison
        try:
            return float(param_value) == float(target_value)
        except (ValueError, TypeError):
            return str(param_value) == str(target_value)

    def _contains_comparison(self, param_value: Any, target_value: Any) -> bool:
        """Handle contains comparison."""
        param_str = str(param_value)
        target_str = str(target_value)

        if not self.case_sensitive:
            param_str = param_str.lower()
            target_str = target_str.lower()

        return target_str in param_str

    def _numeric_comparison(
        self, param_value: Any, target_value: Any, comparison_func: Callable
    ) -> bool:
        """Handle numeric comparisons."""
        try:
            return comparison_func(float(param_value), float(target_value))
        except (ValueError, TypeError):
            return False


class GeometryFilter(FilterCondition):
    """Filter based on element geometry properties."""

    def __init__(
        self,
        bounds: dict[str, Any] | None = None,
        min_area: float | None = None,
        max_area: float | None = None,
        min_volume: float | None = None,
        max_volume: float | None = None,
    ):
        """
        Initialize geometry filter.

        Args:
            bounds: Bounding box dictionary with 'min' and 'max' XYZ coordinates
            min_area: Minimum area threshold
            max_area: Maximum area threshold
            min_volume: Minimum volume threshold
            max_volume: Maximum volume threshold
        """
        self.bounds = bounds
        self.min_area = min_area
        self.max_area = max_area
        self.min_volume = min_volume
        self.max_volume = max_volume
        self.logger = logging.getLogger(__name__)

    def matches(self, element: Element) -> bool:
        """Check if element geometry matches the conditions."""
        try:
            # Check location bounds
            if self.bounds and not self._is_within_bounds(element):
                return False

            # Check area constraints
            if (
                self.min_area is not None or self.max_area is not None
            ) and not self._check_area_constraints(element):
                return False

            # Check volume constraints
            if (
                self.min_volume is not None or self.max_volume is not None
            ) and not self._check_volume_constraints(element):
                return False

            return True

        except Exception as e:
            self.logger.debug(f"Error checking geometry for element {element.Id}: {e}")
            return False

    def _is_within_bounds(self, element: Element) -> bool:
        """Check if element is within specified bounds."""
        try:
            location = element.Location
            if not location:
                return False

            if hasattr(location, "Point"):
                point = location.Point
                return self._point_in_bounds(point)
            elif hasattr(location, "Curve"):
                curve = location.Curve
                start_point = curve.GetEndPoint(0)
                end_point = curve.GetEndPoint(1)
                return self._point_in_bounds(start_point) or self._point_in_bounds(
                    end_point
                )

            return False

        except Exception as e:
            self.logger.debug(f"Error checking bounds for element {element.Id}: {e}")
            return False

    def _point_in_bounds(self, point) -> bool:
        """Check if a point is within the specified bounds."""
        if not self.bounds:
            return True

        min_pt = self.bounds.get("min", {})
        max_pt = self.bounds.get("max", {})

        x_ok = (
            min_pt.get("x", float("-inf")) <= point.X <= max_pt.get("x", float("inf"))
        )
        y_ok = (
            min_pt.get("y", float("-inf")) <= point.Y <= max_pt.get("y", float("inf"))
        )
        z_ok = (
            min_pt.get("z", float("-inf")) <= point.Z <= max_pt.get("z", float("inf"))
        )

        return x_ok and y_ok and z_ok

    def _check_area_constraints(self, element: Element) -> bool:
        """Check area constraints."""
        try:
            area_param = element.LookupParameter("Area")
            if not area_param or not area_param.HasValue:
                return True  # Skip if no area parameter

            area = area_param.AsDouble()

            if self.min_area is not None and area < self.min_area:
                return False

            if self.max_area is not None and area > self.max_area:
                return False

            return True

        except Exception as e:
            self.logger.debug(f"Error checking area for element {element.Id}: {e}")
            return True  # Default to passing on error

    def _check_volume_constraints(self, element: Element) -> bool:
        """Check volume constraints."""
        try:
            volume_param = element.LookupParameter("Volume")
            if not volume_param or not volume_param.HasValue:
                return True  # Skip if no volume parameter

            volume = volume_param.AsDouble()

            if self.min_volume is not None and volume < self.min_volume:
                return False

            if self.max_volume is not None and volume > self.max_volume:
                return False

            return True

        except Exception as e:
            self.logger.debug(f"Error checking volume for element {element.Id}: {e}")
            return True  # Default to passing on error


class CategoryFilter(FilterCondition):
    """Filter based on element category."""

    def __init__(self, categories: str | list[str], exclude: bool = False):
        """
        Initialize category filter.

        Args:
            categories: Single category name or list of category names
            exclude: Whether to exclude (True) or include (False) the categories
        """
        if isinstance(categories, str):
            self.categories = [categories]
        else:
            self.categories = categories

        self.exclude = exclude
        self.logger = logging.getLogger(__name__)

    def matches(self, element: Element) -> bool:
        """Check if element category matches the condition."""
        try:
            if not element.Category:
                return self.exclude  # No category matches exclusion logic

            category_name = element.Category.Name
            is_in_categories = category_name in self.categories

            return not is_in_categories if self.exclude else is_in_categories

        except Exception as e:
            self.logger.debug(f"Error checking category for element {element.Id}: {e}")
            return False


class CustomElementFilter:
    """
    Advanced element filtering system with multiple filter conditions.

    This class allows combining multiple filter conditions with AND/OR logic
    and provides performance optimizations for large element sets.
    """

    def __init__(self):
        """Initialize the custom element filter."""
        self.logger = logging.getLogger(__name__)
        self.conditions = []
        self.logic = "AND"  # Default to AND logic

    def add_condition(self, condition: FilterCondition) -> "CustomElementFilter":
        """
        Add a filter condition.

        Args:
            condition: FilterCondition instance

        Returns:
            Self for method chaining
        """
        self.conditions.append(condition)
        return self

    def add_parameter_filter(
        self,
        parameter_name: str,
        value: Any,
        comparison: str = "equals",
        case_sensitive: bool = True,
    ) -> "CustomElementFilter":
        """
        Add a parameter-based filter condition.

        Args:
            parameter_name: Name of parameter to check
            value: Value to compare against
            comparison: Comparison type
            case_sensitive: Whether string comparisons should be case sensitive

        Returns:
            Self for method chaining
        """
        condition = ParameterFilter(parameter_name, value, comparison, case_sensitive)
        return self.add_condition(condition)

    def add_geometry_filter(self, **kwargs) -> "CustomElementFilter":
        """
        Add a geometry-based filter condition.

        Args:
            **kwargs: Geometry filter parameters

        Returns:
            Self for method chaining
        """
        condition = GeometryFilter(**kwargs)
        return self.add_condition(condition)

    def add_category_filter(
        self, categories: str | list[str], exclude: bool = False
    ) -> "CustomElementFilter":
        """
        Add a category-based filter condition.

        Args:
            categories: Category name(s) to filter
            exclude: Whether to exclude the categories

        Returns:
            Self for method chaining
        """
        condition = CategoryFilter(categories, exclude)
        return self.add_condition(condition)

    def set_logic(self, logic: str) -> "CustomElementFilter":
        """
        Set the logic for combining conditions.

        Args:
            logic: "AND" or "OR"

        Returns:
            Self for method chaining
        """
        if logic.upper() not in ["AND", "OR"]:
            raise ValueError("Logic must be 'AND' or 'OR'")

        self.logic = logic.upper()
        return self

    def filter_elements(self, elements: list[Element]) -> list[Element]:
        """
        Apply all filter conditions to the element list.

        Args:
            elements: List of elements to filter

        Returns:
            Filtered list of elements
        """
        if not self.conditions:
            self.logger.warning(
                "No filter conditions specified, returning all elements"
            )
            return elements

        filtered_elements = []

        for element in elements:
            if self._element_matches(element):
                filtered_elements.append(element)

        self.logger.info(
            f"Filtered {len(elements)} elements to {len(filtered_elements)} results"
        )
        return filtered_elements

    def filter_by_parameter(
        self,
        elements: list[Element],
        parameter_name: str,
        parameter_value: Any,
        comparison: str = "equals",
    ) -> list[Element]:
        """
        Quick filter by single parameter (legacy method for compatibility).

        Args:
            elements: List of elements to filter
            parameter_name: Name of parameter to check
            parameter_value: Value to match
            comparison: Comparison type

        Returns:
            Filtered list of elements
        """
        # Create temporary filter
        temp_filter = CustomElementFilter()
        temp_filter.add_parameter_filter(parameter_name, parameter_value, comparison)

        return temp_filter.filter_elements(elements)

    def filter_by_location(
        self, elements: list[Element], bounds: dict[str, Any]
    ) -> list[Element]:
        """
        Quick filter by location bounds (legacy method for compatibility).

        Args:
            elements: List of elements to filter
            bounds: Dictionary with 'min' and 'max' XYZ coordinates

        Returns:
            Elements within the specified bounds
        """
        # Create temporary filter
        temp_filter = CustomElementFilter()
        temp_filter.add_geometry_filter(bounds=bounds)

        return temp_filter.filter_elements(elements)

    def create_complex_filter(self, **criteria) -> list[Element]:
        """
        Create and apply a complex filter with multiple criteria.

        Args:
            **criteria: Various filter criteria

        Example:
            filter.create_complex_filter(
                categories=['Walls', 'Floors'],
                parameter_filters=[
                    {'name': 'Type Mark', 'value': 'W1', 'comparison': 'equals'},
                    {'name': 'Area', 'value': 100, 'comparison': 'greater'}
                ],
                bounds={'min': {'x': 0, 'y': 0}, 'max': {'x': 100, 'y': 100}},
                logic='AND'
            )
        """
        # Reset conditions
        self.conditions = []

        # Add category filter
        if "categories" in criteria:
            self.add_category_filter(criteria["categories"])

        # Add parameter filters
        if "parameter_filters" in criteria:
            for param_filter in criteria["parameter_filters"]:
                self.add_parameter_filter(**param_filter)

        # Add geometry filter
        geometry_kwargs = {}
        for key in ["bounds", "min_area", "max_area", "min_volume", "max_volume"]:
            if key in criteria:
                geometry_kwargs[key] = criteria[key]

        if geometry_kwargs:
            self.add_geometry_filter(**geometry_kwargs)

        # Set logic
        if "logic" in criteria:
            self.set_logic(criteria["logic"])

        # Apply to elements if provided
        if "elements" in criteria:
            return self.filter_elements(criteria["elements"])

        return []

    def _element_matches(self, element: Element) -> bool:
        """Check if element matches all/any conditions based on logic."""
        if not self.conditions:
            return True

        results = []
        for condition in self.conditions:
            try:
                results.append(condition.matches(element))
            except Exception as e:
                self.logger.error(
                    f"Error applying condition to element {element.Id}: {e}"
                )
                results.append(False)

        if self.logic == "AND":
            return all(results)
        else:  # OR
            return any(results)

    def get_filter_summary(self) -> str:
        """Get a summary of the current filter configuration."""
        if not self.conditions:
            return "No filter conditions"

        condition_descriptions = []
        for i, condition in enumerate(self.conditions):
            if isinstance(condition, ParameterFilter):
                desc = f"Parameter '{condition.parameter_name}' {condition.comparison} '{condition.value}'"
            elif isinstance(condition, GeometryFilter):
                desc = "Geometry filter (bounds/area/volume constraints)"
            elif isinstance(condition, CategoryFilter):
                action = "exclude" if condition.exclude else "include"
                desc = f"Category filter ({action} {condition.categories})"
            else:
                desc = f"Custom condition {type(condition).__name__}"

            condition_descriptions.append(f"  {i+1}. {desc}")

        conditions_text = "\n".join(condition_descriptions)
        return f"Filter Logic: {self.logic}\nConditions:\n{conditions_text}"
