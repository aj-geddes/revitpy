---
layout: api
title: Async Support API
description: Async/await patterns for non-blocking Revit operations
---

# Async Support API

The Async Support module provides async/await wrappers for long-running Revit operations, with support for background tasks, progress reporting, cancellation, and batched processing.

**Module:** `revitpy.async_support.async_revit`

---

## AsyncRevit

Async wrapper for `RevitAPI` that provides non-blocking execution of Revit operations by delegating work to thread executors and managing a task queue.

### Constructor

```python
AsyncRevit(revit_application=None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `revit_application` | `IRevitApplication` or `None` | Optional Revit application instance. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `api` | `RevitAPI` | The underlying synchronous `RevitAPI` instance. |
| `is_connected` | `bool` | Whether the underlying API is connected to Revit. |
| `task_queue` | `TaskQueue` | The task queue (lazily created on first access). |

### Methods

#### `initialize(max_concurrent_tasks=4, revit_application=None)`

Initializes the async interface, connects to Revit, and starts the task queue.

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_concurrent_tasks` | `int` | Maximum concurrent tasks. Default `4`. |
| `revit_application` | `IRevitApplication` or `None` | Optional Revit application to connect to. |

```python
async_revit = AsyncRevit()
await async_revit.initialize(max_concurrent_tasks=8)
```

#### `shutdown(timeout=None)`

Shuts down the async interface. Cancels background tasks, stops the task queue, and disconnects from Revit.

| Parameter | Type | Description |
|-----------|------|-------------|
| `timeout` | `float` or `None` | Optional timeout in seconds for shutdown. |

#### `open_document_async(file_path)`

Opens a document asynchronously.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | `str` | Path to the Revit file. |

**Returns:** Document provider.

#### `create_document_async(template_path=None)`

Creates a new document asynchronously.

| Parameter | Type | Description |
|-----------|------|-------------|
| `template_path` | `str` or `None` | Optional template path. |

**Returns:** Document provider.

#### `save_document_async(provider=None)`

Saves the active or specified document asynchronously.

**Returns:** `bool` -- Success status.

#### `close_document_async(provider=None, save_changes=True)`

Closes a document asynchronously.

**Returns:** `bool` -- Success status.

#### `get_elements_async(progress_reporter=None, cancellation_token=None)`

Gets all elements asynchronously with optional progress reporting and cancellation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `progress_reporter` | `ProgressReporter` or `None` | Optional progress reporter. |
| `cancellation_token` | `CancellationToken` or `None` | Optional cancellation token. |

**Returns:** `ElementSet[Element]`

```python
elements = await async_revit.get_elements_async()
print(f"Found {elements.count} elements")
```

#### `query_elements_async(query_func, progress_reporter=None, cancellation_token=None)`

Queries elements asynchronously using a query builder function.

| Parameter | Type | Description |
|-----------|------|-------------|
| `query_func` | `Callable[[QueryBuilder], QueryBuilder]` | Function that configures the query. |
| `progress_reporter` | `ProgressReporter` or `None` | Optional progress reporter. |
| `cancellation_token` | `CancellationToken` or `None` | Optional cancellation token. |

**Returns:** `ElementSet[Element]`

```python
walls = await async_revit.query_elements_async(
    lambda q: q.equals("Category", "Walls")
)
```

#### `update_elements_async(elements, update_func, batch_size=100, progress_reporter=None, cancellation_token=None)`

Updates multiple elements asynchronously in batches.

| Parameter | Type | Description |
|-----------|------|-------------|
| `elements` | `list[Element]` | Elements to update. |
| `update_func` | `Callable[[Element], None]` | Function to apply to each element. |
| `batch_size` | `int` | Elements per batch. Default `100`. |
| `progress_reporter` | `ProgressReporter` or `None` | Optional progress reporter. |
| `cancellation_token` | `CancellationToken` or `None` | Optional cancellation token. |

**Returns:** `int` -- Number of elements updated.

```python
count = await async_revit.update_elements_async(
    walls,
    lambda w: w.set_parameter_value("Comments", "Updated"),
    batch_size=50,
)
print(f"Updated {count} walls")
```

#### `async_transaction(name=None, timeout=None, **kwargs)`

Creates an async transaction context manager.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` or `None` | Transaction name. |
| `timeout` | `timedelta` or `None` | Optional timeout. |

**Returns:** Async context manager yielding a transaction.

**Raises:** `RuntimeError` if no active document.

```python
async with async_revit.async_transaction("Update"):
    element.set_parameter_value("Comments", "Async update")
```

#### `execute_in_transaction_async(operation, name=None, timeout=None, **kwargs)`

Executes an operation inside an async transaction. Supports both sync and async callables.

| Parameter | Type | Description |
|-----------|------|-------------|
| `operation` | `Callable` | The operation to execute. |
| `name` | `str` or `None` | Transaction name. |
| `timeout` | `timedelta` or `None` | Optional timeout. |

**Returns:** Result of the operation.

#### `run_background_task(operation, *args, name=None, priority=TaskPriority.NORMAL, timeout=None, progress=False, **kwargs)`

Runs an operation as a background task in the task queue.

| Parameter | Type | Description |
|-----------|------|-------------|
| `operation` | `Callable` | Operation to run. |
| `*args` | | Arguments for the operation. |
| `name` | `str` or `None` | Task name. Defaults to the function name. |
| `priority` | `TaskPriority` | Task priority level. Default `NORMAL`. |
| `timeout` | `timedelta` or `None` | Optional timeout. |
| `progress` | `bool` | Whether to enable a progress reporter. Default `False`. |

**Returns:** `str` -- Task ID.

#### `wait_for_background_task(task_id, timeout=None)`

Waits for a background task to complete and returns its result.

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | `str` | Task ID from `run_background_task`. |
| `timeout` | `float` or `None` | Optional timeout in seconds. |

**Returns:** The task result.

**Raises:** The task's exception if it failed.

#### `start_background_task(operation, name=None)`

Starts a long-running background task using `asyncio.create_task`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `operation` | `Callable` | Sync or async callable. |
| `name` | `str` or `None` | Task name. |

**Returns:** `str` -- Task ID.

#### `cancel_background_task(task_id)`

Cancels a background task.

**Returns:** `bool` -- `True` if the task was found and cancelled.

#### `batch_process(items, process_func, batch_size=100, delay_between_batches=timedelta(milliseconds=100), progress_reporter=None, cancellation_token=None)`

Processes items in batches asynchronously. Each batch runs items in parallel.

| Parameter | Type | Description |
|-----------|------|-------------|
| `items` | `list[T]` | Items to process. |
| `process_func` | `Callable[[T], Any]` | Function to process each item. Sync or async. |
| `batch_size` | `int` | Items per batch. Default `100`. |
| `delay_between_batches` | `timedelta` | Delay between batches. Default `100ms`. |
| `progress_reporter` | `ProgressReporter` or `None` | Optional progress reporter. |
| `cancellation_token` | `CancellationToken` or `None` | Optional cancellation token. |

**Returns:** `list[Any]` -- Results from all items (includes exceptions as values if `return_exceptions=True` in gather).

```python
results = await async_revit.batch_process(
    element_list,
    lambda e: e.get_parameter_value("Height"),
    batch_size=50,
)
```

#### `element_scope(elements, **kwargs)`

Creates an async element scope context manager for resource management.

**Returns:** Async context manager from `async_element_scope`.

#### `progress_scope(**kwargs)`

Creates an async progress scope context manager.

**Returns:** Async context manager from `async_progress_scope`.

### Context Manager Usage

`AsyncRevit` supports `async with` for lifecycle management:

```python
async with AsyncRevit(revit_app) as async_revit:
    # initialize() called on entry
    walls = await async_revit.query_elements_async(
        lambda q: q.equals("Category", "Walls")
    )
    print(f"Found {walls.count} walls")
# shutdown() called on exit
```

---

## CancellationToken

Provides cooperative cancellation for async operations.

**Module:** `revitpy.async_support.cancellation`

### Constructor

```python
CancellationToken()
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_cancelled` | `bool` | Whether cancellation was requested. |

### Methods

#### `cancel()`

Requests cancellation.

### Usage

```python
from revitpy.async_support.cancellation import CancellationToken

token = CancellationToken()

# Pass to async operations
task_id = await async_revit.run_background_task(
    long_operation,
    cancellation_token=token,
)

# Cancel later
token.cancel()
```

---

## ProgressReporter

Reports progress for long-running async operations.

**Module:** `revitpy.async_support.progress`

### Key Methods

| Method | Description |
|--------|-------------|
| `start(message)` | Marks the start of the operation. |
| `set_total(total)` | Sets the total item count for percentage calculation. |
| `complete(message)` | Marks successful completion. |
| `cancel(message)` | Marks cancellation. |
| `fail(message)` | Marks failure. |
| `async_increment(count, message)` | Asynchronously increments progress by `count` items. |

### Factory Function

```python
from revitpy.async_support.progress import create_progress_reporter

reporter = create_progress_reporter()
```

---

## Usage Examples

### Async Query with Progress

```python
from revitpy.async_support import AsyncRevit
from revitpy.async_support.progress import create_progress_reporter

async def query_with_progress(revit_app):
    async with AsyncRevit(revit_app) as ar:
        reporter = create_progress_reporter()

        walls = await ar.query_elements_async(
            lambda q: q.equals("Category", "Walls"),
            progress_reporter=reporter,
        )

        print(f"Found {walls.count} walls")
```

### Batch Update with Cancellation

```python
from revitpy.async_support import AsyncRevit
from revitpy.async_support.cancellation import CancellationToken

async def batch_update(revit_app, elements):
    token = CancellationToken()

    async with AsyncRevit(revit_app) as ar:
        count = await ar.update_elements_async(
            elements,
            lambda e: e.set_parameter_value("Comments", "Batch updated"),
            batch_size=50,
            cancellation_token=token,
        )
        print(f"Updated {count} elements")
```

### Background Tasks

```python
from revitpy.async_support import AsyncRevit

async def background_processing(revit_app):
    async with AsyncRevit(revit_app) as ar:
        # Enqueue a background task
        task_id = await ar.run_background_task(
            expensive_analysis,
            name="Analysis",
            progress=True,
        )

        # Do other work...

        # Wait for result
        result = await ar.wait_for_background_task(task_id, timeout=60.0)
        print(f"Analysis result: {result}")
```

---

## Best Practices

1. **Use `async with AsyncRevit()` for lifecycle management** -- Ensures proper initialization and shutdown.
2. **Pass cancellation tokens to long operations** -- Enables graceful cancellation.
3. **Use batch processing for bulk updates** -- Prevents overwhelming the Revit API with concurrent calls.
4. **Add delays between batches** -- The default 100ms delay avoids saturating the UI thread.
5. **Monitor progress** -- Use `ProgressReporter` to keep users informed during long operations.

---

## Next Steps

- **[Core API]({{ '/reference/api/core/' | relative_url }})**: Synchronous `RevitAPI` interface
- **[Event System]({{ '/reference/api/events/' | relative_url }})**: Combine async with event-driven patterns
- **[Testing]({{ '/reference/api/testing/' | relative_url }})**: Test async operations with mocks
