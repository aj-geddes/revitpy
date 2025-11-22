"""
Parameter serialization for Revit elements.
"""

import time
from enum import Enum
from typing import Any

from ..core.config import SerializationConfig
from ..core.exceptions import BridgeDataError


class ParameterType(Enum):
    """Revit parameter types for serialization."""

    TEXT = "text"
    INTEGER = "integer"
    NUMBER = "number"
    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    ANGLE = "angle"
    YESNO = "yes_no"
    ELEMENT_ID = "element_id"
    MATERIAL = "material"
    FAMILY_TYPE = "family_type"
    OTHER = "other"


class ParameterSerializer:
    """Serializer for Revit parameters."""

    def __init__(self, config: SerializationConfig):
        """Initialize parameter serializer."""
        self.config = config

        # Parameter type mapping
        self.type_mappings = {
            "Text": ParameterType.TEXT,
            "Integer": ParameterType.INTEGER,
            "Number": ParameterType.NUMBER,
            "Length": ParameterType.LENGTH,
            "Area": ParameterType.AREA,
            "Volume": ParameterType.VOLUME,
            "Angle": ParameterType.ANGLE,
            "YesNo": ParameterType.YESNO,
            "ElementId": ParameterType.ELEMENT_ID,
            "Material": ParameterType.MATERIAL,
            "FamilyType": ParameterType.FAMILY_TYPE,
        }

    def serialize_parameters(self, parameters: Any) -> dict[str, Any]:
        """
        Serialize Revit parameters collection.

        Args:
            parameters: Revit parameters collection

        Returns:
            Serialized parameters data
        """
        try:
            serialized_params = {}

            for param in parameters:
                try:
                    param_data = self._serialize_single_parameter(param)
                    if param_data:
                        param_name = param_data.get("name", f"param_{id(param)}")
                        serialized_params[param_name] = param_data
                except Exception as e:
                    # Log parameter serialization error but continue
                    param_id = getattr(param, "Id", "unknown")
                    print(f"Warning: Failed to serialize parameter {param_id}: {e}")
                    continue

            return {
                "parameters": serialized_params,
                "count": len(serialized_params),
                "serialization_info": {
                    "precision": self.config.geometry_precision,
                    "include_metadata": self.config.include_metadata,
                },
            }

        except Exception as e:
            raise BridgeDataError("parameter_serialization", "parameters", str(e))

    def _serialize_single_parameter(self, parameter: Any) -> dict[str, Any] | None:
        """Serialize a single parameter."""
        try:
            # Get parameter definition
            definition = self._get_parameter_definition(parameter)
            if not definition:
                return None

            # Get parameter value
            param_value = self._extract_parameter_value(parameter)

            # Get parameter type
            param_type = self._get_parameter_type(parameter)

            # Build parameter data
            param_data = {
                "name": definition.get("name"),
                "type": param_type.value if param_type else "unknown",
                "value": param_value,
                "is_shared": definition.get("is_shared", False),
                "is_read_only": self._is_parameter_read_only(parameter),
                "storage_type": definition.get("storage_type"),
                "group": definition.get("parameter_group"),
                "guid": definition.get("guid"),
            }

            # Add metadata if enabled
            if self.config.include_metadata:
                param_data["metadata"] = self._extract_parameter_metadata(parameter)

            return param_data

        except Exception as e:
            # Return minimal data on error
            return {
                "error": str(e),
                "partial_data": True,
                "name": self._safe_get_parameter_name(parameter),
            }

    def _get_parameter_definition(self, parameter: Any) -> dict[str, Any] | None:
        """Extract parameter definition information."""
        try:
            definition = {}

            # Get parameter definition
            if hasattr(parameter, "Definition"):
                param_def = parameter.Definition

                definition["name"] = (
                    param_def.Name if hasattr(param_def, "Name") else None
                )
                definition["parameter_type"] = (
                    param_def.ParameterType.ToString()
                    if hasattr(param_def, "ParameterType")
                    else None
                )
                definition["unit_type"] = (
                    param_def.UnitType.ToString()
                    if hasattr(param_def, "UnitType")
                    else None
                )
                definition["parameter_group"] = (
                    param_def.ParameterGroup.ToString()
                    if hasattr(param_def, "ParameterGroup")
                    else None
                )

                # Check if it's a shared parameter
                if hasattr(param_def, "GUID"):
                    definition["is_shared"] = True
                    definition["guid"] = str(param_def.GUID)
                else:
                    definition["is_shared"] = False
                    definition["guid"] = None

            # Get storage type
            if hasattr(parameter, "StorageType"):
                definition["storage_type"] = parameter.StorageType.ToString()

            return definition if definition else None

        except Exception as e:
            print(f"Warning: Failed to get parameter definition: {e}")
            return None

    def _extract_parameter_value(self, parameter: Any) -> Any:
        """Extract parameter value based on storage type."""
        try:
            if not hasattr(parameter, "StorageType"):
                return None

            storage_type = parameter.StorageType.ToString()

            # Extract value based on storage type
            if storage_type == "String":
                return parameter.AsString() if hasattr(parameter, "AsString") else None

            elif storage_type == "Integer":
                return (
                    parameter.AsInteger() if hasattr(parameter, "AsInteger") else None
                )

            elif storage_type == "Double":
                value = parameter.AsDouble() if hasattr(parameter, "AsDouble") else None
                if value is not None:
                    return round(value, self.config.geometry_precision)
                return value

            elif storage_type == "ElementId":
                if hasattr(parameter, "AsElementId"):
                    element_id = parameter.AsElementId()
                    if element_id and hasattr(element_id, "IntegerValue"):
                        return element_id.IntegerValue
                return None

            else:
                # Try to get string representation for other types
                return (
                    parameter.AsValueString()
                    if hasattr(parameter, "AsValueString")
                    else None
                )

        except Exception as e:
            print(f"Warning: Failed to extract parameter value: {e}")
            return None

    def _get_parameter_type(self, parameter: Any) -> ParameterType | None:
        """Determine parameter type for serialization."""
        try:
            if hasattr(parameter, "Definition") and hasattr(
                parameter.Definition, "ParameterType"
            ):
                param_type_str = parameter.Definition.ParameterType.ToString()
                return self.type_mappings.get(param_type_str, ParameterType.OTHER)

            # Fallback to storage type
            if hasattr(parameter, "StorageType"):
                storage_type = parameter.StorageType.ToString()
                storage_mappings = {
                    "String": ParameterType.TEXT,
                    "Integer": ParameterType.INTEGER,
                    "Double": ParameterType.NUMBER,
                    "ElementId": ParameterType.ELEMENT_ID,
                }
                return storage_mappings.get(storage_type, ParameterType.OTHER)

            return ParameterType.OTHER

        except Exception:
            return ParameterType.OTHER

    def _is_parameter_read_only(self, parameter: Any) -> bool:
        """Check if parameter is read-only."""
        try:
            return parameter.IsReadOnly if hasattr(parameter, "IsReadOnly") else False
        except Exception:
            return False

    def _extract_parameter_metadata(self, parameter: Any) -> dict[str, Any]:
        """Extract additional parameter metadata."""
        metadata = {}

        try:
            # Parameter ID
            if hasattr(parameter, "Id"):
                metadata["parameter_id"] = (
                    parameter.Id.IntegerValue
                    if hasattr(parameter.Id, "IntegerValue")
                    else str(parameter.Id)
                )

            # Element ID (owner element)
            if hasattr(parameter, "Element") and hasattr(parameter.Element, "Id"):
                metadata["element_id"] = parameter.Element.Id.IntegerValue

            # User modifiable
            if hasattr(parameter, "UserModifiable"):
                metadata["user_modifiable"] = parameter.UserModifiable

            # Has value
            if hasattr(parameter, "HasValue"):
                metadata["has_value"] = parameter.HasValue

            # Formula
            if hasattr(parameter, "Formula"):
                formula = parameter.Formula
                metadata["formula"] = formula if formula else None

            # Display unit type
            if hasattr(parameter, "DisplayUnitType"):
                metadata["display_unit_type"] = parameter.DisplayUnitType.ToString()

        except Exception as e:
            metadata["extraction_error"] = str(e)

        return metadata

    def _safe_get_parameter_name(self, parameter: Any) -> str:
        """Safely get parameter name with fallback."""
        try:
            if hasattr(parameter, "Definition") and hasattr(
                parameter.Definition, "Name"
            ):
                return parameter.Definition.Name

            if hasattr(parameter, "Id"):
                return f"param_{parameter.Id.IntegerValue if hasattr(parameter.Id, 'IntegerValue') else parameter.Id}"

            return f"param_{id(parameter)}"

        except Exception:
            return "unknown_parameter"

    def serialize_parameter_set(self, parameter_set: Any) -> dict[str, Any]:
        """Serialize a parameter set (like type parameters)."""
        try:
            parameters = {}

            for param in parameter_set:
                try:
                    param_data = self._serialize_single_parameter(param)
                    if param_data:
                        param_name = param_data.get("name", f"param_{id(param)}")
                        parameters[param_name] = param_data
                except Exception as e:
                    print(f"Warning: Failed to serialize parameter in set: {e}")
                    continue

            return {
                "parameters": parameters,
                "count": len(parameters),
                "set_type": "parameter_set",
            }

        except Exception as e:
            raise BridgeDataError(
                "parameter_set_serialization", "parameter_set", str(e)
            )

    def create_parameter_filter(
        self, filter_criteria: dict[str, Any]
    ) -> dict[str, Any]:
        """Create parameter filter for element queries."""
        try:
            filter_data = {
                "type": "parameter_filter",
                "criteria": filter_criteria,
                "created_at": time.time(),
            }

            # Validate filter criteria
            required_fields = ["parameter_name", "operator", "value"]
            for field in required_fields:
                if field not in filter_criteria:
                    raise ValueError(f"Missing required filter field: {field}")

            # Add supported operators
            filter_data["supported_operators"] = [
                "equals",
                "not_equals",
                "greater_than",
                "less_than",
                "greater_or_equal",
                "less_or_equal",
                "contains",
                "starts_with",
            ]

            return filter_data

        except Exception as e:
            raise BridgeDataError("parameter_filter_creation", "filter", str(e))

    def extract_parameter_summary(
        self, parameters_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract summary information from serialized parameters."""
        try:
            parameters = parameters_data.get("parameters", {})

            summary = {
                "total_count": len(parameters),
                "type_distribution": {},
                "shared_parameters": 0,
                "read_only_parameters": 0,
                "parameters_with_formulas": 0,
                "parameter_groups": set(),
            }

            for _param_name, param_data in parameters.items():
                # Count by type
                param_type = param_data.get("type", "unknown")
                summary["type_distribution"][param_type] = (
                    summary["type_distribution"].get(param_type, 0) + 1
                )

                # Count shared parameters
                if param_data.get("is_shared", False):
                    summary["shared_parameters"] += 1

                # Count read-only parameters
                if param_data.get("is_read_only", False):
                    summary["read_only_parameters"] += 1

                # Count parameters with formulas
                if param_data.get("metadata", {}).get("formula"):
                    summary["parameters_with_formulas"] += 1

                # Collect parameter groups
                group = param_data.get("group")
                if group:
                    summary["parameter_groups"].add(group)

            # Convert set to list for JSON serialization
            summary["parameter_groups"] = list(summary["parameter_groups"])

            return summary

        except Exception as e:
            return {"error": f"Failed to create parameter summary: {e}"}

    def validate_parameter_data(self, parameter_data: dict[str, Any]) -> list[str]:
        """Validate serialized parameter data."""
        errors = []

        try:
            # Check required fields
            required_fields = ["name", "type", "value"]
            for field in required_fields:
                if field not in parameter_data:
                    errors.append(f"Missing required field: {field}")

            # Validate parameter type
            param_type = parameter_data.get("type")
            if param_type:
                valid_types = [pt.value for pt in ParameterType]
                if param_type not in valid_types:
                    errors.append(f"Invalid parameter type: {param_type}")

            # Validate value based on type
            value = parameter_data.get("value")
            if value is not None and param_type:
                if param_type == ParameterType.INTEGER.value and not isinstance(
                    value, int
                ):
                    errors.append(
                        f"Value {value} is not an integer for parameter type {param_type}"
                    )
                elif param_type == ParameterType.NUMBER.value and not isinstance(
                    value, int | float
                ):
                    errors.append(
                        f"Value {value} is not a number for parameter type {param_type}"
                    )
                elif param_type == ParameterType.TEXT.value and not isinstance(
                    value, str
                ):
                    errors.append(
                        f"Value {value} is not a string for parameter type {param_type}"
                    )

        except Exception as e:
            errors.append(f"Validation error: {e}")

        return errors
