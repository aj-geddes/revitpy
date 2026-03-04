"""
Merge engine for RevitPy interop.

This module resolves differences between local and remote element sets
according to a configurable conflict resolution strategy.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .diff import SpeckleDiff
from .exceptions import MergeConflictError
from .types import ConflictResolution, DiffEntry, MergeResult


class SpeckleMerge:
    """Merges local and remote element sets.

    Args:
        resolution: Default conflict resolution strategy.
    """

    def __init__(
        self,
        resolution: ConflictResolution = ConflictResolution.LOCAL_WINS,
    ) -> None:
        self._resolution = resolution
        self._diff = SpeckleDiff()

    def merge(
        self,
        local_elements: list[dict[str, Any]],
        remote_elements: list[dict[str, Any]],
        diff_entries: list[DiffEntry] | None = None,
    ) -> MergeResult:
        """Merge local and remote elements according to the strategy.

        When ``diff_entries`` is ``None`` the diff is computed
        automatically.

        Args:
            local_elements: Element dicts from the local model.
            remote_elements: Element dicts from the remote stream.
            diff_entries: Optional pre-computed diff entries.

        Returns:
            A :class:`MergeResult` describing the outcome.

        Raises:
            MergeConflictError: When using ``MANUAL`` resolution and
                unresolved conflicts remain.
        """
        if diff_entries is None:
            diff_entries = self._diff.compare(local_elements, remote_elements)

        conflicts = [e for e in diff_entries if e.change_type == "modified"]

        if self._resolution == ConflictResolution.MANUAL and conflicts:
            ids = list({c.element_id for c in conflicts})
            raise MergeConflictError(
                f"Manual resolution required for {len(conflicts)} conflict(s)",
                element_id=ids[0] if len(ids) == 1 else None,
                conflicts=[f"{c.element_id}.{c.property_name}" for c in conflicts],
            )

        # Count non-conflict entries as merged
        merged_count = sum(
            1 for e in diff_entries if e.change_type in ("added", "removed")
        )

        # Auto-resolve conflicts per strategy
        if conflicts and self._resolution != ConflictResolution.MANUAL:
            merged_count += len(conflicts)

        logger.info(
            "Merge complete: {} merged, {} conflicts (strategy={})",
            merged_count,
            len(conflicts),
            self._resolution.value,
        )

        return MergeResult(
            merged_count=merged_count,
            conflict_count=len(conflicts),
            conflicts=conflicts,
            resolution=self._resolution,
        )

    def resolve_conflicts(
        self,
        conflicts: list[DiffEntry],
        strategy: ConflictResolution,
    ) -> list[dict[str, Any]]:
        """Resolve a list of conflict entries using the given strategy.

        For ``LOCAL_WINS`` the local value is kept.  For
        ``REMOTE_WINS`` the remote value is used.  For ``MANUAL``
        an error is raised.

        Args:
            conflicts: List of conflict :class:`DiffEntry` instances.
            strategy: Resolution strategy to apply.

        Returns:
            List of resolved property dicts.

        Raises:
            MergeConflictError: When ``MANUAL`` is specified as
                the strategy.
        """
        if strategy == ConflictResolution.MANUAL:
            raise MergeConflictError(
                "Cannot auto-resolve with MANUAL strategy",
                conflicts=[f"{c.element_id}.{c.property_name}" for c in conflicts],
            )

        resolved: list[dict[str, Any]] = []
        for conflict in conflicts:
            if strategy == ConflictResolution.LOCAL_WINS:
                value = conflict.local_value
            else:
                value = conflict.remote_value

            resolved.append(
                {
                    "element_id": conflict.element_id,
                    "property_name": conflict.property_name,
                    "resolved_value": value,
                }
            )

        logger.debug(
            "Resolved {} conflicts with strategy {}",
            len(resolved),
            strategy.value,
        )
        return resolved
