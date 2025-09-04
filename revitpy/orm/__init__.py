"""
RevitPy ORM Layer - High-level Pythonic interface to Revit elements and operations.

This module provides a comprehensive ORM (Object-Relational Mapping) layer for Revit,
offering LINQ-style querying, relationship mapping, change tracking, caching, and
async support for high-performance Revit development.

Key Features:
- LINQ-style fluent query interface with lazy evaluation
- Relationship mapping between Revit elements
- Intelligent change tracking with batch operations
- Multi-level caching with smart invalidation
- Full async/await support
- Complete type safety with runtime validation
- <100ms response time for complex queries on 10,000+ elements

Usage:
    from revitpy.orm import RevitContext, Wall, Room
    
    async with RevitContext() as ctx:
        # LINQ-style querying
        walls = await ctx.walls.where(lambda w: w.level.name == "Level 1") \
                              .order_by(lambda w: w.name) \
                              .to_list_async()
        
        # Relationship navigation
        wall = await ctx.walls.first_async()
        room = wall.room  # Navigate relationship
        adjacent_walls = room.walls  # Reverse navigation
        
        # Change tracking and batch operations
        for wall in walls:
            wall.mark = "Updated"
        
        await ctx.save_changes_async()  # Batch update all changes
"""

from .context import RevitContext
from .query_builder import QueryBuilder, LazyQueryExecutor
from .element_set import ElementSet, AsyncElementSet
from .relationships import RelationshipManager, Relationship, OneToManyRelationship, ManyToManyRelationship
from .cache import CacheManager, CacheKey, CacheEntry
from .change_tracker import ChangeTracker, ChangeSet, EntityState
from .async_support import AsyncRevitContext, async_transaction, async_batch_operation
from .types import (
    ElementFilter, SortCriteria, QueryExpression, 
    ElementState, CachePolicy, BatchOperation
)
from .decorators import cached, lazy_property, tracked_property
from .validation import (
    BaseElement, WallElement, RoomElement, DoorElement, WindowElement,
    ElementValidator, ValidationLevel, ValidationRule, ConstraintType,
    TypeSafetyMixin, create_wall, create_room, create_door, create_window
)
from .exceptions import (
    ORMException, RelationshipError, CacheError, 
    ChangeTrackingError, QueryError, ValidationError
)

# Version info
__version__ = "1.0.0"
__all__ = [
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
    "EntityState",
    
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