"""
Type definitions, enums, and dataclasses for the RevitPy IFC layer.

This module provides all type definitions used throughout the IFC system
for IFC export/import, IDS validation, BCF collaboration, and model diffing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class IfcVersion(Enum):
    """Supported IFC schema versions."""

    IFC2X3 = "IFC2X3"
    IFC4 = "IFC4"
    IFC4X3 = "IFC4X3"


class IfcChangeType(Enum):
    """Types of changes detected during IFC model comparison."""

    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"


@dataclass
class IfcExportConfig:
    """Configuration for IFC export operations."""

    version: IfcVersion = IfcVersion.IFC4
    include_quantities: bool = True
    include_materials: bool = True
    site_name: str = "Default Site"
    building_name: str = "Default Building"
    author: str = ""


@dataclass
class IfcImportConfig:
    """Configuration for IFC import operations."""

    merge_strategy: str = "replace"
    update_existing: bool = True
    create_new: bool = True
    property_mapping: dict[str, str] = field(default_factory=dict)


@dataclass
class IfcMapping:
    """Mapping between a RevitPy type and an IFC entity type."""

    revitpy_type: str
    ifc_entity_type: str
    property_map: dict[str, str] = field(default_factory=dict)
    bidirectional: bool = True


@dataclass
class IdsRequirement:
    """A single IDS (Information Delivery Specification) requirement."""

    name: str
    description: str = ""
    entity_type: str | None = None
    property_name: str | None = None
    property_value: str | None = None
    required: bool = True


@dataclass
class IdsValidationResult:
    """Result of validating an element against an IDS requirement."""

    requirement: IdsRequirement
    passed: bool
    entity_id: Any | None = None
    actual_value: Any | None = None
    message: str = ""


@dataclass
class BcfIssue:
    """A single BCF (BIM Collaboration Format) issue."""

    guid: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    author: str = ""
    creation_date: datetime = field(default_factory=datetime.now)
    status: str = "Open"
    assigned_to: str = ""
    element_ids: list[str] = field(default_factory=list)


@dataclass
class BcfComment:
    """A comment on a BCF issue."""

    text: str = ""
    author: str = ""
    date: datetime = field(default_factory=datetime.now)
    viewpoint_guid: str | None = None


@dataclass
class IfcDiffEntry:
    """A single difference entry between two IFC model states."""

    global_id: str
    entity_type: str
    change_type: IfcChangeType
    old_properties: dict[str, Any] = field(default_factory=dict)
    new_properties: dict[str, Any] = field(default_factory=dict)
    changed_fields: list[str] = field(default_factory=list)


@dataclass
class IfcDiffResult:
    """Result of comparing two IFC model states."""

    added: list[IfcDiffEntry] = field(default_factory=list)
    modified: list[IfcDiffEntry] = field(default_factory=list)
    removed: list[IfcDiffEntry] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.summary:
            self.summary = {
                "added": len(self.added),
                "modified": len(self.modified),
                "removed": len(self.removed),
            }
