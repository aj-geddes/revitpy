---
layout: api
title: Core API
description: Core API reference for RevitContext, Element, Transaction, and Query classes
---

# Core API

The Core API provides the fundamental classes and functions for interacting with Autodesk Revit through RevitPy.

## RevitContext

The main entry point for all RevitPy operations. Use as a context manager to ensure proper resource cleanup.

```python
from revitpy import RevitContext

with RevitContext() as context:
    walls = context.elements.of_category('Walls')
```

### Constructor

```python
RevitContext(document=None, application=None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `document` | `Document` | Optional Revit document. Uses active document if not specified. |
| `application` | `Application` | Optional Revit application instance. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `elements` | `ElementQueryBuilder` | Query builder for accessing Revit elements |
| `document` | `Document` | The active Revit document |
| `application` | `Application` | The Revit application instance |

### Methods

#### `transaction(name)`
Creates a new transaction for modifying the Revit model.

```python
with context.transaction("Update Elements") as txn:
    # Make changes
    txn.commit()
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Name of the transaction (shown in Undo menu) |

**Returns:** `Transaction` - A transaction context manager

#### `get_element_by_id(element_id)`
Retrieves an element by its ID.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element_id` | `int` or `ElementId` | The element's ID |

**Returns:** `Element` - The wrapped element
**Raises:** `ElementNotFound` - If element doesn't exist

#### `get_active_document()`
Returns the currently active Revit document.

**Returns:** `Document` - The active document

#### `get_application()`
Returns the Revit application instance.

**Returns:** `Application` - The Revit application

---

## Element

Wrapper class for Revit elements providing a Pythonic interface.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `Id` | `ElementId` | The element's unique identifier |
| `Name` | `str` | The element's name |
| `Category` | `str` | The element's category name |
| `BoundingBox` | `BoundingBox` | The element's bounding box |

### Methods

#### `get_parameter(name)`
Gets a parameter value by name.

```python
height = wall.get_parameter('Unconnected Height')
print(height.value, height.unit)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Parameter name |

**Returns:** `ParameterValue` - The parameter value with unit information
**Raises:** `ParameterNotFound` - If parameter doesn't exist

#### `set_parameter(name, value)`
Sets a parameter value. Must be called within a transaction.

```python
with context.transaction("Update") as txn:
    wall.set_parameter('Comments', 'Updated by RevitPy')
    txn.commit()
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Parameter name |
| `value` | `any` | New value |

**Raises:** `ParameterNotFound`, `ReadOnlyParameter`

#### `get_geometry(options=None)`
Returns the element's geometry.

**Returns:** `GeometryElement` - The element's geometry

#### `delete()`
Deletes the element. Must be called within a transaction.

---

## Transaction

Manages Revit transactions for model modifications.

### Usage

```python
with context.transaction("My Changes") as txn:
    # Make modifications
    wall.set_parameter('Comments', 'Updated')

    # Commit or rollback
    txn.commit()
    # or txn.rollback()
```

### Methods

#### `commit()`
Commits all changes made within the transaction.

#### `rollback()`
Rolls back all changes made within the transaction.

#### `get_status()`
Returns the current transaction status.

**Returns:** `str` - One of: `'Started'`, `'Committed'`, `'RolledBack'`

---

## QueryResult

Result of an element query operation.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `elements` | `list[Element]` | The queried elements |
| `count` | `int` | Number of elements |
| `execution_time` | `float` | Query execution time in seconds |

### Methods

#### `to_list()`
Converts results to a Python list.

**Returns:** `list[Element]`

#### `to_dict()`
Converts results to a dictionary keyed by element ID.

**Returns:** `dict[int, Element]`

---

## Usage Examples

### Basic Element Access

```python
from revitpy import RevitContext

def list_all_walls():
    """List all walls in the active document."""
    with RevitContext() as context:
        walls = context.elements.of_category('Walls')

        for wall in walls:
            print(f"Wall ID: {wall.Id}")
            print(f"Wall Name: {wall.Name}")
            print(f"Wall Height: {wall.get_parameter('Height').value}")
            print("---")
```

### Transaction Management

```python
def update_wall_comments():
    """Update comments for all walls."""
    with RevitContext() as context:
        walls = context.elements.of_category('Walls')

        with context.transaction("Update Wall Comments") as txn:
            for wall in walls:
                height = wall.get_parameter('Height').value
                comment = f"Height: {height:.1f} ft"
                wall.set_parameter('Comments', comment)

            txn.commit()
```

### Error Handling

```python
from revitpy import RevitContext
from revitpy.exceptions import ElementNotFound, TransactionFailed

def safe_element_access(element_id):
    """Safely access an element by ID."""
    try:
        with RevitContext() as context:
            element = context.get_element_by_id(element_id)
            return element.Name
    except ElementNotFound as e:
        print(f"Element {element_id} not found: {e}")
        return None
    except TransactionFailed as e:
        print(f"Transaction failed: {e}")
        return None
```

---

## Performance Tips

### 1. Use Context Managers

Always use `with RevitContext()` to ensure proper resource cleanup:

```python
# Good
with RevitContext() as context:
    elements = context.elements.of_category('Walls')

# Bad - resources may not be cleaned up
context = RevitContext()
elements = context.elements.of_category('Walls')
```

### 2. Minimize Transactions

Group related operations in a single transaction:

```python
# Good - Single transaction
with RevitContext() as context:
    with context.transaction("Batch Update") as txn:
        for wall in walls:
            wall.set_parameter('Comments', 'Updated')
        txn.commit()

# Bad - Multiple transactions (slower)
with RevitContext() as context:
    for wall in walls:
        with context.transaction("Update Wall") as txn:
            wall.set_parameter('Comments', 'Updated')
            txn.commit()
```

### 3. Cache Frequently Used Data

Store commonly accessed data to avoid repeated queries:

```python
def process_elements_efficiently():
    with RevitContext() as context:
        # Cache wall types once
        wall_types = {wt.Name: wt for wt in context.elements.of_category('WallTypes')}

        for wall in context.elements.of_category('Walls'):
            wall_type_name = wall.WallType.Name
            wall_type = wall_types.get(wall_type_name)  # Fast lookup
            # Process wall with cached type data
```

---

## Thread Safety

<div class="callout callout-warning">
  <div class="callout-title">Revit API Limitations</div>
  <p>The Revit API has threading limitations. Operations that modify the model must be performed on the main UI thread. Use RevitPy's async support for better concurrency patterns.</p>
</div>

Each thread needs its own RevitContext:

```python
import threading
from revitpy import RevitContext

def process_in_thread():
    with RevitContext() as context:
        walls = context.elements.of_category('Walls')
        return len(walls)

threads = []
for i in range(4):
    thread = threading.Thread(target=process_in_thread)
    threads.append(thread)
    thread.start()

for thread in threads:
    thread.join()
```

---

## Next Steps

- **[ORM Layer]({{ '/reference/api/orm/' | relative_url }})**: Learn about LINQ-style queries
- **[Async Support]({{ '/reference/api/async/' | relative_url }})**: Asynchronous operations
- **[Events]({{ '/reference/api/events/' | relative_url }})**: Event handling
- **[Testing]({{ '/reference/api/testing/' | relative_url }})**: Testing utilities
