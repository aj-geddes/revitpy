"""
Extension framework with dependency injection and lifecycle management.
"""

from .extension import Extension, ExtensionMetadata, ExtensionStatus
from .manager import ExtensionManager
from .loader import ExtensionLoader
from .dependency_injection import DIContainer, Injectable, inject, singleton, transient, scoped
from .lifecycle import LifecycleManager, LifecycleStage
from .registry import ExtensionRegistry
from .decorators import extension, command, service, tool, analyzer

__all__ = [
    'Extension',
    'ExtensionMetadata', 
    'ExtensionStatus',
    'ExtensionManager',
    'ExtensionLoader',
    'DIContainer',
    'Injectable',
    'inject',
    'singleton',
    'transient',
    'scoped',
    'LifecycleManager',
    'LifecycleStage',
    'ExtensionRegistry',
    'extension',
    'command',
    'service',
    'tool',
    'analyzer',
]