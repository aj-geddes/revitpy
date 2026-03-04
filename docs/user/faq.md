---
layout: page
title: FAQ
description: Frequently asked questions about RevitPy covering Python version support, querying, transactions, ORM change tracking, async operations, and extensions.
doc_tier: user
---

# Frequently Asked Questions

## General

### What Python versions are supported?

RevitPy requires Python 3.11 or later. The `pyproject.toml` specifies `requires-python = ">=3.11"` and classifiers list Python 3.11 and 3.12.

### What license is RevitPy released under?

RevitPy is released under the MIT license.

### Do I need Revit installed to develop with RevitPy?

No. RevitPy includes a `MockRevit` environment that simulates the Revit application, documents, and elements. You can develop and test your code entirely without a Revit installation. See the [Testing guide](features/testing) for details.

## API and Querying

### What is the difference between the API QueryBuilder and the ORM QueryBuilder?

RevitPy has two query builders that serve different purposes:

**API QueryBuilder** (`revitpy.api.query.QueryBuilder`):
- Filters by property name and `FilterOperator` enum (e.g., `equals("Name", "Wall-1")`).
- Sorts by property name and `SortDirection`.
- Has `skip`, `take`, `distinct` with property name arguments.
- Terminal operations: `execute()` returns an `ElementSet`, plus `count()`, `first()`, `any()`, `to_list()`.

**ORM QueryBuilder** (`revitpy.orm.query_builder.QueryBuilder`):
- Filters with predicate functions (e.g., `where(lambda e: e.name == "Wall-1")`).
- Projects with selector functions (e.g., `select(lambda e: e.name)`).
- Sorts with key selector functions.
- Has lazy evaluation with query plan optimization.
- Has both sync and async terminal operations (e.g., `to_list()`, `to_list_async()`).
- Supports streaming queries for large datasets via `as_streaming()`.

Use the API QueryBuilder for straightforward property-based queries. Use the ORM QueryBuilder when you need predicate-based filtering, projection, lazy evaluation, async execution, or integration with change tracking.

### How do I get all elements from a document?

```python
# Using the API
all_elements = api.elements.execute()

# Using the ORM
all_of_type = context.all(WallElement)
```

### How do I paginate results?

Use `skip` and `take`:

```python
page_size = 25
page_number = 2  # 0-indexed

results = (
    api.elements
    .order_by_ascending("Name")
    .skip(page_number * page_size)
    .take(page_size)
    .execute()
)
```

## Transactions

### What happens if an exception occurs inside a transaction?

When using `Transaction` as a context manager, an exception causes the transaction to roll back automatically. The `auto_commit` option (default `True`) controls whether the transaction commits on a clean exit:

```python
with api.transaction("My Work") as txn:
    # If this raises, the transaction rolls back
    do_work()
# If no exception, the transaction commits (when auto_commit=True)
```

### Can I nest transactions?

RevitPy does not support nested transactions in the API layer. Use `TransactionGroup` to coordinate multiple transactions:

```python
with api.transaction_group("Batch") as group:
    txn1 = group.add_transaction()
    txn2 = group.add_transaction()
    # All start, commit, or rollback together
```

### How does retry work with transactions?

Use `retry_transaction` from `revitpy.api.transaction`:

```python
from revitpy.api.transaction import retry_transaction

result = retry_transaction(
    provider=api.active_document,
    operation=lambda: do_work(),
    max_retries=3,
    delay=1.0,
    name="Retry Example",
)
```

This retries the operation up to `max_retries` times with the specified delay between attempts.

## ORM and Change Tracking

### How does change tracking work?

When `auto_track_changes` is enabled in `ContextConfiguration` (the default), entities retrieved through `RevitContext` are automatically attached and tracked. The `ChangeTracker` records entity states:

1. When you retrieve an entity, it is attached with state `UNCHANGED`.
2. When you modify an attached entity, it transitions to `MODIFIED`.
3. `context.add(entity)` marks it as `ADDED`.
4. `context.remove(entity)` marks it as `DELETED`.
5. `context.save_changes()` persists all pending changes and accepts them.
6. `context.reject_changes()` reverts to the last accepted state.

You can check the state of any entity with `context.get_entity_state(entity)`.

### What are the CachePolicy options?

| Policy | Behavior |
|---|---|
| `NONE` | No caching at all |
| `MEMORY` | Cache in memory with LRU eviction (default) |
| `PERSISTENT` | Persistent cache with invalidation support |
| `AGGRESSIVE` | Cache everything, maximize hit rate |

### How do I clear the ORM cache?

```python
# Clear all cache
context.clear_cache()

# Invalidate by type
context.invalidate_cache(entity_type=WallElement)

# Invalidate a specific entity
context.invalidate_cache(entity_type=WallElement, entity_id=some_id)
```

## Events

### How do I register event handlers at module level?

Use the `@event_handler` decorator at module level. The handler metadata is stored on the function. To activate it, either let the `EventManager` auto-discover it, or register it manually:

```python
from revitpy.events.decorators import event_handler
from revitpy.events.types import EventType, EventResult

@event_handler([EventType.ELEMENT_CREATED])
def on_created(event_data):
    return EventResult.CONTINUE

# Manual registration
from revitpy.events.manager import get_event_manager
manager = get_event_manager()
manager.register_handler(on_created._event_handler, on_created._event_types)
```

### What is the maximum error count for handlers?

By default, event handlers are disabled after 10 errors (`max_errors=10` in the `@event_handler` decorator). You can change this per handler.

## Async

### Can I use async operations without an event loop?

The `@async_revit_operation` and `@background_task` decorators detect the execution context. If there is no running event loop, they fall back to synchronous execution.

### How do I cancel a long-running async operation?

Use a `CancellationToken`:

```python
from revitpy.async_support.cancellation import CancellationToken

token = CancellationToken()

# Start the operation
task = asyncio.create_task(
    async_revit.get_elements_async(cancellation_token=token)
)

# Cancel when needed
token.cancel()
```

## Extensions

### How are extension dependencies resolved?

When `dependency_resolution` is enabled in `ExtensionManagerConfig` (the default), the `ExtensionManager` loads dependencies before loading the dependent extension. Dependencies are listed by name in `ExtensionMetadata.dependencies`.

### Can I use dependency injection outside of extensions?

Yes. The `DIContainer` can be used standalone:

```python
from revitpy.extensions.dependency_injection import DIContainer

container = DIContainer()
container.register_singleton(MyService, instance=my_service)
service = container.get_service(MyService)
```

## Testing

### How do I run tests without Revit?

Use `MockRevit` to simulate the Revit environment:

```python
from revitpy import RevitAPI, MockRevit

mock = MockRevit()
doc = mock.create_document("Test.rvt")
mock.create_elements(count=5, element_type="Wall")

api = RevitAPI()
api.connect(mock.application)

# Run tests against the API as normal
```

See the [Testing guide](features/testing) for pytest integration examples.

### Can I serialize mock state for reproducible tests?

Yes. `MockRevit` supports `save_state(path)` and `load_state(path)` to persist the entire mock environment (documents, elements, fixtures) as JSON.
