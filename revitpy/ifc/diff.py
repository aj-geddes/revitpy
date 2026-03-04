"""
IFC model diff engine for RevitPy.

This module provides the IfcDiff class for comparing two sets of
elements (or two IFC files) and producing a structured diff result
that identifies added, modified, and removed entities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from ._compat import require_ifcopenshell
from .mapper import IfcElementMapper
from .types import IfcChangeType, IfcDiffEntry, IfcDiffResult


class IfcDiff:
    """Compare two IFC model states and produce a diff.

    Elements are matched by a unique identifier (``id`` or
    ``global_id`` attribute). Property-level changes are tracked for
    modified elements.
    """

    def __init__(self) -> None:
        self._mapper = IfcElementMapper()

    def compare(
        self,
        old_elements: list[Any],
        new_elements: list[Any],
    ) -> IfcDiffResult:
        """Compare two element lists and return the differences.

        Each element should have an ``id`` (or ``global_id``) attribute
        and a dict-like set of properties accessible as attributes.

        Args:
            old_elements: The baseline element list.
            new_elements: The updated element list.

        Returns:
            An IfcDiffResult summarizing added, modified, and removed
            entries.
        """
        old_map = self._build_element_map(old_elements)
        new_map = self._build_element_map(new_elements)

        old_ids = set(old_map.keys())
        new_ids = set(new_map.keys())

        added_ids = new_ids - old_ids
        removed_ids = old_ids - new_ids
        common_ids = old_ids & new_ids

        added: list[IfcDiffEntry] = []
        modified: list[IfcDiffEntry] = []
        removed: list[IfcDiffEntry] = []

        for eid in added_ids:
            elem = new_map[eid]
            added.append(
                IfcDiffEntry(
                    global_id=str(eid),
                    entity_type=self._get_type(elem),
                    change_type=IfcChangeType.ADDED,
                    new_properties=self._get_properties(elem),
                )
            )

        for eid in removed_ids:
            elem = old_map[eid]
            removed.append(
                IfcDiffEntry(
                    global_id=str(eid),
                    entity_type=self._get_type(elem),
                    change_type=IfcChangeType.REMOVED,
                    old_properties=self._get_properties(elem),
                )
            )

        for eid in common_ids:
            old_elem = old_map[eid]
            new_elem = new_map[eid]
            old_props = self._get_properties(old_elem)
            new_props = self._get_properties(new_elem)

            changed_fields = [
                k
                for k in set(old_props) | set(new_props)
                if old_props.get(k) != new_props.get(k)
            ]

            if changed_fields:
                modified.append(
                    IfcDiffEntry(
                        global_id=str(eid),
                        entity_type=self._get_type(new_elem),
                        change_type=IfcChangeType.MODIFIED,
                        old_properties=old_props,
                        new_properties=new_props,
                        changed_fields=sorted(changed_fields),
                    )
                )

        result = IfcDiffResult(
            added=added,
            modified=modified,
            removed=removed,
            summary={
                "added": len(added),
                "modified": len(modified),
                "removed": len(removed),
            },
        )

        logger.info(
            "Diff result: {} added, {} modified, {} removed",
            len(added),
            len(modified),
            len(removed),
        )
        return result

    def compare_files(
        self,
        old_path: str | Path,
        new_path: str | Path,
    ) -> IfcDiffResult:
        """Compare two IFC files and return the differences.

        Both files are imported via :class:`IfcElementMapper` and then
        compared at the property level.

        Args:
            old_path: Path to the baseline IFC file.
            new_path: Path to the updated IFC file.

        Returns:
            An IfcDiffResult.

        Raises:
            ImportError: If ifcopenshell is not installed.
            IfcImportError: If a file cannot be read.
        """
        require_ifcopenshell()

        from .importer import IfcImporter

        importer = IfcImporter(mapper=self._mapper)
        old_elements = importer.import_file(old_path)
        new_elements = importer.import_file(new_path)

        return self.compare(old_elements, new_elements)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_element_map(elements: list[Any]) -> dict[str, Any]:
        """Build a lookup dict keyed by element ID."""
        result: dict[str, Any] = {}
        for elem in elements:
            if isinstance(elem, dict):
                eid = elem.get("global_id") or elem.get("id") or id(elem)
            else:
                eid = (
                    getattr(elem, "global_id", None)
                    or getattr(elem, "id", None)
                    or id(elem)
                )
            result[str(eid)] = elem
        return result

    @staticmethod
    def _get_type(element: Any) -> str:
        """Get the type string for an element."""
        if isinstance(element, dict):
            return element.get("type", element.get("ifc_type", "Unknown"))
        return getattr(element, "category", None) or type(element).__name__

    @staticmethod
    def _get_properties(element: Any) -> dict[str, Any]:
        """Extract a flat property dict from an element."""
        if isinstance(element, dict):
            return dict(element)

        props: dict[str, Any] = {}
        for attr in (
            "name",
            "category",
            "height",
            "width",
            "length",
            "area",
            "volume",
            "level",
            "material",
        ):
            value = getattr(element, attr, None)
            if value is not None:
                props[attr] = value
        return props
