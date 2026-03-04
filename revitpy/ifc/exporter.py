"""
IFC exporter for RevitPy.

This module provides the IfcExporter class for converting collections
of RevitPy elements into IFC files, with both synchronous and
asynchronous interfaces.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from ._compat import require_ifcopenshell
from .exceptions import IfcExportError
from .mapper import IfcElementMapper
from .types import IfcExportConfig, IfcVersion


class IfcExporter:
    """Export RevitPy elements to IFC files.

    Uses ifcopenshell to create standards-compliant IFC files from
    RevitPy element collections.
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
        import ifcopenshell  # noqa: E402

        try:
            ifc_file = ifcopenshell.file(schema=version.value)

            # Create project structure
            ifc_file.create_entity(
                "IfcProject",
                GlobalId=ifcopenshell.guid.new(),
                Name="RevitPy Export",
            )

            ifc_file.create_entity(
                "IfcSite",
                GlobalId=ifcopenshell.guid.new(),
                Name=self._config.site_name,
            )

            ifc_file.create_entity(
                "IfcBuilding",
                GlobalId=ifcopenshell.guid.new(),
                Name=self._config.building_name,
            )

            # Export each element
            exported_count = 0
            for element in elements:
                try:
                    self._mapper.to_ifc(element, ifc_file, self._config)
                    exported_count += 1
                except IfcExportError:
                    logger.warning(
                        "Skipping unmapped element type: {}",
                        type(element).__name__,
                    )

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
