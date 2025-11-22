---
layout: api
title: Async Support API
description: Async Support API reference documentation
---

# Async Support API

RevitPy provides comprehensive async/await support for modern asynchronous programming patterns with Revit.

## Overview

The Async Support module enables:

- **Async/await syntax**: Modern Python asynchronous programming
- **Task queues**: Manage background operations efficiently
- **Progress tracking**: Monitor long-running operations
- **Cancellation tokens**: Cancel operations gracefully
- **Context managers**: Async context management
- **Thread-safe operations**: Safe concurrent access to Revit API

---

## AsyncRevit

Main class for asynchronous Revit operations.

### Constructor

```python
AsyncRevit(max_concurrent_tasks=4)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_concurrent_tasks` | `int` | Maximum number of concurrent tasks. Default is `4`. |

### Methods

#### `execute_async(func, *args, **kwargs)`
Executes a function asynchronously.

```python
result = await async_revit.execute_async(process_elements, elements)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `func` | `Callable` | Function to execute |
| `*args` | `any` | Positional arguments for the function |
| `**kwargs` | `any` | Keyword arguments for the function |

**Returns:** `any` - Result of the function execution

#### `create_task(coroutine, name=None)`
Creates a new async task.

| Parameter | Type | Description |
|-----------|------|-------------|
| `coroutine` | `Coroutine` | Async coroutine to execute |
| `name` | `str` | Optional task name for identification |

**Returns:** `Task` - The created task

#### `cancel_all_tasks()`
Cancels all running and pending tasks.

#### `wait_for_completion(timeout=None)`
Waits for all tasks to complete.

| Parameter | Type | Description |
|-----------|------|-------------|
| `timeout` | `float` | Optional timeout in seconds |

**Returns:** `bool` - True if all tasks completed, False if timeout

#### `get_task_status(task_id)`
Gets the status of a specific task.

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | `str` | Task identifier |

**Returns:** `str` - Task status: `'pending'`, `'running'`, `'completed'`, `'cancelled'`, or `'failed'`

#### `set_max_concurrent_tasks(count)`
Sets the maximum number of concurrent tasks.

| Parameter | Type | Description |
|-----------|------|-------------|
| `count` | `int` | Maximum concurrent tasks |

#### `get_elements_async(category)`
Asynchronously retrieves elements by category.

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | `str` | Element category name |

**Returns:** `list[Element]` - List of elements

#### `get_element_by_id_async(element_id)`
Asynchronously retrieves an element by ID.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element_id` | `int` or `ElementId` | Element identifier |

**Returns:** `Element` - The element
**Raises:** `ElementNotFound` - If element doesn't exist

#### `set_parameter_async(element, name, value)`
Asynchronously sets a parameter value.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element` | `Element` | Target element |
| `name` | `str` | Parameter name |
| `value` | `any` | New value |

---

## async_transaction

Async context manager for transactions.

### Usage

```python
async with async_transaction(async_revit, "Transaction Name") as txn:
    # Make changes
    await txn.commit()
```

### Methods

#### `commit()`
Commits the transaction asynchronously.

#### `rollback()`
Rolls back the transaction asynchronously.

---

## TaskQueue

Manages queued asynchronous tasks.

### Constructor

```python
TaskQueue(max_concurrent=4)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_concurrent` | `int` | Maximum concurrent tasks |

### Methods

#### `enqueue(task)`
Adds a task to the queue.

| Parameter | Type | Description |
|-----------|------|-------------|
| `task` | `Task` | Task to enqueue |

#### `dequeue()`
Removes and returns the next task from the queue.

**Returns:** `Task` - The next task

#### `process_all()`
Processes all queued tasks.

#### `get_pending_tasks()`
Returns all pending tasks.

**Returns:** `list[Task]` - Pending tasks

#### `get_running_tasks()`
Returns all running tasks.

**Returns:** `list[Task]` - Running tasks

#### `get_completed_tasks()`
Returns all completed tasks.

**Returns:** `list[Task]` - Completed tasks

#### `clear_completed()`
Clears completed tasks from the queue.

---

## Task

Represents an asynchronous task.

### Constructor

```python
Task(name, coroutine, priority=0)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Task name |
| `coroutine` | `Coroutine` | Async coroutine |
| `priority` | `int` | Task priority (higher = more important) |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Unique task identifier |
| `name` | `str` | Task name |
| `status` | `str` | Current status |
| `result` | `any` | Task result (when completed) |
| `error` | `Exception` | Task error (when failed) |
| `progress` | `float` | Progress percentage (0-100) |
| `created_at` | `datetime` | Creation timestamp |
| `started_at` | `datetime` | Start timestamp |
| `completed_at` | `datetime` | Completion timestamp |

### Methods

#### `cancel()`
Cancels the task.

---

## CancellationToken

Provides cancellation support for async operations.

### Constructor

```python
CancellationToken()
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_cancelled` | `bool` | Whether cancellation was requested |

### Methods

#### `cancel()`
Requests cancellation.

#### `throw_if_cancelled()`
Throws `TaskCancelledError` if cancelled.

**Raises:** `TaskCancelledError` - If cancellation was requested

#### `register_callback(callback)`
Registers a callback to be called on cancellation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `callback` | `Callable` | Callback function |

---

## ProgressReporter

Reports progress for long-running operations.

### Constructor

```python
ProgressReporter()
```

### Methods

#### `report_progress(percentage, message=None)`
Reports progress percentage and optional message.

| Parameter | Type | Description |
|-----------|------|-------------|
| `percentage` | `float` | Progress percentage (0-100) |
| `message` | `str` | Optional status message |

#### `report_status(status)`
Reports a status change.

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | `str` | Status description |

#### `get_progress()`
Gets current progress.

**Returns:** `tuple[float, str]` - Progress percentage and message

#### `add_callback(callback)`
Adds a progress callback.

| Parameter | Type | Description |
|-----------|------|-------------|
| `callback` | `ProgressCallback` | Callback instance |

#### `is_indeterminate()`
Checks if progress is indeterminate.

**Returns:** `bool` - True if progress cannot be determined

---

## Basic Usage

### Simple Async Operation

```python
import asyncio
from revitpy.async_support import AsyncRevit, async_transaction

async def update_walls_async():
    """Update walls asynchronously."""
    async_revit = AsyncRevit()

    async with async_transaction(async_revit, "Update Walls") as txn:
        # Get walls
        walls = await async_revit.get_elements_async('Walls')

        # Update each wall
        for wall in walls:
            await async_revit.set_parameter_async(
                wall,
                'Comments',
                'Updated asynchronously'
            )

        await txn.commit()

# Run async function
asyncio.run(update_walls_async())
```

### Async with Progress Reporting

```python
from revitpy.async_support import ProgressReporter

async def process_elements_with_progress(element_ids):
    """Process elements with progress tracking."""
    async_revit = AsyncRevit()
    progress = ProgressReporter()

    total = len(element_ids)

    for i, element_id in enumerate(element_ids):
        # Update progress
        progress.report_progress(i / total * 100, f"Processing element {i+1}/{total}")

        # Process element
        element = await async_revit.get_element_by_id_async(element_id)
        await process_element(element)

    progress.report_progress(100, "Complete")

# Usage
asyncio.run(process_elements_with_progress([123, 456, 789]))
```

### Cancellable Operations

```python
from revitpy.async_support import CancellationToken

async def cancellable_operation(cancel_token):
    """Long-running operation that can be cancelled."""
    async_revit = AsyncRevit()

    walls = await async_revit.get_elements_async('Walls')

    for i, wall in enumerate(walls):
        # Check for cancellation
        if cancel_token.is_cancelled:
            print(f"Operation cancelled after {i} elements")
            return

        # Process wall
        await async_revit.set_parameter_async(wall, 'Mark', f'W-{i+1}')

# Create cancellation token
token = CancellationToken()

# Start operation
task = asyncio.create_task(cancellable_operation(token))

# Cancel after 5 seconds
await asyncio.sleep(5)
token.cancel()

await task
```

---

## Task Queue Management

### Creating and Managing Tasks

```python
from revitpy.async_support import TaskQueue, Task

async def manage_task_queue():
    """Manage a queue of asynchronous tasks."""
    queue = TaskQueue(max_concurrent=4)

    # Define tasks
    async def update_wall(wall_id):
        async_revit = AsyncRevit()
        wall = await async_revit.get_element_by_id_async(wall_id)
        await async_revit.set_parameter_async(wall, 'Comments', 'Updated')
        return wall_id

    # Enqueue tasks
    wall_ids = [123, 456, 789, 101, 112, 131]
    for wall_id in wall_ids:
        task = Task(
            name=f"Update Wall {wall_id}",
            coroutine=update_wall(wall_id)
        )
        queue.enqueue(task)

    # Process queue
    await queue.process_all()

    # Get results
    completed = queue.get_completed_tasks()
    for task in completed:
        print(f"Task {task.name}: {task.result}")

asyncio.run(manage_task_queue())
```

### Priority Queue

```python
from revitpy.async_support import PriorityTaskQueue

async def priority_task_processing():
    """Process tasks with priority ordering."""
    queue = PriorityTaskQueue()

    # Add tasks with priorities (higher = more important)
    queue.enqueue(update_critical_elements(), priority=10, name="Critical Update")
    queue.enqueue(update_normal_elements(), priority=5, name="Normal Update")
    queue.enqueue(update_low_priority_elements(), priority=1, name="Low Priority Update")

    # Process queue (critical tasks run first)
    await queue.process_all()
```

---

## Advanced Async Patterns

### Parallel Processing

```python
async def parallel_element_processing(element_ids):
    """Process multiple elements in parallel."""
    async_revit = AsyncRevit()

    async def process_single_element(element_id):
        element = await async_revit.get_element_by_id_async(element_id)
        # Process element...
        return await analyze_element(element)

    # Process all elements in parallel
    results = await asyncio.gather(
        *[process_single_element(eid) for eid in element_ids]
    )

    return results
```

### Async Context Managers

```python
from revitpy.async_support import async_element_scope

async def use_async_context_manager():
    """Use async context managers for resource management."""
    async_revit = AsyncRevit()

    # Automatically manages element lifecycle
    async with async_element_scope(async_revit, element_id=123) as element:
        await async_revit.set_parameter_async(element, 'Height', 12.0)
        # Element is automatically cleaned up on exit
```

### Async Iteration

```python
from revitpy.async_support import AsyncElementIterator

async def iterate_elements_async():
    """Iterate over elements asynchronously."""
    async_revit = AsyncRevit()

    # Create async iterator
    iterator = AsyncElementIterator(async_revit, category='Walls')

    # Iterate asynchronously
    async for wall in iterator:
        print(f"Wall: {wall.Name}")
        await process_wall(wall)
```

### Batch Async Operations

```python
async def batch_async_updates(updates):
    """Perform batch updates asynchronously."""
    async_revit = AsyncRevit()

    async with async_transaction(async_revit, "Batch Update") as txn:
        # Create batches
        batch_size = 100
        batches = [updates[i:i+batch_size] for i in range(0, len(updates), batch_size)]

        for batch in batches:
            # Process batch in parallel
            await asyncio.gather(*[
                async_revit.set_parameter_async(elem_id, param, value)
                for elem_id, param, value in batch
            ])

        await txn.commit()
```

---

## Progress Tracking

### Detailed Progress Reporting

```python
from revitpy.async_support import ProgressReporter, ProgressCallback

class DetailedProgressCallback(ProgressCallback):
    """Custom progress callback with detailed reporting."""

    def on_progress(self, percentage, message):
        print(f"[{percentage:6.2f}%] {message}")

    def on_status_change(self, old_status, new_status):
        print(f"Status changed: {old_status} -> {new_status}")

async def operation_with_detailed_progress():
    """Operation with detailed progress tracking."""
    progress = ProgressReporter()
    progress.add_callback(DetailedProgressCallback())

    total_steps = 100

    for step in range(total_steps):
        # Perform operation
        await perform_step(step)

        # Report progress
        progress.report_progress(
            (step + 1) / total_steps * 100,
            f"Completed step {step + 1}/{total_steps}"
        )

    progress.report_status("Completed")
```

### Multi-Stage Progress

```python
async def multi_stage_operation():
    """Operation with multiple stages."""
    progress = ProgressReporter()

    # Stage 1: Load data (0-30%)
    progress.report_status("Loading data")
    for i in range(30):
        await asyncio.sleep(0.1)
        progress.report_progress(i, "Loading...")

    # Stage 2: Process data (30-70%)
    progress.report_status("Processing")
    for i in range(30, 70):
        await asyncio.sleep(0.1)
        progress.report_progress(i, "Processing...")

    # Stage 3: Save results (70-100%)
    progress.report_status("Saving")
    for i in range(70, 101):
        await asyncio.sleep(0.1)
        progress.report_progress(i, "Saving...")

    progress.report_status("Complete")
```

---

## Error Handling

### Async Exception Handling

```python
from revitpy.async_support.exceptions import (
    AsyncOperationError,
    TaskCancelledError,
    TaskTimeoutError
)

async def async_error_handling():
    """Handle errors in async operations."""
    async_revit = AsyncRevit()

    try:
        async with async_transaction(async_revit, "Update") as txn:
            element = await async_revit.get_element_by_id_async(123)
            await async_revit.set_parameter_async(element, 'Height', 12.0)
            await txn.commit()

    except TaskCancelledError:
        print("Operation was cancelled")
    except TaskTimeoutError:
        print("Operation timed out")
    except AsyncOperationError as e:
        print(f"Async operation failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
```

### Retry Logic

```python
async def async_retry_operation(func, max_retries=3, delay=1.0):
    """Retry async operation on failure."""
    for attempt in range(max_retries):
        try:
            return await func()
        except AsyncOperationError as e:
            if attempt == max_retries - 1:
                raise
            print(f"Attempt {attempt + 1} failed, retrying...")
            await asyncio.sleep(delay)

# Usage
async def update_element():
    async_revit = AsyncRevit()
    element = await async_revit.get_element_by_id_async(123)
    await async_revit.set_parameter_async(element, 'Height', 12.0)

result = await async_retry_operation(update_element)
```

---

## Performance Optimization

### Concurrent Task Limits

```python
async def optimized_concurrent_processing(element_ids):
    """Process elements with optimal concurrency."""
    async_revit = AsyncRevit()

    # Limit concurrent operations
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent tasks

    async def process_with_limit(element_id):
        async with semaphore:
            element = await async_revit.get_element_by_id_async(element_id)
            return await process_element(element)

    results = await asyncio.gather(*[
        process_with_limit(eid) for eid in element_ids
    ])

    return results
```

### Async Caching

```python
from functools import lru_cache
from revitpy.async_support import async_lru_cache

class AsyncElementCache:
    """Cache for async element access."""

    def __init__(self):
        self.cache = {}

    @async_lru_cache(maxsize=1000)
    async def get_element_cached(self, element_id):
        """Get element with caching."""
        if element_id not in self.cache:
            async_revit = AsyncRevit()
            element = await async_revit.get_element_by_id_async(element_id)
            self.cache[element_id] = element
        return self.cache[element_id]
```

---

## Integration with Sync Code

### Running Async from Sync

```python
def sync_function_calling_async():
    """Call async function from synchronous code."""
    async def async_operation():
        async_revit = AsyncRevit()
        walls = await async_revit.get_elements_async('Walls')
        return len(walls)

    # Run async code from sync context
    result = asyncio.run(async_operation())
    print(f"Found {result} walls")
```

### Mixing Sync and Async

```python
async def mixed_sync_async_operations():
    """Mix synchronous and asynchronous operations."""
    async_revit = AsyncRevit()

    # Sync operation
    with RevitContext() as context:
        sync_walls = context.elements.of_category('Walls').to_list()

    # Async operation
    async_walls = await async_revit.get_elements_async('Walls')

    # Compare results
    print(f"Sync found {len(sync_walls)} walls")
    print(f"Async found {len(async_walls)} walls")
```

---

## Testing Async Code

### Async Test Cases

```python
import pytest
from revitpy.testing import AsyncRevitTestCase

class TestAsyncOperations(AsyncRevitTestCase):
    """Test async Revit operations."""

    async def test_async_element_update(self):
        """Test async element update."""
        async_revit = AsyncRevit()

        async with async_transaction(async_revit, "Test Update") as txn:
            element = await async_revit.get_element_by_id_async(123)
            await async_revit.set_parameter_async(element, 'Comments', 'Test')
            await txn.commit()

        # Verify
        element = await async_revit.get_element_by_id_async(123)
        assert element.get_parameter('Comments').AsString() == 'Test'

    async def test_cancellation(self):
        """Test operation cancellation."""
        token = CancellationToken()

        async def long_operation():
            for i in range(100):
                token.throw_if_cancelled()
                await asyncio.sleep(0.1)

        # Start and cancel
        task = asyncio.create_task(long_operation())
        await asyncio.sleep(0.5)
        token.cancel()

        with pytest.raises(TaskCancelledError):
            await task
```

---

## Best Practices

1. **Use async/await consistently**: Don't mix async and sync patterns unnecessarily
2. **Limit concurrency**: Use semaphores to prevent overwhelming the Revit API
3. **Handle cancellation**: Always respect cancellation tokens
4. **Report progress**: Keep users informed of long-running operations
5. **Clean up resources**: Use async context managers for proper resource management
6. **Test thoroughly**: Write comprehensive async tests

---

## Thread Safety

<div class="callout callout-warning">
  <div class="callout-title">Revit API Thread Limitations</div>
  <p>The Revit API requires model modifications to occur on the main UI thread. RevitPy's async support automatically marshals operations to the correct thread, but be aware of this limitation when designing your async workflows.</p>
</div>

---

## Next Steps

- **[Event System]({{ '/reference/api/events/' | relative_url }})**: Combine async with event-driven programming
- **[Performance Guide]({{ '/guides/async-performance/' | relative_url }})**: Optimize async operations
- **[Testing Async Code]({{ '/guides/testing-async/' | relative_url }})**: Test async operations
