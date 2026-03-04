---
layout: api
title: API Reference
description: Complete API reference for all RevitPy public classes and methods, covering RevitAPI, ORM, events, extensions, extract, IFC, AI, cloud, and more.
doc_tier: developer
module: revitpy
---

## Core API (`revitpy.api`)

### RevitAPI

The primary interface for interacting with Autodesk Revit.

**Module:** `revitpy.api.wrapper`

```python
class RevitAPI:
    def __init__(self, application: IRevitApplication | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_connected` | `bool` | Whether the API is connected to Revit |
| `active_document` | `RevitDocumentProvider \| None` | The currently active document provider |
| `elements` | `ElementSet` | Access to elements in the active document |

**Methods:**

```python
def connect(self) -> None
```
Connect to the Revit application.

```python
def disconnect(self) -> None
```
Disconnect from the Revit application.

```python
def open_document(self, file_path: str) -> RevitDocumentProvider
```
Open a Revit document from a file path.

```python
def create_document(self, template_path: str | None = None) -> RevitDocumentProvider
```
Create a new Revit document, optionally from a template.

```python
def get_document_info(self, provider: RevitDocumentProvider | None = None) -> DocumentInfo
```
Get information about a document. Uses active document if provider is not specified.

```python
def save_document(self, provider: RevitDocumentProvider | None = None) -> None
```
Save a document. Uses active document if provider is not specified.

```python
def close_document(self, provider: RevitDocumentProvider | None = None, save_changes: bool = True) -> None
```
Close a document. Uses active document if provider is not specified.

```python
def query(self, element_type: str) -> "QueryBuilder"
```
Create a query builder for the given element type.

```python
def transaction(self, name: str, **kwargs) -> Transaction
```
Create a new transaction. Can be used as a context manager.

```python
def transaction_group(self, name: str) -> TransactionGroup
```
Create a new transaction group.

```python
def get_element_by_id(self, element_id: int | ElementId) -> Element | None
```
Get an element by its ID.

```python
def delete_elements(self, elements: list[Element | int | ElementId]) -> None
```
Delete elements from the document.

```python
def refresh_cache(self) -> None
```
Refresh the internal element cache.

---

### Element

Represents a Revit element with parameter access and change tracking.

**Module:** `revitpy.api.element`

```python
class Element:
    def __init__(self, revit_element, provider: RevitDocumentProvider | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `id` | `ElementId` | The element's unique identifier |
| `name` | `str` | The element's name |
| `is_dirty` | `bool` | Whether the element has unsaved changes |
| `changes` | `dict[str, Any]` | Dictionary of pending changes |

**Methods:**

```python
def get_parameter_value(self, parameter_name: str, use_cache: bool = True) -> Any
```
Get the value of a parameter by name.

```python
def set_parameter_value(self, parameter_name: str, value: Any, track_changes: bool = True) -> None
```
Set the value of a parameter.

```python
def get_all_parameters(self, refresh_cache: bool = False) -> dict[str, Any]
```
Get all parameters as a dictionary.

```python
def save_changes(self) -> None
```
Save all pending changes to the element.

```python
def discard_changes(self) -> None
```
Discard all pending changes.

```python
def refresh(self) -> None
```
Refresh element data from Revit.

---

### ElementSet[T]

A LINQ-style collection of elements supporting fluent query operations.

**Module:** `revitpy.api.element`

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `count` | `int` | Number of elements in the set |

**Methods:**

```python
def where(self, predicate: Callable[[T], bool]) -> "ElementSet[T]"
```
Filter elements by a predicate function.

```python
def select(self, selector: Callable[[T], Any]) -> "ElementSet[Any]"
```
Project elements using a selector function.

```python
def first(self, predicate: Callable[[T], bool] | None = None) -> T
```
Return the first element, optionally matching a predicate. Raises if empty.

```python
def first_or_default(self, predicate: Callable[[T], bool] | None = None, default: T | None = None) -> T | None
```
Return the first element or a default value.

```python
def single(self, predicate: Callable[[T], bool] | None = None) -> T
```
Return the single matching element. Raises if zero or more than one match.

```python
def to_list(self) -> list[T]
```
Convert the element set to a list.

```python
def any(self, predicate: Callable[[T], bool] | None = None) -> bool
```
Check if any elements match the predicate.

```python
def all(self, predicate: Callable[[T], bool]) -> bool
```
Check if all elements match the predicate.

```python
def order_by(self, key_selector: Callable[[T], Any]) -> "ElementSet[T]"
```
Sort elements by a key selector.

```python
def group_by(self, key_selector: Callable[[T], Any]) -> dict[Any, list[T]]
```
Group elements by a key selector.

---

### ElementId

**Module:** `revitpy.api.element`

```python
@dataclass
class ElementId:
    value: int
```

---

### ParameterValue

**Module:** `revitpy.api.element`

A Pydantic model representing a parameter value with metadata.

---

### Transaction

Manages Revit transactions with context manager support.

**Module:** `revitpy.api.transaction`

```python
class Transaction:
    def __init__(self, provider, name: str = "Transaction", options: TransactionOptions | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Transaction name |
| `status` | `TransactionStatus` | Current status |
| `is_active` | `bool` | Whether the transaction is currently active |
| `duration` | `float \| None` | Duration in seconds (after commit/rollback) |

**Methods:**

```python
def start(self) -> None
```
Start the transaction.

```python
def commit(self) -> None
```
Commit the transaction.

```python
def rollback(self) -> None
```
Roll back the transaction.

```python
def add_operation(self, operation: Callable) -> None
```
Add an operation to the transaction.

```python
def add_rollback_handler(self, handler: Callable) -> None
```
Add a handler called on rollback.

```python
def add_commit_handler(self, handler: Callable) -> None
```
Add a handler called on commit.

---

### TransactionGroup

Groups multiple transactions for batch execution.

**Module:** `revitpy.api.transaction`

```python
class TransactionGroup:
    def __init__(self, provider, name: str = "TransactionGroup") -> None
```

**Methods:**

```python
def add_transaction(self, options: TransactionOptions | None = None) -> Transaction
```
Add a transaction to the group.

```python
def start_all(self) -> None
```
Start all transactions in the group.

```python
def commit_all(self) -> None
```
Commit all transactions in the group.

```python
def rollback_all(self) -> None
```
Roll back all transactions in the group.

---

### TransactionStatus

**Module:** `revitpy.api.transaction`

```python
class TransactionStatus(Enum):
    NOT_STARTED = "not_started"
    STARTED = "started"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
```

---

### TransactionOptions

**Module:** `revitpy.api.transaction`

```python
@dataclass
class TransactionOptions:
    name: str = "Transaction"
    description: str = ""
    auto_commit: bool = False
    timeout_seconds: float | None = None
    retry_count: int = 0
    retry_delay: float = 1.0
    suppress_warnings: bool = False
```

---

### QueryBuilder[T] (Core API)

Fluent query builder for filtering, sorting, and paginating Revit elements.

**Module:** `revitpy.api.query`

```python
class QueryBuilder(Generic[T]):
    def __init__(self, element_type: str, provider=None) -> None
```

**Filter Methods:**

```python
def where(self, property_name: str, operator: str | FilterOperator, value: Any, case_sensitive: bool = True) -> "QueryBuilder[T]"
```
Add a filter condition.

```python
def equals(self, property_name: str, value: Any) -> "QueryBuilder[T]"
def not_equals(self, property_name: str, value: Any) -> "QueryBuilder[T]"
def contains(self, property_name: str, value: str, case_sensitive: bool = True) -> "QueryBuilder[T]"
def starts_with(self, property_name: str, value: str) -> "QueryBuilder[T]"
def ends_with(self, property_name: str, value: str) -> "QueryBuilder[T]"
def in_values(self, property_name: str, values: list[Any]) -> "QueryBuilder[T]"
def is_null(self, property_name: str) -> "QueryBuilder[T]"
def is_not_null(self, property_name: str) -> "QueryBuilder[T]"
def regex(self, property_name: str, pattern: str) -> "QueryBuilder[T]"
```
Convenience filter methods for common operations.

**Sort Methods:**

```python
def order_by(self, property_name: str, direction: SortDirection = SortDirection.ASCENDING) -> "QueryBuilder[T]"
def order_by_ascending(self, property_name: str) -> "QueryBuilder[T]"
def order_by_descending(self, property_name: str) -> "QueryBuilder[T]"
```

**Pagination Methods:**

```python
def skip(self, count: int) -> "QueryBuilder[T]"
def take(self, count: int) -> "QueryBuilder[T]"
def distinct(self, property_name: str) -> "QueryBuilder[T]"
```

**Terminal Methods:**

```python
def execute(self) -> list[T]
def count(self) -> int
def any(self) -> bool
def first(self) -> T
def first_or_default(self, default: T | None = None) -> T | None
def single(self) -> T
def to_list(self) -> list[T]
```

---

### FilterOperator

**Module:** `revitpy.api.query`

```python
class FilterOperator(Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
```

---

### SortDirection

**Module:** `revitpy.api.query`

```python
class SortDirection(Enum):
    ASCENDING = "ascending"
    DESCENDING = "descending"
```

---

### Exceptions

**Module:** `revitpy.api.exceptions`

```python
class RevitAPIError(Exception):
    def __init__(self, message: str, cause: Exception | None = None) -> None

class TransactionError(RevitAPIError):
    def __init__(self, message: str, transaction_name: str | None = None, cause: Exception | None = None) -> None

class ElementNotFoundError(RevitAPIError):
    def __init__(self, element_id: int | None = None, element_type: str | None = None, cause: Exception | None = None) -> None

class ValidationError(RevitAPIError):
    def __init__(self, message: str, field: str | None = None, value: Any = None, cause: Exception | None = None) -> None

class PermissionError(RevitAPIError):
    def __init__(self, message: str, operation: str | None = None, cause: Exception | None = None) -> None

class ModelError(RevitAPIError):
    def __init__(self, message: str, cause: Exception | None = None) -> None

class ConnectionError(RevitAPIError):
    def __init__(self, message: str, cause: Exception | None = None) -> None
```

---

## ORM Layer (`revitpy.orm`)

### RevitContext

The primary ORM context for querying and managing Revit elements with change tracking, caching, and relationship support.

**Module:** `revitpy.orm.context`

```python
class RevitContext:
    def __init__(
        self,
        provider=None,
        *,
        config: ContextConfiguration | None = None,
        cache_manager: CacheManager | None = None,
        change_tracker: ChangeTracker | None = None,
        relationship_manager: RelationshipManager | None = None,
        unit_of_work=None,
    ) -> None
```

Can be used as a context manager (`with RevitContext() as ctx:`).

**Query Methods:**

```python
def query(self, element_type: type[T]) -> "QueryBuilder[T]"
```
Create a query builder for the given element type.

```python
def all(self, element_type: type[T]) -> list[T]
```
Get all elements of a type.

```python
def where(self, element_type: type[T], predicate: Callable[[T], bool]) -> list[T]
```
Get elements matching a predicate.

```python
def first(self) -> T
def first_or_default(self) -> T | None
def single(self) -> T
def count(self) -> int
def any(self) -> bool
```

```python
def get_by_id(self, element_type: type[T], element_id: int) -> T | None
```
Get a specific element by type and ID.

**Change Tracking Methods:**

```python
def attach(self, entity) -> None
def detach(self, entity) -> None
def add(self, entity) -> None
def remove(self, entity) -> None
def get_entity_state(self, entity) -> str
def accept_changes(self) -> None
def reject_changes(self) -> None
def save_changes(self) -> None
```

**Relationship Methods:**

```python
def load_relationship(self, entity, relationship_name: str) -> Any
def configure_relationship(self, relationship_config) -> None
```

**Cache Methods:**

```python
def clear_cache(self) -> None
def invalidate_cache(self, key: str) -> None
```

**Other Methods:**

```python
def transaction(self, name: str = "Transaction") -> Transaction
def as_async(self) -> "AsyncRevitContext"
def dispose(self) -> None
```

---

### ContextConfiguration

**Module:** `revitpy.orm.context`

```python
@dataclass
class ContextConfiguration:
    # Configuration fields for RevitContext behavior
```

---

### create_context

**Module:** `revitpy.orm.context`

```python
def create_context(provider=None, **kwargs) -> RevitContext
```
Factory function to create a configured RevitContext.

---

### QueryBuilder[T] (ORM)

ORM query builder with lazy evaluation and async support. Distinct from the Core API QueryBuilder.

**Module:** `revitpy.orm.query_builder`

```python
class QueryBuilder(Generic[T]):
    def __init__(self, element_type: type[T], context=None) -> None
```

**Fluent Methods:**

```python
def where(self, predicate: Callable[[T], bool]) -> "QueryBuilder[T]"
def select(self, selector: Callable[[T], Any]) -> "QueryBuilder[Any]"
def order_by(self, key_selector: Callable[[T], Any]) -> "QueryBuilder[T]"
def order_by_descending(self, key_selector: Callable[[T], Any]) -> "QueryBuilder[T]"
def skip(self, count: int) -> "QueryBuilder[T]"
def take(self, count: int) -> "QueryBuilder[T]"
def distinct(self, key_selector: Callable[[T], Any] | None = None) -> "QueryBuilder[T]"
```

**Synchronous Terminal Methods:**

```python
def first(self) -> T
def first_or_default(self, default: T | None = None) -> T | None
def single(self) -> T
def single_or_default(self, default: T | None = None) -> T | None
def any(self, predicate: Callable[[T], bool] | None = None) -> bool
def all(self, predicate: Callable[[T], bool]) -> bool
def count(self) -> int
def to_list(self) -> list[T]
def to_dict(self, key_selector: Callable[[T], Any], value_selector: Callable[[T], Any] | None = None) -> dict
def group_by(self, key_selector: Callable[[T], Any]) -> dict[Any, list[T]]
```

**Asynchronous Terminal Methods:**

```python
async def first_async(self) -> T
async def first_or_default_async(self, default: T | None = None) -> T | None
async def single_async(self) -> T
async def any_async(self, predicate: Callable[[T], bool] | None = None) -> bool
async def count_async(self) -> int
async def to_list_async(self) -> list[T]
async def to_dict_async(self, key_selector: Callable[[T], Any], value_selector: Callable[[T], Any] | None = None) -> dict
```

**Streaming:**

```python
def as_streaming(self, batch_size: int = 100) -> "StreamingQuery[T]"
```

---

### StreamingQuery[T]

Streaming query executor for processing large result sets in batches.

**Module:** `revitpy.orm.query_builder`

```python
async def foreach_async(self, action: Callable[[T], Any]) -> None
async def to_list_async(self) -> list[T]
```

---

### CacheManager

Manages caching of elements and query results with multiple eviction policies.

**Module:** `revitpy.orm.cache`

```python
class CacheManager:
    def __init__(self, config: CacheConfiguration | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `statistics` | `CacheStatistics` | Cache hit/miss statistics |
| `size` | `int` | Number of items in the cache |

**Methods:**

```python
def get(self, key: str) -> Any | None
def set(self, key: str, value: Any, *, ttl_seconds: float | None = None, dependencies: list[str] | None = None) -> None
def delete(self, key: str) -> None
def invalidate(self, key: str) -> None
def invalidate_by_dependency(self, dependency: str) -> None
def invalidate_by_pattern(self, pattern: str) -> None
def clear(self) -> None
def contains(self, key: str) -> bool
def keys(self) -> list[str]
def add_invalidation_callback(self, callback: Callable) -> None
def remove_invalidation_callback(self, callback: Callable) -> None
def get_memory_usage_estimate(self) -> int
```

---

### CacheConfiguration

**Module:** `revitpy.orm.cache`

```python
@dataclass
class CacheConfiguration:
    max_size: int = 1000
    max_memory_mb: float = 100.0
    default_ttl_seconds: float = 300.0
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    enable_statistics: bool = True
    cleanup_interval_seconds: float = 60.0
    compression_enabled: bool = False
    thread_safe: bool = True
```

---

### CacheStatistics

**Module:** `revitpy.orm.cache`

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `hits` | `int` | Number of cache hits |
| `misses` | `int` | Number of cache misses |
| `hit_rate` | `float` | Cache hit rate (0.0 to 1.0) |
| `evictions` | `int` | Number of evictions |
| `invalidations` | `int` | Number of invalidations |
| `memory_usage` | `int` | Estimated memory usage in bytes |
| `uptime` | `float` | Cache uptime in seconds |

---

### EvictionPolicy

**Module:** `revitpy.orm.cache`

```python
class EvictionPolicy(Enum):
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"
    SIZE_BASED = "size_based"
```

---

### ChangeTracker

Tracks changes to entities for the unit of work pattern.

**Module:** `revitpy.orm.change_tracker`

```python
class ChangeTracker:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `auto_track` | `bool` | Whether to automatically track property changes |
| `has_changes` | `bool` | Whether any tracked entities have changes |
| `changed_entities` | `list` | List of entities with changes |
| `change_count` | `int` | Total number of changes |

**Methods:**

```python
def attach(self, entity: Any, entity_id: str | None = None) -> None
def detach(self, entity_id: str) -> None
def track_property_change(self, entity_id: str, property_name: str, old_value: Any, new_value: Any) -> None
def track_relationship_change(self, entity_id: str, relationship_name: str, change_type: ChangeType, related_entity_id: str) -> None
def mark_as_added(self, entity_id: str) -> None
def mark_as_deleted(self, entity_id: str) -> None
def get_entity_state(self, entity_id: str) -> str
def get_changes(self, entity_id: str) -> list[PropertyChange]
def get_all_changes(self) -> dict[str, list[PropertyChange]]
def accept_changes(self, entity_id: str | None = None) -> None
def reject_changes(self, entity_id: str | None = None) -> None
def clear(self) -> None
def create_batch_operation(self, name: str) -> None
def add_batch_operation(self, operation: Callable) -> None
def get_batch_operations(self) -> list
def clear_batch_operations(self) -> None
def add_change_callback(self, callback: Callable) -> None
def remove_change_callback(self, callback: Callable) -> None
def is_tracked(self, entity_id: str) -> bool
def get_tracked_count(self) -> int
```

---

### ChangeType

**Module:** `revitpy.orm.change_tracker`

```python
class ChangeType(Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"
```

---

### PropertyChange

**Module:** `revitpy.orm.change_tracker`

```python
@dataclass
class PropertyChange:
    property_name: str
    old_value: Any
    new_value: Any
```

---

### RelationshipManager

Manages relationships between Revit elements (one-to-one, one-to-many, many-to-many).

**Module:** `revitpy.orm.relationships`

```python
class RelationshipManager:
    def __init__(self) -> None
```

**Methods:**

```python
def register_one_to_one(self, source_type: type, target_type: type, foreign_key: str, **kwargs) -> None
def register_one_to_many(self, source_type: type, target_type: type, foreign_key: str, **kwargs) -> None
def register_many_to_many(self, source_type: type, target_type: type, junction_type: type | None = None, **kwargs) -> None
def get_relationship(self, source_type: type, relationship_name: str) -> Relationship | None
def load_relationship(self, entity: Any, relationship_name: str, context=None) -> Any
async def load_relationship_async(self, entity: Any, relationship_name: str, context=None) -> Any
def invalidate_relationship(self, entity: Any, relationship_name: str) -> None
def invalidate_entity(self, entity: Any) -> None
def get_registered_relationships(self) -> list[Relationship]
```

---

### Validation Models

Pydantic-based validation models for common Revit element types.

**Module:** `revitpy.orm.validation`

#### BaseElement

```python
class BaseElement(BaseModel):
    id: int | None = None
    name: str
    category: str = ""
    level_id: int | None = None
    family_name: str = ""
    type_name: str = ""
    created_at: datetime | None = None
    modified_at: datetime | None = None
    version: int = 1
    is_valid: bool = True
    state: str = "unchanged"
```

**Methods:**

```python
def is_dirty(self) -> bool
def mark_dirty(self) -> None
def mark_clean(self) -> None
```

#### WallElement

```python
class WallElement(BaseElement):
    height: float = 0.0
    length: float = 0.0
    width: float = 0.0
    area: float = 0.0
    volume: float = 0.0
    # Additional wall-specific fields
```

#### RoomElement

```python
class RoomElement(BaseElement):
    number: str = ""
    area: float = 0.0
    perimeter: float = 0.0
    volume: float = 0.0
    department: str = ""
    occupancy: int = 0
    # Additional room-specific fields
```

#### DoorElement

```python
class DoorElement(BaseElement):
    width: float = 0.0
    height: float = 0.0
    material: str = ""
    fire_rating: str = ""
    # Additional door-specific fields
```

#### WindowElement

```python
class WindowElement(BaseElement):
    width: float = 0.0
    height: float = 0.0
    glass_type: str = ""
    # Additional window-specific fields
```

#### Factory Functions

```python
def create_wall(**kwargs) -> WallElement
def create_room(**kwargs) -> RoomElement
def create_door(**kwargs) -> DoorElement
def create_window(**kwargs) -> WindowElement
```

---

### ElementValidator

**Module:** `revitpy.orm.validation`

```python
class ElementValidator:
    # Validates elements against Pydantic models and custom constraints
```

### ValidationLevel

**Module:** `revitpy.orm.validation`

```python
class ValidationLevel(Enum):
    # Defines validation strictness levels
```

### ConstraintType

**Module:** `revitpy.orm.validation`

```python
class ConstraintType(Enum):
    # Defines types of validation constraints
```

---

## Events (`revitpy.events`)

### EventManager

Singleton event manager for registering and dispatching events.

**Module:** `revitpy.events.manager`

```python
class EventManager:
    # Singleton -- use EventManager() to get the instance
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `dispatcher` | `object` | The internal event dispatcher |
| `is_running` | `bool` | Whether the event manager is running |
| `stats` | `dict` | Event processing statistics |

**Lifecycle Methods:**

```python
def start(self, auto_discover: bool = False) -> None
def stop(self, timeout: float | None = None) -> None
```

**Handler Registration:**

```python
def register_handler(self, handler: Callable, event_types: list[EventType] | None = None, priority: EventPriority = EventPriority.NORMAL) -> None
def register_function(self, func: Callable, event_types: list[EventType] | None = None) -> None
def unregister_handler(self, handler: Callable) -> None
def register_class_handlers(self, instance: Any) -> None
```

**Event Dispatch:**

```python
def dispatch_event(self, event: EventData) -> EventResult
async def dispatch_event_async(self, event: EventData) -> EventResult
def emit(self, event_type: EventType, data: dict | None = None, **kwargs) -> EventResult
async def emit_async(self, event_type: EventType, data: dict | None = None, **kwargs) -> EventResult
```

**Discovery:**

```python
def add_discovery_path(self, path: str) -> None
def discover_handlers(self) -> None
```

**Listener Management:**

```python
def add_listener(self, event_type: EventType, listener: Callable) -> None
def remove_listener(self, event_type: EventType, listener: Callable) -> None
```

**Revit Integration:**

```python
def connect_to_revit(self, application) -> None
def disconnect_from_revit(self) -> None
```

**Debugging:**

```python
def enable_debug(self) -> None
def disable_debug(self) -> None
def clear_event_queue(self) -> None
def reset_statistics(self) -> None
def get_registered_handlers(self) -> list
```

---

### EventType

**Module:** `revitpy.events.types`

```python
class EventType(Enum):
    # Document events
    DOCUMENT_OPENED = "document_opened"
    DOCUMENT_CLOSED = "document_closed"
    DOCUMENT_SAVED = "document_saved"
    DOCUMENT_CREATED = "document_created"
    DOCUMENT_MODIFIED = "document_modified"

    # Element events
    ELEMENT_CREATED = "element_created"
    ELEMENT_MODIFIED = "element_modified"
    ELEMENT_DELETED = "element_deleted"

    # Transaction events
    TRANSACTION_STARTED = "transaction_started"
    TRANSACTION_COMMITTED = "transaction_committed"
    TRANSACTION_ROLLED_BACK = "transaction_rolled_back"

    # Parameter events
    PARAMETER_CHANGED = "parameter_changed"

    # View events
    VIEW_ACTIVATED = "view_activated"
    VIEW_DEACTIVATED = "view_deactivated"

    # Selection events
    SELECTION_CHANGED = "selection_changed"

    # Application events
    APPLICATION_INITIALIZED = "application_initialized"
    APPLICATION_CLOSING = "application_closing"
    IDLE_EVENT = "idle_event"

    # Custom events
    CUSTOM = "custom"
    EXTENSION_EVENT = "extension_event"
```

---

### EventPriority

**Module:** `revitpy.events.types`

```python
class EventPriority(Enum):
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100
```

---

### EventResult

**Module:** `revitpy.events.types`

```python
class EventResult(Enum):
    CONTINUE = "continue"
    STOP = "stop"
    CANCEL = "cancel"
```

---

### EventData

**Module:** `revitpy.events.types`

```python
@dataclass
class EventData:
    event_type: EventType
    event_id: str
    timestamp: float
    source: Any = None
    data: dict = field(default_factory=dict)
    cancellable: bool = False
    cancelled: bool = False
```

**Methods:**

```python
def cancel(self) -> None
def get_data(self, key: str, default: Any = None) -> Any
def set_data(self, key: str, value: Any) -> None
```

**Specialized Event Data Classes:**

- `DocumentEventData(EventData)` -- document-specific event data
- `ElementEventData(EventData)` -- element-specific event data
- `TransactionEventData(EventData)` -- transaction-specific event data
- `ParameterEventData(EventData)` -- parameter change event data
- `ViewEventData(EventData)` -- view-specific event data
- `SelectionEventData(EventData)` -- selection change event data

---

### Event Decorators

**Module:** `revitpy.events.decorators`

```python
def event_handler(
    event_types: list[EventType] | EventType | None = None,
    priority: EventPriority = EventPriority.NORMAL,
    event_filter: Callable | None = None,
    max_errors: int = 3,
    enabled: bool = True,
) -> Callable
```
Decorator to register a function as an event handler.

```python
def async_event_handler(
    event_types: list[EventType] | EventType | None = None,
    priority: EventPriority = EventPriority.NORMAL,
    event_filter: Callable | None = None,
    max_errors: int = 3,
    enabled: bool = True,
) -> Callable
```
Decorator to register an async function as an event handler.

```python
def event_filter(filter_instance: Callable) -> Callable
```
Decorator to attach a filter to an event handler.

```python
def throttled_handler(interval_seconds: float) -> Callable
```
Decorator to throttle event handler execution to a minimum interval.

```python
def conditional_handler(condition: Callable[..., bool]) -> Callable
```
Decorator to conditionally execute an event handler.

```python
def retry_on_error(max_retries: int = 3, delay_seconds: float = 1.0) -> Callable
```
Decorator to retry an event handler on error.

```python
def log_events(log_level: str = "INFO") -> Callable
```
Decorator to log event handler invocations.

**Convenience Decorators:**

```python
def on_element_created() -> Callable
def on_element_modified() -> Callable
def on_element_deleted() -> Callable
def on_parameter_changed() -> Callable
def on_document_opened() -> Callable
def on_document_saved() -> Callable
```

---

## Extensions (`revitpy.extensions`)

### Extension

Abstract base class for RevitPy extensions with lifecycle management.

**Module:** `revitpy.extensions.extension`

```python
class Extension(ABC):
    def __init__(self, metadata: ExtensionMetadata | None = None) -> None
```

**Lifecycle Methods (abstract, override in subclasses):**

```python
def load(self) -> None
def activate(self) -> None
def deactivate(self) -> None
def dispose(self) -> None
```

**Internal Lifecycle (called by ExtensionManager):**

```python
def load_extension(self) -> None
def activate_extension(self) -> None
def deactivate_extension(self) -> None
def dispose_extension(self) -> None
```

**Component Access:**

```python
def get_command(self, name: str) -> Any | None
def get_service(self, name: str) -> Any | None
def get_tool(self, name: str) -> Any | None
def get_analyzer(self, name: str) -> Any | None
def get_commands(self) -> dict[str, Any]
def get_services(self) -> dict[str, Any]
def get_tools(self) -> dict[str, Any]
def get_analyzers(self) -> dict[str, Any]
```

**Lifecycle Callbacks:**

```python
def on_load(self) -> None
def on_activation(self) -> None
def on_deactivation(self) -> None
def on_disposal(self) -> None
```

---

### ExtensionMetadata

**Module:** `revitpy.extensions.extension`

```python
@dataclass
class ExtensionMetadata:
    name: str
    version: str
    description: str = ""
    author: str = ""
    # Additional metadata fields
```

---

### ExtensionStatus

**Module:** `revitpy.extensions.extension`

```python
class ExtensionStatus(Enum):
    # 9 status values covering the full extension lifecycle
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    INACTIVE = "inactive"
    DISPOSING = "disposing"
    DISPOSED = "disposed"
```

---

### ExtensionManager

Singleton manager for discovering, loading, and managing extensions.

**Module:** `revitpy.extensions.manager`

```python
class ExtensionManager:
    # Singleton -- use ExtensionManager() to get the instance
```

**Methods:**

```python
def initialize(self) -> None
def shutdown(self) -> None
def discover_extensions(self, path: str | None = None) -> list[Extension]
def load_extension(self, extension: Extension | str) -> None
def unload_extension(self, extension_name: str) -> None
def activate_extension(self, extension_name: str) -> None
def deactivate_extension(self, extension_name: str) -> None
def get_extension(self, extension_name: str) -> Extension | None
def get_extensions(self) -> list[Extension]
def get_active_extensions(self) -> list[Extension]
def get_extensions_by_status(self, status: ExtensionStatus) -> list[Extension]
def has_extension(self, extension_name: str) -> bool
def is_extension_active(self, extension_name: str) -> bool
def get_statistics(self) -> dict[str, Any]
def get_extension_info(self, extension_name: str) -> dict[str, Any]
```

---

### Extension Decorators

**Module:** `revitpy.extensions.decorators`

```python
def extension(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    author: str = "",
    dependencies: list[str] | None = None,
) -> Callable
```
Class decorator to register a class as an extension.

```python
def command(
    name: str,
    description: str = "",
    icon: str = "",
    tooltip: str = "",
    shortcut: str = "",
    category: str = "",
    enabled: bool = True,
    visible: bool = True,
) -> Callable
```
Decorator to register a method as a command.

```python
def service(
    name: str,
    description: str = "",
    auto_start: bool = False,
    singleton: bool = True,
    dependencies: list[str] | None = None,
) -> Callable
```
Decorator to register a method as a service.

```python
def tool(
    name: str,
    description: str = "",
    icon: str = "",
    tooltip: str = "",
    category: str = "",
    interactive: bool = False,
    preview: bool = False,
) -> Callable
```
Decorator to register a method as a tool.

```python
def analyzer(
    name: str,
    description: str = "",
    element_types: list[str] | None = None,
    categories: list[str] | None = None,
    real_time: bool = False,
    on_demand: bool = True,
) -> Callable
```
Decorator to register a method as an analyzer.

```python
def panel(
    name: str,
    title: str = "",
    width: int = 300,
    height: int = 400,
    resizable: bool = True,
    dockable: bool = True,
    floating: bool = False,
) -> Callable
```
Decorator to register a method as a panel.

```python
def startup(priority: int = 0) -> Callable
```
Decorator to mark a method to run on extension startup.

```python
def shutdown(priority: int = 0) -> Callable
```
Decorator to mark a method to run on extension shutdown.

```python
def config(
    key: str,
    default_value: Any = None,
    description: str = "",
    required: bool = False,
    validator: Callable | None = None,
) -> Callable
```
Decorator to register a configuration option.

```python
def permission(
    name: str,
    description: str = "",
    required: bool = True,
    category: str = "",
) -> Callable
```
Decorator to declare a required permission.

```python
def cache(
    ttl: float = 300.0,
    max_size: int = 100,
    key_func: Callable | None = None,
) -> Callable
```
Decorator to cache method results.

---

## Async Support (`revitpy.async_support`)

### AsyncRevit

Asynchronous interface for Revit operations.

**Module:** `revitpy.async_support.async_revit`

```python
class AsyncRevit:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `api` | `RevitAPI` | The underlying RevitAPI instance |
| `is_connected` | `bool` | Whether connected to Revit |
| `task_queue` | `TaskQueue` | The internal task queue |

**Initialization:**

```python
async def initialize(self, max_concurrent_tasks: int = 4, revit_application=None) -> None
async def shutdown(self, timeout: float | None = None) -> None
```

**Document Operations:**

```python
async def open_document_async(self, file_path: str) -> Any
async def create_document_async(self, template_path: str | None = None) -> Any
async def save_document_async(self, provider=None) -> None
async def close_document_async(self, provider=None, save_changes: bool = True) -> None
```

**Element Operations:**

```python
async def get_elements_async(self, element_type: str | None = None) -> list
async def query_elements_async(self, element_type: str, **filters) -> list
async def update_elements_async(self, elements: list, **updates) -> None
```

**Transaction:**

```python
def async_transaction(self, name: str = "Transaction") -> Any
async def execute_in_transaction_async(self, func: Callable, name: str = "Transaction") -> Any
```

**Background Tasks:**

```python
async def run_background_task(self, func: Callable, *args, **kwargs) -> Any
async def wait_for_background_task(self, task_id: str, timeout: float | None = None) -> Any
async def start_background_task(self, func: Callable, *args, **kwargs) -> str
async def cancel_background_task(self, task_id: str) -> None
```

**Context Managers:**

```python
def element_scope(self, elements: list, auto_save: bool = True) -> Any
def progress_scope(self, total: int, message: str = "") -> Any
```

**Batch Processing:**

```python
async def batch_process(self, items: list, processor: Callable, batch_size: int = 100) -> list
```

---

### Async Decorators

**Module:** `revitpy.async_support.decorators`

```python
def async_revit_operation(
    timeout: float | None = None,
    retry_count: int = 0,
    retry_delay: float = 1.0,
    cancellation_token: CancellationToken | None = None,
    progress_reporter: ProgressReporter | None = None,
) -> Callable
```
Decorator for async Revit operations with timeout, retry, and progress support.

```python
def background_task(
    priority: TaskPriority = TaskPriority.NORMAL,
    timeout: float | None = None,
    retry_count: int = 0,
    retry_delay: float = 1.0,
    progress: bool = False,
    task_queue: TaskQueue | None = None,
) -> Callable
```
Decorator to run a function as a background task.

```python
def revit_transaction(
    name: str = "Transaction",
    auto_commit: bool = True,
    timeout: float | None = None,
) -> Callable
```
Decorator to wrap a function in a Revit transaction.

```python
def rate_limited(max_calls: int, time_window: float) -> Callable
```
Decorator to rate-limit function calls.

```python
def cache_result(ttl: float = 300.0, max_size: int = 100) -> Callable
```
Decorator to cache function results.

---

### Async Context Managers

**Module:** `revitpy.async_support.context_managers`

```python
async def async_transaction(
    provider,
    name: str = "Transaction",
    auto_commit: bool = True,
    timeout: float | None = None,
    retry_count: int = 0,
    retry_delay: float = 1.0,
    cancellation_token: CancellationToken | None = None,
) -> AsyncContextManager
```

```python
async def async_element_scope(
    elements: list,
    auto_save: bool = True,
    rollback_on_error: bool = True,
) -> AsyncContextManager
```

```python
async def async_progress_scope(
    total: int,
    message: str = "",
    console_output: bool = True,
) -> AsyncContextManager
```

```python
async def async_cancellation_scope(
    timeout: float | None = None,
    reason: str = "",
) -> AsyncContextManager
```

```python
async def async_batch_operations(
    batch_size: int = 100,
    delay_between_batches: float = 0.0,
) -> AsyncContextManager
```

```python
async def async_resource_scope(*resources) -> AsyncContextManager
```

---

### TaskQueue

Manages a queue of asynchronous tasks with priority ordering.

**Module:** `revitpy.async_support.task_queue`

```python
class TaskQueue:
    def __init__(self, max_concurrent: int = 4) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_running` | `bool` | Whether the queue is processing |
| `pending_count` | `int` | Number of pending tasks |
| `running_count` | `int` | Number of running tasks |
| `completed_count` | `int` | Number of completed tasks |
| `stats` | `dict` | Queue statistics |

**Methods:**

```python
async def enqueue(self, task: Task) -> str
def enqueue_sync(self, task: Task) -> str
async def submit(self, func: Callable, *args, **kwargs) -> str
async def wait_for_task(self, task_id: str, timeout: float | None = None) -> TaskResult
def get_task_status(self, task_id: str) -> TaskStatus
def get_task_result(self, task_id: str) -> TaskResult | None
async def start(self) -> None
async def stop(self, timeout: float | None = None) -> None
def clear_completed(self, older_than: float | None = None) -> int
```

---

### TaskStatus

**Module:** `revitpy.async_support.task_queue`

```python
class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

---

### TaskPriority

**Module:** `revitpy.async_support.task_queue`

```python
class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3
```

---

### TaskResult

**Module:** `revitpy.async_support.task_queue`

```python
@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Exception | None = None
    duration: float = 0.0
```

---

### ProgressReporter

Reports progress for long-running operations.

**Module:** `revitpy.async_support.progress`

```python
class ProgressReporter:
    def __init__(self, total: int = 100) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `current` | `int` | Current progress value |
| `total` | `int` | Total progress value |
| `percentage` | `float` | Progress as a percentage (0.0-100.0) |
| `state` | `ProgressState` | Current progress state |
| `last_report` | `ProgressReport \| None` | Most recent progress report |
| `elapsed_time` | `float` | Elapsed time in seconds |
| `estimated_remaining` | `float \| None` | Estimated remaining time |

**Methods:**

```python
def add_callback(self, callback: Callable) -> None
def remove_callback(self, callback: Callable) -> None
def set_total(self, total: int) -> None
def start(self) -> None
def increment(self, amount: int = 1) -> None
def set_progress(self, current: int) -> None
def report_progress(self, current: int, message: str = "") -> None
def report(self, message: str = "") -> None
def complete(self) -> None
def fail(self, error: str = "") -> None
def cancel(self) -> None
```

---

### ProgressState

**Module:** `revitpy.async_support.progress`

```python
class ProgressState(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

---

### ProgressReport

**Module:** `revitpy.async_support.progress`

```python
@dataclass
class ProgressReport:
    current: int
    total: int
    percentage: float
    message: str
    state: ProgressState
    elapsed_time: float
    estimated_remaining: float | None
```

---

### CancellationToken

Token for cooperative cancellation of async operations.

**Module:** `revitpy.async_support.cancellation`

```python
class CancellationToken:
    # Created via CancellationTokenSource
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_cancelled` | `bool` | Whether cancellation has been requested |
| `cancelled_at` | `float \| None` | Timestamp when cancelled |
| `reason` | `str` | Reason for cancellation |

**Methods:**

```python
def throw_if_cancellation_requested(self) -> None
```
Raises `OperationCancelledError` if cancellation has been requested.

```python
def register_callback(self, callback: Callable) -> None
```
Register a callback to be called when cancellation is requested.

---

### CancellationTokenSource

Creates and controls `CancellationToken` instances.

**Module:** `revitpy.async_support.cancellation`

```python
class CancellationTokenSource:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `token` | `CancellationToken` | The cancellation token |
| `is_cancelled` | `bool` | Whether cancellation has been requested |

**Methods:**

```python
def cancel(self, reason: str = "") -> None
```
Request cancellation.

```python
def cancel_after(self, timeout: float, reason: str = "") -> None
```
Request cancellation after a timeout.

```python
def dispose(self) -> None
```
Dispose of resources.

---

### OperationCancelledError

**Module:** `revitpy.async_support.cancellation`

```python
class OperationCancelledError(Exception):
    pass
```

---

### Utility Functions

**Module:** `revitpy.async_support.cancellation`

```python
def combine_tokens(*tokens: CancellationToken) -> CancellationToken
```
Combine multiple tokens into one that cancels when any source cancels.

```python
def with_cancellation(token: CancellationToken) -> Callable
```
Decorator to add cancellation support to an async function.

---

## Testing (`revitpy.testing`)

### MockRevit

Mock Revit environment for testing without an actual Revit installation.

**Module:** `revitpy.testing.mock_revit`

```python
class MockRevit:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `application` | `MockApplication` | The mock application instance |
| `active_document` | `MockDocument \| None` | The currently active document |

**Methods:**

```python
def create_document(self, title: str = "TestDocument.rvt") -> MockDocument
```
Create a test document.

```python
def create_element(
    self,
    name: str = "TestElement",
    category: str = "Generic",
    element_type: str = "Element",
    parameters: dict[str, Any] | None = None,
) -> MockElement
```
Create a test element. If an active document exists, the element is added to it.

```python
def create_elements(
    self,
    count: int,
    name_prefix: str = "Element",
    category: str = "Generic",
    element_type: str = "Element",
) -> list[MockElement]
```
Create multiple test elements with sequential names.

```python
def load_fixture(self, fixture_name: str, fixture_data: Any) -> None
def get_fixture(self, fixture_name: str) -> Any
```
Load and retrieve test fixtures.

```python
def save_state(self, file_path: str) -> None
def load_state(self, file_path: str) -> None
```
Save/load mock Revit state to/from JSON files.

```python
def reset(self) -> None
```
Reset mock environment to initial state.

```python
def add_event_handler(self, handler: Callable) -> None
def trigger_event(self, event_type: str, event_data: Any) -> None
```
Add and trigger event handlers for testing.

```python
def get_statistics(self) -> dict[str, Any]
```
Returns dict with keys: `documents`, `total_elements`, `fixtures`, `event_handlers`, `has_active_document`.

---

### MockDocument

**Module:** `revitpy.testing.mock_revit`

```python
class MockDocument:
    def __init__(
        self,
        title: str = "MockDocument.rvt",
        path: str = "",
        is_family_document: bool = False,
    ) -> None
```

**Attributes:** `Title`, `PathName`, `IsFamilyDocument`

**Methods:**

```python
def GetElements(self, filter_criteria=None) -> list[MockElement]
def GetElement(self, element_id: int | MockElementId) -> MockElement | None
def AddElement(self, element: MockElement) -> MockElement
def CreateElement(self, name: str = "NewElement", category: str = "Generic", element_type: str = "Element") -> MockElement
def Delete(self, element_ids: list[int | MockElementId]) -> None
def Save(self) -> bool
def Close(self, save_changes: bool = True) -> bool
def StartTransaction(self, name: str = "Transaction") -> MockTransaction
def IsModified(self) -> bool
def GetElementCount(self) -> int
def GetElementsByCategory(self, category: str) -> list[MockElement]
def GetElementsByType(self, element_type: str) -> list[MockElement]
def to_dict(self) -> dict[str, Any]
@classmethod
def from_dict(cls, data: dict[str, Any]) -> "MockDocument"
```

---

### MockElement

**Module:** `revitpy.testing.mock_revit`

```python
class MockElement:
    def __init__(
        self,
        element_id: int = None,
        name: str = "MockElement",
        category: str = "Generic",
        element_type: str = "Element",
    ) -> None
```

**Attributes:** `Id` (MockElementId), `Name`, `Category`, `ElementType`

**Methods:**

```python
def GetParameterValue(self, parameter_name: str) -> Any
def SetParameterValue(self, parameter_name: str, value: Any) -> None
def GetParameter(self, parameter_name: str) -> MockParameter | None
def SetParameter(self, parameter_name: str, parameter: MockParameter) -> None
def GetAllParameters(self) -> dict[str, MockParameter]
def HasParameter(self, parameter_name: str) -> bool
def GetProperty(self, property_name: str) -> Any
def SetProperty(self, property_name: str, value: Any) -> None
def to_dict(self) -> dict[str, Any]
@classmethod
def from_dict(cls, data: dict[str, Any]) -> "MockElement"
```

---

### MockApplication

**Module:** `revitpy.testing.mock_revit`

```python
class MockApplication:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `ActiveDocument` | `MockDocument \| None` | The active document |

**Methods:**

```python
def OpenDocumentFile(self, file_path: str) -> MockDocument
def CreateDocument(self, template_path: str | None = None) -> MockDocument
def GetOpenDocuments(self) -> list[MockDocument]
def CloseDocument(self, document: MockDocument) -> bool
```

---

### MockTransaction

**Module:** `revitpy.testing.mock_revit`

```python
class MockTransaction:
    def __init__(self, name: str = "MockTransaction") -> None
```

**Attributes:** `name`, `is_started`, `is_committed`, `is_rolled_back`

**Methods:**

```python
def Start(self) -> bool
def Commit(self) -> bool
def RollBack(self) -> bool
```

---

### MockParameter

**Module:** `revitpy.testing.mock_revit`

```python
@dataclass
class MockParameter:
    name: str
    value: Any = None
    type_name: str = "String"
    storage_type: str = "String"
    is_read_only: bool = False
```

**Methods:**

```python
def AsString(self) -> str
def AsDouble(self) -> float
def AsInteger(self) -> int
def AsValueString(self) -> str
```

---

### MockElementId

**Module:** `revitpy.testing.mock_revit`

```python
class MockElementId:
    def __init__(self, value: int) -> None
```

**Attributes:** `IntegerValue`

---

## Performance (`revitpy.performance`)

**Module:** `revitpy.performance`

The performance module exports the following classes:

| Class | Description |
|-------|-------------|
| `PerformanceOptimizer` | Optimization engine |
| `OptimizationConfig` | Configuration for the optimizer |
| `BenchmarkSuite` | Suite of performance benchmarks |
| `BenchmarkRunner` | Runs benchmark suites |
| `MemoryManager` | Memory management utilities |
| `MemoryLeakDetector` | Detects memory leaks |
| `LatencyTracker` | Tracks operation latency |
| `LatencyBenchmark` | Latency benchmark definitions |
| `IntelligentCacheManager` | Advanced caching with adaptive policies |
| `CacheConfiguration` | Cache configuration (performance module) |
| `MetricsCollector` | Collects performance metrics |
| `PerformanceMetrics` | Container for collected metrics |
| `PerformanceMonitor` | Real-time performance monitoring |
| `AlertingSystem` | Performance alerting |
| `RevitPyProfiler` | Code profiling |
| `ProfileReport` | Profiling results |

---

## Configuration (`revitpy.config`)

**Exports:** `Config`, `ConfigManager`

These classes are exported from `revitpy.__init__` and handle framework configuration. See the [Developer Setup Guide]({{ '/developer/setup/' | relative_url }}) for configuration details.

---

## Quantity Extraction (`revitpy.extract`)

### QuantityExtractor

Extract measured quantities (area, volume, length, count, weight) from Revit elements using duck-typed attribute access.

**Module:** `revitpy.extract.quantities`

```python
class QuantityExtractor:
    def __init__(self, context: Any | None = None) -> None
```

**Methods:**

```python
def extract(self, elements: list[Any], quantity_types: list[QuantityType] | None = None) -> list[QuantityItem]
```
Extract quantities from elements. Defaults to all quantity types when `quantity_types` is `None`.

```python
def extract_grouped(self, elements: list[Any], group_by: AggregationLevel = AggregationLevel.CATEGORY, quantity_types: list[QuantityType] | None = None) -> dict[str, list[QuantityItem]]
```
Extract and group quantities by aggregation level (category, level, system, element, or building).

```python
def summarize(self, items: list[QuantityItem]) -> dict[str, float]
```
Summarize quantities by type, summing values. Returns a dict mapping quantity type names to summed values.

```python
async def extract_async(self, elements: list[Any], quantity_types: list[QuantityType] | None = None, progress: Callable[[int, int], None] | None = None) -> list[QuantityItem]
```
Async version of extract with optional progress reporting callback `(current, total)`.

---

### MaterialTakeoff

Extract and process material quantities from Revit elements, with aggregation and industry-standard classification.

**Module:** `revitpy.extract.materials`

```python
class MaterialTakeoff:
    def __init__(self, context: Any | None = None) -> None
```

**Methods:**

```python
def extract(self, elements: list[Any]) -> list[MaterialQuantity]
```
Extract material data from elements. Elements are duck-typed with optional `material_name`, `material_volume`, `material_area`, `material_mass`, and `category` attributes.

```python
def aggregate(self, materials: list[MaterialQuantity]) -> list[MaterialQuantity]
```
Aggregate material quantities by material name, summing volume, area, and mass.

```python
def classify(self, materials: list[MaterialQuantity], system: str = "UniFormat") -> list[MaterialQuantity]
```
Classify materials against a standard system (`"UniFormat"` or `"MasterFormat"`). Returns new list with `classification_code` and `classification_system` set.

---

### CostEstimator

Map extracted quantities to cost data, producing itemized cost breakdowns and aggregated summaries.

**Module:** `revitpy.extract.costs`

```python
class CostEstimator:
    def __init__(self, cost_database: dict[str, float] | Path | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `database` | `dict[str, float]` | Copy of the current cost database |

**Methods:**

```python
def load_database(self, path: Path) -> None
```
Load cost data from a file. Supports CSV, JSON, and YAML formats (auto-detected from extension).

```python
def estimate(self, quantities: list[QuantityItem], aggregation: AggregationLevel = AggregationLevel.CATEGORY) -> CostSummary
```
Map quantities to costs and produce a summary with itemized costs and aggregated totals by category, system, and level.

---

### DataExporter

Export tabular data to CSV, JSON, Excel, Parquet, or plain dicts.

**Module:** `revitpy.extract.exporters`

```python
class DataExporter:
    # No constructor arguments required
```

**Methods:**

```python
def export(self, data: list[dict[str, Any]], config: ExportConfig) -> Path | list[dict[str, Any]]
```
Export data according to the given configuration. Returns a `Path` for file formats, or `list[dict]` for `DICT` format.

```python
def to_csv(self, data: list[dict[str, Any]], path: Path | None, *, include_headers: bool = True, decimal_places: int = 2) -> Path
```
Export data to CSV.

```python
def to_json(self, data: list[dict[str, Any]], path: Path | None, *, decimal_places: int = 2) -> Path
```
Export data to JSON.

```python
def to_excel(self, data: list[dict[str, Any]], path: Path | None, *, sheet_name: str = "Sheet1", include_headers: bool = True) -> Path
```
Export data to Excel (xlsx). Requires the optional `openpyxl` dependency.

```python
def to_parquet(self, data: list[dict[str, Any]], path: Path | None) -> Path
```
Export data to Parquet. Requires the optional `pyarrow` dependency.

```python
def to_dicts(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]
```
Return data as a list of dicts (shallow copy passthrough).

---

## IFC Interoperability (`revitpy.ifc`)

### IfcElementMapper

Bidirectional mapping between RevitPy element types and IFC entity types, with custom property map support and type registration.

**Module:** `revitpy.ifc.mapper`

```python
class IfcElementMapper:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `registered_types` | `list[str]` | All registered RevitPy type names |
| `registered_ifc_types` | `list[str]` | All registered IFC entity type names |

**Methods:**

```python
def register_mapping(self, revitpy_type: str, ifc_entity_type: str, property_map: dict[str, str] | None = None, *, bidirectional: bool = True) -> None
```
Register a custom mapping between a RevitPy type and IFC entity type.

```python
def get_mapping(self, revitpy_type: str) -> IfcMapping | None
```
Get the IFC mapping for a RevitPy type.

```python
def get_ifc_type(self, revitpy_type: str) -> str | None
```
Get the IFC entity type name for a RevitPy type.

```python
def get_revitpy_type(self, ifc_entity_type: str) -> str | None
```
Get the RevitPy type name for an IFC entity type.

```python
def to_ifc(self, element: Any, ifc_file: Any, config: IfcExportConfig | None = None) -> Any
```
Convert a RevitPy element to an IFC entity. Requires `ifcopenshell`.

```python
def from_ifc(self, ifc_entity: Any, target_type: str | None = None) -> dict[str, Any]
```
Convert an IFC entity to a dict representation. Consults the reverse registry when `target_type` is not provided.

---

### IfcExporter

Export RevitPy elements to IFC files using ifcopenshell.

**Module:** `revitpy.ifc.exporter`

```python
class IfcExporter:
    def __init__(self, mapper: IfcElementMapper | None = None, config: IfcExportConfig | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `mapper` | `IfcElementMapper` | The element mapper used by this exporter |
| `config` | `IfcExportConfig` | The export configuration |

**Methods:**

```python
def export(self, elements: list[Any], output_path: str | Path, version: IfcVersion = IfcVersion.IFC4) -> Path
```
Export elements to an IFC file. Creates project structure (IfcProject, IfcSite, IfcBuilding) and converts each element via the mapper.

```python
async def export_async(self, elements: list[Any], output_path: str | Path, version: IfcVersion = IfcVersion.IFC4, progress: Callable[[int, int], None] | None = None) -> Path
```
Export elements to an IFC file asynchronously with optional progress reporting.

---

### IfcImporter

Import elements from IFC files and convert them to RevitPy element dictionaries.

**Module:** `revitpy.ifc.importer`

```python
class IfcImporter:
    def __init__(self, mapper: IfcElementMapper | None = None, config: IfcImportConfig | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `mapper` | `IfcElementMapper` | The element mapper used by this importer |
| `config` | `IfcImportConfig` | The import configuration |

**Methods:**

```python
def import_file(self, path: str | Path) -> list[dict[str, Any]]
```
Import elements from an IFC file. Parses the file with ifcopenshell and converts entities via the mapper.

```python
async def import_file_async(self, path: str | Path) -> list[dict[str, Any]]
```
Import elements from an IFC file asynchronously.

---

### IdsValidator

Validate elements against IDS (Information Delivery Specification) requirements by inspecting their properties.

**Module:** `revitpy.ifc.validator`

```python
class IdsValidator:
    def __init__(self) -> None
```

**Methods:**

```python
def validate(self, elements: list[Any], requirements: list[IdsRequirement]) -> list[IdsValidationResult]
```
Validate elements against a list of IDS requirements. Each element is checked against every applicable requirement.

```python
def validate_from_file(self, elements: list[Any], ids_path: str | Path) -> list[IdsValidationResult]
```
Validate elements against requirements loaded from a JSON file.

---

### BcfManager

Create, read, and write BCF (BIM Collaboration Format) issues with simplified BCF 2.1 compatible workflow.

**Module:** `revitpy.ifc.bcf`

```python
class BcfManager:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `issues` | `list[BcfIssue]` | All managed issues |

**Methods:**

```python
def create_issue(self, title: str, description: str = "", *, author: str = "", status: str = "Open", assigned_to: str = "", element_ids: list[str] | None = None) -> BcfIssue
```
Create a new BCF issue and add it to the managed list.

```python
def read_bcf(self, path: str | Path) -> list[BcfIssue]
```
Read BCF issues from a file. Supports `.bcf`/`.bcfzip` ZIP archives and `.json` files.

```python
def write_bcf(self, issues: list[BcfIssue] | None = None, path: str | Path = "issues.bcf") -> Path
```
Write BCF issues to a ZIP archive containing XML `markup.xml` per topic. Defaults to all managed issues.

---

### IfcDiff

Compare two IFC model states and produce a structured diff identifying added, modified, and removed entities.

**Module:** `revitpy.ifc.diff`

```python
class IfcDiff:
    def __init__(self) -> None
```

**Methods:**

```python
def compare(self, old_elements: list[Any], new_elements: list[Any]) -> IfcDiffResult
```
Compare two element lists and return differences. Elements are matched by `id` or `global_id`.

```python
def compare_files(self, old_path: str | Path, new_path: str | Path) -> IfcDiffResult
```
Compare two IFC files and return differences. Both files are imported and compared at the property level.

---

## AI & MCP Server (`revitpy.ai`)

### RevitTools

Registry of tools that can be invoked through the MCP server. Manages tool definitions, validates arguments, dispatches execution, and converts tools to MCP-compatible JSON Schema format.

**Module:** `revitpy.ai.tools`

```python
class RevitTools:
    def __init__(self, context: Any = None) -> None
```

**Methods:**

```python
def register_tool(self, definition: ToolDefinition, handler: Callable) -> None
```
Register a tool with its handler callable.

```python
def get_tool(self, name: str) -> ToolDefinition | None
```
Return the definition of a registered tool, or `None`.

```python
def list_tools(self) -> list[ToolDefinition]
```
Return all registered tool definitions.

```python
def execute_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult
```
Execute a tool by name. Validates required parameters, invokes the handler, and wraps the outcome in a `ToolResult`.

```python
def to_mcp_tool_list(self) -> list[dict[str, Any]]
```
Convert all tools to MCP-format JSON Schema definitions.

---

### SafetyGuard

Validates tool calls against a safety policy. Supports `READ_ONLY`, `CAUTIOUS`, and permissive modes, and provides an undo stack for rollback.

**Module:** `revitpy.ai.safety`

```python
class SafetyGuard:
    def __init__(self, config: SafetyConfig | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `config` | `SafetyConfig` | The active safety configuration |

**Methods:**

```python
def validate_tool_call(self, tool: ToolDefinition, arguments: dict[str, Any]) -> bool
```
Check whether a tool call is allowed under the current policy. Raises `SafetyViolationError` when blocked.

```python
def preview_changes(self, tool: ToolDefinition, arguments: dict[str, Any]) -> dict[str, Any]
```
Return a dry-run preview of the changes a tool call would make.

```python
def push_undo(self, operation: dict[str, Any]) -> None
```
Push an operation onto the undo stack (bounded by `SafetyConfig.max_undo_stack`).

```python
def undo_last(self) -> dict[str, Any] | None
```
Pop and return the most recent undo entry, or `None`.

```python
def get_undo_stack(self) -> list[dict[str, Any]]
```
Return a copy of the current undo stack.

---

### PromptLibrary

Manages and renders Jinja2 prompt templates for LLM interactions within the MCP server. Built-in templates are registered at construction time.

**Module:** `revitpy.ai.prompts`

```python
class PromptLibrary:
    def __init__(self) -> None
```

**Methods:**

```python
def render(self, template_name: str, /, **kwargs: Any) -> str
```
Render a template by name. Raises `PromptError` if the template does not exist or rendering fails.

```python
def register_template(self, name: str, template: str) -> None
```
Register or overwrite a Jinja2 template.

```python
def get_template(self, name: str) -> str | None
```
Return the raw source of a template, or `None`.

```python
def list_templates(self) -> list[str]
```
Return sorted list of all template names.

```python
def to_mcp_prompts_list(self) -> list[dict[str, Any]]
```
Convert templates to MCP-format prompt definitions.

---

### McpServer

Asynchronous WebSocket server implementing a subset of the Model Context Protocol, exposing tools, prompts, and safety controls.

**Module:** `revitpy.ai.server`

```python
class McpServer:
    def __init__(self, tools: RevitTools, *, config: McpServerConfig | None = None, safety_guard: SafetyGuard | None = None, prompt_library: PromptLibrary | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `config` | `McpServerConfig` | The active server configuration |
| `connections` | `set[Any]` | Set of active WebSocket connections |

**Methods:**

```python
async def start(self) -> None
```
Start the WebSocket server on the configured host and port.

```python
async def stop(self, timeout: float = 5.0) -> None
```
Gracefully stop the server. Waits up to `timeout` seconds for connections to close.

Supports async context manager protocol (`async with McpServer(...) as server:`).

---

## Sustainability (`revitpy.sustainability`)

### CarbonCalculator

Calculate embodied carbon for building materials using EPD database lookups. Supports mass-based and volume-based calculation methods.

**Module:** `revitpy.sustainability.carbon`

```python
class CarbonCalculator:
    def __init__(self, epd_database: EpdDatabase | None = None) -> None
```

**Methods:**

```python
def calculate(self, materials: list[MaterialData], lifecycle_stages: list[LifecycleStage] | None = None) -> list[CarbonResult]
```
Calculate embodied carbon for a list of materials. Defaults to A1-A3 lifecycle stages. Looks up EPD records and computes carbon as `mass * gwp_per_kg` or `volume * gwp_per_m3`.

```python
def summarize(self, results: list[CarbonResult]) -> BuildingCarbonSummary
```
Aggregate carbon results into a building-level summary with totals by material, system, level, and lifecycle stage.

```python
def benchmark(self, summary: BuildingCarbonSummary, building_area_m2: float, building_type: str = "default") -> CarbonBenchmark
```
Benchmark building carbon against RIBA 2030 Climate Challenge targets. Returns rating (Excellent, Good, Acceptable, Below Average, Poor).

```python
async def calculate_async(self, materials: list[MaterialData], lifecycle_stages: list[LifecycleStage] | None = None, progress: Callable[[int, int], None] | None = None) -> list[CarbonResult]
```
Asynchronously calculate embodied carbon with optional progress callback `(completed, total)`.

---

### EpdDatabase

Environmental Product Declaration database with local cache, generic fallback values, and optional EC3 API integration.

**Module:** `revitpy.sustainability.epd`

```python
class EpdDatabase:
    def __init__(self, *, api_token: str | None = None, cache_path: Path | str | None = None) -> None
```

**Methods:**

```python
def lookup(self, material_name: str, category: str | None = None) -> EpdRecord | None
```
Look up an EPD record for a material. Searches exact cache match, fuzzy keyword match, then category-based generic fallback.

```python
async def lookup_async(self, material_name: str, category: str | None = None) -> EpdRecord | None
```
Asynchronously look up an EPD record, querying the EC3 API when a token is configured and local cache misses.

```python
async def search_async(self, query: str, limit: int = 10) -> list[EpdRecord]
```
Search for EPD records matching a query. Searches local cache and optionally the EC3 API.

```python
def get_generic_epd(self, material_category: str) -> EpdRecord | None
```
Get a generic EPD record for a material category (e.g. `"Concrete"`, `"Metals"`).

```python
def load_cache(self, path: Path | str) -> None
```
Load cached EPD records from a JSON file.

```python
def save_cache(self, path: Path | str) -> None
```
Save cached EPD records to a JSON file.

---

### ComplianceChecker

Check building data against emissions compliance standards including NYC LL97, Boston BERDO, EU EPBD, and ASHRAE 90.1.

**Module:** `revitpy.sustainability.compliance`

```python
class ComplianceChecker:
    def __init__(self) -> None
```

**Methods:**

```python
def check(self, standard: ComplianceStandard, building_data: dict) -> ComplianceResult
```
Check compliance against a specific standard. Dispatches to the standard-specific checker. Required keys in `building_data` vary by standard.

```python
def check_ll97(self, building_data: dict) -> ComplianceResult
```
Check NYC Local Law 97 compliance. Requires `area_sqft` and `annual_emissions_tco2e`.

```python
def check_berdo(self, building_data: dict) -> ComplianceResult
```
Check Boston BERDO compliance. Requires `area_sqft` and `annual_emissions_kgco2e`.

```python
def check_epbd(self, building_data: dict) -> ComplianceResult
```
Check EU EPBD compliance. Requires `area_m2` and `primary_energy_kwh`.

```python
def check_ashrae(self, envelope_data: EnergyEnvelopeData) -> ComplianceResult
```
Check ASHRAE 90.1 envelope compliance (wall R-value, roof R-value, window U-value, glazing ratio) for climate zone 4A.

```python
def get_recommendations(self, result: ComplianceResult) -> list[str]
```
Get improvement recommendations based on a compliance result.

---

### SustainabilityReporter

Generate sustainability assessment reports in JSON, CSV, and HTML formats, and produce certification documentation for LEED, BREEAM, DGNB, and Green Star.

**Module:** `revitpy.sustainability.reports`

```python
class SustainabilityReporter:
    def __init__(self) -> None
```

**Methods:**

```python
def generate(self, summary: BuildingCarbonSummary, format: ReportFormat = ReportFormat.JSON, output_path: str | Path | None = None) -> str | Path
```
Generate a sustainability report. Returns content as a string when `output_path` is `None`, or the output `Path` when written to disk.

```python
def to_json(self, summary: BuildingCarbonSummary, path: str | Path | None = None) -> str | Path
```
Generate a JSON sustainability report.

```python
def to_csv(self, summary: BuildingCarbonSummary, path: str | Path | None = None) -> str | Path
```
Generate a CSV sustainability report with material rows, carbon values, and percentages.

```python
def to_html(self, summary: BuildingCarbonSummary, path: str | Path | None = None) -> str | Path
```
Generate an HTML sustainability report. Uses Jinja2 if available, otherwise falls back to string formatting.

```python
def generate_certification_docs(self, summary: BuildingCarbonSummary, system: CertificationSystem) -> dict
```
Generate certification documentation helpers for a given rating system (LEED, BREEAM, DGNB, Green Star). Returns a dict with certification-specific credit sections.

---

## Speckle Interop (`revitpy.interop`)

### SpeckleTypeMapper

Bidirectional mapping between RevitPy element types and Speckle object types, with custom property maps and type registration.

**Module:** `revitpy.interop.mapper`

```python
class SpeckleTypeMapper:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `registered_types` | `list[str]` | All registered RevitPy type names |
| `registered_speckle_types` | `list[str]` | All registered Speckle type identifiers |

**Methods:**

```python
def register_mapping(self, revitpy_type: str, speckle_type: str, property_map: dict[str, str] | None = None) -> None
```
Register a custom mapping between a RevitPy type and Speckle type.

```python
def get_mapping(self, revitpy_type: str) -> TypeMapping | None
```
Get the Speckle mapping for a RevitPy type.

```python
def to_speckle(self, element: Any) -> dict[str, Any]
```
Convert a RevitPy element to a Speckle-compatible dict. Raises `TypeMappingError` if the element type is not mapped.

```python
def from_speckle(self, speckle_obj: dict[str, Any], target_type: str | None = None) -> dict[str, Any]
```
Convert a Speckle object dict back to a RevitPy-compatible dict. Consults the reverse registry when `target_type` is not provided.

```python
def get_unmapped_status(self, revitpy_type: str) -> TypeMapping
```
Return a `TypeMapping` with `MappingStatus.UNMAPPED` for an unregistered type.

---

### SpeckleClient

Async HTTP client for the Speckle GraphQL API. Uses `httpx.AsyncClient` for transport and optionally leverages `specklepy`.

**Module:** `revitpy.interop.client`

```python
class SpeckleClient:
    def __init__(self, config: SpeckleConfig | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_connected` | `bool` | Whether the client has successfully connected |
| `config` | `SpeckleConfig` | The current server configuration |

**Methods:**

```python
async def connect(self) -> None
```
Validate the connection to the Speckle server by sending a `serverInfo` query.

```python
async def get_streams(self) -> list[dict[str, Any]]
```
Return a list of streams visible to the authenticated user.

```python
async def get_stream(self, stream_id: str) -> dict[str, Any]
```
Return details of a single stream.

```python
async def get_branches(self, stream_id: str) -> list[dict[str, Any]]
```
Return the branches of a stream.

```python
async def get_commits(self, stream_id: str, branch: str = "main", limit: int = 10) -> list[SpeckleCommit]
```
Return recent commits on a branch.

```python
async def send_objects(self, stream_id: str, objects: list[dict[str, Any]], branch: str = "main", message: str = "") -> SpeckleCommit
```
Send objects to a Speckle stream and create a commit.

```python
async def receive_objects(self, stream_id: str, commit_id: str | None = None, branch: str = "main") -> list[dict[str, Any]]
```
Receive objects from a Speckle stream. Uses the latest commit when `commit_id` is `None`.

```python
async def close(self) -> None
```
Close the underlying HTTP client.

---

### SpeckleSync

High-level synchronisation between RevitPy and Speckle, with push, pull, and bidirectional sync operations.

**Module:** `revitpy.interop.sync`

```python
class SpeckleSync:
    def __init__(self, client: SpeckleClient, mapper: SpeckleTypeMapper | None = None, change_tracker: Any | None = None) -> None
```

**Methods:**

```python
async def push(self, elements: list[Any], stream_id: str, branch: str = "main", message: str = "") -> SyncResult
```
Push local elements to a Speckle stream. Maps each element via the mapper and sends through the client.

```python
async def pull(self, stream_id: str, branch: str = "main", commit_id: str | None = None) -> list[dict[str, Any]]
```
Pull objects from a Speckle stream and map them back to RevitPy-compatible dicts.

```python
async def sync(self, elements: list[Any], stream_id: str, mode: SyncMode = SyncMode.INCREMENTAL, direction: SyncDirection = SyncDirection.BIDIRECTIONAL) -> SyncResult
```
Run a full sync operation. Direction controls whether elements are pushed, pulled, or both. Mode controls whether all or only changed elements are synced.

---

### SpeckleDiff

Compare local and remote element sets to produce diff entries describing additions, modifications, and removals at the property level.

**Module:** `revitpy.interop.diff`

```python
class SpeckleDiff:
    def __init__(self) -> None
```

**Methods:**

```python
def compare(self, local_elements: list[dict[str, Any]], remote_elements: list[dict[str, Any]]) -> list[DiffEntry]
```
Compare local and remote element dicts and return diffs. Elements are matched by their `id` key.

```python
def has_changes(self, local_elements: list[dict[str, Any]], remote_elements: list[dict[str, Any]]) -> bool
```
Return whether any differences exist between the two sets.

---

### SpeckleMerge

Merge local and remote element sets according to a configurable conflict resolution strategy (`LOCAL_WINS`, `REMOTE_WINS`, or `MANUAL`).

**Module:** `revitpy.interop.merge`

```python
class SpeckleMerge:
    def __init__(self, resolution: ConflictResolution = ConflictResolution.LOCAL_WINS) -> None
```

**Methods:**

```python
def merge(self, local_elements: list[dict[str, Any]], remote_elements: list[dict[str, Any]], diff_entries: list[DiffEntry] | None = None) -> MergeResult
```
Merge local and remote elements. Computes the diff automatically when `diff_entries` is `None`. Raises `MergeConflictError` when using `MANUAL` resolution with unresolved conflicts.

```python
def resolve_conflicts(self, conflicts: list[DiffEntry], strategy: ConflictResolution) -> list[dict[str, Any]]
```
Resolve a list of conflict entries using the given strategy. Returns list of resolved property dicts.

---

## Cloud & Design Automation (`revitpy.cloud`)

### ApsAuthenticator

OAuth2 client-credentials authentication for Autodesk Platform Services, with token caching and automatic refresh.

**Module:** `revitpy.cloud.auth`

```python
class ApsAuthenticator:
    def __init__(self, credentials: ApsCredentials) -> None
```

**Methods:**

```python
async def authenticate(self) -> ApsToken
```
Perform a fresh OAuth2 client-credentials authentication against the APS token endpoint.

```python
async def get_token(self) -> ApsToken
```
Return a cached token, refreshing it if expired or not yet obtained.

```python
def is_token_valid(self) -> bool
```
Check whether the cached token is still valid (uses a 60-second buffer before expiry).

---

### ApsClient

Authenticated HTTP client for the APS API with sliding-window rate limiting (20 req/s) and exponential-backoff retry on transient failures.

**Module:** `revitpy.cloud.client`

```python
class ApsClient:
    def __init__(self, authenticator: ApsAuthenticator, *, region: CloudRegion = CloudRegion.US) -> None
```

**Methods:**

```python
async def request(self, method: str, endpoint: str, **kwargs: Any) -> dict
```
Make an authenticated HTTP request with retry and rate limiting. Automatically injects Bearer token.

```python
async def get(self, endpoint: str, **kwargs: Any) -> dict
```
Perform an authenticated GET request.

```python
async def post(self, endpoint: str, **kwargs: Any) -> dict
```
Perform an authenticated POST request.

```python
async def delete(self, endpoint: str, **kwargs: Any) -> dict
```
Perform an authenticated DELETE request.

---

### JobManager

Manages Design Automation work items through the APS API: submit, poll, download results, cancel, and retrieve logs.

**Module:** `revitpy.cloud.jobs`

```python
class JobManager:
    def __init__(self, client: ApsClient) -> None
```

**Methods:**

```python
async def submit(self, config: JobConfig) -> str
```
Submit a new Design Automation work item. Returns the `job_id`.

```python
async def get_status(self, job_id: str) -> JobStatus
```
Get the current status of a work item.

```python
async def wait_for_completion(self, job_id: str, timeout: float = 600.0, poll_interval: float = 5.0) -> JobResult
```
Poll a work item until it reaches a terminal state. Raises `JobExecutionError` on failure or timeout.

```python
async def download_results(self, job_id: str, output_dir: Path) -> list[Path]
```
Download output files for a completed work item to a local directory.

```python
async def cancel(self, job_id: str) -> bool
```
Cancel a running work item. Returns `True` if cancellation succeeded.

```python
async def get_logs(self, job_id: str) -> str
```
Retrieve execution logs for a work item.

---

### BatchProcessor

Process multiple Design Automation jobs concurrently with bounded parallelism, automatic retry, and optional progress/cancellation callbacks.

**Module:** `revitpy.cloud.batch`

```python
class BatchProcessor:
    def __init__(self, job_manager: JobManager, *, config: BatchConfig | None = None) -> None
```

**Methods:**

```python
async def process(self, jobs: list[JobConfig], progress: Callable[[int, int], Any] | None = None, cancel: asyncio.Event | None = None) -> BatchResult
```
Process a list of jobs with bounded concurrency. Reports progress via callback `(completed, total)`. Stops submitting new jobs when the `cancel` event is set.

```python
async def process_directory(self, input_dir: Path, script_path: Path, *, activity_id: str = "RevitPy.Validate+prod", **kwargs: Any) -> BatchResult
```
Create and process jobs for every `.rvt` file in a directory.

---

### CIHelper

Generate CI/CD pipeline configurations for GitHub Actions and GitLab CI.

**Module:** `revitpy.cloud.ci`

```python
class CIHelper:
    def __init__(self) -> None
```

**Methods:**

```python
def generate_github_workflow(self, name: str = "revitpy-validation", script_path: str = "validate.py", revit_version: str = "2024", *, branches: str = "main", runner: str = "ubuntu-latest", python_version: str = "3.11") -> str
```
Generate a GitHub Actions workflow YAML string.

```python
def generate_gitlab_ci(self, name: str = "revitpy-validation", script_path: str = "validate.py", revit_version: str = "2024", *, python_version: str = "3.11") -> str
```
Generate a GitLab CI pipeline YAML string.

```python
def save_workflow(self, content: str, output_path: str | Path) -> Path
```
Write a workflow/pipeline configuration to disk.

---

### WebhookHandler

Receive, verify (HMAC-SHA256), and route APS Design Automation webhook events to registered callbacks.

**Module:** `revitpy.cloud.webhooks`

```python
class WebhookHandler:
    def __init__(self, config: WebhookConfig | None = None) -> None
```

**Methods:**

```python
def verify_signature(self, payload: bytes, signature: str) -> bool
```
Verify HMAC-SHA256 signature of an incoming webhook payload. Raises `WebhookError` if no secret is configured.

```python
def handle_event(self, event_data: dict[str, Any]) -> WebhookEvent
```
Parse an incoming webhook payload and dispatch to registered callbacks. Returns the parsed `WebhookEvent`.

```python
def register_callback(self, event_type: str, callback: Callable) -> None
```
Register a callback for a specific event type. Use `"*"` to listen for all event types.
