---
layout: page
title: ORM
description: Guide to the RevitPy ORM layer with RevitContext, intelligent caching, change tracking, relationship management, streaming queries, and async support.
doc_tier: user
---

# ORM

RevitPy includes an ORM (Object-Relational Mapping) layer that provides change tracking, intelligent caching, relationship management, and both synchronous and asynchronous query execution. The central class is `RevitContext`.

## RevitContext

`RevitContext` is the main ORM context. It coordinates querying, change tracking, caching, and relationships.

### Creating a Context

```python
from revitpy.orm.context import RevitContext, ContextConfiguration, create_context

# With defaults
context = create_context(provider)

# With custom configuration
config = ContextConfiguration(
    auto_track_changes=True,
    cache_policy=CachePolicy.MEMORY,
    cache_max_size=10000,
    cache_max_memory_mb=500,
    lazy_loading_enabled=True,
    batch_size=100,
    thread_safe=True,
    validation_enabled=True,
    performance_monitoring=True,
)
context = RevitContext(provider, config=config)
```

`RevitContext` is a context manager. When the `with` block exits, the context is disposed:

```python
with RevitContext(provider) as ctx:
    # work with the context
pass  # ctx.dispose() is called automatically
```

### ContextConfiguration Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `auto_track_changes` | `bool` | `True` | Automatically track changes to attached entities |
| `cache_policy` | `CachePolicy` | `CachePolicy.MEMORY` | Caching strategy |
| `cache_max_size` | `int` | `10000` | Maximum number of cached entries |
| `cache_max_memory_mb` | `int` | `500` | Maximum cache memory in MB |
| `lazy_loading_enabled` | `bool` | `True` | Enable lazy loading of relationships |
| `batch_size` | `int` | `100` | Batch size for bulk operations |
| `thread_safe` | `bool` | `True` | Enable thread-safe operations |
| `validation_enabled` | `bool` | `True` | Enable entity validation |
| `performance_monitoring` | `bool` | `True` | Enable performance statistics |

## Querying with the ORM QueryBuilder

The ORM has its own `QueryBuilder` (in `revitpy.orm.query_builder`) that provides lazy evaluation, query optimization, async execution, and caching.

### Creating Queries

```python
# Query all elements
results = context.query().to_list()

# Query by type
results = context.query(WallElement).to_list()

# Get all elements of a type as an ElementSet
walls = context.all(WallElement)
```

### Fluent Query Methods

The ORM `QueryBuilder` uses predicate functions instead of property-name-based filters:

```python
# Filter with a predicate
tall_walls = (
    context.query(WallElement)
    .where(lambda w: w.get_parameter_value("Height") > 3.0)
    .to_list()
)

# Project with a selector
names = (
    context.query(WallElement)
    .select(lambda w: w.name)
    .to_list()
)

# Sort
sorted_walls = (
    context.query(WallElement)
    .order_by(lambda w: w.name)
    .to_list()
)

# Sort descending
sorted_desc = (
    context.query(WallElement)
    .order_by_descending(lambda w: w.get_parameter_value("Height"))
    .to_list()
)

# Pagination
page = (
    context.query(WallElement)
    .skip(20)
    .take(10)
    .to_list()
)

# Distinct
unique = (
    context.query(WallElement)
    .distinct(lambda w: w.get_parameter_value("Type"))
    .to_list()
)
```

### Terminal Operations (Synchronous)

| Method | Returns | Description |
|---|---|---|
| `to_list()` | `list[T]` | Execute query and return results as a list |
| `first(predicate=None)` | `T` | First matching element (raises `QueryError` if empty) |
| `first_or_default(predicate=None, default=None)` | `T` or `None` | First matching element or default |
| `single(predicate=None)` | `T` | Single matching element (raises on 0 or >1) |
| `single_or_default(predicate=None, default=None)` | `T` or `None` | Single matching element or default |
| `count(predicate=None)` | `int` | Count of matching elements |
| `any(predicate=None)` | `bool` | True if any elements match |
| `all(predicate)` | `bool` | True if all elements match |
| `to_dict(key_selector)` | `dict[Any, T]` | Results as a dictionary |
| `group_by(key_selector)` | `dict[Any, list[T]]` | Grouped results |

### Terminal Operations (Asynchronous)

| Method | Returns | Description |
|---|---|---|
| `to_list_async()` | `list[T]` | Async execute and return list |
| `first_async(predicate=None)` | `T` | Async first element |
| `first_or_default_async(predicate=None, default=None)` | `T` or `None` | Async first or default |
| `single_async(predicate=None)` | `T` | Async single element |
| `count_async(predicate=None)` | `int` | Async count |
| `any_async(predicate=None)` | `bool` | Async any check |
| `to_dict_async(key_selector)` | `dict[Any, T]` | Async dictionary |

### Streaming Queries

For large datasets, convert a query to a streaming query:

```python
streaming = context.query(WallElement).as_streaming(batch_size=100)

async for batch in streaming:
    for element in batch:
        process(element)

# Or collect all into a list
all_results = await streaming.to_list_async()
```

### Convenience Methods on RevitContext

`RevitContext` also provides shortcut query methods:

```python
# Get all elements of a type
walls = context.all(WallElement)

# Filter with a predicate
tall = context.where(WallElement, lambda w: w.height > 3.0)

# Get first
wall = context.first(WallElement)
wall = context.first(WallElement, lambda w: w.name == "Wall-1")

# Get first or default
wall = context.first_or_default(WallElement, default=None)

# Get single
wall = context.single(WallElement)

# Count
total = context.count(WallElement)
filtered = context.count(WallElement, lambda w: w.height > 3.0)

# Check existence
exists = context.any(WallElement)

# Get by ID
wall = context.get_by_id(WallElement, element_id)
```

## Change Tracking

When `auto_track_changes` is enabled (the default), entities retrieved through the context are automatically tracked. The context monitors which entities have been added, modified, or deleted.

### Entity States

The `ElementState` enum defines the possible states:

| State | Description |
|---|---|
| `UNCHANGED` | Entity has not been modified since it was attached |
| `ADDED` | Entity has been marked as new |
| `MODIFIED` | Entity has changes pending |
| `DELETED` | Entity has been marked for deletion |
| `DETACHED` | Entity is not tracked by the context |

### Tracking Operations

```python
# Attach an entity to the context for tracking
context.attach(entity, entity_id=some_id)

# Detach from tracking
context.detach(entity)

# Mark as added (new entity)
context.add(entity)

# Mark as deleted
context.remove(entity)

# Check entity state
state = context.get_entity_state(entity)

# Accept changes (mark current state as baseline)
context.accept_changes(entity)  # For one entity
context.accept_changes()        # For all entities

# Reject changes (revert to baseline)
context.reject_changes(entity)
context.reject_changes()
```

### Saving Changes

Call `save_changes()` to persist all pending changes:

```python
with RevitContext(provider) as ctx:
    wall = ctx.get_by_id(WallElement, wall_id)
    # ... modify wall ...
    ctx.add(new_element)
    ctx.remove(old_element)

    changes_saved = ctx.save_changes()
    print(f"Saved {changes_saved} changes")
```

`save_changes()` returns the number of changes persisted. If there are no pending changes, it returns `0`.

### Context Properties

- `context.has_changes` -- `True` if there are pending changes.
- `context.change_count` -- Number of pending changes.

## Transactions

`RevitContext` provides a transaction context manager that integrates with change tracking:

```python
with context.transaction(auto_commit=True):
    # Perform operations
    context.add(new_entity)
    # If auto_commit is True and there are changes, save_changes() is called.
    # On exception, reject_changes() is called automatically.
```

## Caching

The ORM layer uses intelligent caching to reduce redundant Revit API calls.

### CacheConfiguration

The `CacheConfiguration` dataclass controls cache behavior:

| Field | Type | Default | Description |
|---|---|---|---|
| `max_size` | `int` | `10000` | Maximum number of cached entries |
| `max_memory_mb` | `int` | `500` | Maximum memory in MB |
| `default_ttl_seconds` | `int` or `None` | `3600` | Default time-to-live (1 hour) |
| `eviction_policy` | `EvictionPolicy` | `EvictionPolicy.LRU` | Eviction strategy |
| `enable_statistics` | `bool` | `True` | Enable hit/miss tracking |
| `cleanup_interval_seconds` | `int` | `300` | Interval for cleanup (5 minutes) |
| `compression_enabled` | `bool` | `False` | Enable data compression |
| `thread_safe` | `bool` | `True` | Thread-safe operations |

### Cache Policies

The `CachePolicy` enum defines caching strategies:

| Policy | Description |
|---|---|
| `NONE` | No caching |
| `MEMORY` | In-memory caching only |
| `PERSISTENT` | Persistent cache with invalidation |
| `AGGRESSIVE` | Cache everything aggressively |

### Cache Management

```python
# Clear all cached data
context.clear_cache()

# Invalidate specific entries
context.invalidate_cache(entity_type=WallElement, entity_id=some_id)
context.invalidate_cache(entity_type=WallElement)  # All walls
context.invalidate_cache()  # Everything

# Access cache statistics
stats = context.cache_statistics
```

## Relationships

RevitPy supports relationship loading between entities with configurable loading strategies.

### LoadStrategy Enum

| Strategy | Description |
|---|---|
| `LAZY` | Load on demand when the relationship is first accessed |
| `EAGER` | Load with the parent entity |
| `SELECT` | Use a separate select query |
| `BATCH` | Batch load multiple entities |

### Loading Relationships

```python
from revitpy.orm.types import LoadStrategy

# Load a relationship for an entity
related = context.load_relationship(entity, "rooms", strategy=LoadStrategy.LAZY)

# Configure a relationship
context.configure_relationship(WallElement, "rooms", RoomElement)
```

## Async Operations

Convert a `RevitContext` to an async interface:

```python
async_ctx = context.as_async()

# Use async query methods
results = await async_ctx.query(WallElement).to_list_async()
```

The `create_async_context` factory function creates an `AsyncRevitContext` directly:

```python
from revitpy.orm.context import create_async_context

async_ctx = create_async_context(provider)
```
