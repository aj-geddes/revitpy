"""
Type definitions, enums, and dataclasses for the RevitPy interop layer.

This module provides all type definitions used throughout the interop system
for Speckle integration, type mapping, synchronisation, diffing, and merging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SyncDirection(Enum):
    """Direction of a synchronisation operation."""

    PUSH = "push"
    PULL = "pull"
    BIDIRECTIONAL = "bidirectional"


class SyncMode(Enum):
    """Strategy for selecting objects to synchronise."""

    FULL = "full"
    INCREMENTAL = "incremental"
    SELECTIVE = "selective"


class ConflictResolution(Enum):
    """Strategy for resolving merge conflicts."""

    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    MANUAL = "manual"


class MappingStatus(Enum):
    """Status of a type mapping between systems."""

    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class SpeckleConfig:
    """Configuration for connecting to a Speckle server."""

    server_url: str = "https://app.speckle.systems"
    token: str | None = None
    default_stream: str | None = None


@dataclass
class SpeckleCommit:
    """Represents a single Speckle commit."""

    id: str
    message: str
    author: str
    created_at: str
    source_application: str = "revitpy"
    total_objects: int = 0


@dataclass
class TypeMapping:
    """Mapping between a RevitPy type and a Speckle type."""

    revitpy_type: str
    speckle_type: str
    property_map: dict[str, str] = field(default_factory=dict)
    status: MappingStatus = MappingStatus.MAPPED


@dataclass
class SyncResult:
    """Result of a synchronisation operation."""

    direction: SyncDirection
    objects_sent: int = 0
    objects_received: int = 0
    errors: list[str] = field(default_factory=list)
    commit_id: str | None = None
    duration_ms: float = 0.0


@dataclass
class DiffEntry:
    """A single difference between local and remote element states."""

    element_id: str
    change_type: str
    property_name: str | None = None
    local_value: Any = None
    remote_value: Any = None


@dataclass
class MergeResult:
    """Result of merging local and remote element sets."""

    merged_count: int = 0
    conflict_count: int = 0
    conflicts: list[DiffEntry] = field(default_factory=list)
    resolution: ConflictResolution = ConflictResolution.LOCAL_WINS
