"""
RevitPy: Modern Python Framework for Revit Development

A complete Python framework that brings modern capabilities to Revit development,
featuring async/await support, event systems, comprehensive testing, quantity
extraction, IFC interoperability, AI agent integration, sustainability analytics,
Speckle connectivity, and cloud automation.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

try:
    __version__ = _dist_version("revitpy")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.0.0+unknown"
__author__ = "RevitPy Team"

from .ai import McpServer, PromptLibrary, RevitTools, SafetyGuard
from .api import Element, FilterOperator, RevitAPI, Transaction
from .async_support import AsyncRevit, async_transaction
from .cloud import ApsClient, BatchProcessor, JobManager
from .config import Config, ConfigManager
from .events import EventManager, EventPriority, EventType, event_handler
from .extensions import Extension, ExtensionManager
from .extract import CostEstimator, DataExporter, MaterialTakeoff, QuantityExtractor
from .orm import ElementSet, QueryBuilder
from .sustainability import CarbonCalculator, ComplianceChecker, EpdDatabase
from .testing import MockRevit

# IFC (optional dependency: ifcopenshell)
_optional_exports: list[str] = []

try:
    from .ifc import IfcElementMapper, IfcExporter, IfcImporter

    _optional_exports += ["IfcExporter", "IfcImporter", "IfcElementMapper"]
except ImportError:
    pass

# Speckle Interop (optional dependency: specklepy)
try:
    from .interop import SpeckleClient, SpeckleSync, SpeckleTypeMapper

    _optional_exports += ["SpeckleSync", "SpeckleClient", "SpeckleTypeMapper"]
except ImportError:
    pass

# Core framework components
__all__ = [
    # API Wrapper
    "RevitAPI",
    "Element",
    "Transaction",
    "FilterOperator",
    # Async Support
    "AsyncRevit",
    "async_transaction",
    # Event System
    "EventManager",
    "event_handler",
    "EventType",
    "EventPriority",
    # Extensions
    "ExtensionManager",
    "Extension",
    # Testing
    "MockRevit",
    # Configuration
    "Config",
    "ConfigManager",
    # ORM
    "QueryBuilder",
    "ElementSet",
    # Quantity Takeoff & Data Pipeline
    "QuantityExtractor",
    "MaterialTakeoff",
    "CostEstimator",
    "DataExporter",
    # AI & MCP Server
    "McpServer",
    "RevitTools",
    "SafetyGuard",
    "PromptLibrary",
    # Sustainability & Carbon Analytics
    "CarbonCalculator",
    "ComplianceChecker",
    "EpdDatabase",
    # Cloud & Design Automation
    "JobManager",
    "BatchProcessor",
    "ApsClient",
    # IFC / Speckle interop, when their optional dependencies are installed
    *_optional_exports,
]
