---
layout: page
title: Getting Started
description: Install RevitPy and learn the basics: connect to Revit, query elements with the fluent QueryBuilder, and run your first transaction with auto-rollback.
doc_tier: user
---

# Getting Started

This page covers installation, connecting to Revit, running your first query, and executing your first transaction.

## Installation

Install RevitPy from PyPI:

```bash
pip install revitpy
```

RevitPy requires Python 3.11 or later.

## Basic Usage Pattern

The primary entry point is the `RevitAPI` class. You create an instance, connect to a Revit application, and then use it to query elements, open documents, and run transactions.

```python
from revitpy import RevitAPI

# Create the API wrapper and connect
api = RevitAPI()
api.connect(revit_application)
```

`RevitAPI` can also be used as a context manager. When the `with` block exits, the API disconnects automatically:

```python
with RevitAPI() as api:
    api.connect(revit_application)
    # work with the API
# api.disconnect() is called automatically
```

### Key Properties and Methods

Once connected, `RevitAPI` provides:

- `api.is_connected` -- Returns `True` if connected to Revit.
- `api.active_document` -- Returns the active `RevitDocumentProvider`, or `None`.
- `api.elements` -- Returns a `QueryBuilder` for all elements in the active document.
- `api.query(element_type)` -- Returns a typed `QueryBuilder`.
- `api.transaction(name)` -- Returns a `Transaction` context manager.
- `api.transaction_group(name)` -- Returns a `TransactionGroup` context manager.
- `api.get_element_by_id(element_id)` -- Returns an `Element` or `None`.
- `api.open_document(file_path)` -- Opens a Revit document and returns a `RevitDocumentProvider`.
- `api.create_document(template_path)` -- Creates a new document.
- `api.save_document()` -- Saves the active document.
- `api.close_document(save_changes=True)` -- Closes the active document.
- `api.get_document_info()` -- Returns a `DocumentInfo` dataclass with `title`, `path`, `is_modified`, `is_read_only`, and `version` fields.

## Your First Query

Use `api.elements` to get a `QueryBuilder`, then chain filter and sort methods:

```python
from revitpy import RevitAPI

api = RevitAPI()
api.connect(revit_application)

# Find all elements named "Wall-1"
walls = (
    api.elements
    .equals("Name", "Wall-1")
    .execute()
)

for wall in walls:
    print(wall.name, wall.id)
```

The `QueryBuilder` supports methods like `equals`, `contains`, `starts_with`, `order_by`, `skip`, `take`, and terminal operations like `execute()`, `first()`, `count()`, and `to_list()`. See the [Query Builder guide](features/query-builder) for the full API.

## Your First Transaction

All modifications to a Revit model must occur inside a transaction. RevitPy provides a `Transaction` class that works as a context manager:

```python
from revitpy import RevitAPI

api = RevitAPI()
api.connect(revit_application)

# Use transaction as a context manager
with api.transaction("Update Comments") as txn:
    element = api.get_element_by_id(12345)
    if element:
        element.set_parameter_value("Comments", "Updated by RevitPy")

# The transaction auto-commits on success, or rolls back on exception.
```

### Transaction Options

The `TransactionOptions` dataclass controls transaction behavior:

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` or `None` | Auto-generated | Transaction name |
| `description` | `str` or `None` | `None` | Description |
| `auto_commit` | `bool` | `True` | Commit automatically when the context manager exits without error |
| `timeout_seconds` | `float` or `None` | `None` | Timeout for the transaction |
| `retry_count` | `int` | `0` | Number of retry attempts |
| `retry_delay` | `float` | `1.0` | Delay in seconds between retries |
| `suppress_warnings` | `bool` | `False` | Suppress transaction warnings |

You can pass these options through `api.transaction()`:

```python
with api.transaction("My Transaction", auto_commit=True, retry_count=2) as txn:
    # operations
    pass
```

### Transaction Groups

For coordinating multiple transactions together, use `TransactionGroup`:

```python
with api.transaction_group("Batch Update") as group:
    txn1 = group.add_transaction()
    txn2 = group.add_transaction()
    # All transactions are started, committed, or rolled back together.
```

## Working with Elements

The `Element` class wraps Revit elements with Pythonic property access, caching, and change tracking.

```python
element = api.get_element_by_id(12345)

# Read parameters
name = element.name
comments = element.get_parameter_value("Comments")

# Write parameters
element.set_parameter_value("Comments", "New value")

# Check for unsaved changes
if element.is_dirty:
    print("Changes:", element.changes)

# Discard changes
element.discard_changes()

# Refresh from Revit
element.refresh()
```

Elements have built-in property mappings for common parameters: `name`, `family_name`, `type_name`, `level`, `comments`, and `mark`.

## Next Steps

- [Query Builder](features/query-builder) -- Learn the full query API with filters, sorting, and pagination.
- [ORM](features/orm) -- Use the ORM layer for change tracking and relationship management.
- [Events](features/events) -- React to Revit events with the event system.
- [Async Support](features/async) -- Run operations asynchronously for better responsiveness.
- [Testing](features/testing) -- Test your code without a Revit installation.
