---
layout: api
title: Core API
description: Core API reference for RevitAPI, RevitDocumentProvider, Element, and Query classes
---

# Core API

The Core API provides the fundamental classes and functions for interacting with Autodesk Revit through RevitPy. The primary entry point is `RevitAPI`, which manages the Revit connection, document access, querying, and transactions.

---

## RevitAPI

The main RevitPy API class providing a high-level interface to Revit. Supports use as a context manager for automatic cleanup.

**Module:** `revitpy.api.wrapper`

### Constructor

```python
RevitAPI(revit_application=None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `revit_application` | `IRevitApplication` or `None` | Optional Revit application instance. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_connected` | `bool` | Whether the API is connected to a Revit application. |
| `active_document` | `RevitDocumentProvider` or `None` | The active document provider. Returns `None` if not connected. Raises `RevitAPIError` on failure. |
| `elements` | `QueryBuilder[Element]` | Query builder for all elements in the active document. Raises `ConnectionError` if no active document. |

### Methods

#### `connect(revit_application=None)`

Connects to a Revit application. Tests the connection by accessing the active document.

| Parameter | Type | Description |
|-----------|------|-------------|
| `revit_application` | `IRevitApplication` or `None` | Revit application to connect to. Uses the instance provided at construction if `None`. |

**Raises:** `ConnectionError` -- If no application is provided or connection fails.

```python
from revitpy.api.wrapper import RevitAPI

api = RevitAPI()
api.connect(revit_app)
```

#### `disconnect()`

Disconnects from the Revit application. Clears the active document and document cache.

#### `open_document(file_path)`

Opens a Revit document file and sets it as the active document.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file_path` | `str` | Path to the Revit file. |

**Returns:** `RevitDocumentProvider` -- The document provider for the opened document.

**Raises:** `ConnectionError` if not connected. `ModelError` if the file cannot be opened.

```python
with RevitAPI() as api:
    api.connect(revit_app)
    provider = api.open_document("/path/to/model.rvt")
```

#### `create_document(template_path=None)`

Creates a new Revit document, optionally from a template.

| Parameter | Type | Description |
|-----------|------|-------------|
| `template_path` | `str` or `None` | Optional path to a template file. |

**Returns:** `RevitDocumentProvider` -- The document provider for the new document.

**Raises:** `ConnectionError` if not connected. `ModelError` if creation fails.

#### `get_document_info(provider=None)`

Returns metadata about a document.

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | `RevitDocumentProvider` or `None` | Document provider. Uses active document if `None`. |

**Returns:** `DocumentInfo` -- A dataclass with `title`, `path`, `is_modified`, `is_read_only`, and `version` fields.

#### `save_document(provider=None)`

Saves the specified or active document.

**Returns:** `bool` -- `True` if saved successfully.

**Raises:** `RevitAPIError` if save fails.

#### `close_document(provider=None, save_changes=True)`

Closes the specified or active document.

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | `RevitDocumentProvider` or `None` | Document provider. Uses active document if `None`. |
| `save_changes` | `bool` | Whether to save changes before closing. Default is `True`. |

**Returns:** `bool` -- `True` if closed successfully.

#### `query(element_type=None)`

Creates a typed query builder.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element_type` | `type[Element]` or `None` | Optional element type to query for. |

**Returns:** `QueryBuilder[T]` -- A query builder scoped to the given type.

**Raises:** `ConnectionError` if no active document.

```python
walls = api.query(WallElement).equals("Level", "Level 1").to_list()
```

#### `transaction(name=None, **kwargs)`

Creates a transaction for model modifications. The returned `Transaction` object can be used as a context manager.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` or `None` | Transaction name shown in the Undo menu. Auto-generated if `None`. |
| `**kwargs` | | Additional options passed to `TransactionOptions`. |

**Returns:** `Transaction` -- A transaction context manager.

**Raises:** `ConnectionError` if no active document.

```python
with api.transaction("Update Walls") as txn:
    element.set_parameter_value("Comments", "Updated")
    # auto-commits on exit if no exception
```

#### `transaction_group(name=None)`

Creates a transaction group for coordinating multiple transactions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` or `None` | Group name. Auto-generated if `None`. |

**Returns:** `TransactionGroup` -- A transaction group context manager.

#### `get_element_by_id(element_id)`

Retrieves an element by its ID.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element_id` | `int` or element ID | The element's ID. |

**Returns:** `Element` or `None` -- The wrapped element, or `None` if not found.

**Raises:** `ConnectionError` if no active document.

#### `delete_elements(elements)`

Deletes one or more elements.

| Parameter | Type | Description |
|-----------|------|-------------|
| `elements` | `Element`, `list[Element]`, or `ElementSet` | Elements to delete. |

#### `refresh_cache()`

Refreshes the element cache and cleans up dead document references.

### Context Manager Usage

```python
from revitpy.api.wrapper import RevitAPI

with RevitAPI(revit_app) as api:
    api.connect()
    walls = api.elements.equals("Category", "Walls").to_list()
    for wall in walls:
        print(wall.name)
# disconnect() called automatically on exit
```

---

## RevitDocumentProvider

Bridges RevitPy to an actual Revit document. Implements both `IElementProvider` and `ITransactionProvider`.

**Module:** `revitpy.api.wrapper`

### Constructor

```python
RevitDocumentProvider(revit_document)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `revit_document` | `IRevitDocument` | The underlying Revit document object. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `document` | `IRevitDocument` | The underlying Revit document. |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_all_elements()` | `list[Element]` | Returns all elements from the document. |
| `get_elements_of_type(element_type)` | `list[Element]` | Returns elements of a specific type. |
| `get_element_by_id(element_id)` | `Element` or `None` | Returns an element by ID, using a cache for repeated lookups. Raises `ElementNotFoundError` on API errors. |
| `delete_elements(element_ids)` | `None` | Deletes elements by their IDs. |
| `refresh_element_cache()` | `None` | Clears the internal element cache. |
| `start_transaction(name)` | transaction handle | Starts a new transaction on the document. |
| `commit_transaction(transaction)` | `bool` | Commits a transaction. Returns `True` on success. |
| `rollback_transaction(transaction)` | `bool` | Rolls back a transaction. Returns `True` on success. |
| `is_in_transaction()` | `bool` | Returns whether a transaction is currently active. |

---

## DocumentInfo

Dataclass containing metadata about a Revit document.

**Module:** `revitpy.api.wrapper`

```python
@dataclass
class DocumentInfo:
    title: str
    path: str
    is_modified: bool = False
    is_read_only: bool = False
    version: str | None = None
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `title` | `str` | Document title including extension. |
| `path` | `str` | Full file path. |
| `is_modified` | `bool` | Whether the document has unsaved changes. |
| `is_read_only` | `bool` | Whether the document is read-only. |
| `version` | `str` or `None` | Revit version string. |
| `name` | `str` | Document name without file extension (computed property). |

---

## Usage Examples

### Basic Element Access

```python
from revitpy.api.wrapper import RevitAPI

def list_all_walls(revit_app):
    """List all walls in the active document."""
    with RevitAPI(revit_app) as api:
        api.connect()

        walls = api.elements.equals("Category", "Walls").execute()

        for wall in walls:
            print(f"Wall ID: {wall.id}")
            print(f"Wall Name: {wall.name}")
            height = wall.get_parameter_value("Height")
            print(f"Wall Height: {height}")
            print("---")
```

### Transaction Management

```python
from revitpy.api.wrapper import RevitAPI

def update_wall_comments(revit_app):
    """Update comments on all walls."""
    with RevitAPI(revit_app) as api:
        api.connect()
        walls = api.elements.equals("Category", "Walls").to_list()

        with api.transaction("Update Wall Comments"):
            for wall in walls:
                height = wall.get_parameter_value("Height")
                wall.set_parameter_value("Comments", f"Height: {height}")
            # auto-commits on successful exit
```

### Error Handling

```python
from revitpy.api.wrapper import RevitAPI
from revitpy.api.exceptions import (
    ConnectionError,
    ElementNotFoundError,
    RevitAPIError,
)

def safe_element_access(revit_app, element_id):
    """Safely access an element by ID."""
    try:
        with RevitAPI(revit_app) as api:
            api.connect()
            element = api.get_element_by_id(element_id)
            if element is None:
                print(f"Element {element_id} not found")
                return None
            return element.name

    except ConnectionError as e:
        print(f"Connection error: {e}")
        return None
    except ElementNotFoundError as e:
        print(f"Element lookup error: {e}")
        return None
    except RevitAPIError as e:
        print(f"Revit API error: {e}")
        return None
```

---

## Next Steps

- **[Element API]({{ '/reference/api/element-api/' | relative_url }})**: Detailed element manipulation
- **[Transaction API]({{ '/reference/api/transaction-api/' | relative_url }})**: Transaction management
- **[Query API]({{ '/reference/api/query/' | relative_url }})**: LINQ-style queries
- **[ORM Layer]({{ '/reference/api/orm/' | relative_url }})**: Higher-level ORM context
