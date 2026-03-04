"""
IFC importer for RevitPy.

This module provides the IfcImporter class for reading IFC files and
converting their contents into RevitPy element dictionaries, with both
synchronous and asynchronous interfaces.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from ._compat import require_ifcopenshell
from .exceptions import IfcImportError
from .mapper import IfcElementMapper
from .types import IfcImportConfig


class IfcImporter:
    """Import elements from IFC files.

    Uses ifcopenshell to parse IFC files and convert entities into
    RevitPy element dictionaries via the mapper.
    """

    # IFC entity types that typically represent building elements.
    _ELEMENT_TYPES: list[str] = [
        "IfcWall",
        "IfcWallStandardCase",
        "IfcDoor",
        "IfcWindow",
        "IfcSlab",
        "IfcRoof",
        "IfcColumn",
        "IfcBeam",
        "IfcStairFlight",
        "IfcRailing",
        "IfcSpace",
    ]

    def __init__(
        self,
        mapper: IfcElementMapper | None = None,
        config: IfcImportConfig | None = None,
    ) -> None:
        self._mapper = mapper or IfcElementMapper()
        self._config = config or IfcImportConfig()

    @property
    def mapper(self) -> IfcElementMapper:
        """Return the element mapper used by this importer."""
        return self._mapper

    @property
    def config(self) -> IfcImportConfig:
        """Return the import configuration."""
        return self._config

    def import_file(self, path: str | Path) -> list[dict[str, Any]]:
        """Import elements from an IFC file.

        Args:
            path: Path to the IFC file.

        Returns:
            List of dicts representing the imported elements.

        Raises:
            ImportError: If ifcopenshell is not installed.
            IfcImportError: If the import operation fails.
        """
        path = Path(path)
        if not path.exists():
            raise IfcImportError(
                f"IFC file not found: {path}",
                input_path=str(path),
            )

        require_ifcopenshell()
        import ifcopenshell  # noqa: E402

        try:
            ifc_file = ifcopenshell.open(str(path))
        except Exception as exc:
            raise IfcImportError(
                f"Failed to open IFC file: {exc}",
                input_path=str(path),
                cause=exc,
            ) from exc

        results: list[dict[str, Any]] = []

        for entity_type in self._ELEMENT_TYPES:
            try:
                entities = ifc_file.by_type(entity_type)
            except Exception:  # noqa: S112
                # Entity type not supported by this IFC file; skip gracefully
                continue

            for entity in entities:
                try:
                    element_dict = self._mapper.from_ifc(entity)
                    # Apply property mapping overrides from config
                    for src, dst in self._config.property_mapping.items():
                        if src in element_dict:
                            element_dict[dst] = element_dict.pop(src)
                    results.append(element_dict)
                except IfcImportError:
                    logger.warning(
                        "Skipping unmapped IFC entity: {}",
                        entity_type,
                    )

        logger.info(
            "Imported {} elements from {}",
            len(results),
            path,
        )
        return results

    async def import_file_async(
        self,
        path: str | Path,
    ) -> list[dict[str, Any]]:
        """Import elements from an IFC file asynchronously.

        Args:
            path: Path to the IFC file.

        Returns:
            List of dicts representing the imported elements.

        Raises:
            ImportError: If ifcopenshell is not installed.
            IfcImportError: If the import operation fails.
        """
        return await asyncio.to_thread(self.import_file, path)
