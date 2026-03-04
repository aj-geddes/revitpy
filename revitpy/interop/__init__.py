"""
RevitPy Interop Layer - Speckle integration for BIM collaboration.

This module provides bidirectional synchronisation between RevitPy and
Speckle, including type mapping, diffing, merging, and real-time
subscriptions.

Key Features:
- Bidirectional type mapping (RevitPy <-> Speckle)
- Push / pull / bidirectional synchronisation
- Property-level diffing and conflict resolution
- Real-time commit subscriptions via WebSocket
- Optional specklepy enhancement (works without it)

Usage:
    from revitpy.interop import push_to_speckle, pull_from_speckle

    result = await push_to_speckle(elements, stream_id="abc123")
    elements = await pull_from_speckle(stream_id="abc123")
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
    stream_id: str,
    branch: str = "main",
    message: str = "",
    config: SpeckleConfig | None = None,
) -> SyncResult:
    """Push elements to a Speckle stream.

    Convenience wrapper around :class:`SpeckleSync.push`.

    Args:
        elements: List of RevitPy element objects.
        stream_id: Target Speckle stream identifier.
        branch: Target branch name.
        message: Commit message.
        config: Optional Speckle server configuration.

    Returns:
        A :class:`SyncResult` summarising the operation.
    """
    client = SpeckleClient(config=config)
    syncer = SpeckleSync(client=client)
    try:
        return await syncer.push(elements, stream_id, branch=branch, message=message)
    finally:
        await client.close()


async def pull_from_speckle(
    stream_id: str,
    branch: str = "main",
    commit_id: str | None = None,
    config: SpeckleConfig | None = None,
) -> list[dict]:
    """Pull objects from a Speckle stream.

    Convenience wrapper around :class:`SpeckleSync.pull`.

    Args:
        stream_id: Source Speckle stream identifier.
        branch: Branch name.
        commit_id: Optional specific commit to pull.
        config: Optional Speckle server configuration.

    Returns:
        List of RevitPy-compatible element dicts.
    """
    client = SpeckleClient(config=config)
    syncer = SpeckleSync(client=client)
    try:
        return await syncer.pull(stream_id, branch=branch, commit_id=commit_id)
    finally:
        await client.close()


async def sync(
    elements: list,
    stream_id: str,
    mode: SyncMode = SyncMode.INCREMENTAL,
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
    config: SpeckleConfig | None = None,
) -> SyncResult:
    """Run a full sync operation.

    Convenience wrapper around :class:`SpeckleSync.sync`.

    Args:
        elements: Local RevitPy elements.
        stream_id: Speckle stream identifier.
        mode: Sync strategy.
        direction: Direction of the sync.
        config: Optional Speckle server configuration.

    Returns:
        A :class:`SyncResult` summarising the operation.
    """
    client = SpeckleClient(config=config)
    syncer = SpeckleSync(client=client)
    try:
        return await syncer.sync(elements, stream_id, mode=mode, direction=direction)
    finally:
        await client.close()
