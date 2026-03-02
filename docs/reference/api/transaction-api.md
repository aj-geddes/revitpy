---
layout: api
title: Transaction API
description: Transaction management with context managers and batch operations
---

# Transaction API

The Transaction API provides robust transaction management for Revit model modifications, including context manager support, automatic rollback, transaction groups, and retry logic.

**Module:** `revitpy.api.transaction`

---

## TransactionStatus

Enumeration of possible transaction states.

```python
class TransactionStatus(Enum):
    NOT_STARTED = "not_started"
    STARTED     = "started"
    COMMITTED   = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED      = "failed"
```

---

## TransactionOptions

Dataclass for configuring transaction behavior.

```python
TransactionOptions(
    name=None,
    description=None,
    auto_commit=True,
    timeout_seconds=None,
    retry_count=0,
    retry_delay=1.0,
    suppress_warnings=False
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` or `None` | `None` | Transaction name. Auto-generated if `None`. |
| `description` | `str` or `None` | `None` | Optional description. |
| `auto_commit` | `bool` | `True` | Auto-commit on successful context manager exit. |
| `timeout_seconds` | `float` or `None` | `None` | Optional timeout. |
| `retry_count` | `int` | `0` | Number of retry attempts on failure. |
| `retry_delay` | `float` | `1.0` | Delay in seconds between retries. |
| `suppress_warnings` | `bool` | `False` | Whether to suppress Revit API warnings. |

---

## Transaction

Pythonic transaction wrapper with synchronous and asynchronous context manager support.

### Constructor

```python
Transaction(provider: ITransactionProvider, options: TransactionOptions | None = None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | `ITransactionProvider` | The transaction provider (typically a `RevitDocumentProvider`). |
| `options` | `TransactionOptions` or `None` | Configuration options. Uses defaults if `None`. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Transaction name. |
| `status` | `TransactionStatus` | Current transaction status. |
| `is_active` | `bool` | `True` when status is `STARTED`. |
| `duration` | `float` or `None` | Elapsed time in seconds since start, or `None` if not started. |

### Methods

#### `start()`

Starts the transaction. Must be in `NOT_STARTED` state.

**Raises:** `TransactionError` if the transaction was already started or if starting fails.

#### `commit()`

Commits the transaction. Executes all pending operations added via `add_operation()`, then commits through the provider. On failure, automatically rolls back.

**Raises:** `TransactionError` if the transaction is not active or if commit fails.

#### `rollback()`

Rolls back the transaction. Safe to call even if the transaction has already failed.

**Raises:** `TransactionError` only if the rollback itself encounters an error.

#### `add_operation(operation)`

Adds a callable to be executed during commit.

| Parameter | Type | Description |
|-----------|------|-------------|
| `operation` | `Callable` | A zero-argument callable. |

**Raises:** `TransactionError` if the transaction is not active.

#### `add_commit_handler(handler)`

Registers a callback to run after successful commit.

| Parameter | Type | Description |
|-----------|------|-------------|
| `handler` | `Callable` | A zero-argument callable. |

#### `add_rollback_handler(handler)`

Registers a callback to run after rollback.

| Parameter | Type | Description |
|-----------|------|-------------|
| `handler` | `Callable` | A zero-argument callable. |

### Context Manager Usage

When used as a context manager, the transaction starts on entry. On exit, it auto-commits if `auto_commit=True` and no exception occurred; otherwise it rolls back.

```python
from revitpy.api.transaction import Transaction, TransactionOptions

options = TransactionOptions(name="Update Walls", auto_commit=True)
txn = Transaction(provider, options)

with txn:
    element.set_parameter_value("Comments", "Updated")
    # auto-commits on successful exit
```

Explicit commit/rollback with `auto_commit=False`:

```python
options = TransactionOptions(name="Conditional Update", auto_commit=False)

with Transaction(provider, options) as txn:
    element.set_parameter_value("Height", new_height)

    if new_height >= 6.0:
        txn.commit()
    else:
        txn.rollback()
```

### Async Context Manager

`Transaction` also supports `async with`:

```python
async with Transaction(provider, options) as txn:
    element.set_parameter_value("Comments", "Async update")
    # auto-commits on exit
```

---

## TransactionGroup

Groups multiple transactions into a single coordinated unit. Supports both sync and async context managers.

### Constructor

```python
TransactionGroup(provider: ITransactionProvider, name: str | None = None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | `ITransactionProvider` | The transaction provider. |
| `name` | `str` or `None` | Group name. Auto-generated if `None`. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Group name. |
| `status` | `TransactionStatus` | Current group status. |

### Methods

#### `add_transaction(options=None)`

Adds a new transaction to the group.

| Parameter | Type | Description |
|-----------|------|-------------|
| `options` | `TransactionOptions` or `None` | Options for the new transaction. `auto_commit` defaults to `False` in groups. |

**Returns:** `Transaction` -- The newly created transaction.

**Raises:** `TransactionError` if the group has already been started.

#### `start_all()`

Starts all transactions in the group. If any start fails, all are rolled back.

**Raises:** `TransactionError` if the group was already started or if any transaction fails to start.

#### `commit_all()`

Commits all transactions in order. If any commit fails, all previously committed transactions are rolled back.

**Raises:** `TransactionError` on failure.

#### `rollback_all()`

Rolls back all transactions in the group.

### Context Manager Usage

```python
from revitpy.api.transaction import TransactionGroup

with TransactionGroup(provider, "Batch Operations") as group:
    txn1 = group.add_transaction(TransactionOptions(name="Step 1"))
    txn2 = group.add_transaction(TransactionOptions(name="Step 2"))

    # All transactions started on group entry
    # element modifications happen here...

    # All committed on successful exit; all rolled back on exception
```

---

## ITransactionProvider

Abstract protocol that transaction providers must implement. `RevitDocumentProvider` implements this.

```python
class ITransactionProvider(ABC):
    def start_transaction(self, name: str) -> Any: ...
    def commit_transaction(self, transaction: Any) -> bool: ...
    def rollback_transaction(self, transaction: Any) -> bool: ...
    def is_in_transaction(self) -> bool: ...
```

---

## Convenience Functions

### `transaction(provider, name=None, auto_commit=True, retry_count=0, retry_delay=1.0)`

Factory function that creates a `Transaction` with common options.

**Returns:** `Transaction`

```python
from revitpy.api.transaction import transaction

txn = transaction(provider, name="Quick Update")
with txn:
    element.set_parameter_value("Mark", "A-101")
```

### `transaction_scope(provider, name=None, **kwargs)`

Context manager that yields a `Transaction`.

```python
from revitpy.api.transaction import transaction_scope

with transaction_scope(provider, name="Scoped Update") as txn:
    element.set_parameter_value("Comments", "Updated in scope")
```

### `async_transaction_scope(provider, name=None, **kwargs)`

Async context manager that yields a `Transaction`.

```python
from revitpy.api.transaction import async_transaction_scope

async with async_transaction_scope(provider, name="Async Update") as txn:
    element.set_parameter_value("Comments", "Async update")
```

### `retry_transaction(provider, operation, max_retries=3, delay=1.0, name=None)`

Executes an operation inside a transaction with automatic retry on failure.

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | `ITransactionProvider` | Transaction provider. |
| `operation` | `Callable[[], Any]` | Zero-argument callable to execute. |
| `max_retries` | `int` | Maximum number of retries (in addition to the initial attempt). Default `3`. |
| `delay` | `float` | Delay in seconds between retries. Default `1.0`. |
| `name` | `str` or `None` | Transaction name. |

**Returns:** The result of `operation()`.

**Raises:** The last exception if all attempts fail.

```python
from revitpy.api.transaction import retry_transaction

def risky_operation():
    element.set_parameter_value("Height", 12.0)
    return True

result = retry_transaction(provider, risky_operation, max_retries=3)
```

---

## Usage Examples

### Simple Transaction with Auto-Commit

```python
from revitpy.api.wrapper import RevitAPI

def update_walls(revit_app):
    with RevitAPI(revit_app) as api:
        api.connect()
        walls = api.elements.equals("Category", "Walls").to_list()

        with api.transaction("Update Walls"):
            for wall in walls:
                wall.set_parameter_value("Comments", "Reviewed")
            # auto-commits on exit
```

### Transaction Group

```python
from revitpy.api.wrapper import RevitAPI
from revitpy.api.transaction import TransactionOptions

def staged_updates(revit_app):
    with RevitAPI(revit_app) as api:
        api.connect()
        provider = api.active_document

        with api.transaction_group("Multi-Step") as group:
            txn1 = group.add_transaction(TransactionOptions(name="Walls"))
            txn2 = group.add_transaction(TransactionOptions(name="Doors"))
            # modify elements...
            # all committed or all rolled back together
```

### Monitoring Transaction Duration

```python
from revitpy.api.wrapper import RevitAPI

def timed_update(revit_app):
    with RevitAPI(revit_app) as api:
        api.connect()

        with api.transaction("Timed Update") as txn:
            walls = api.elements.equals("Category", "Walls").to_list()
            for wall in walls:
                wall.set_parameter_value("Comments", "Updated")

        print(f"Transaction took {txn.duration:.3f}s")
        print(f"Status: {txn.status.value}")
```

---

## Best Practices

1. **Use context managers** -- They handle start, commit, and rollback automatically.
2. **Name transactions descriptively** -- Names appear in the Revit Undo menu.
3. **Keep transactions short** -- Move read-only operations outside the transaction scope.
4. **Batch modifications** -- Use a single transaction for related writes instead of many small transactions.
5. **Handle errors explicitly** -- Catch `TransactionError` for robust error handling.

---

## Next Steps

- **[Element API]({{ '/reference/api/element-api/' | relative_url }})**: Element manipulation
- **[Core API]({{ '/reference/api/core/' | relative_url }})**: `RevitAPI.transaction()` shorthand
- **[Async Support]({{ '/reference/api/async/' | relative_url }})**: Async transaction patterns
