"""
Extension framework with dependency injection and lifecycle management.
"""

from .decorators import analyzer, command, extension, service, tool
from .dependency_injection import (
    DIContainer,
    Injectable,
    inject,
    scoped,
    singleton,
    transient,
)
from .extension import Extension, ExtensionMetadata, ExtensionStatus
from .lifecycle import LifecycleManager, LifecycleStage
from .loader import ExtensionLoader
from .manager import ExtensionManager
from .registry import ExtensionRegistry

__all__ = [
    "Extension",
    "ExtensionMetadata",
    "ExtensionStatus",
    "ExtensionManager",
    "ExtensionLoader",
    "DIContainer",
    "Injectable",
    "inject",
    "singleton",
    "transient",
    "scoped",
    "LifecycleManager",
    "LifecycleStage",
    "ExtensionRegistry",
    "extension",
    "command",
    "service",
    "tool",
    "analyzer",
]
