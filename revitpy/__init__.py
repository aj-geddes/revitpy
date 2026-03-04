"""
RevitPy: Modern Python Framework for Revit Development

A complete Python framework that brings modern capabilities to Revit development,
featuring async/await support, event systems, comprehensive testing, quantity
extraction, IFC interoperability, AI agent integration, sustainability analytics,
Speckle connectivity, and cloud automation.
"""

__version__ = "0.1.0"
__author__ = "RevitPy Team"

from .ai import McpServer, PromptLibrary, RevitTools, SafetyGuard
from .api import Element, RevitAPI, Transaction
from .async_support import AsyncRevit, async_transaction
from .cloud import ApsClient, BatchProcessor, JobManager
from .config import Config, ConfigManager
from .events import EventManager, event_handler
from .extensions import Extension, ExtensionManager
from .extract import CostEstimator, DataExporter, MaterialTakeoff, QuantityExtractor
from .orm import ElementSet, QueryBuilder
from .sustainability import CarbonCalculator, ComplianceChecker, EpdDatabase
from .testing import MockRevit

# IFC (optional dependency: ifcopenshell)
try:
    from .ifc import IfcElementMapper, IfcExporter, IfcImporter
except ImportError:
    pass

# Speckle Interop (optional dependency: specklepy)
try:
    from .interop import SpeckleClient, SpeckleSync, SpeckleTypeMapper
except ImportError:
    pass

# Core framework components
__all__ = [
    # API Wrapper
    "RevitAPI",
    "Element",
    "Transaction",
    # Async Support
    "AsyncRevit",
    "async_transaction",
    # Event System
    "EventManager",
    "event_handler",
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
    # IFC (optional)
    "IfcExporter",
    "IfcImporter",
    "IfcElementMapper",
    # AI & MCP Server
    "McpServer",
    "RevitTools",
    "SafetyGuard",
    "PromptLibrary",
    # Sustainability & Carbon Analytics
    "CarbonCalculator",
    "ComplianceChecker",
    "EpdDatabase",
    # Speckle Interop (optional)
    "SpeckleSync",
    "SpeckleClient",
    "SpeckleTypeMapper",
    # Cloud & Design Automation
    "JobManager",
    "BatchProcessor",
    "ApsClient",
]
