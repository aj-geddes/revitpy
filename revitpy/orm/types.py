"""
Type definitions and enums for the RevitPy ORM layer.

This module provides all type definitions, protocols, and enums used
throughout the ORM system for better type safety and code clarity.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import (
    Any,
    Protocol,
    TypeVar,
    Union,
    runtime_checkable,
)
from uuid import UUID, uuid4

# Type variables
T = TypeVar("T")
E = TypeVar("E", bound="Element")
R = TypeVar("R")

# Forward declarations
Element = TypeVar("Element")
RevitElement = Any  # Will be the actual Revit element type


class ElementState(Enum):
    """State of an element in the ORM context."""

    UNCHANGED = "unchanged"
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    DETACHED = "detached"


class CachePolicy(Enum):
    """Cache policies for element loading."""

    NONE = "none"  # No caching
    MEMORY = "memory"  # In-memory caching only
    PERSISTENT = "persistent"  # Persistent cache with invalidation
    AGGRESSIVE = "aggressive"  # Cache everything aggressively


class QueryMode(Enum):
    """Query execution modes."""

    LAZY = "lazy"  # Lazy evaluation (default)
    EAGER = "eager"  # Immediate evaluation
    STREAMING = "streaming"  # Streaming evaluation for large datasets


class RelationshipType(Enum):
    """Types of relationships between elements."""

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class LoadStrategy(Enum):
    """Strategies for loading related entities."""

    LAZY = "lazy"  # Load on demand
    EAGER = "eager"  # Load with parent
    SELECT = "select"  # Use separate select query
    BATCH = "batch"  # Batch load multiple entities


class IsolationLevel(IntEnum):
    """Transaction isolation levels."""

    READ_UNCOMMITTED = 1
    READ_COMMITTED = 2
    REPEATABLE_READ = 3
    SERIALIZABLE = 4


class BatchOperationType(Enum):
    """Types of batch operations."""

    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    BULK_UPDATE = "bulk_update"


@dataclass(frozen=True)
class ElementFilter:
    """Represents a filter condition for querying elements."""

    property_name: str
    operator: str
    value: Any = None
    case_sensitive: bool = True
    negate: bool = False

    def __post_init__(self) -> None:
        valid_operators = {
            "eq",
            "ne",
            "lt",
            "le",
            "gt",
            "ge",
            "contains",
            "startswith",
            "endswith",
            "in",
            "not_in",
            "is_null",
            "is_not_null",
            "regex",
        }
        if self.operator not in valid_operators:
            raise ValueError(f"Invalid operator: {self.operator}")


@dataclass(frozen=True)
class SortCriteria:
    """Represents sort criteria for query results."""

    property_name: str
    ascending: bool = True
    null_handling: str = "last"  # "first", "last", "error"

    def __post_init__(self) -> None:
        if self.null_handling not in ["first", "last", "error"]:
            raise ValueError(f"Invalid null_handling: {self.null_handling}")


@dataclass
class QueryExpression:
    """Represents a complete query expression."""

    filters: list[ElementFilter] = field(default_factory=list)
    sorts: list[SortCriteria] = field(default_factory=list)
    skip: int = 0
    take: int | None = None
    distinct: bool = False
    distinct_by: str | None = None
    include_relationships: set[str] = field(default_factory=set)
    cache_policy: CachePolicy = CachePolicy.MEMORY
    query_mode: QueryMode = QueryMode.LAZY


@dataclass
class CacheKey:
    """Key for caching query results and entities."""

    entity_type: str
    query_hash: str | None = None
    entity_id: Any | None = None
    relationship_path: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        parts = [self.entity_type]
        if self.entity_id:
            parts.append(f"id:{self.entity_id}")
        if self.query_hash:
            parts.append(f"query:{self.query_hash}")
        if self.relationship_path:
            parts.append(f"rel:{self.relationship_path}")
        return "|".join(parts)


@dataclass
class CacheEntry:
    """Cached data entry."""

    key: CacheKey
    data: Any
    created_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    ttl_seconds: int | None = None
    dependencies: set[str] = field(default_factory=set)

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl_seconds is None:
            return False

        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed > self.ttl_seconds

    def mark_accessed(self) -> None:
        """Mark entry as accessed."""
        self.accessed_at = datetime.utcnow()
        self.access_count += 1


@dataclass
class BatchOperation:
    """Represents a batch operation to be executed."""

    operation_type: BatchOperationType
    entity: Any
    properties: dict[str, Any] = field(default_factory=dict)
    operation_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    dependencies: list[UUID] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.operation_id)


@dataclass
class ChangeSet:
    """Represents a set of changes for an entity."""

    entity_id: Any
    entity_type: str
    original_values: dict[str, Any] = field(default_factory=dict)
    current_values: dict[str, Any] = field(default_factory=dict)
    state: ElementState = ElementState.UNCHANGED
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def changed_properties(self) -> set[str]:
        """Get set of changed property names."""
        if self.state == ElementState.ADDED:
            return set(self.current_values.keys())

        changed = set()
        for key, value in self.current_values.items():
            original = self.original_values.get(key)
            if original != value:
                changed.add(key)
        return changed

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return self.state != ElementState.UNCHANGED or bool(self.changed_properties)


# Protocols for type safety


@runtime_checkable
class IQueryable(Protocol[T]):
    """Protocol for queryable collections."""

    def where(self, predicate: Callable[[T], bool]) -> IQueryable[T]: ...

    def select(self, selector: Callable[[T], R]) -> IQueryable[R]: ...

    def order_by(self, key_selector: Callable[[T], Any]) -> IQueryable[T]: ...

    def skip(self, count: int) -> IQueryable[T]: ...

    def take(self, count: int) -> IQueryable[T]: ...

    def first(self, predicate: Callable[[T], bool] | None = None) -> T: ...

    def to_list(self) -> list[T]: ...


@runtime_checkable
class IAsyncQueryable(Protocol[T]):
    """Protocol for async queryable collections."""

    def where(self, predicate: Callable[[T], bool]) -> IAsyncQueryable[T]: ...

    def select(self, selector: Callable[[T], R]) -> IAsyncQueryable[R]: ...

    def order_by(self, key_selector: Callable[[T], Any]) -> IAsyncQueryable[T]: ...

    def skip(self, count: int) -> IAsyncQueryable[T]: ...

    def take(self, count: int) -> IAsyncQueryable[T]: ...

    async def first_async(self, predicate: Callable[[T], bool] | None = None) -> T: ...

    async def to_list_async(self) -> list[T]: ...

    def __aiter__(self) -> AsyncIterator[T]: ...


@runtime_checkable
class ICacheable(Protocol):
    """Protocol for cacheable objects."""

    @property
    def cache_key(self) -> CacheKey: ...

    @property
    def cache_dependencies(self) -> set[str]: ...

    def invalidate_cache(self) -> None: ...


@runtime_checkable
class ITrackable(Protocol):
    """Protocol for objects that support change tracking."""

    @property
    def is_dirty(self) -> bool: ...

    @property
    def state(self) -> ElementState: ...

    @property
    def original_values(self) -> dict[str, Any]: ...

    def accept_changes(self) -> None: ...

    def reject_changes(self) -> None: ...


@runtime_checkable
class IElementProvider(Protocol):
    """Protocol for element providers."""

    def get_all_elements(self) -> list[Any]: ...

    def get_elements_of_type(self, element_type: type[E]) -> list[E]: ...

    def get_element_by_id(self, element_id: Any) -> Any | None: ...

    async def get_all_elements_async(self) -> list[Any]: ...

    async def get_elements_of_type_async(self, element_type: type[E]) -> list[E]: ...


@runtime_checkable
class IRelationshipLoader(Protocol):
    """Protocol for loading relationships."""

    def load_relationship(
        self,
        entity: Any,
        relationship_name: str,
        strategy: LoadStrategy = LoadStrategy.LAZY,
    ) -> Any: ...

    async def load_relationship_async(
        self,
        entity: Any,
        relationship_name: str,
        strategy: LoadStrategy = LoadStrategy.LAZY,
    ) -> Any: ...


@runtime_checkable
class IUnitOfWork(Protocol):
    """Protocol for unit of work pattern."""

    def register_new(self, entity: Any) -> None: ...

    def register_dirty(self, entity: Any) -> None: ...

    def register_removed(self, entity: Any) -> None: ...

    def register_clean(self, entity: Any) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    async def commit_async(self) -> None: ...

    async def rollback_async(self) -> None: ...


# Type aliases for better readability
QueryPredicate = Callable[[T], bool]
QuerySelector = Callable[[T], R]
QueryKeySelector = Callable[[T], Any]
AsyncQueryPredicate = Callable[[T], Awaitable[bool]]
AsyncQuerySelector = Callable[[T], Awaitable[R]]

ElementId = Union[int, str, UUID]
PropertyValue = Union[str, int, float, bool, datetime, None]
PropertyDict = dict[str, PropertyValue]

# Async type aliases
AsyncGenerator = AsyncIterator[T]
AsyncPredicate = Callable[[T], Awaitable[bool]]
AsyncSelector = Callable[[T], Awaitable[R]]
