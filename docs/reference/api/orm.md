---
layout: api
title: ORM Layer
description: High-level ORM context for querying, change tracking, caching, and relationship management
---

# ORM Layer

The ORM layer provides a high-level context for working with Revit elements using LINQ-style queries, automatic change tracking, intelligent caching, relationship navigation, and transaction management.

**Module:** `revitpy.orm.context`

---

## ContextConfiguration

Configuration dataclass for `RevitContext`.

### Constructor

```python
ContextConfiguration(
    auto_track_changes: bool = True,
    cache_policy: CachePolicy = CachePolicy.MEMORY,
    cache_max_size: int = 10000,
    cache_max_memory_mb: int = 500,
    lazy_loading_enabled: bool = True,
    batch_size: int = 100,
    thread_safe: bool = True,
    validation_enabled: bool = True,
    performance_monitoring: bool = True
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `auto_track_changes` | `bool` | `True` | Automatically track entity changes. |
| `cache_policy` | `CachePolicy` | `CachePolicy.MEMORY` | Caching strategy (`NONE`, `MEMORY`). |
| `cache_max_size` | `int` | `10000` | Maximum number of cached entities. |
| `cache_max_memory_mb` | `int` | `500` | Maximum cache memory in megabytes. |
| `lazy_loading_enabled` | `bool` | `True` | Enable lazy loading of relationships. |
| `batch_size` | `int` | `100` | Default batch size for bulk operations. |
| `thread_safe` | `bool` | `True` | Enable thread-safe locking. |
| `validation_enabled` | `bool` | `True` | Enable validation on entity operations. |
| `performance_monitoring` | `bool` | `True` | Enable cache and performance statistics. |

---

## RevitContext

Main ORM context that orchestrates querying, change tracking, caching, relationships, and transactions. Supports both sync and async workflows.

### Constructor

```python
RevitContext(
    provider: IElementProvider,
    *,
    config: ContextConfiguration | None = None,
    cache_manager: CacheManager | None = None,
    change_tracker: ChangeTracker | None = None,
    relationship_manager: RelationshipManager | None = None,
    unit_of_work: IUnitOfWork | None = None
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | `IElementProvider` | The element data source. |
| `config` | `ContextConfiguration` or `None` | Configuration. Uses defaults if `None`. |
| `cache_manager` | `CacheManager` or `None` | Custom cache manager. Auto-created if `None`. |
| `change_tracker` | `ChangeTracker` or `None` | Custom change tracker. Auto-created if `None`. |
| `relationship_manager` | `RelationshipManager` or `None` | Custom relationship manager. |
| `unit_of_work` | `IUnitOfWork` or `None` | Unit of work for persisting changes. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_disposed` | `bool` | Whether the context has been disposed. |
| `has_changes` | `bool` | Whether there are pending tracked changes. |
| `change_count` | `int` | Number of pending changes. |
| `cache_statistics` | `Any` or `None` | Cache hit/miss statistics (if monitoring is enabled). |

### Query Methods

#### `query(element_type=None)`

Creates a new `QueryBuilder` for the given element type.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element_type` | `type[T]` or `None` | Optional element type filter. |

**Returns:** `QueryBuilder[T]`

```python
walls = ctx.query(Wall).equals("Category", "Walls").to_list()
```

#### `all(element_type)`

Returns all elements of the specified type as an `ElementSet`. Results are cached per type.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element_type` | `type[T]` | Element type to retrieve. |

**Returns:** `ElementSet[T]`

```python
all_walls = ctx.all(Wall)
```

#### `where(element_type, predicate)`

Queries elements of the given type filtered by a predicate.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element_type` | `type[T]` | Element type. |
| `predicate` | `Callable[[T], bool]` | Filter function. |

**Returns:** `ElementSet[T]`

```python
tall_walls = ctx.where(Wall, lambda w: w.get_parameter_value("Height") > 10.0)
```

#### `first(element_type, predicate=None)`

Returns the first element of the specified type, optionally matching a predicate.

**Returns:** `T`

**Raises:** `ElementNotFoundError` if no elements match.

#### `first_or_default(element_type, predicate=None, default=None)`

Returns the first matching element or a default value.

**Returns:** `T` or `None`

#### `single(element_type, predicate=None)`

Returns the single matching element.

**Raises:** `ElementNotFoundError` if none found. `ValidationError` if more than one match.

#### `count(element_type, predicate=None)`

Returns the count of matching elements.

**Returns:** `int`

#### `any(element_type, predicate=None)`

Returns `True` if any elements match.

**Returns:** `bool`

#### `get_by_id(element_type, element_id)`

Gets an element by ID, checking the cache first. Automatically attaches it for change tracking.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element_type` | `type[T]` | Element type. |
| `element_id` | `ElementId` | The element ID to look up. |

**Returns:** `T` or `None`

**Raises:** `ORMException` if the lookup fails.

### Change Tracking Methods

#### `attach(entity, entity_id=None)`

Attaches an entity to the context for change tracking.

| Parameter | Type | Description |
|-----------|------|-------------|
| `entity` | `T` | Entity to attach. |
| `entity_id` | `ElementId` or `None` | Optional ID. Inferred from entity if `None`. |

#### `detach(entity)`

Detaches an entity from change tracking.

#### `add(entity)`

Marks an entity as newly added.

#### `remove(entity)`

Marks an entity as deleted.

#### `get_entity_state(entity)`

Returns the current tracking state of an entity.

**Returns:** `ElementState` -- One of `ADDED`, `MODIFIED`, `DELETED`, `UNCHANGED`, `DETACHED`.

#### `accept_changes(entity=None)`

Accepts changes for a specific entity or all entities, resetting their state to `UNCHANGED`.

#### `reject_changes(entity=None)`

Rejects changes for a specific entity or all entities, reverting modifications.

#### `save_changes()`

Saves all pending changes through the unit of work. Processes added, modified, and deleted entities, then accepts all changes and invalidates affected cache entries.

**Returns:** `int` -- Number of changes saved.

**Raises:** `ORMException` if saving fails (automatically attempts rollback).

```python
ctx.add(new_element)
existing_element.set_parameter_value("Comments", "Updated")
ctx.remove(old_element)

count = ctx.save_changes()
print(f"Saved {count} changes")
```

### Relationship Methods

#### `load_relationship(entity, relationship_name, strategy=LoadStrategy.LAZY)`

Loads relationship data for an entity.

| Parameter | Type | Description |
|-----------|------|-------------|
| `entity` | `T` | Source entity. |
| `relationship_name` | `str` | Name of the relationship to load. |
| `strategy` | `LoadStrategy` | Loading strategy (`LAZY` or `EAGER`). Default `LAZY`. |

**Returns:** Related entity, list of entities, or `None`.

**Raises:** `RelationshipError` if no relationship manager is configured.

#### `configure_relationship(source_type, relationship_name, target_type, **kwargs)`

Configures a relationship between two entity types. Creates the relationship manager if needed.

### Transaction Support

#### `transaction(auto_commit=True)`

Creates a context manager for transactional operations. On successful exit with `auto_commit=True`, pending changes are saved. On exception, changes are rejected.

| Parameter | Type | Description |
|-----------|------|-------------|
| `auto_commit` | `bool` | Auto-save changes on success. Default `True`. |

```python
with ctx.transaction(auto_commit=True):
    element.set_parameter_value("Comments", "Updated in transaction")
    # auto-saves on exit; rolls back on exception
```

### Async Interface

#### `as_async()`

Returns an `AsyncRevitContext` wrapping this context's components.

**Returns:** `AsyncRevitContext`

```python
async_ctx = ctx.as_async()
```

### Cache Management

#### `clear_cache()`

Clears all cached data and entity sets.

#### `invalidate_cache(entity_type=None, entity_id=None)`

Invalidates specific cache entries or all entries.

| Parameter | Type | Description |
|-----------|------|-------------|
| `entity_type` | `type` or `None` | Entity type to invalidate. `None` for all. |
| `entity_id` | `ElementId` or `None` | Specific entity ID. |

### Disposal

#### `dispose()`

Disposes the context. Rejects pending changes, clears the change tracker and cache. After disposal, all operations raise `ORMException`.

### Context Manager

```python
with RevitContext(provider, config=config) as ctx:
    walls = ctx.all(Wall).to_list()
    for wall in walls:
        wall.set_parameter_value("Mark", "A-101")
    ctx.save_changes()
# dispose() called on exit
```

---

## Factory Functions

**Module:** `revitpy.orm.context`

```python
from revitpy.orm.context import create_context, create_async_context

# Create a sync context
ctx = create_context(provider, config=config)

# Create an async context
async_ctx = create_async_context(provider, config=config)
```

---

## Usage Examples

### Querying with Change Tracking

```python
from revitpy.orm.context import RevitContext, ContextConfiguration

config = ContextConfiguration(
    auto_track_changes=True,
    cache_policy=CachePolicy.MEMORY,
)

with RevitContext(provider, config=config) as ctx:
    # Query elements
    walls = ctx.where(Wall, lambda w: w.get_parameter_value("Height") > 10.0)

    # Modify elements (changes are tracked automatically)
    for wall in walls.to_list():
        wall.set_parameter_value("Comments", "Tall wall")

    # Save all tracked changes
    count = ctx.save_changes()
    print(f"Saved {count} changes")
```

### Entity Lifecycle Management

```python
with RevitContext(provider) as ctx:
    # Look up by ID
    element = ctx.get_by_id(Wall, element_id)

    # Check state
    state = ctx.get_entity_state(element)
    print(f"State: {state}")

    # Modify
    element.set_parameter_value("Mark", "B-202")
    print(f"Has changes: {ctx.has_changes}")  # True

    # Accept or reject
    ctx.accept_changes(element)
    # ctx.reject_changes(element)  # to undo
```

### Transaction with Rollback

```python
with RevitContext(provider) as ctx:
    try:
        with ctx.transaction(auto_commit=True):
            element = ctx.get_by_id(Wall, wall_id)
            element.set_parameter_value("Height", new_height)
            # If this block exits normally, changes are saved
            # If an exception occurs, changes are rejected
    except ORMException as e:
        print(f"Transaction failed: {e}")
```

### Cache Management

```python
with RevitContext(provider) as ctx:
    # First query -- hits the provider
    walls = ctx.all(Wall).to_list()

    # Second query for same type -- uses cached ElementSet
    walls_again = ctx.all(Wall).to_list()

    # Invalidate cache for a specific type
    ctx.invalidate_cache(entity_type=Wall)

    # Clear all caches
    ctx.clear_cache()

    # View cache statistics
    stats = ctx.cache_statistics
    if stats:
        print(f"Cache stats: {stats}")
```

---

## Best Practices

1. **Use the context manager** -- Ensures `dispose()` is called and pending changes are cleaned up.
2. **Enable change tracking for write workflows** -- Set `auto_track_changes=True` and call `save_changes()` to persist.
3. **Use transactions for multi-step operations** -- The `transaction()` context manager auto-commits or rolls back.
4. **Invalidate cache after external modifications** -- If data changes outside the context, call `invalidate_cache()`.
5. **Prefer `get_by_id()` for single lookups** -- It checks the cache first for better performance.
6. **Keep contexts short-lived** -- Dispose contexts when done to free resources.

---

## Next Steps

- **[Query API]({{ '/reference/api/query/' | relative_url }})**: The `QueryBuilder` used by `RevitContext.query()`
- **[Element API]({{ '/reference/api/element-api/' | relative_url }})**: `Element` and `ElementSet` classes
- **[Transaction API]({{ '/reference/api/transaction-api/' | relative_url }})**: Lower-level transaction management
- **[Async Support]({{ '/reference/api/async/' | relative_url }})**: Async operations and `AsyncRevitContext`
