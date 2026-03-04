"""
RevitPy IFC Layer - IFC export/import, IDS validation, BCF, and model diffing.

This module provides comprehensive IFC (Industry Foundation Classes)
support for RevitPy, including:

- Bidirectional element mapping between RevitPy and IFC types
- IFC export with configurable schema versions (IFC2X3, IFC4, IFC4X3)
- IFC import with property mapping
- IDS (Information Delivery Specification) validation
- BCF (BIM Collaboration Format) issue management
- Model diffing between two IFC states

Usage:
    from revitpy.ifc import IfcExporter, IfcImporter, ifc_available

    if ifc_available():
        exporter = IfcExporter()
        exporter.export(elements, "output.ifc")
    else:
        print("Install ifcopenshell for IFC support")
"""

from ._compat import _HAS_IFCOPENSHELL
from .bcf import BcfManager
from .diff import IfcDiff
from .exceptions import (
    BcfError,
    IdsValidationError,
    IfcError,
    IfcExportError,
    IfcImportError,
    IfcValidationError,
)
from .exporter import IfcExporter
from .importer import IfcImporter
from .mapper import IfcElementMapper
from .types import (
    BcfComment,
    BcfIssue,
    IdsRequirement,
    IdsValidationResult,
    IfcChangeType,
    IfcDiffEntry,
    IfcDiffResult,
    IfcExportConfig,
    IfcImportConfig,
    IfcMapping,
    IfcVersion,
)
from .validator import IdsValidator


def ifc_available() -> bool:
    """Return True if ifcopenshell is installed and available."""
    return _HAS_IFCOPENSHELL


__all__ = [
    # Availability check
    "ifc_available",
    # Core classes
    "IfcElementMapper",
    "IfcExporter",
    "IfcImporter",
    "IdsValidator",
    "BcfManager",
    "IfcDiff",
    # Configuration
    "IfcExportConfig",
    "IfcImportConfig",
    "IfcMapping",
    # Types and enums
    "IfcVersion",
    "IfcChangeType",
    "IdsRequirement",
    "IdsValidationResult",
    "BcfIssue",
    "BcfComment",
    "IfcDiffEntry",
    "IfcDiffResult",
    # Exceptions
    "IfcError",
    "IfcExportError",
    "IfcImportError",
    "IfcValidationError",
    "IdsValidationError",
    "BcfError",
]
