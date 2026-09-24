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

from ._compat import resolve_renamed
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

    def _default_project(self) -> str | None:
        """Return the configured default project (if any)."""
        config = getattr(self._client, "config", None)
        if config is None:
            return None
        return config.default_project or config.default_stream

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------

    async def push(
        self,
        elements: list[Any],
        project_id: str | None = None,
        model: str = "main",
        message: str = "",
        *,
        stream_id: str | None = None,
        branch: str | None = None,
    ) -> SyncResult:
        """Push local elements to a Speckle model as a new version.

        Each element is mapped to a Speckle-compatible dict via the
        mapper, then uploaded through the client.

        Args:
            elements: List of RevitPy element objects.
            project_id: Target Speckle project identifier.
            model: Target model name or id.
            message: Version message.
            stream_id: Deprecated alias of ``project_id``.
            branch: Deprecated alias of ``model``.

        Returns:
            A :class:`SyncResult` summarising the operation.
            ``commit_id`` / ``version_id`` hold the created version id
            and ``object_id`` the uploaded root object hash.
        """
        project_id = resolve_renamed(
            project_id,
            stream_id,
            new_name="project_id",
            old_name="stream_id",
            default=self._default_project(),
        )
        if branch is not None:
            model = resolve_renamed(
                None if model == "main" else model,
                branch,
                new_name="model",
                old_name="branch",
            )
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
        object_id: str | None = None
        if mapped_objects:
            try:
                commit = await self._client.send_objects(
                    project_id,
                    mapped_objects,
                    model=model,
                    message=message,
                )
                commit_id = commit.id
                object_id = commit.referenced_object
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
            object_id=object_id,
        )

    # ------------------------------------------------------------------
    # Pull
    # ------------------------------------------------------------------

    async def pull(
        self,
        project_id: str | None = None,
        model: str = "main",
        version_id: str | None = None,
        *,
        stream_id: str | None = None,
        branch: str | None = None,
        commit_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Pull objects from a Speckle model version and map them back.

        Args:
            project_id: Source Speckle project identifier.
            model: Model name or id (latest version is used when
                ``version_id`` is ``None``).
            version_id: Optional specific version to pull.
            stream_id: Deprecated alias of ``project_id``.
            branch: Deprecated alias of ``model``.
            commit_id: Deprecated alias of ``version_id``.

        Returns:
            List of RevitPy-compatible element dicts.
        """
        project_id = resolve_renamed(
            project_id,
            stream_id,
            new_name="project_id",
            old_name="stream_id",
            default=self._default_project(),
        )
        if branch is not None:
            model = resolve_renamed(
                None if model == "main" else model,
                branch,
                new_name="model",
                old_name="branch",
            )
        if commit_id is not None:
            version_id = resolve_renamed(
                version_id, commit_id, new_name="version_id", old_name="commit_id"
            )
        raw_objects = await self._client.receive_objects(
            project_id,
            version_id=version_id,
            model=model,
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
        project_id: str | None = None,
        mode: SyncMode = SyncMode.INCREMENTAL,
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
        *,
        model: str = "main",
        stream_id: str | None = None,
    ) -> SyncResult:
        """Run a synchronisation operation.

        For ``PUSH`` direction only elements are sent.  For ``PULL``
        direction only objects are received.  For ``BIDIRECTIONAL``
        mode both operations are performed.

        Args:
            elements: Local RevitPy elements.
            project_id: Speckle project identifier.
            mode: Sync strategy (full / incremental / selective).
            direction: Direction of the sync.
            model: Model name or id.
            stream_id: Deprecated alias of ``project_id``.

        Returns:
            A :class:`SyncResult` summarising the operation.
        """
        project_id = resolve_renamed(
            project_id,
            stream_id,
            new_name="project_id",
            old_name="stream_id",
            default=self._default_project(),
        )
        start = time.monotonic()
        errors: list[str] = []
        objects_sent = 0
        objects_received = 0
        commit_id: str | None = None
        object_id: str | None = None

        sync_elements = elements
        if mode == SyncMode.INCREMENTAL and self._change_tracker:
            sync_elements = [e for e in elements if self._change_tracker.is_changed(e)]

        if direction in (
            SyncDirection.PUSH,
            SyncDirection.BIDIRECTIONAL,
        ):
            push_result = await self.push(sync_elements, project_id, model=model)
            objects_sent = push_result.objects_sent
            errors.extend(push_result.errors)
            commit_id = push_result.commit_id
            object_id = push_result.object_id

        if direction in (
            SyncDirection.PULL,
            SyncDirection.BIDIRECTIONAL,
        ):
            pulled = await self.pull(project_id, model=model)
            objects_received = len(pulled)

        duration = (time.monotonic() - start) * 1000
        return SyncResult(
            direction=direction,
            objects_sent=objects_sent,
            objects_received=objects_received,
            errors=errors,
            commit_id=commit_id,
            duration_ms=duration,
            object_id=object_id,
        )
