"""
RevitPy Interop Layer - Speckle integration for BIM collaboration.

This module provides bidirectional synchronisation between RevitPy and
Speckle, including type mapping, diffing, merging, and real-time
subscriptions.

Key Features:
- Bidirectional type mapping (RevitPy <-> Speckle)
- Push / pull / bidirectional synchronisation via the specklepy SDK
  (Projects / Models / Versions)
- Property-level diffing and conflict resolution
- Real-time version subscriptions via WebSocket

Speckle network operations require the optional ``specklepy`` package
(``pip install revitpy[interop]``).  Type mapping, diffing and merging
work without it, and this package always imports.

Usage:
    from revitpy.interop import push_to_speckle, pull_from_speckle

    result = await push_to_speckle(elements, project_id="abc123", model="main")
    elements = await pull_from_speckle(project_id="abc123", model="main")
"""

from ._compat import _HAS_SPECKLEPY
from .client import SpeckleClient
from .diff import SpeckleDiff
from .exceptions import (
    InteropError,
    MergeConflictError,
    SpeckleConnectionError,
    SpeckleSyncError,
    TypeMappingError,
)
from .mapper import SpeckleTypeMapper
from .merge import SpeckleMerge
from .subscriptions import SpeckleSubscriptions
from .sync import SpeckleSync
from .types import (
    ConflictResolution,
    DiffEntry,
    MappingStatus,
    MergeResult,
    SpeckleCommit,
    SpeckleConfig,
    SpeckleVersion,
    SyncDirection,
    SyncMode,
    SyncResult,
    TypeMapping,
)

__all__ = [
    # Core classes
    "SpeckleClient",
    "SpeckleTypeMapper",
    "SpeckleSync",
    "SpeckleDiff",
    "SpeckleMerge",
    "SpeckleSubscriptions",
    # Types and enums
    "SyncDirection",
    "SyncMode",
    "ConflictResolution",
    "MappingStatus",
    # Dataclasses
    "SpeckleConfig",
    "SpeckleCommit",
    "SpeckleVersion",
    "TypeMapping",
    "SyncResult",
    "DiffEntry",
    "MergeResult",
    # Exceptions
    "InteropError",
    "SpeckleConnectionError",
    "SpeckleSyncError",
    "TypeMappingError",
    "MergeConflictError",
    # Convenience functions
    "push_to_speckle",
    "pull_from_speckle",
    "sync",
    "speckle_available",
]


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def speckle_available() -> bool:
    """Return whether the optional specklepy package is installed."""
    return _HAS_SPECKLEPY


async def push_to_speckle(
    elements: list,
    project_id: str | None = None,
    model: str = "main",
    message: str = "",
    config: SpeckleConfig | None = None,
    *,
    stream_id: str | None = None,
    branch: str | None = None,
) -> SyncResult:
    """Push elements to a Speckle model as a new version.

    Convenience wrapper around :class:`SpeckleSync.push`.

    Args:
        elements: List of RevitPy element objects.
        project_id: Target Speckle project identifier.
        model: Target model name or id.
        message: Version message.
        config: Optional Speckle server configuration.
        stream_id: Deprecated alias of ``project_id``.
        branch: Deprecated alias of ``model``.

    Returns:
        A :class:`SyncResult` summarising the operation.
    """
    client = SpeckleClient(config=config)
    syncer = SpeckleSync(client=client)
    try:
        return await syncer.push(
            elements,
            project_id,
            model=model,
            message=message,
            stream_id=stream_id,
            branch=branch,
        )
    finally:
        await client.close()


async def pull_from_speckle(
    project_id: str | None = None,
    model: str = "main",
    version_id: str | None = None,
    config: SpeckleConfig | None = None,
    *,
    stream_id: str | None = None,
    branch: str | None = None,
    commit_id: str | None = None,
) -> list[dict]:
    """Pull objects from a Speckle model version.

    Convenience wrapper around :class:`SpeckleSync.pull`.

    Args:
        project_id: Source Speckle project identifier.
        model: Model name or id.
        version_id: Optional specific version to pull (latest if omitted).
        config: Optional Speckle server configuration.
        stream_id: Deprecated alias of ``project_id``.
        branch: Deprecated alias of ``model``.
        commit_id: Deprecated alias of ``version_id``.

    Returns:
        List of RevitPy-compatible element dicts.
    """
    client = SpeckleClient(config=config)
    syncer = SpeckleSync(client=client)
    try:
        return await syncer.pull(
            project_id,
            model=model,
            version_id=version_id,
            stream_id=stream_id,
            branch=branch,
            commit_id=commit_id,
        )
    finally:
        await client.close()


async def sync(
    elements: list,
    project_id: str | None = None,
    mode: SyncMode = SyncMode.INCREMENTAL,
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
    config: SpeckleConfig | None = None,
    *,
    model: str = "main",
    stream_id: str | None = None,
) -> SyncResult:
    """Run a full sync operation.

    Convenience wrapper around :class:`SpeckleSync.sync`.

    Args:
        elements: Local RevitPy elements.
        project_id: Speckle project identifier.
        mode: Sync strategy.
        direction: Direction of the sync.
        config: Optional Speckle server configuration.
        model: Model name or id.
        stream_id: Deprecated alias of ``project_id``.

    Returns:
        A :class:`SyncResult` summarising the operation.
    """
    client = SpeckleClient(config=config)
    syncer = SpeckleSync(client=client)
    try:
        return await syncer.sync(
            elements,
            project_id,
            mode=mode,
            direction=direction,
            model=model,
            stream_id=stream_id,
        )
    finally:
        await client.close()
