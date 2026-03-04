"""
Speckle synchronisation engine for RevitPy.

This module orchestrates push, pull, and bidirectional sync operations,
delegating transport to :class:`SpeckleClient` and type conversion to
:class:`SpeckleTypeMapper`.
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from .client import SpeckleClient
from .diff import SpeckleDiff
from .exceptions import SpeckleSyncError
from .mapper import SpeckleTypeMapper
from .types import SyncDirection, SyncMode, SyncResult


class SpeckleSync:
    """High-level synchronisation between RevitPy and Speckle.

    Args:
        client: An initialised :class:`SpeckleClient`.
        mapper: Optional type mapper; a default one is created when
            ``None``.
        change_tracker: Optional change tracker for incremental sync.
    """

    def __init__(
        self,
        client: SpeckleClient,
        mapper: SpeckleTypeMapper | None = None,
        change_tracker: Any | None = None,
    ) -> None:
        self._client = client
        self._mapper = mapper or SpeckleTypeMapper()
        self._change_tracker = change_tracker
        self._diff = SpeckleDiff()

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------

    async def push(
        self,
        elements: list[Any],
        stream_id: str,
        branch: str = "main",
        message: str = "",
    ) -> SyncResult:
        """Push local elements to a Speckle stream.

        Each element is mapped to a Speckle-compatible dict via the
        mapper, then sent through the client.

        Args:
            elements: List of RevitPy element objects.
            stream_id: Target Speckle stream identifier.
            branch: Target branch name.
            message: Commit message.

        Returns:
            A :class:`SyncResult` summarising the operation.
        """
        start = time.monotonic()
        errors: list[str] = []
        mapped_objects: list[dict[str, Any]] = []

        for element in elements:
            try:
                obj = self._mapper.to_speckle(element)
                mapped_objects.append(obj)
            except Exception as exc:
                errors.append(f"Failed to map {type(element).__name__}: {exc}")

        commit_id: str | None = None
        if mapped_objects:
            try:
                commit = await self._client.send_objects(
                    stream_id,
                    mapped_objects,
                    branch=branch,
                    message=message,
                )
                commit_id = commit.id
            except SpeckleSyncError as exc:
                errors.append(str(exc))

        duration = (time.monotonic() - start) * 1000
        logger.info(
            "Push complete: {} objects sent, {} errors, {:.1f}ms",
            len(mapped_objects),
            len(errors),
            duration,
        )

        return SyncResult(
            direction=SyncDirection.PUSH,
            objects_sent=len(mapped_objects),
            errors=errors,
            commit_id=commit_id,
            duration_ms=duration,
        )

    # ------------------------------------------------------------------
    # Pull
    # ------------------------------------------------------------------

    async def pull(
        self,
        stream_id: str,
        branch: str = "main",
        commit_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Pull objects from a Speckle stream and map them back.

        Args:
            stream_id: Source Speckle stream identifier.
            branch: Branch name.
            commit_id: Optional specific commit to pull.

        Returns:
            List of RevitPy-compatible element dicts.
        """
        raw_objects = await self._client.receive_objects(
            stream_id,
            commit_id=commit_id,
            branch=branch,
        )

        mapped: list[dict[str, Any]] = []
        for obj in raw_objects:
            try:
                element = self._mapper.from_speckle(obj)
                mapped.append(element)
            except Exception as exc:
                logger.warning("Skipping unmapped object: {}", exc)

        logger.info(
            "Pull complete: {} objects received, {} mapped",
            len(raw_objects),
            len(mapped),
        )
        return mapped

    # ------------------------------------------------------------------
    # Bidirectional sync
    # ------------------------------------------------------------------

    async def sync(
        self,
        elements: list[Any],
        stream_id: str,
        mode: SyncMode = SyncMode.INCREMENTAL,
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
    ) -> SyncResult:
        """Run a synchronisation operation.

        For ``PUSH`` direction only elements are sent.  For ``PULL``
        direction only objects are received.  For ``BIDIRECTIONAL``
        mode both operations are performed.

        Args:
            elements: Local RevitPy elements.
            stream_id: Speckle stream identifier.
            mode: Sync strategy (full / incremental / selective).
            direction: Direction of the sync.

        Returns:
            A :class:`SyncResult` summarising the operation.
        """
        start = time.monotonic()
        errors: list[str] = []
        objects_sent = 0
        objects_received = 0
        commit_id: str | None = None

        sync_elements = elements
        if mode == SyncMode.INCREMENTAL and self._change_tracker:
            sync_elements = [e for e in elements if self._change_tracker.is_changed(e)]

        if direction in (
            SyncDirection.PUSH,
            SyncDirection.BIDIRECTIONAL,
        ):
            push_result = await self.push(sync_elements, stream_id)
            objects_sent = push_result.objects_sent
            errors.extend(push_result.errors)
            commit_id = push_result.commit_id

        if direction in (
            SyncDirection.PULL,
            SyncDirection.BIDIRECTIONAL,
        ):
            pulled = await self.pull(stream_id)
            objects_received = len(pulled)

        duration = (time.monotonic() - start) * 1000
        return SyncResult(
            direction=direction,
            objects_sent=objects_sent,
            objects_received=objects_received,
            errors=errors,
            commit_id=commit_id,
            duration_ms=duration,
        )
