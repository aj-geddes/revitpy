"""
Speckle type mapper for RevitPy.

This module provides bidirectional mapping between RevitPy element types
and Speckle object types, supporting custom property mappings and type
registration.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .exceptions import TypeMappingError
from .types import MappingStatus, TypeMapping


class SpeckleTypeMapper:
    """Maps RevitPy element types to Speckle object types and vice versa.

    Maintains a registry of type mappings with optional property maps
    for converting between RevitPy elements and Speckle objects.
    """

    _DEFAULT_MAPPINGS: dict[str, str] = {
        "WallElement": "Objects.BuiltElements.Wall:Wall",
        "RoomElement": "Objects.BuiltElements.Room:Room",
        "DoorElement": "Objects.BuiltElements.Door:Door",
        "WindowElement": "Objects.BuiltElements.Window:Window",
        "SlabElement": "Objects.BuiltElements.Floor:Floor",
        "RoofElement": "Objects.BuiltElements.Roof:Roof",
        "ColumnElement": "Objects.BuiltElements.Column:Column",
        "BeamElement": "Objects.BuiltElements.Beam:Beam",
        "StairElement": "Objects.BuiltElements.Stair:Stair",
        "RailingElement": "Objects.BuiltElements.Railing:Railing",
    }

    def __init__(self) -> None:
        self._registry: dict[str, TypeMapping] = {}
        self._reverse_registry: dict[str, str] = {}
        self._populate_defaults()

    def _populate_defaults(self) -> None:
        """Populate the registry from the default mappings."""
        for revitpy_type, speckle_type in self._DEFAULT_MAPPINGS.items():
            mapping = TypeMapping(
                revitpy_type=revitpy_type,
                speckle_type=speckle_type,
            )
            self._registry[revitpy_type] = mapping
            self._reverse_registry[speckle_type] = revitpy_type

    def register_mapping(
        self,
        revitpy_type: str,
        speckle_type: str,
        property_map: dict[str, str] | None = None,
    ) -> None:
        """Register a custom mapping between a RevitPy type and Speckle type.

        Args:
            revitpy_type: The RevitPy element type name.
            speckle_type: The Speckle object type identifier.
            property_map: Optional dict mapping RevitPy property names
                to Speckle property names.
        """
        mapping = TypeMapping(
            revitpy_type=revitpy_type,
            speckle_type=speckle_type,
            property_map=property_map or {},
        )
        self._registry[revitpy_type] = mapping
        self._reverse_registry[speckle_type] = revitpy_type

        logger.debug(
            "Registered Speckle mapping: {} <-> {}",
            revitpy_type,
            speckle_type,
        )

    def get_mapping(self, revitpy_type: str) -> TypeMapping | None:
        """Get the Speckle mapping for a RevitPy type.

        Args:
            revitpy_type: The RevitPy element type name.

        Returns:
            The TypeMapping if found, or None.
        """
        return self._registry.get(revitpy_type)

    def to_speckle(self, element: Any) -> dict[str, Any]:
        """Convert a RevitPy element to a Speckle-compatible dict.

        Args:
            element: A duck-typed RevitPy element with at least
                a class name matching a registered type.

        Returns:
            Dict suitable for sending to Speckle.

        Raises:
            TypeMappingError: If the element type is not mapped.
        """
        element_type = type(element).__name__
        mapping = self._registry.get(element_type)

        if mapping is None:
            raise TypeMappingError(
                f"No Speckle mapping found for type: {element_type}",
                source_type=element_type,
                target_type=None,
            )

        result: dict[str, Any] = {
            "speckle_type": mapping.speckle_type,
            "revitpy_type": element_type,
            "id": getattr(element, "id", None),
            "name": getattr(element, "name", None),
        }

        # Apply property mappings
        if mapping.property_map:
            for revit_prop, speckle_prop in mapping.property_map.items():
                value = getattr(element, revit_prop, None)
                if value is not None:
                    result[speckle_prop] = value
        else:
            # Fallback: copy all public attributes
            for attr in dir(element):
                if not attr.startswith("_") and attr not in (
                    "id",
                    "name",
                ):
                    value = getattr(element, attr, None)
                    if value is not None and not callable(value):
                        result[attr] = value

        logger.debug(
            "Converted {} to Speckle type {}",
            element_type,
            mapping.speckle_type,
        )
        return result

    def from_speckle(
        self,
        speckle_obj: dict[str, Any],
        target_type: str | None = None,
    ) -> dict[str, Any]:
        """Convert a Speckle object dict back to a RevitPy-compatible dict.

        Args:
            speckle_obj: Dict received from Speckle.
            target_type: Optional target RevitPy type name. If not
                provided, the reverse registry is consulted using
                the ``speckle_type`` key.

        Returns:
            Dict with RevitPy element properties.

        Raises:
            TypeMappingError: If the Speckle type is not mapped and
                no ``target_type`` is given.
        """
        speckle_type = speckle_obj.get("speckle_type", "Unknown")

        if target_type is None:
            target_type = self._reverse_registry.get(speckle_type)

        if target_type is None:
            raise TypeMappingError(
                f"No RevitPy mapping found for Speckle type: {speckle_type}",
                source_type=speckle_type,
                target_type=None,
            )

        mapping = self._registry.get(target_type)
        result: dict[str, Any] = {
            "type": target_type,
            "speckle_type": speckle_type,
            "id": speckle_obj.get("id"),
            "name": speckle_obj.get("name"),
        }

        # Apply reverse property mappings
        if mapping and mapping.property_map:
            reverse_map = {v: k for k, v in mapping.property_map.items()}
            for speckle_prop, revit_prop in reverse_map.items():
                value = speckle_obj.get(speckle_prop)
                if value is not None:
                    result[revit_prop] = value
        else:
            # Fallback: copy known keys
            for key, value in speckle_obj.items():
                if key not in ("speckle_type", "id", "name"):
                    result[key] = value

        logger.debug(
            "Converted Speckle {} to RevitPy type {}",
            speckle_type,
            target_type,
        )
        return result

    @property
    def registered_types(self) -> list[str]:
        """Return a list of all registered RevitPy type names."""
        return list(self._registry.keys())

    @property
    def registered_speckle_types(self) -> list[str]:
        """Return a list of all registered Speckle type identifiers."""
        return list(self._reverse_registry.keys())

    def get_unmapped_status(self, revitpy_type: str) -> TypeMapping:
        """Return an UNMAPPED TypeMapping for an unregistered type.

        Args:
            revitpy_type: The RevitPy element type name.

        Returns:
            A TypeMapping with ``MappingStatus.UNMAPPED``.
        """
        return TypeMapping(
            revitpy_type=revitpy_type,
            speckle_type="",
            status=MappingStatus.UNMAPPED,
        )
