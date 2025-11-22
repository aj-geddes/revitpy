---
layout: api
title: Core API
description: Core API reference documentation
---

# Core API

The Core API provides the fundamental classes and functions for interacting with Autodesk Revit through RevitPy.

## RevitContext

The main entry point for all RevitPy operations.

::: revitpy.orm.context.RevitContext
    options:
      members:
        - __init__
        - __enter__
        - __exit__
        - elements
        - transaction
        - get_element_by_id
        - get_active_document
        - get_application

## Element API

Classes and functions for working with Revit elements.

::: revitpy.api.element.Element
    options:
      members:
        - Name
        - Id
        - Category
        - get_parameter
        - set_parameter
        - get_geometry
        - delete

::: revitpy.api.element.ElementWrapper
    options:
      members:
        - __init__
        - wrap_element
        - unwrap_element
        - get_properties

## Query API

Query execution and result handling.

::: revitpy.api.query.QueryExecutor
    options:
      members:
        - execute
        - execute_async
        - explain_query
        - get_statistics

::: revitpy.api.query.QueryResult
    options:
      members:
        - elements
        - count
        - execution_time
        - to_list
        - to_dict

## Transaction API

Transaction management for Revit operations.

::: revitpy.api.transaction.Transaction
    options:
      members:
        - __init__
        - __enter__
        - __exit__
        - commit
        - rollback
        - get_status

::: revitpy.api.transaction.TransactionManager
    options:
      members:
        - start_transaction
        - commit_transaction
        - rollback_transaction
        - is_transaction_active

## Wrapper API

Low-level wrapper around the Revit API.

::: revitpy.api.wrapper.RevitAPIWrapper
    options:
      members:
        - get_application
        - get_active_document
        - create_transaction
        - get_selection
        - refresh_active_view

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
            print(f"Wall Height: {wall.get_parameter('Height').AsDouble()}")
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
                height = wall.get_parameter('Height').AsDouble()
                comment = f"Height: {height:.1f} ft"
                wall.set_parameter('Comments', comment)

            txn.commit()
```

### Element Creation
```python
def create_wall(start_point, end_point, height):
    """Create a new wall between two points."""
    with RevitContext() as context:
        with context.transaction("Create Wall") as txn:
            # Get wall type
            wall_types = context.elements.of_category('WallTypes')
            wall_type = wall_types.first()

            # Create wall using Revit API
            from Autodesk.Revit.DB import Wall, Line, XYZ

            line = Line.CreateBound(
                XYZ(start_point[0], start_point[1], 0),
                XYZ(end_point[0], end_point[1], 0)
            )

            wall = Wall.Create(
                context.get_active_document(),
                line,
                wall_type.Id,
                context.get_active_document().ActiveView.GenLevel.Id,
                height,
                0,
                False,
                False
            )

            txn.commit()
            return context.wrap_element(wall)
```

### Error Handling
```python
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

## Performance Tips

### 1. Use Context Managers
Always use `with RevitContext()` to ensure proper resource cleanup:

```python
# Good
with RevitContext() as context:
    elements = context.elements.of_category('Walls')

# Bad
context = RevitContext()
elements = context.elements.of_category('Walls')
# Resources may not be properly cleaned up
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

# Bad - Multiple transactions
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

## Thread Safety

The Core API is designed to be thread-safe within the constraints of the Revit API:

```python
import threading
from revitpy import RevitContext

def process_in_thread():
    """Process elements in a background thread."""
    # Each thread needs its own RevitContext
    with RevitContext() as context:
        walls = context.elements.of_category('Walls')
        return len(walls)

# Create and start threads
threads = []
for i in range(4):
    thread = threading.Thread(target=process_in_thread)
    threads.append(thread)
    thread.start()

# Wait for completion
for thread in threads:
    thread.join()
```

!!! warning "Revit API Limitations"
    The Revit API itself has threading limitations. Operations that modify the Revit model must be performed on the main UI thread. Use RevitPy's async support for better concurrency patterns.

## Next Steps

- **[ORM Layer](orm.md)**: Learn about the object-relational mapping capabilities
- **[Element Sets](element-sets.md)**: Work with collections of elements efficiently
- **[Transaction Management](transaction-api.md)**: Master transaction patterns
- **[Error Handling](../guides/error-handling.md)**: Implement robust error handling
