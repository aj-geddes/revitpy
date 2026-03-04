"""
Element diff engine for RevitPy interop.

This module compares local and remote element sets, producing a list
of :class:`DiffEntry` records that describe additions, modifications,
and removals at the property level.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .types import DiffEntry


class SpeckleDiff:
    """Compares local and remote element sets to produce diff entries.

    Elements are matched by their ``id`` key (or ``element_id``).
    Properties are compared to detect modifications.
    """

    def __init__(self) -> None:
        self._ignored_keys: set[str] = {
            "speckle_type",
            "revitpy_type",
            "type",
        }

    @staticmethod
    def _element_id(element: dict[str, Any]) -> str | None:
        """Extract the canonical element id from a dict."""
        return (
            str(
                element.get("id")
                or element.get("element_id")
                or element.get("Id")
                or ""
            )
            or None
        )

    def compare(
        self,
        local_elements: list[dict[str, Any]],
        remote_elements: list[dict[str, Any]],
    ) -> list[DiffEntry]:
        """Compare local and remote element dicts and return diffs.

        Args:
            local_elements: Element dicts from the local model.
            remote_elements: Element dicts from the remote stream.

        Returns:
            List of :class:`DiffEntry` describing every change.
        """
        local_map: dict[str, dict[str, Any]] = {}
        for elem in local_elements:
            eid = self._element_id(elem)
            if eid:
                local_map[eid] = elem

        remote_map: dict[str, dict[str, Any]] = {}
        for elem in remote_elements:
            eid = self._element_id(elem)
            if eid:
                remote_map[eid] = elem

        entries: list[DiffEntry] = []

        # Added (in local, not in remote)
        for eid, elem in local_map.items():
            if eid not in remote_map:
                entries.append(
                    DiffEntry(
                        element_id=eid,
                        change_type="added",
                    )
                )

        # Removed (in remote, not in local)
        for eid in remote_map:
            if eid not in local_map:
                entries.append(
                    DiffEntry(
                        element_id=eid,
                        change_type="removed",
                    )
                )

        # Modified (in both, with property differences)
        for eid in local_map:
            if eid not in remote_map:
                continue

            local_elem = local_map[eid]
            remote_elem = remote_map[eid]

            all_keys = (
                set(local_elem.keys()) | set(remote_elem.keys())
            ) - self._ignored_keys

            for key in sorted(all_keys):
                local_val = local_elem.get(key)
                remote_val = remote_elem.get(key)
                if local_val != remote_val:
                    entries.append(
                        DiffEntry(
                            element_id=eid,
                            change_type="modified",
                            property_name=key,
                            local_value=local_val,
                            remote_value=remote_val,
                        )
                    )

        logger.debug(
            "Diff complete: {} entries ({} added, {} removed, {} modified)",
            len(entries),
            sum(1 for e in entries if e.change_type == "added"),
            sum(1 for e in entries if e.change_type == "removed"),
            sum(1 for e in entries if e.change_type == "modified"),
        )
        return entries

    def has_changes(
        self,
        local_elements: list[dict[str, Any]],
        remote_elements: list[dict[str, Any]],
    ) -> bool:
        """Return whether any differences exist between the two sets.

        This is a convenience shortcut that avoids materialising the
        full diff list when only a boolean answer is needed.

        Args:
            local_elements: Element dicts from the local model.
            remote_elements: Element dicts from the remote stream.

        Returns:
            ``True`` if there is at least one difference.
        """
        return len(self.compare(local_elements, remote_elements)) > 0
