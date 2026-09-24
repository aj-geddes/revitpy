---
layout: page
title: FAQ
description: Frequently asked questions about RevitPy covering Python version support, querying, transactions, ORM change tracking, async operations, and extensions.
doc_tier: user
---

# Frequently Asked Questions

## General

### What Python versions are supported?

RevitPy supports CPython 3.11–3.13. `pyproject.toml` specifies `requires-python = ">=3.11"`, and CI tests 3.11, 3.12 and 3.13. The RevitPy Revit add-in can embed a 64-bit CPython 3.11–3.14. IronPython is not supported.

### What license is RevitPy released under?

RevitPy is released under the MIT license.

### Do I need Revit installed to develop with RevitPy?

No. RevitPy includes a `MockRevit` environment that simulates the Revit application, documents, and elements. You can develop and test your code entirely without a Revit installation. See the [Testing guide]({{ '/user/features/testing/' | relative_url }}) for details.

### How do I run RevitPy against a live Revit model?

Run your script inside Revit, either through the RevitPy add-in (**RevitPy > Run Script**) or in a pyRevit script on a CPython 3.11+ engine. Then connect with Revit's `UIApplication`:

```python
from revitpy import RevitAPI

api = RevitAPI()
api.connect(__revit__)
```

See [Getting Started]({{ '/user/getting-started/' | relative_url }}#connect-to-revit) for installing the add-in. RevitPy cannot attach to Revit from a separate process.

### What units are values in?

Revit internal units. Lengths are in **feet**, areas in square feet and volumes in cubic feet, no matter what display units the project uses. `set_parameter_value("Unconnected Height", 10.0)` sets 10 ft. Convert explicitly, for example `metres = feet * 0.3048`.

### Can I call RevitPy from a background thread?

Not directly. The Revit API only works on Revit's main thread. Inside the RevitPy add-in, use `revitpy.revit.host.call_on_revit_thread()` to run a function there and get its result:

```python
from revitpy.revit.host import call_on_revit_thread

title = call_on_revit_thread(lambda uiapp: uiapp.ActiveUIDocument.Document.Title)
```

It raises `TimeoutError` (default 60 s) if Revit cannot run the request, for example while a modal dialog is open. `AsyncRevit`, `TaskQueue` and the async decorators run synchronous work in thread-pool executors. Don't use them for Revit API calls on a live model.

### Is there a command-line tool?

Yes, the package installs `revitpy`:

- `revitpy version` prints the installed version.
- `revitpy doctor [--json]` checks Python, dependencies and optional integrations. It exits with status 1 if a core dependency is missing.
- `revitpy mcp-serve [--host --port --token]` runs the MCP server without a live Revit connection. Tools that need a document report that RevitPy is not connected. To work on a live model, use the add-in's **MCP Server** button.

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
from revitpy.api import Wall
from revitpy.orm import create_context

context = create_context(api.active_document)
all_walls = context.all(Wall)
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

Yes. On a live document, a `with api.transaction(...)` block opened inside another one becomes a Revit `SubTransaction`. If it raises, only its own changes roll back:

```python
with api.transaction("Outer"):
    wall.set_parameter_value("Comments", "kept")
    try:
        with api.transaction("Inner"):
            wall.set_parameter_value("Mark", "discarded")
            raise ValueError("undo only the inner block")
    except ValueError:
        pass
```

`MockDocument` behaves the same way through snapshot and restore. Documents without a `StartTransaction` method cannot open transactions, and `RevitDocumentProvider.start_transaction()` raises `TransactionError` for them.

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
2. When you modify an attached entity (or call `context.update(entity, name=value)`), it transitions to `MODIFIED`.
3. `context.add(entity)` marks it as `ADDED`.
4. `context.remove(entity)` marks it as `DELETED`.
5. `context.save_changes()` (or `await ctx.save_changes_async()`) hands pending changes to the context's `unit_of_work` and commits it. A commit failure raises. Without a unit of work, changes are only accepted in the tracker and nothing is written. On a live model, `Element` parameter writes already go straight to Revit inside `api.transaction()`.
6. `context.reject_changes()` sets each changed property back to its value before the first change; properties that weren't changed are left alone.

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

### Which element event types exist?

`EventType.ELEMENT_CREATED`, `ELEMENT_MODIFIED`, `ELEMENT_DELETED` and `ELEMENT_TYPE_CHANGED`. There is no `ELEMENT_CHANGED`.

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

# Or skip the decorator entirely
manager.register_function(on_created, [EventType.ELEMENT_CREATED])
```

Decorated methods on a class work too: call `manager.register_class_handlers(instance)` and each method is bound to that instance.

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
mock.create_elements(count=5, category="OST_Walls", element_type="Wall")

api = RevitAPI()
api.connect(mock.application)

# Run tests against the API as normal
```

See the [Testing guide]({{ '/user/features/testing/' | relative_url }}) for pytest integration examples.

### Can I serialize mock state for reproducible tests?

Yes. `MockRevit` supports `save_state(path)` and `load_state(path)` to persist the entire mock environment (documents, elements, fixtures) as JSON.

## Integrations

### Why does installing `revitpy[interop]` downgrade `websockets`?

`specklepy` depends on `gql[websockets]`, which pins `websockets<12`. RevitPy itself accepts `websockets>=11` and its MCP server works with both the legacy (<13) and the new asyncio websockets APIs. The downgrade is expected. If another package in the same environment needs `websockets>=12`, install Speckle support in a separate virtual environment.

### What does the `ifc` extra install?

`ifcopenshell>=0.8`, `ifctester` (used by `IdsValidator.validate_ifc_file()`) and `defusedxml` (safe BCF XML parsing).
