---
layout: page
title: Async Support
description: Guide to async operations in RevitPy with AsyncRevit, async transactions, background task queues, progress reporting, cancellation tokens, and batching.
doc_tier: user
---

# Async Support

RevitPy provides async/await support for long-running Revit operations. The `AsyncRevit` class wraps the synchronous `RevitAPI` with async methods, and decorators like `@async_revit_operation` and `@background_task` make it easy to write non-blocking code.

## AsyncRevit

`AsyncRevit` is the main async interface. It wraps a `RevitAPI` instance and provides async versions of document and element operations.

```python
from revitpy import AsyncRevit

async_revit = AsyncRevit()

# Initialize with optional parameters
await async_revit.initialize(
    max_concurrent_tasks=4,
    revit_application=revit_app,
)

# Or use as an async context manager
async with AsyncRevit() as async_revit:
    # async_revit.initialize() is called
    pass
# async_revit.shutdown() is called automatically
```

### Properties

- `async_revit.api` -- The underlying `RevitAPI` instance.
- `async_revit.is_connected` -- `True` if connected to Revit.
- `async_revit.task_queue` -- The `TaskQueue` instance (created lazily).

### Async Document Operations

```python
# Open a document
provider = await async_revit.open_document_async("path/to/file.rvt")

# Create a new document
provider = await async_revit.create_document_async("path/to/template.rte")

# Save and close
success = await async_revit.save_document_async()
success = await async_revit.close_document_async(save_changes=True)
```

### Async Element Operations

#### Get All Elements

```python
from revitpy.async_support.progress import ProgressReporter
from revitpy.async_support.cancellation import CancellationToken

# Simple retrieval
elements = await async_revit.get_elements_async()

# With progress reporting and cancellation
token = CancellationToken()
reporter = ProgressReporter()
elements = await async_revit.get_elements_async(
    progress_reporter=reporter,
    cancellation_token=token,
)
```

#### Query Elements

Pass a function that builds a query from a `QueryBuilder`:

```python
elements = await async_revit.query_elements_async(
    query_func=lambda q: q.contains("Name", "Wall").order_by_ascending("Name"),
    progress_reporter=reporter,
    cancellation_token=token,
)
```

#### Update Elements in Batches

```python
count = await async_revit.update_elements_async(
    elements=wall_list,
    update_func=lambda wall: wall.set_parameter_value("Comments", "Reviewed"),
    batch_size=100,
    progress_reporter=reporter,
    cancellation_token=token,
)
```

This processes elements in batches with a small delay between each batch to avoid overwhelming Revit. It returns the number of elements updated.

## Async Transactions

### async_transaction Context Manager

The `async_transaction` context manager from `revitpy.async_support.context_managers` wraps operations in a transaction:

```python
from revitpy import async_transaction

# Via AsyncRevit
async with async_revit.async_transaction("Update Walls") as txn:
    # perform modifications
    pass
# Auto-commits on success, rolls back on exception
```

### execute_in_transaction_async

Execute a single operation inside a transaction:

```python
result = await async_revit.execute_in_transaction_async(
    operation=lambda: modify_elements(),
    name="Modify Elements",
    timeout=timedelta(seconds=30),
)
```

The `operation` can be a sync function (run in an executor) or an async coroutine.

## @async_revit_operation Decorator

Wraps a function to be async-aware. Sync functions are automatically run in an executor. Supports timeout, retry, cancellation, and progress reporting.

```python
from revitpy.async_support.decorators import async_revit_operation
from datetime import timedelta

@async_revit_operation(
    timeout=timedelta(seconds=30),
    retry_count=3,
    retry_delay=timedelta(seconds=1),
)
def process_elements():
    # This sync function runs in an executor when called from async context
    return do_work()
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `timeout` | `timedelta` or `None` | `None` | Operation timeout |
| `retry_count` | `int` | `0` | Number of retry attempts |
| `retry_delay` | `timedelta` | 1 second | Delay between retries |
| `cancellation_token` | `CancellationToken` or `None` | `None` | Cancellation token |
| `progress_reporter` | `ProgressReporter` or `None` | `None` | Progress reporter |

When called from an async context (inside a running event loop), the function returns a coroutine. When called from a sync context, it executes synchronously.

## @background_task Decorator

Runs a function as a queued background task. Returns a task ID that can be used to wait for or cancel the task.

```python
from revitpy.async_support.decorators import background_task
from revitpy.async_support.task_queue import TaskPriority

@background_task(
    priority=TaskPriority.NORMAL,
    timeout=timedelta(minutes=5),
    retry_count=2,
    retry_delay=timedelta(seconds=1),
    progress=True,
)
def long_running_analysis():
    return analyze_model()

# In async context, returns a task ID
task_id = await long_running_analysis()
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `priority` | `TaskPriority` | `NORMAL` | Task priority |
| `timeout` | `timedelta` or `None` | `None` | Task timeout |
| `retry_count` | `int` | `0` | Retry attempts |
| `retry_delay` | `timedelta` | 1 second | Delay between retries |
| `progress` | `bool` | `False` | Enable progress reporting |
| `task_queue` | `TaskQueue` or `None` | `None` | Custom task queue (uses default if None) |

## TaskQueue

The `TaskQueue` manages background task execution with priority ordering and concurrency limits.

```python
from revitpy.async_support.task_queue import TaskQueue, Task, TaskPriority

queue = TaskQueue(max_concurrent_tasks=4, name="MyQueue")
await queue.start()

# Enqueue a task
task_id = await queue.enqueue(Task(
    my_function,
    name="My Task",
    priority=TaskPriority.HIGH,
))

# Wait for a task to complete
result = await queue.wait_for_task(task_id, timeout=30.0)

# Stop the queue
await queue.stop(timeout=10.0)
```

### TaskPriority

| Priority | Description |
|---|---|
| `LOW` | Low priority |
| `NORMAL` | Normal priority (default) |
| `HIGH` | High priority |
| `CRITICAL` | Critical priority |

### Running Background Tasks via AsyncRevit

```python
# Enqueue a background task
task_id = await async_revit.run_background_task(
    my_function,
    arg1, arg2,
    name="My Task",
    priority=TaskPriority.NORMAL,
    timeout=timedelta(minutes=5),
    progress=True,
)

# Wait for result
result = await async_revit.wait_for_background_task(task_id, timeout=60.0)

# Start a long-running task
task_id = async_revit.start_background_task(my_operation, name="Long Task")

# Cancel a background task
cancelled = await async_revit.cancel_background_task(task_id)
```

## ProgressReporter

`ProgressReporter` tracks the progress of long-running operations.

```python
from revitpy.async_support.progress import ProgressReporter, create_progress_reporter

reporter = create_progress_reporter()
reporter.set_total(100)
reporter.start("Processing elements...")

for i in range(100):
    process(elements[i])
    await reporter.async_increment(1, f"Processed {i + 1}/100")

reporter.complete("All elements processed")
```

Key methods:

- `set_total(total)` -- Set the total number of items.
- `start(message)` -- Mark the operation as started.
- `complete(message)` -- Mark as completed.
- `fail(message)` -- Mark as failed.
- `cancel(message)` -- Mark as cancelled.
- `async_increment(count, message)` -- Increment progress asynchronously.

## CancellationToken

`CancellationToken` provides cooperative cancellation for async operations.

```python
from revitpy.async_support.cancellation import CancellationToken

token = CancellationToken()

# Pass to an async operation
elements = await async_revit.get_elements_async(cancellation_token=token)

# Cancel from another coroutine or callback
token.cancel()

# Check cancellation status
if token.is_cancelled:
    print("Operation was cancelled")
```

## Batch Processing

`AsyncRevit.batch_process` processes a list of items in batches with configurable concurrency, delays, progress, and cancellation:

```python
from datetime import timedelta

results = await async_revit.batch_process(
    items=element_list,
    process_func=lambda elem: analyze(elem),
    batch_size=100,
    delay_between_batches=timedelta(milliseconds=100),
    progress_reporter=reporter,
    cancellation_token=token,
)
```

The `process_func` can be sync or async. Within each batch, items are processed concurrently using `asyncio.gather`.

## Additional Decorators

### @revit_transaction

Wraps a function in a Revit transaction automatically:

```python
from revitpy.async_support.decorators import revit_transaction

@revit_transaction(name="Update Walls", auto_commit=True, timeout=timedelta(seconds=30))
def update_walls():
    # Runs inside a transaction
    pass
```

### @rate_limited

Limits how frequently an async function can be called:

```python
from revitpy.async_support.decorators import rate_limited

@rate_limited(max_calls=10, time_window=timedelta(seconds=1))
async def api_call():
    pass
```

### @cache_result

Caches function results with optional TTL:

```python
from revitpy.async_support.decorators import cache_result

@cache_result(ttl=timedelta(minutes=5), max_size=128)
async def expensive_query():
    return await fetch_data()
```

## Context Managers

`AsyncRevit` provides additional context managers:

```python
# Element scope -- manages a set of elements
async with async_revit.element_scope(elements) as scope:
    pass

# Progress scope -- manages progress reporting
async with async_revit.progress_scope() as progress:
    pass
```
