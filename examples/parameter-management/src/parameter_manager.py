"""
Parameter Manager - Core functionality for Revit parameter management.

This module provides comprehensive parameter management capabilities including:
- Reading and writing all parameter types
- Parameter validation and error handling
- Transaction management for safe operations
- Change tracking and audit trails
- Unit conversion and handling
"""

import logging
import time
from datetime import datetime
from typing import Any

try:
    # RevitPy imports
    from revitpy import Element, Parameter, RevitAPI, Transaction
    from revitpy.exceptions import RevitPyException
    from revitpy.parameters import BuiltInParameter, ParameterType, StorageType
    from revitpy.units import DisplayUnitType, UnitUtils
except ImportError:
    # Mock imports for development/testing
    from .utils import MockElement as Element
    from .utils import MockParameter as Parameter
    from .utils import MockRevitPy as RevitAPI
    from .utils import MockRevitPyException as RevitPyException
    from .utils import MockTransaction as Transaction


class ParameterError(Exception):
    """Base exception for parameter-related errors."""

    pass


class ParameterNotFoundError(ParameterError):
    """Raised when a parameter is not found on an element."""

    def __init__(self, parameter_name: str, element_id: int = None):
        self.parameter_name = parameter_name
        self.element_id = element_id
        super().__init__(
            f"Parameter '{parameter_name}' not found"
            + (f" on element {element_id}" if element_id else "")
        )


class ParameterReadOnlyError(ParameterError):
    """Raised when attempting to modify a read-only parameter."""

    def __init__(self, parameter_name: str):
        self.parameter_name = parameter_name
        super().__init__(f"Parameter '{parameter_name}' is read-only")


class ParameterValidationError(ParameterError):
    """Raised when parameter validation fails."""

    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__(f"Parameter validation failed: {errors}")


class TransactionError(ParameterError):
    """Raised when a transaction fails."""

    def __init__(self, message: str, transaction_name: str = None):
        self.message = message
        self.transaction_name = transaction_name
        super().__init__(message)


class ParameterManager:
    """
    Comprehensive parameter management system for Revit elements.

    This class provides safe, efficient, and feature-rich parameter operations
    with comprehensive error handling, validation, and change tracking.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the Parameter Manager.

        Args:
            config: Configuration dictionary with settings
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or self._get_default_config()

        # Initialize RevitPy connection
        try:
            self.revit = RevitAPI()
            self.doc = self.revit.get_active_document()

            if not self.doc:
                raise RevitPyException("No active Revit document found")

            self.logger.info(f"Connected to document: {self.doc.Title}")

        except Exception as e:
            self.logger.error(f"Failed to connect to Revit: {e}")
            raise ParameterError(f"Revit connection failed: {e}")

        # Initialize change tracking if enabled
        self.change_tracking = self.config.get("parameters", {}).get(
            "track_changes", False
        )
        self.change_history = [] if self.change_tracking else None

        # Initialize statistics
        self.stats = {
            "parameters_read": 0,
            "parameters_written": 0,
            "transactions_executed": 0,
            "validation_errors": 0,
            "operation_time": 0,
        }

    def get_element_by_id(self, element_id: int | str) -> Element:
        """
        Get element by its ID.

        Args:
            element_id: Element ID (integer or string)

        Returns:
            Revit element

        Raises:
            ParameterError: If element not found
        """
        try:
            if isinstance(element_id, str):
                element_id = int(element_id)

            element = self.doc.GetElement(element_id)
            if not element:
                raise ParameterError(f"Element with ID {element_id} not found")

            return element

        except ValueError:
            raise ParameterError(f"Invalid element ID format: {element_id}")
        except Exception as e:
            raise ParameterError(f"Failed to get element {element_id}: {e}")

    def get_elements_by_category(self, category_name: str) -> list[Element]:
        """
        Get all elements in a category.

        Args:
            category_name: Name of the category

        Returns:
            List of elements
        """
        try:
            from revitpy import FilteredElementCollector

            collector = FilteredElementCollector(self.doc)
            elements = (
                collector.of_category(category_name)
                .where_element_is_not_element_type()
                .to_elements()
            )

            self.logger.info(
                f"Found {len(elements)} elements in category '{category_name}'"
            )
            return elements

        except Exception as e:
            self.logger.error(
                f"Failed to get elements from category '{category_name}': {e}"
            )
            raise ParameterError(f"Category query failed: {e}")

    def get_parameter(self, element: Element, parameter_name: str) -> Parameter | None:
        """
        Get a parameter from an element by name.

        Args:
            element: Revit element
            parameter_name: Name of the parameter

        Returns:
            Parameter object or None if not found
        """
        try:
            param = element.LookupParameter(parameter_name)
            if param:
                self.stats["parameters_read"] += 1
            return param

        except Exception as e:
            self.logger.debug(f"Error getting parameter '{parameter_name}': {e}")
            return None

    def get_parameter_value(self, element: Element, parameter_name: str) -> Any:
        """
        Get the value of a parameter.

        Args:
            element: Revit element
            parameter_name: Name of the parameter

        Returns:
            Parameter value or None if not found

        Raises:
            ParameterNotFoundError: If parameter not found
        """
        param = self.get_parameter(element, parameter_name)
        if not param:
            raise ParameterNotFoundError(parameter_name, element.Id.IntegerValue)

        return self._get_parameter_value_by_storage_type(param)

    def get_parameters(
        self, element: Element, parameter_names: list[str]
    ) -> dict[str, Any]:
        """
        Get multiple parameter values from an element.

        Args:
            element: Revit element
            parameter_names: List of parameter names to retrieve

        Returns:
            Dictionary mapping parameter names to values
        """
        parameters = {}

        for param_name in parameter_names:
            try:
                value = self.get_parameter_value(element, param_name)
                parameters[param_name] = value
            except ParameterNotFoundError:
                parameters[param_name] = None
                if (
                    self.config.get("parameters", {}).get("handle_readonly_parameters")
                    == "warn"
                ):
                    self.logger.warning(
                        f"Parameter '{param_name}' not found on element {element.Id}"
                    )

        return parameters

    def get_all_parameters(self, element: Element) -> dict[str, Any]:
        """
        Get all parameters from an element.

        Args:
            element: Revit element

        Returns:
            Dictionary mapping parameter names to values
        """
        parameters = {}

        try:
            for param in element.Parameters:
                param_name = param.Definition.Name
                value = self._get_parameter_value_by_storage_type(param)
                parameters[param_name] = value
                self.stats["parameters_read"] += 1

            return parameters

        except Exception as e:
            self.logger.error(
                f"Error getting all parameters from element {element.Id}: {e}"
            )
            return {}

    def get_parameters_detailed(self, element: Element) -> dict[str, dict[str, Any]]:
        """
        Get detailed parameter information including metadata.

        Args:
            element: Revit element

        Returns:
            Dictionary with detailed parameter information
        """
        detailed_params = {}

        try:
            for param in element.Parameters:
                param_name = param.Definition.Name

                param_info = {
                    "value": self._get_parameter_value_by_storage_type(param),
                    "storage_type": str(param.StorageType),
                    "is_read_only": param.IsReadOnly,
                    "has_value": param.HasValue,
                    "is_shared": param.IsShared
                    if hasattr(param, "IsShared")
                    else False,
                    "group_name": self._get_parameter_group(param),
                    "unit_type": self._get_parameter_unit_type(param),
                    "definition_type": "Built-in"
                    if self._is_built_in_parameter(param)
                    else "Custom",
                }

                detailed_params[param_name] = param_info
                self.stats["parameters_read"] += 1

            return detailed_params

        except Exception as e:
            self.logger.error(
                f"Error getting detailed parameters from element {element.Id}: {e}"
            )
            return {}

    def set_parameter(
        self, element: Element, parameter_name: str, value: Any, validate: bool = None
    ) -> bool:
        """
        Set a parameter value on an element.

        Args:
            element: Revit element
            parameter_name: Name of the parameter
            value: Value to set
            validate: Whether to validate before setting (uses config default if None)

        Returns:
            True if successful, False otherwise

        Raises:
            ParameterNotFoundError: If parameter not found
            ParameterReadOnlyError: If parameter is read-only
            ParameterValidationError: If validation fails
        """
        if validate is None:
            validate = self.config.get("parameters", {}).get(
                "validate_before_set", True
            )

        param = self.get_parameter(element, parameter_name)
        if not param:
            raise ParameterNotFoundError(parameter_name, element.Id.IntegerValue)

        if param.IsReadOnly:
            raise ParameterReadOnlyError(parameter_name)

        # Validate if requested
        if validate:
            validation_errors = self._validate_parameter_value(param, value)
            if validation_errors:
                self.stats["validation_errors"] += 1
                raise ParameterValidationError({parameter_name: validation_errors})

        # Track change if enabled
        if self.change_tracking:
            old_value = self._get_parameter_value_by_storage_type(param)
            self._record_parameter_change(element, parameter_name, old_value, value)

        # Set the value
        transaction_name = f"Set {parameter_name}"
        with self._create_transaction(transaction_name):
            success = self._set_parameter_value_by_storage_type(param, value)

            if success:
                self.stats["parameters_written"] += 1
                self.logger.debug(
                    f"Set parameter '{parameter_name}' = '{value}' on element {element.Id}"
                )

            return success

    def set_parameters(
        self, element: Element, parameters: dict[str, Any], validate: bool = None
    ) -> dict[str, bool]:
        """
        Set multiple parameter values on an element.

        Args:
            element: Revit element
            parameters: Dictionary of parameter names and values
            validate: Whether to validate before setting

        Returns:
            Dictionary mapping parameter names to success status
        """
        if validate is None:
            validate = self.config.get("parameters", {}).get(
                "validate_before_set", True
            )

        results = {}
        validation_errors = {}

        # Pre-validation if requested
        if validate:
            for param_name, value in parameters.items():
                param = self.get_parameter(element, param_name)
                if param:
                    errors = self._validate_parameter_value(param, value)
                    if errors:
                        validation_errors[param_name] = errors

        if validation_errors:
            self.stats["validation_errors"] += len(validation_errors)
            raise ParameterValidationError(validation_errors)

        # Set parameters in a single transaction
        transaction_name = f"Set multiple parameters ({len(parameters)} params)"

        try:
            with self._create_transaction(transaction_name):
                for param_name, value in parameters.items():
                    try:
                        success = self.set_parameter(
                            element, param_name, value, validate=False
                        )
                        results[param_name] = success
                    except Exception as e:
                        self.logger.error(
                            f"Failed to set parameter '{param_name}': {e}"
                        )
                        results[param_name] = False

            return results

        except Exception as e:
            self.logger.error(f"Transaction failed while setting parameters: {e}")
            raise TransactionError(f"Failed to set parameters: {e}", transaction_name)

    def copy_parameters(
        self,
        source_element: Element,
        target_element: Element,
        parameter_names: list[str] | None = None,
        skip_readonly: bool = True,
    ) -> dict[str, bool]:
        """
        Copy parameters from one element to another.

        Args:
            source_element: Element to copy parameters from
            target_element: Element to copy parameters to
            parameter_names: List of parameter names to copy (all if None)
            skip_readonly: Whether to skip read-only parameters

        Returns:
            Dictionary mapping parameter names to success status
        """
        results = {}

        # Get source parameters
        if parameter_names:
            source_params = self.get_parameters(source_element, parameter_names)
        else:
            source_params = self.get_all_parameters(source_element)

        # Filter out None values
        source_params = {k: v for k, v in source_params.items() if v is not None}

        # Copy to target element
        transaction_name = f"Copy parameters ({len(source_params)} params)"

        try:
            with self._create_transaction(transaction_name):
                for param_name, value in source_params.items():
                    try:
                        target_param = self.get_parameter(target_element, param_name)

                        if not target_param:
                            results[param_name] = False
                            continue

                        if target_param.IsReadOnly and skip_readonly:
                            self.logger.debug(
                                f"Skipping read-only parameter: {param_name}"
                            )
                            results[param_name] = False
                            continue

                        success = self.set_parameter(
                            target_element, param_name, value, validate=False
                        )
                        results[param_name] = success

                    except Exception as e:
                        self.logger.error(
                            f"Failed to copy parameter '{param_name}': {e}"
                        )
                        results[param_name] = False

            successful = sum(1 for success in results.values() if success)
            self.logger.info(f"Copied {successful}/{len(source_params)} parameters")

            return results

        except Exception as e:
            self.logger.error(f"Transaction failed while copying parameters: {e}")
            raise TransactionError(f"Failed to copy parameters: {e}", transaction_name)

    def clear_parameter(self, element: Element, parameter_name: str) -> bool:
        """
        Clear a parameter value (set to default/empty).

        Args:
            element: Revit element
            parameter_name: Name of the parameter to clear

        Returns:
            True if successful, False otherwise
        """
        param = self.get_parameter(element, parameter_name)
        if not param or param.IsReadOnly:
            return False

        # Get appropriate empty value based on storage type
        storage_type = param.StorageType.ToString()
        empty_value = self._get_empty_value_for_storage_type(storage_type)

        return self.set_parameter(element, parameter_name, empty_value, validate=False)

    def find_elements_by_parameter(
        self, parameter_name: str, parameter_value: Any, category: str | None = None
    ) -> list[Element]:
        """
        Find elements with a specific parameter value.

        Args:
            parameter_name: Name of the parameter
            parameter_value: Value to search for
            category: Optional category to limit search

        Returns:
            List of matching elements
        """
        matching_elements = []

        try:
            # Get elements to search
            if category:
                elements = self.get_elements_by_category(category)
            else:
                from revitpy import FilteredElementCollector

                collector = FilteredElementCollector(self.doc)
                elements = collector.where_element_is_not_element_type().to_elements()

            # Search for matching parameter values
            for element in elements:
                try:
                    current_value = self.get_parameter_value(element, parameter_name)
                    if self._values_match(current_value, parameter_value):
                        matching_elements.append(element)
                except ParameterNotFoundError:
                    continue

            self.logger.info(
                f"Found {len(matching_elements)} elements with {parameter_name}='{parameter_value}'"
            )
            return matching_elements

        except Exception as e:
            self.logger.error(f"Error searching for elements by parameter: {e}")
            return []

    def enable_change_tracking(self):
        """Enable parameter change tracking."""
        self.change_tracking = True
        if self.change_history is None:
            self.change_history = []
        self.logger.info("Parameter change tracking enabled")

    def disable_change_tracking(self):
        """Disable parameter change tracking."""
        self.change_tracking = False
        self.logger.info("Parameter change tracking disabled")

    def get_parameter_changes(
        self, element: Element | None = None
    ) -> list[dict[str, Any]]:
        """
        Get parameter change history.

        Args:
            element: Optional element to filter changes for

        Returns:
            List of parameter changes
        """
        if not self.change_history:
            return []

        if element:
            element_id = element.Id.IntegerValue
            return [
                change
                for change in self.change_history
                if change.get("element_id") == element_id
            ]

        return self.change_history[:]

    def get_statistics(self) -> dict[str, Any]:
        """
        Get parameter manager usage statistics.

        Returns:
            Dictionary with usage statistics
        """
        return self.stats.copy()

    def reset_statistics(self):
        """Reset usage statistics."""
        self.stats = {
            "parameters_read": 0,
            "parameters_written": 0,
            "transactions_executed": 0,
            "validation_errors": 0,
            "operation_time": 0,
        }

    # Private helper methods

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration."""
        return {
            "general": {
                "default_transaction_name": "RevitPy Parameter Operation",
                "enable_undo": True,
                "max_batch_size": 100,
                "timeout_seconds": 300,
            },
            "parameters": {
                "handle_readonly_parameters": "warn",
                "convert_units": True,
                "validate_before_set": True,
                "track_changes": False,
            },
            "validation": {"strict_mode": False, "log_validation_errors": True},
        }

    def _get_parameter_value_by_storage_type(self, param: Parameter) -> Any:
        """Get parameter value based on its storage type."""
        try:
            if not param.HasValue:
                return None

            storage_type = param.StorageType.ToString()

            if storage_type == "String":
                return param.AsString()
            elif storage_type == "Integer":
                return param.AsInteger()
            elif storage_type == "Double":
                return param.AsDouble()
            elif storage_type == "ElementId":
                element_id = param.AsElementId()
                if element_id and element_id.IntegerValue != -1:
                    referenced_element = self.doc.GetElement(element_id)
                    return (
                        referenced_element.Name
                        if referenced_element
                        else str(element_id.IntegerValue)
                    )
                return None
            else:
                return param.AsValueString()

        except Exception as e:
            self.logger.debug(f"Error getting parameter value: {e}")
            return None

    def _set_parameter_value_by_storage_type(
        self, param: Parameter, value: Any
    ) -> bool:
        """Set parameter value based on its storage type."""
        try:
            storage_type = param.StorageType.ToString()

            if storage_type == "String":
                return param.Set(str(value) if value is not None else "")
            elif storage_type == "Integer":
                return param.Set(int(value))
            elif storage_type == "Double":
                return param.Set(float(value))
            elif storage_type == "ElementId":
                # Handle ElementId parameters (complex - simplified for example)
                if isinstance(value, int):
                    element = self.doc.GetElement(value)
                    if element:
                        return param.Set(element.Id)
                return False
            else:
                # Try string conversion as fallback
                return param.Set(str(value))

        except Exception as e:
            self.logger.error(f"Error setting parameter value: {e}")
            return False

    def _validate_parameter_value(self, param: Parameter, value: Any) -> str | None:
        """Validate a parameter value."""
        if param.IsReadOnly:
            return "Parameter is read-only"

        if value is None and param.Definition.ParameterType.ToString() != "Text":
            return "Value cannot be None for this parameter type"

        storage_type = param.StorageType.ToString()

        if storage_type == "Integer":
            try:
                int(value)
            except (ValueError, TypeError):
                return f"Invalid integer value: {value}"

        elif storage_type == "Double":
            try:
                float(value)
            except (ValueError, TypeError):
                return f"Invalid numeric value: {value}"

        return None

    def _create_transaction(self, name: str):
        """Create a transaction context manager."""
        return TransactionContext(self.doc, name, self.stats)

    def _record_parameter_change(
        self, element: Element, parameter_name: str, old_value: Any, new_value: Any
    ):
        """Record a parameter change for tracking."""
        if self.change_history is not None:
            change_record = {
                "timestamp": datetime.now().isoformat(),
                "element_id": element.Id.IntegerValue,
                "parameter": parameter_name,
                "old_value": old_value,
                "new_value": new_value,
                "element_category": element.Category.Name
                if element.Category
                else "Unknown",
            }
            self.change_history.append(change_record)

    def _values_match(self, value1: Any, value2: Any) -> bool:
        """Check if two parameter values match."""
        if value1 is None and value2 is None:
            return True
        if value1 is None or value2 is None:
            return False

        # Handle numeric comparisons with tolerance
        try:
            num1, num2 = float(value1), float(value2)
            return abs(num1 - num2) < 1e-10
        except (ValueError, TypeError):
            # String comparison
            return str(value1).strip().lower() == str(value2).strip().lower()

    def _get_empty_value_for_storage_type(self, storage_type: str) -> Any:
        """Get appropriate empty value for storage type."""
        if storage_type == "String":
            return ""
        elif storage_type == "Integer":
            return 0
        elif storage_type == "Double":
            return 0.0
        elif storage_type == "ElementId":
            return None
        else:
            return ""

    def _get_parameter_group(self, param: Parameter) -> str:
        """Get parameter group name."""
        try:
            return param.Definition.ParameterGroup.ToString()
        except:
            return "Unknown"

    def _get_parameter_unit_type(self, param: Parameter) -> str:
        """Get parameter unit type."""
        try:
            return param.Definition.UnitType.ToString()
        except:
            return "Unknown"

    def _is_built_in_parameter(self, param: Parameter) -> bool:
        """Check if parameter is a built-in parameter."""
        try:
            return hasattr(param.Definition, "BuiltInParameter")
        except:
            return False


class TransactionContext:
    """Context manager for Revit transactions."""

    def __init__(self, document, name: str, stats: dict[str, Any]):
        self.document = document
        self.name = name
        self.stats = stats
        self.transaction = None
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        try:
            self.transaction = Transaction(self.document, self.name)
            self.transaction.Start()
            return self.transaction
        except Exception as e:
            raise TransactionError(
                f"Failed to start transaction '{self.name}': {e}", self.name
            )

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.transaction:
                if exc_type is None:
                    self.transaction.Commit()
                    self.stats["transactions_executed"] += 1
                else:
                    self.transaction.RollBack()

            # Record operation time
            if self.start_time:
                self.stats["operation_time"] += time.time() - self.start_time

        except Exception as e:
            raise TransactionError(
                f"Failed to complete transaction '{self.name}': {e}", self.name
            )
