"""
RevitPy: Modern Python Framework for Revit Development

A complete Python framework that brings modern capabilities to Revit development,
featuring async/await support, event systems, and comprehensive testing.
"""

__version__ = "0.1.0"
__author__ = "RevitPy Team"

from .api import RevitAPI, Element, Transaction
from .async_support import AsyncRevit, async_transaction
from .events import EventManager, event_handler
from .extensions import ExtensionManager, Extension
from .testing import MockRevit, RevitTestCase
from .config import Config, ConfigManager
from .orm import Query, ElementSet

# Core framework components
__all__ = [
    # API Wrapper
    'RevitAPI',
    'Element',
    'Transaction',
    
    # Async Support
    'AsyncRevit',
    'async_transaction',
    
    # Event System
    'EventManager',
    'event_handler',
    
    # Extensions
    'ExtensionManager',
    'Extension',
    
    # Testing
    'MockRevit',
    'RevitTestCase',
    
    # Configuration
    'Config',
    'ConfigManager',
    
    # ORM
    'Query',
    'ElementSet',
]