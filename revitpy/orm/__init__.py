"""
RevitPy ORM Layer - High-level Pythonic interface to Revit elements and operations.

This module provides a comprehensive ORM (Object-Relational Mapping) layer for Revit,
offering LINQ-style querying, relationship mapping, change tracking, caching, and
async support for high-performance Revit development.

Key Features:
- LINQ-style fluent queries (``where``/``order_by``/``take``...) with lazy evaluation
- Change tracking with persistence through a pluggable ``IUnitOfWork``
- Result caching for callable-free query plans
- Async facade (``RevitContext.as_async()``)
- Pydantic v2 element models with validation

Usage:
    from revitpy import RevitAPI
    from revitpy.api import Wall
    from revitpy.orm import RevitContext

    api = RevitAPI()
    api.connect(__revit__)  # or a revitpy.testing.MockApplication

    with RevitContext(api.active_document) as ctx:
        tall = (
            ctx.all(Wall)
            .where(lambda w: w.name.startswith("Ext"))
            .order_by(lambda w: w.name)
            .to_list()
        )
        ctx.update(tall[0], comments="Checked")  # tracked change
        ctx.save_changes()  # registered with the configured IUnitOfWork
"""

from .async_support import AsyncRevitContext, async_batch_operation, async_transaction
from .cache import CacheEntry, CacheKey, CacheManager
from .change_tracker import ChangeSet, ChangeTracker
from .context import RevitContext, create_context
from .decorators import cached, lazy_property, tracked_property
from .element_set import AsyncElementSet, ElementSet
from .exceptions import (
    CacheError,
    ChangeTrackingError,
    ORMException,
    QueryError,
    RelationshipError,
    ValidationError,
)
from .query_builder import LazyQueryExecutor, QueryBuilder
from .relationships import (
    ManyToManyRelationship,
    OneToManyRelationship,
    Relationship,
    RelationshipManager,
)
from .types import (
    BatchOperation,
    CachePolicy,
    ElementFilter,
    ElementState,
    QueryExpression,
    SortCriteria,
)
from .validation import (
    BaseElement,
    ConstraintType,
    DoorElement,
    ElementValidator,
    RoomElement,
    TypeSafetyMixin,
    ValidationLevel,
    ValidationRule,
    WallElement,
    WindowElement,
    create_door,
    create_room,
    create_wall,
    create_window,
)

# Version info
__version__ = "1.0.0"
__all__ = [
    "create_context",
    # Core classes
    "RevitContext",
    "QueryBuilder",
    "LazyQueryExecutor",
    "ElementSet",
    "AsyncElementSet",
    # Relationship management
    "RelationshipManager",
    "Relationship",
    "OneToManyRelationship",
    "ManyToManyRelationship",
    # Caching
    "CacheManager",
    "CacheKey",
    "CacheEntry",
    # Change tracking
    "ChangeTracker",
    "ChangeSet",
    # Async support
    "AsyncRevitContext",
    "async_transaction",
    "async_batch_operation",
    # Types and enums
    "ElementFilter",
    "SortCriteria",
    "QueryExpression",
    "ElementState",
    "CachePolicy",
    "BatchOperation",
    # Decorators
    "cached",
    "lazy_property",
    "tracked_property",
    # Validation and type safety
    "BaseElement",
    "WallElement",
    "RoomElement",
    "DoorElement",
    "WindowElement",
    "ElementValidator",
    "ValidationLevel",
    "ValidationRule",
    "ConstraintType",
    "TypeSafetyMixin",
    "create_wall",
    "create_room",
    "create_door",
    "create_window",
    # Exceptions
    "ORMException",
    "RelationshipError",
    "CacheError",
    "ChangeTrackingError",
    "QueryError",
    "ValidationError",
]
