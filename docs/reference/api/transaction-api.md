---
layout: api
title: Transaction API
description: Transaction API reference documentation
---

# Transaction API

The Transaction API provides robust transaction management for Revit operations, ensuring data integrity and proper error handling.

## Overview

Transactions are required for any operation that modifies the Revit model. RevitPy's Transaction API provides:

- **Context manager support**: Pythonic transaction handling with `with` statements
- **Automatic rollback**: Failed transactions are automatically rolled back
- **Transaction groups**: Group multiple transactions for complex operations
- **Sub-transactions**: Fine-grained control within transactions
- **Transaction monitoring**: Track transaction performance and status

## Core Classes

### Transaction

Main transaction class for database modifications.

::: revitpy.api.transaction.Transaction
    options:
      members:
        - __init__
        - __enter__
        - __exit__
        - commit
        - rollback
        - get_status
        - get_name
        - has_started
        - has_ended

### TransactionGroup

Groups multiple transactions into a single unit of work.

::: revitpy.api.transaction.TransactionGroup
    options:
      members:
        - __init__
        - __enter__
        - __exit__
        - assimilate
        - rollback
        - get_status
        - get_name

### SubTransaction

Provides checkpoint functionality within a transaction.

::: revitpy.api.transaction.SubTransaction
    options:
      members:
        - __init__
        - __enter__
        - __exit__
        - commit
        - rollback
        - get_status

### TransactionManager

Manages transaction lifecycle and coordination.

::: revitpy.api.transaction.TransactionManager
    options:
      members:
        - start_transaction
        - commit_transaction
        - rollback_transaction
        - is_transaction_active
        - get_current_transaction
        - get_transaction_history

## Basic Usage

### Simple Transaction

```python
from revitpy import RevitContext

def update_wall_properties():
    """Update wall properties in a transaction."""
    with RevitContext() as context:
        walls = context.elements.of_category('Walls').to_list()

        # Start transaction
        with context.transaction("Update Walls") as txn:
            for wall in walls:
                wall.set_parameter('Comments', 'Updated')

            # Commit transaction
            txn.commit()
```

### Transaction with Error Handling

```python
from revitpy.api.exceptions import TransactionError

def safe_element_update(element_id, parameters):
    """Update element with proper error handling."""
    with RevitContext() as context:
        try:
            element = context.get_element_by_id(element_id)

            with context.transaction("Update Element") as txn:
                for param_name, value in parameters.items():
                    element.set_parameter(param_name, value)

                txn.commit()
                print("Update successful")

        except TransactionError as e:
            print(f"Transaction failed: {e}")
            # Transaction automatically rolled back
        except Exception as e:
            print(f"Unexpected error: {e}")
```

### Conditional Commit

```python
def update_with_validation(element_id, new_height):
    """Update element only if validation passes."""
    with RevitContext() as context:
        element = context.get_element_by_id(element_id)

        with context.transaction("Update Height") as txn:
            # Store original value
            original_height = element.get_parameter_value('Height')

            # Update value
            element.set_parameter('Height', new_height)

            # Validate
            if new_height < 6.0:
                print("Height too low, rolling back")
                txn.rollback()
            else:
                print("Validation passed, committing")
                txn.commit()
```

## Transaction Groups

### Grouping Multiple Transactions

```python
def complex_model_update():
    """Perform multiple related transactions as a group."""
    with RevitContext() as context:
        # Start transaction group
        with context.transaction_group("Model Update") as group:

            # First transaction: Update walls
            with context.transaction("Update Walls") as txn:
                walls = context.elements.of_category('Walls')
                for wall in walls:
                    wall.set_parameter('Comments', 'Phase 1')
                txn.commit()

            # Second transaction: Update doors
            with context.transaction("Update Doors") as txn:
                doors = context.elements.of_category('Doors')
                for door in doors:
                    door.set_parameter('Mark', 'D-' + door.Id.value)
                txn.commit()

            # Third transaction: Update rooms
            with context.transaction("Update Rooms") as txn:
                rooms = context.elements.of_category('Rooms')
                for room in rooms:
                    room.set_parameter('Department', 'Engineering')
                txn.commit()

            # Assimilate group (combine into single undo operation)
            group.assimilate()
```

### Transaction Group with Rollback

```python
def atomic_multi_operation():
    """Perform multiple operations atomically - all or nothing."""
    with RevitContext() as context:
        try:
            with context.transaction_group("Atomic Update") as group:

                # Operation 1
                with context.transaction("Step 1") as txn:
                    # ... perform updates ...
                    txn.commit()

                # Operation 2 - might fail
                with context.transaction("Step 2") as txn:
                    # ... perform risky operation ...
                    if error_condition:
                        raise ValueError("Operation 2 failed")
                    txn.commit()

                # Operation 3
                with context.transaction("Step 3") as txn:
                    # ... perform final updates ...
                    txn.commit()

                group.assimilate()

        except Exception as e:
            print(f"Transaction group failed: {e}")
            # All transactions in group are automatically rolled back
```

## Sub-Transactions

### Using Sub-Transactions for Checkpoints

```python
def incremental_update_with_checkpoints():
    """Update elements with rollback checkpoints."""
    with RevitContext() as context:
        elements = context.elements.of_category('Walls').to_list()

        with context.transaction("Batch Update") as txn:
            successful_updates = 0

            for element in elements:
                # Create checkpoint
                with context.sub_transaction() as sub_txn:
                    try:
                        # Try to update
                        element.set_parameter('Height', 12.0)
                        element.set_parameter('Comments', 'Updated')

                        # Commit checkpoint
                        sub_txn.commit()
                        successful_updates += 1

                    except Exception as e:
                        # Rollback to checkpoint
                        print(f"Failed to update element {element.Id}: {e}")
                        sub_txn.rollback()
                        # Continue with next element

            # Commit main transaction
            txn.commit()
            print(f"Successfully updated {successful_updates}/{len(elements)} elements")
```

### Iterative Design Exploration

```python
def explore_design_options(wall_id, height_options):
    """Try different heights and keep the best option."""
    with RevitContext() as context:
        wall = context.get_element_by_id(wall_id)
        best_option = None
        best_score = 0

        with context.transaction("Design Exploration") as txn:
            for height in height_options:
                # Try this option
                with context.sub_transaction() as sub_txn:
                    wall.set_parameter('Height', height)

                    # Evaluate option
                    score = evaluate_design(wall)

                    if score > best_score:
                        best_score = score
                        best_option = height
                        # Keep this change
                        sub_txn.commit()
                    else:
                        # Revert this option
                        sub_txn.rollback()

            # Main transaction commits with best option
            txn.commit()
            print(f"Best option: height = {best_option}, score = {best_score}")
```

## Advanced Patterns

### Transaction Callbacks

```python
from revitpy.api.transaction import TransactionCallback

class UpdateProgressCallback(TransactionCallback):
    """Callback to track transaction progress."""

    def __init__(self):
        self.operations = []

    def on_start(self, transaction):
        print(f"Transaction started: {transaction.get_name()}")
        self.start_time = time.time()

    def on_commit(self, transaction):
        elapsed = time.time() - self.start_time
        print(f"Transaction committed: {transaction.get_name()} ({elapsed:.2f}s)")

    def on_rollback(self, transaction):
        print(f"Transaction rolled back: {transaction.get_name()}")

def update_with_progress():
    """Update elements with progress tracking."""
    callback = UpdateProgressCallback()

    with RevitContext() as context:
        with context.transaction("Update Elements", callback=callback) as txn:
            # Perform updates
            walls = context.elements.of_category('Walls')
            for wall in walls:
                wall.set_parameter('Comments', 'Updated')

            txn.commit()
```

### Transaction Retry Logic

```python
from time import sleep

def update_with_retry(element_id, parameters, max_retries=3):
    """Update element with automatic retry on failure."""
    with RevitContext() as context:
        element = context.get_element_by_id(element_id)

        for attempt in range(max_retries):
            try:
                with context.transaction(f"Update Attempt {attempt + 1}") as txn:
                    for param_name, value in parameters.items():
                        element.set_parameter(param_name, value)

                    txn.commit()
                    print(f"Update successful on attempt {attempt + 1}")
                    return True

            except TransactionError as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    sleep(1)  # Wait before retry
                else:
                    print("Max retries exceeded")
                    return False
```

### Nested Transaction Context

```python
def nested_transaction_example():
    """Demonstrate nested transaction contexts."""
    with RevitContext() as context:
        # Outer transaction for structural changes
        with context.transaction("Structural Update") as outer_txn:

            walls = context.elements.of_category('Walls')
            for wall in walls:
                wall.set_parameter('Structural', True)

            # Inner transaction group for details
            with context.transaction_group("Detail Updates") as group:

                with context.transaction("Update Marks") as txn:
                    for i, wall in enumerate(walls):
                        wall.set_parameter('Mark', f'W-{i+1:03d}')
                    txn.commit()

                with context.transaction("Update Comments") as txn:
                    for wall in walls:
                        wall.set_parameter('Comments', 'Structural wall')
                    txn.commit()

                group.assimilate()

            outer_txn.commit()
```

## Transaction Monitoring

### Performance Tracking

```python
from revitpy.performance import TransactionProfiler

def profile_transaction_performance():
    """Profile transaction performance."""
    profiler = TransactionProfiler()

    with RevitContext() as context:
        with profiler.profile("Batch Update"):
            with context.transaction("Update Elements") as txn:
                elements = context.elements.of_category('Walls').to_list()

                for element in elements:
                    element.set_parameter('Comments', 'Updated')

                txn.commit()

        # Get profiling results
        results = profiler.get_results("Batch Update")
        print(f"Transaction time: {results.duration:.2f}s")
        print(f"Elements processed: {results.element_count}")
        print(f"Time per element: {results.time_per_element:.4f}s")
```

### Transaction History

```python
def view_transaction_history():
    """View recent transaction history."""
    with RevitContext() as context:
        # Perform some transactions
        with context.transaction("Transaction 1") as txn:
            # ... updates ...
            txn.commit()

        with context.transaction("Transaction 2") as txn:
            # ... updates ...
            txn.commit()

        # Get history
        history = context.get_transaction_manager().get_transaction_history()

        print("Recent transactions:")
        for entry in history:
            print(f"  {entry.name}: {entry.status} ({entry.duration:.2f}s)")
```

## Best Practices

### 1. Always Use Context Managers

```python
# GOOD: Automatic transaction management
with context.transaction("Update") as txn:
    element.set_parameter('Value', 100)
    txn.commit()

# BAD: Manual transaction management (error-prone)
txn = context.start_transaction("Update")
try:
    element.set_parameter('Value', 100)
    txn.commit()
except:
    txn.rollback()
```

### 2. Name Transactions Descriptively

```python
# GOOD: Clear, descriptive names
with context.transaction("Update Wall Heights in Level 1") as txn:
    ...

# BAD: Vague names
with context.transaction("Update") as txn:
    ...
```

### 3. Keep Transactions Short

```python
# GOOD: Focused transaction
with context.transaction("Update Heights") as txn:
    for wall in walls:
        wall.set_parameter('Height', 10.0)
    txn.commit()

# BAD: Long-running transaction with mixed operations
with context.transaction("Big Update") as txn:
    # Many unrelated operations...
    txn.commit()
```

### 4. Use Transaction Groups for Related Operations

```python
# GOOD: Logical grouping
with context.transaction_group("Room Setup") as group:
    with context.transaction("Create Rooms") as txn:
        # Create rooms...
        txn.commit()

    with context.transaction("Apply Room Data") as txn:
        # Set room parameters...
        txn.commit()

    group.assimilate()
```

### 5. Handle Errors Explicitly

```python
# GOOD: Explicit error handling
try:
    with context.transaction("Update") as txn:
        element.set_parameter('Height', new_height)
        txn.commit()
except TransactionError as e:
    print(f"Transaction failed: {e}")
    # Handle error appropriately
```

## Performance Optimization

### Batch Updates

```python
# SLOW: Multiple transactions
for element in elements:
    with context.transaction("Update Single") as txn:
        element.set_parameter('Value', 100)
        txn.commit()

# FAST: Single transaction
with context.transaction("Update Batch") as txn:
    for element in elements:
        element.set_parameter('Value', 100)
    txn.commit()
```

### Minimize Transaction Scope

```python
# SLOW: Transaction includes unnecessary operations
with context.transaction("Update") as txn:
    elements = context.elements.of_category('Walls').to_list()  # Read operation
    analysis = analyze_elements(elements)  # Read operation

    for element in elements:
        element.set_parameter('Value', analysis[element.Id])  # Write operation

    txn.commit()

# FAST: Transaction only includes write operations
elements = context.elements.of_category('Walls').to_list()
analysis = analyze_elements(elements)

with context.transaction("Update") as txn:
    for element in elements:
        element.set_parameter('Value', analysis[element.Id])
    txn.commit()
```

## Error Handling

### Common Transaction Errors

```python
from revitpy.api.exceptions import (
    TransactionError,
    TransactionCommitError,
    TransactionRollbackError,
    TransactionNotStartedError
)

def handle_transaction_errors():
    """Demonstrate handling of transaction errors."""
    with RevitContext() as context:
        try:
            with context.transaction("Update") as txn:
                # Perform operations...
                txn.commit()

        except TransactionCommitError as e:
            print(f"Failed to commit transaction: {e}")
            # Transaction automatically rolled back

        except TransactionRollbackError as e:
            print(f"Failed to rollback transaction: {e}")

        except TransactionNotStartedError as e:
            print(f"Transaction not properly started: {e}")

        except TransactionError as e:
            print(f"General transaction error: {e}")
```

## Next Steps

- **[Element API](element-api.md)**: Work with Revit elements
- **[ORM Layer](orm.md)**: Use ORM with transactions
- **[Async Support](async.md)**: Asynchronous transaction management
- **[Performance Guide](../../guides/performance.md)**: Optimize transaction performance
