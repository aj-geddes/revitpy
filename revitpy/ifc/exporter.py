"""
IFC exporter for RevitPy.

This module provides the IfcExporter class for converting collections
of RevitPy elements into IFC files, with both synchronous and
asynchronous interfaces.

The exported file contains a valid spatial structure built with the
``ifcopenshell.api`` (0.8+):

- ``IfcProject`` > ``IfcSite`` > ``IfcBuilding`` > ``IfcBuildingStorey``,
  linked with ``IfcRelAggregates``. One storey is created per Revit level
  (read from ``element.level`` / ``element.level_name``); elements without
  a level go to a default storey.
- Physical elements are contained in their storey via
  ``IfcRelContainedInSpatialStructure``; spatial elements such as
  ``IfcSpace`` are aggregated under the storey instead.
- Owner history (person, organisation, application), SI units (metre,
  square metre, cubic metre, radian) and a ``Model`` / ``Body``
  geometric representation context.
- An ``IfcLocalPlacement`` for every product.

Geometry is intentionally minimal: when an element exposes a
``bounding_box`` (``{"min": (x, y, z), "max": (x, y, z)}``, an object with
``min``/``max``, or a ``(min, max)`` pair; metres) an axis-aligned
extruded box is written as its ``Body`` representation. Otherwise no
geometric representation is exported -- Revit geometry is not
tessellated or converted.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _get_version
from pathlib import Path
from typing import Any

from loguru import logger

from ._compat import require_ifcopenshell
from .exceptions import IfcExportError
from .mapper import IfcElementMapper
from .types import IfcExportConfig, IfcVersion

Point3 = tuple[float, float, float]


def _load_api() -> Any:
    """Import and return ``ifcopenshell.api`` with the submodules used here."""
    import ifcopenshell.api.aggregate
    import ifcopenshell.api.context
    import ifcopenshell.api.geometry
    import ifcopenshell.api.owner
    import ifcopenshell.api.root
    import ifcopenshell.api.spatial
    import ifcopenshell.api.unit

    return ifcopenshell.api


def _revitpy_version() -> str:
    """Return the installed RevitPy version, or ``"0.0.0"`` if unknown."""
    try:
        return _get_version("revitpy")
    except PackageNotFoundError:
        return "0.0.0"


def _point(value: Any) -> Point3:
    """Convert a point-like value (sequence or object with x/y/z) to floats."""
    if isinstance(value, list | tuple) and len(value) >= 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    return (float(value.x), float(value.y), float(value.z))


def _bounding_box(element: Any) -> tuple[Point3, Point3] | None:
    """Extract an axis-aligned bounding box ``(min, max)`` from an element.

    Args:
        element: The RevitPy element.

    Returns:
        ``((min_x, min_y, min_z), (max_x, max_y, max_z))`` in metres, or
        None if the element has no usable ``bounding_box``.
    """
    raw = getattr(element, "bounding_box", None)
    if raw is None:
        return None
    try:
        if isinstance(raw, Mapping):
            return _point(raw["min"]), _point(raw["max"])
        if isinstance(raw, list | tuple) and len(raw) == 2:
            return _point(raw[0]), _point(raw[1])
        if hasattr(raw, "min") and hasattr(raw, "max"):
            return _point(raw.min), _point(raw.max)
    except (TypeError, ValueError, AttributeError, KeyError):
        return None
    return None


def _translation(x: float, y: float, z: float) -> Any:
    """Return a 4x4 homogeneous translation matrix (numpy array)."""
    import numpy as np  # hard dependency of ifcopenshell

    matrix = np.eye(4)
    matrix[0, 3] = x
    matrix[1, 3] = y
    matrix[2, 3] = z
    return matrix


def _level_info(element: Any, default_name: str) -> tuple[str, float | None]:
    """Return the ``(storey name, elevation)`` an element belongs to.

    Args:
        element: The RevitPy element.
        default_name: Storey name used when the element exposes no level.

    Returns:
        Tuple of storey name and optional elevation in metres.
    """
    level = getattr(element, "level", None)
    if isinstance(level, str) and level.strip():
        return level.strip(), None
    if level is not None and not isinstance(level, str):
        name = getattr(level, "name", None)
        if name:
            elevation = getattr(level, "elevation", None)
            if isinstance(elevation, int | float) and not isinstance(elevation, bool):
                return str(name), float(elevation)
            return str(name), None

    level_name = getattr(element, "level_name", None)
    if isinstance(level_name, str) and level_name.strip():
        return level_name.strip(), None

    return default_name, None


class IfcExporter:
    """Export RevitPy elements to IFC files.

    Uses ifcopenshell to create IFC files with a complete spatial
    hierarchy (project, site, building, storeys) and contained elements.
    """

    def __init__(
        self,
        mapper: IfcElementMapper | None = None,
        config: IfcExportConfig | None = None,
    ) -> None:
        self._mapper = mapper or IfcElementMapper()
        self._config = config or IfcExportConfig()

    @property
    def mapper(self) -> IfcElementMapper:
        """Return the element mapper used by this exporter."""
        return self._mapper

    @property
    def config(self) -> IfcExportConfig:
        """Return the export configuration."""
        return self._config

    def export(
        self,
        elements: list[Any],
        output_path: str | Path,
        version: IfcVersion = IfcVersion.IFC4,
    ) -> Path:
        """Export elements to an IFC file.

        Args:
            elements: List of RevitPy elements to export.
            output_path: Destination file path for the IFC output.
            version: IFC schema version to use.

        Returns:
            Path to the created IFC file.

        Raises:
            ImportError: If ifcopenshell is not installed.
            IfcExportError: If the export operation fails.
        """
        output_path = Path(output_path)

        if not elements:
            raise IfcExportError(
                "No elements provided for export",
                output_path=str(output_path),
                element_count=0,
                version=version.value,
            )

        require_ifcopenshell()
        import ifcopenshell

        api = _load_api()

        try:
            ifc_file = ifcopenshell.file(schema=version.value)

            # Owner history prerequisites must exist before rooted entities
            # are created (mandatory for IFC2X3).
            self._add_owner(ifc_file, api)

            project = api.root.create_entity(
                ifc_file, ifc_class="IfcProject", name=self._config.project_name
            )
            api.unit.assign_unit(
                ifc_file,
                units=[
                    api.unit.add_si_unit(ifc_file, unit_type=unit_type)
                    for unit_type in (
                        "LENGTHUNIT",
                        "AREAUNIT",
                        "VOLUMEUNIT",
                        "PLANEANGLEUNIT",
                    )
                ],
            )
            model = api.context.add_context(ifc_file, context_type="Model")
            body = api.context.add_context(
                ifc_file,
                context_type="Model",
                context_identifier="Body",
                target_view="MODEL_VIEW",
                parent=model,
            )

            site = api.root.create_entity(
                ifc_file, ifc_class="IfcSite", name=self._config.site_name
            )
            building = api.root.create_entity(
                ifc_file, ifc_class="IfcBuilding", name=self._config.building_name
            )
            api.aggregate.assign_object(
                ifc_file, products=[site], relating_object=project
            )
            api.aggregate.assign_object(
                ifc_file, products=[building], relating_object=site
            )
            api.geometry.edit_object_placement(ifc_file, product=site)
            api.geometry.edit_object_placement(ifc_file, product=building)

            storeys: dict[str, Any] = {}
            exported_count = 0
            for element in elements:
                try:
                    entity = self._mapper.to_ifc(element, ifc_file, self._config)
                except IfcExportError:
                    logger.warning(
                        "Skipping unmapped element type: {}",
                        getattr(element, "category", None) or type(element).__name__,
                    )
                    continue

                storey = self._get_storey(ifc_file, api, building, element, storeys)
                self._contain(ifc_file, api, entity, storey, version)

                try:
                    self._place(ifc_file, api, entity, element, body)
                except Exception as exc:
                    logger.warning(
                        "Could not add placement/geometry for {}: {}",
                        getattr(element, "name", type(element).__name__),
                        exc,
                    )
                exported_count += 1

            ifc_file.write(str(output_path))

            logger.info(
                "Exported {} of {} elements to {}",
                exported_count,
                len(elements),
                output_path,
            )
            return output_path

        except IfcExportError:
            raise
        except Exception as exc:
            raise IfcExportError(
                f"IFC export failed: {exc}",
                output_path=str(output_path),
                element_count=len(elements),
                version=version.value,
                cause=exc,
            ) from exc

    async def export_async(
        self,
        elements: list[Any],
        output_path: str | Path,
        version: IfcVersion = IfcVersion.IFC4,
        progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        """Export elements to an IFC file asynchronously.

        Args:
            elements: List of RevitPy elements to export.
            output_path: Destination file path for the IFC output.
            version: IFC schema version to use.
            progress: Optional callback ``(current, total)`` for progress
                reporting.

        Returns:
            Path to the created IFC file.

        Raises:
            ImportError: If ifcopenshell is not installed.
            IfcExportError: If the export operation fails.
        """
        if progress is not None:
            progress(0, len(elements))

        result = await asyncio.to_thread(self.export, elements, output_path, version)

        if progress is not None:
            progress(len(elements), len(elements))

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_owner(self, ifc_file: Any, api: Any) -> None:
        """Create the person, organisation and application for owner history."""
        person = api.owner.add_person(
            ifc_file,
            identification=self._config.author or "revitpy",
            family_name=self._config.author or "RevitPy",
            given_name="",
        )
        organisation = api.owner.add_organisation(
            ifc_file,
            identification="RevitPy",
            name=self._config.organization,
        )
        api.owner.add_person_and_organisation(
            ifc_file, person=person, organisation=organisation
        )
        api.owner.add_application(
            ifc_file,
            application_developer=organisation,
            version=_revitpy_version(),
            application_full_name="RevitPy",
            application_identifier="RevitPy",
        )

    def _get_storey(
        self,
        ifc_file: Any,
        api: Any,
        building: Any,
        element: Any,
        storeys: dict[str, Any],
    ) -> Any:
        """Return (creating on first use) the storey for an element's level."""
        name, elevation = _level_info(element, self._config.default_storey_name)
        storey = storeys.get(name)
        if storey is not None:
            return storey

        storey = api.root.create_entity(
            ifc_file, ifc_class="IfcBuildingStorey", name=name
        )
        if elevation is not None:
            storey.Elevation = elevation
        api.aggregate.assign_object(
            ifc_file, products=[storey], relating_object=building
        )
        api.geometry.edit_object_placement(
            ifc_file,
            product=storey,
            matrix=_translation(0.0, 0.0, elevation or 0.0),
        )
        storeys[name] = storey
        return storey

    @staticmethod
    def _contain(
        ifc_file: Any, api: Any, entity: Any, storey: Any, version: IfcVersion
    ) -> None:
        """Attach an entity to its storey (aggregation for spatial elements)."""
        is_spatial = entity.is_a("IfcSpatialStructureElement") or (
            version != IfcVersion.IFC2X3 and entity.is_a("IfcSpatialElement")
        )
        if is_spatial:
            api.aggregate.assign_object(
                ifc_file, products=[entity], relating_object=storey
            )
        else:
            api.spatial.assign_container(
                ifc_file, products=[entity], relating_structure=storey
            )

    def _place(
        self, ifc_file: Any, api: Any, entity: Any, element: Any, body: Any
    ) -> None:
        """Add a local placement and, if possible, a bounding-box body."""
        bbox = _bounding_box(element)
        origin = bbox[0] if bbox else (0.0, 0.0, 0.0)
        api.geometry.edit_object_placement(
            ifc_file, product=entity, matrix=_translation(*origin)
        )

        if not (self._config.include_geometry and bbox):
            return

        min_pt, max_pt = bbox
        dx = max_pt[0] - min_pt[0]
        dy = max_pt[1] - min_pt[1]
        dz = max_pt[2] - min_pt[2]
        if dx <= 0 or dy <= 0 or dz <= 0:
            return

        # add_wall_representation builds an extruded rectangle
        # (length x thickness) of the given height from the local origin,
        # i.e. an axis-aligned box.
        representation = api.geometry.add_wall_representation(
            ifc_file, context=body, length=dx, height=dz, thickness=dy
        )
        api.geometry.assign_representation(
            ifc_file, product=entity, representation=representation
        )
