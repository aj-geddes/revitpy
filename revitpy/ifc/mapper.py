"""
IFC element mapper for RevitPy.

This module provides bidirectional mapping between RevitPy element types
and IFC entity types, supporting custom property mappings and type
registration.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from ._compat import require_ifcopenshell
from .exceptions import IfcExportError, IfcImportError
from .types import IfcExportConfig, IfcMapping


class IfcElementMapper:
    """Maps RevitPy element types to IFC entity types and vice versa.

    Maintains a registry of type mappings with optional property maps
    for converting between RevitPy elements and IFC entities.
    """

    _DEFAULT_MAPPINGS: dict[str, str] = {
        "WallElement": "IfcWall",
        "RoomElement": "IfcSpace",
        "DoorElement": "IfcDoor",
        "WindowElement": "IfcWindow",
        "SlabElement": "IfcSlab",
        "RoofElement": "IfcRoof",
        "ColumnElement": "IfcColumn",
        "BeamElement": "IfcBeam",
        "StairElement": "IfcStairFlight",
        "RailingElement": "IfcRailing",
    }

    def __init__(self) -> None:
        self._registry: dict[str, IfcMapping] = {}
        self._reverse_registry: dict[str, str] = {}
        self._populate_defaults()

    def _populate_defaults(self) -> None:
        """Populate the registry from the default mappings."""
        for revitpy_type, ifc_entity_type in self._DEFAULT_MAPPINGS.items():
            mapping = IfcMapping(
                revitpy_type=revitpy_type,
                ifc_entity_type=ifc_entity_type,
                bidirectional=True,
            )
            self._registry[revitpy_type] = mapping
            self._reverse_registry[ifc_entity_type] = revitpy_type

    def register_mapping(
        self,
        revitpy_type: str,
        ifc_entity_type: str,
        property_map: dict[str, str] | None = None,
        *,
        bidirectional: bool = True,
    ) -> None:
        """Register a custom mapping between a RevitPy type and IFC entity.

        Args:
            revitpy_type: The RevitPy element type name.
            ifc_entity_type: The IFC entity type name.
            property_map: Optional dict mapping RevitPy property names
                to IFC property names.
            bidirectional: Whether the mapping works in both directions.
        """
        mapping = IfcMapping(
            revitpy_type=revitpy_type,
            ifc_entity_type=ifc_entity_type,
            property_map=property_map or {},
            bidirectional=bidirectional,
        )
        self._registry[revitpy_type] = mapping
        if bidirectional:
            self._reverse_registry[ifc_entity_type] = revitpy_type

        logger.debug(
            "Registered IFC mapping: {} <-> {}",
            revitpy_type,
            ifc_entity_type,
        )

    def get_mapping(self, revitpy_type: str) -> IfcMapping | None:
        """Get the IFC mapping for a RevitPy type.

        Args:
            revitpy_type: The RevitPy element type name.

        Returns:
            The IfcMapping if found, or None.
        """
        return self._registry.get(revitpy_type)

    def get_ifc_type(self, revitpy_type: str) -> str | None:
        """Get the IFC entity type for a RevitPy type.

        Args:
            revitpy_type: The RevitPy element type name.

        Returns:
            The IFC entity type name, or None if not mapped.
        """
        mapping = self._registry.get(revitpy_type)
        return mapping.ifc_entity_type if mapping else None

    def get_revitpy_type(self, ifc_entity_type: str) -> str | None:
        """Get the RevitPy type for an IFC entity type.

        Args:
            ifc_entity_type: The IFC entity type name.

        Returns:
            The RevitPy type name, or None if not mapped.
        """
        return self._reverse_registry.get(ifc_entity_type)

    def to_ifc(
        self,
        element: Any,
        ifc_file: Any,
        config: IfcExportConfig | None = None,
    ) -> Any:
        """Convert a RevitPy element to an IFC entity.

        Requires ifcopenshell to be installed.

        Args:
            element: The RevitPy element to convert.
            ifc_file: An ifcopenshell file object to create the entity in.
            config: Optional export configuration.

        Returns:
            The created IFC entity.

        Raises:
            ImportError: If ifcopenshell is not installed.
            IfcExportError: If the element type is not mapped or
                conversion fails.
        """
        require_ifcopenshell()
        import ifcopenshell  # noqa: F811

        element_type = type(element).__name__
        mapping = self._registry.get(element_type)
        if mapping is None:
            raise IfcExportError(
                f"No IFC mapping found for type: {element_type}",
                element_count=1,
            )

        try:
            ifc_entity = ifc_file.create_entity(
                mapping.ifc_entity_type,
                GlobalId=ifcopenshell.guid.new(),
                Name=getattr(element, "name", ""),
            )

            # Apply property mappings if any
            for revit_prop, ifc_prop in mapping.property_map.items():
                value = getattr(element, revit_prop, None)
                if value is not None:
                    setattr(ifc_entity, ifc_prop, value)

            logger.debug(
                "Converted {} to {}",
                element_type,
                mapping.ifc_entity_type,
            )
            return ifc_entity

        except Exception as exc:
            raise IfcExportError(
                f"Failed to convert {element_type} to IFC: {exc}",
                element_count=1,
                cause=exc,
            ) from exc

    def from_ifc(
        self,
        ifc_entity: Any,
        target_type: str | None = None,
    ) -> dict[str, Any]:
        """Convert an IFC entity to a dict representation.

        Args:
            ifc_entity: The IFC entity to convert.
            target_type: Optional target RevitPy type name. If not
                provided, the reverse registry is consulted.

        Returns:
            A dict with element properties extracted from the IFC entity.

        Raises:
            IfcImportError: If the IFC entity type is not mapped and
                no target_type is given.
        """
        ifc_type = getattr(ifc_entity, "is_a", lambda: "Unknown")()

        if target_type is None:
            target_type = self._reverse_registry.get(ifc_type)

        if target_type is None:
            raise IfcImportError(
                f"No RevitPy mapping found for IFC type: {ifc_type}",
                entity_type=ifc_type,
            )

        result: dict[str, Any] = {
            "type": target_type,
            "ifc_type": ifc_type,
            "global_id": getattr(ifc_entity, "GlobalId", None),
            "name": getattr(ifc_entity, "Name", None),
        }

        # Apply reverse property mappings
        mapping = self._registry.get(target_type)
        if mapping and mapping.property_map:
            for revit_prop, ifc_prop in mapping.property_map.items():
                value = getattr(ifc_entity, ifc_prop, None)
                if value is not None:
                    result[revit_prop] = value

        logger.debug("Converted {} to dict (type={})", ifc_type, target_type)
        return result

    @property
    def registered_types(self) -> list[str]:
        """Return a list of all registered RevitPy type names."""
        return list(self._registry.keys())

    @property
    def registered_ifc_types(self) -> list[str]:
        """Return a list of all registered IFC entity type names."""
        return list(self._reverse_registry.keys())
