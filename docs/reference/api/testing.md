---
layout: api
title: Testing Framework API
description: Mock objects and utilities for testing RevitPy applications without Revit
---

# Testing Framework API

The Testing Framework provides mock implementations of the Revit environment, enabling unit and integration testing of RevitPy applications without a running Revit instance. It includes mock elements, documents, transactions, applications, and state persistence.

**Module:** `revitpy.testing.mock_revit`

---

## MockParameter

Dataclass representing a mock Revit parameter with typed value accessors.

### Constructor

```python
MockParameter(
    name: str,
    value: Any = None,
    type_name: str = "String",
    storage_type: str = "String",
    is_read_only: bool = False
)
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | | Parameter name. |
| `value` | `Any` | `None` | The parameter value. |
| `type_name` | `str` | `"String"` | Python type name of the value. |
| `storage_type` | `str` | `"String"` | Revit storage type. |
| `is_read_only` | `bool` | `False` | Whether the parameter is read-only. |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `AsString()` | `str` | Returns the value as a string. Returns `""` if `None`. |
| `AsDouble()` | `float` | Returns the value as a float. Returns `0.0` on conversion failure. |
| `AsInteger()` | `int` | Returns the value as an integer. Returns `0` on conversion failure. |
| `AsValueString()` | `str` | Alias for `AsString()`. |

```python
param = MockParameter("Height", 10.5, storage_type="Double")
print(param.AsDouble())   # 10.5
print(param.AsString())   # "10.5"
print(param.AsInteger())  # 10
```

---

## MockElementId

Mock Revit element ID with equality and hashing support.

### Constructor

```python
MockElementId(value: int)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `int` | The integer element ID. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `IntegerValue` | `int` | The raw integer ID. |

Supports `==`, `hash()`, and `str()`.

```python
eid = MockElementId(12345)
print(eid.IntegerValue)  # 12345
print(str(eid))          # "12345"
```

---

## MockElement

Mock Revit element with configurable parameters and properties.

### Constructor

```python
MockElement(
    element_id: int | None = None,
    name: str = "MockElement",
    category: str = "Generic",
    element_type: str = "Element"
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `element_id` | `int` or `None` | `None` | Element ID. Auto-generated if `None`. |
| `name` | `str` | `"MockElement"` | Element name. |
| `category` | `str` | `"Generic"` | Element category. |
| `element_type` | `str` | `"Element"` | Element type name. |

Default parameters (`Name`, `Category`, `Type`, `Comments`, `Mark`) are created automatically.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `Id` | `MockElementId` | The element's ID. |
| `Name` | `str` | The element name. |
| `Category` | `str` | The element category. |
| `ElementType` | `str` | The element type. |

### Methods

#### `GetParameterValue(parameter_name)`

Gets a parameter by name and returns the `MockParameter` object.

**Returns:** `MockParameter`

**Raises:** `KeyError` if the parameter does not exist.

#### `SetParameterValue(parameter_name, value)`

Sets a parameter value. Creates the parameter if it does not exist.

**Raises:** `ValueError` if the parameter is read-only.

```python
element = MockElement(name="Wall-1", category="Walls")
element.SetParameterValue("Height", 10.0)
element.SetParameterValue("Comments", "Test wall")

param = element.GetParameterValue("Height")
print(param.AsDouble())  # 10.0
```

#### `GetParameter(parameter_name)`

Gets the `MockParameter` object, or `None` if not found.

**Returns:** `MockParameter` or `None`

#### `SetParameter(parameter_name, parameter)`

Sets a `MockParameter` object directly.

#### `GetAllParameters()`

Returns a copy of all parameters.

**Returns:** `dict[str, MockParameter]`

#### `HasParameter(parameter_name)`

Checks whether a parameter exists.

**Returns:** `bool`

#### `GetProperty(property_name)` / `SetProperty(property_name, value)`

Gets or sets a custom property on the element.

#### `to_dict()` / `from_dict(data)`

Serializes the element to a dictionary and deserializes from one. Useful for fixture persistence.

---

## MockTransaction

Mock Revit transaction with start, commit, and rollback tracking.

### Constructor

```python
MockTransaction(name: str = "MockTransaction")
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Transaction name. |
| `is_started` | `bool` | Whether `Start()` has been called. |
| `is_committed` | `bool` | Whether `Commit()` has been called. |
| `is_rolled_back` | `bool` | Whether `RollBack()` has been called. |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `Start()` | `bool` | Marks the transaction as started. Always returns `True`. |
| `Commit()` | `bool` | Commits the transaction. Returns `False` if not started. |
| `RollBack()` | `bool` | Rolls back the transaction. Returns `False` if not started. |

```python
txn = MockTransaction("Update Walls")
txn.Start()
# ... make modifications ...
txn.Commit()

assert txn.is_committed
assert not txn.is_rolled_back
```

---

## MockDocument

Mock Revit document with element storage, transaction support, and serialization.

### Constructor

```python
MockDocument(
    title: str = "MockDocument.rvt",
    path: str = "",
    is_family_document: bool = False
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | `"MockDocument.rvt"` | Document title. |
| `path` | `str` | `""` | File path. |
| `is_family_document` | `bool` | `False` | Whether this is a family document. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `Title` | `str` | Document title. |
| `PathName` | `str` | File path. |
| `IsFamilyDocument` | `bool` | Whether this is a family document. |

### Methods

#### `CreateElement(name="NewElement", category="Generic", element_type="Element")`

Creates a new element in the document with an auto-incremented ID.

**Returns:** `MockElement`

#### `AddElement(element)`

Adds an existing element to the document.

**Returns:** `MockElement`

#### `GetElement(element_id)`

Gets an element by integer ID or `MockElementId`.

**Returns:** `MockElement` or `None`

#### `GetElements(filter_criteria=None)`

Gets all elements, optionally filtered by a callable predicate.

**Returns:** `list[MockElement]`

#### `GetElementsByCategory(category)`

Gets all elements matching a category string.

**Returns:** `list[MockElement]`

#### `GetElementsByType(element_type)`

Gets all elements matching a type string.

**Returns:** `list[MockElement]`

#### `Delete(element_ids)`

Deletes elements by a list of integer IDs or `MockElementId` objects.

#### `StartTransaction(name="Transaction")`

Creates and starts a new `MockTransaction`.

**Returns:** `MockTransaction`

#### `Save()` / `Close(save_changes=True)`

Saves or closes the document. `Save()` returns `False` if no path is set.

#### `IsModified()` / `GetElementCount()`

Check modification status or get the element count.

#### `to_dict()` / `from_dict(data)`

Serializes/deserializes the document including all elements.

```python
doc = MockDocument(title="TestProject.rvt")
wall = doc.CreateElement(name="Wall-1", category="Walls")
wall.SetParameterValue("Height", 10.0)

walls = doc.GetElementsByCategory("Walls")
print(f"Found {len(walls)} walls")

txn = doc.StartTransaction("Update")
wall.SetParameterValue("Comments", "Updated")
txn.Commit()
```

---

## MockApplication

Mock Revit application managing multiple documents.

### Constructor

```python
MockApplication()
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `ActiveDocument` | `MockDocument` or `None` | The currently active document. |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `OpenDocumentFile(file_path)` | `MockDocument` | Opens a document from a file path. Sets it as active. |
| `CreateDocument(template_path=None)` | `MockDocument` | Creates a new document. Sets it as active. |
| `GetOpenDocuments()` | `list[MockDocument]` | Returns all open documents. |
| `CloseDocument(document)` | `bool` | Closes a document. Updates active document if needed. |

---

## MockRevit

Top-level mock Revit environment for testing. Provides convenience methods for creating documents, elements, fixtures, and state persistence.

### Constructor

```python
MockRevit()
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `application` | `MockApplication` | The mock application instance. |
| `active_document` | `MockDocument` or `None` | The currently active document. |

### Methods

#### `create_document(title="TestDocument.rvt")`

Creates a mock document and sets it as active.

**Returns:** `MockDocument`

#### `create_element(name="TestElement", category="Generic", element_type="Element", parameters=None)`

Creates a mock element. If a document is active, the element is added to it.

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Element name. |
| `category` | `str` | Element category. |
| `element_type` | `str` | Element type. |
| `parameters` | `dict[str, Any]` or `None` | Parameter values to set. |

**Returns:** `MockElement`

#### `create_elements(count, name_prefix="Element", category="Generic", element_type="Element")`

Creates multiple elements with sequential names.

**Returns:** `list[MockElement]`

#### `load_fixture(fixture_name, fixture_data)` / `get_fixture(fixture_name)`

Stores and retrieves named test fixtures.

#### `save_state(file_path)` / `load_state(file_path)`

Persists or restores the entire mock environment (documents, elements, fixtures) to/from a JSON file.

#### `reset()`

Resets the mock environment to its initial empty state.

#### `add_event_handler(handler)` / `trigger_event(event_type, event_data)`

Registers event handlers and triggers events for testing event-driven code.

#### `get_statistics()`

Returns a summary of the mock environment.

**Returns:** `dict[str, Any]` -- Contains `documents`, `total_elements`, `fixtures`, `event_handlers`, and `has_active_document`.

---

## Usage Examples

### Basic Element Testing

```python
from revitpy.testing.mock_revit import MockRevit

def test_wall_creation():
    mock = MockRevit()
    doc = mock.create_document("TestProject.rvt")

    wall = mock.create_element(
        name="Exterior Wall",
        category="Walls",
        parameters={"Height": 10.0, "Width": 0.5},
    )

    assert wall.Name == "Exterior Wall"
    assert wall.Category == "Walls"
    assert wall.GetParameterValue("Height").AsDouble() == 10.0
```

### Transaction Testing

```python
from revitpy.testing.mock_revit import MockRevit

def test_transaction_workflow():
    mock = MockRevit()
    doc = mock.create_document()

    wall = doc.CreateElement(name="Wall-1", category="Walls")
    wall.SetParameterValue("Height", 8.0)

    txn = doc.StartTransaction("Update Height")
    wall.SetParameterValue("Height", 12.0)
    txn.Commit()

    assert txn.is_committed
    assert wall.GetParameterValue("Height").AsDouble() == 12.0
```

### Batch Element Creation

```python
from revitpy.testing.mock_revit import MockRevit

def test_batch_operations():
    mock = MockRevit()
    doc = mock.create_document()

    walls = mock.create_elements(count=20, name_prefix="Wall", category="Walls")
    assert len(walls) == 20
    assert doc.GetElementCount() == 20

    # Query by category
    found = doc.GetElementsByCategory("Walls")
    assert len(found) == 20
```

### State Persistence

```python
from revitpy.testing.mock_revit import MockRevit

def test_state_save_load():
    # Set up state
    mock = MockRevit()
    doc = mock.create_document("Project.rvt")
    mock.create_elements(count=5, category="Walls")
    mock.load_fixture("config", {"max_height": 20.0})

    # Save state
    mock.save_state("/tmp/test_state.json")

    # Load state in a fresh environment
    mock2 = MockRevit()
    mock2.load_state("/tmp/test_state.json")

    assert mock2.active_document.Title == "Project.rvt"
    assert mock2.active_document.GetElementCount() == 5
    assert mock2.get_fixture("config")["max_height"] == 20.0
```

### Event Handler Testing

```python
from revitpy.testing.mock_revit import MockRevit

def test_event_handling():
    mock = MockRevit()
    events_received = []

    def on_event(event_type, event_data):
        events_received.append((event_type, event_data))

    mock.add_event_handler(on_event)
    mock.trigger_event("document_saved", {"title": "Project.rvt"})

    assert len(events_received) == 1
    assert events_received[0][0] == "document_saved"
```

### Testing with pytest

```python
import pytest
from revitpy.testing.mock_revit import MockRevit, MockElement

@pytest.fixture
def mock_revit():
    mock = MockRevit()
    mock.create_document("Test.rvt")
    yield mock
    mock.reset()

@pytest.fixture
def mock_walls(mock_revit):
    return mock_revit.create_elements(count=10, category="Walls", name_prefix="Wall")

def test_element_count(mock_revit, mock_walls):
    doc = mock_revit.active_document
    assert doc.GetElementCount() == 10

def test_parameter_access(mock_revit, mock_walls):
    wall = mock_walls[0]
    wall.SetParameterValue("Height", 15.0)

    param = wall.GetParameter("Height")
    assert param is not None
    assert param.AsDouble() == 15.0

def test_element_deletion(mock_revit, mock_walls):
    doc = mock_revit.active_document
    wall_id = mock_walls[0].Id
    doc.Delete([wall_id])
    assert doc.GetElementCount() == 9
    assert doc.GetElement(wall_id) is None
```

---

## Best Practices

1. **Use `MockRevit` as the entry point** -- It manages the application, documents, and elements together.
2. **Reset between tests** -- Call `mock.reset()` to ensure test isolation.
3. **Use fixtures for reusable setups** -- `load_fixture()` and `get_fixture()` store arbitrary test data.
4. **Test transactions explicitly** -- Check `is_committed` and `is_rolled_back` to verify transaction behavior.
5. **Persist state for complex scenarios** -- Use `save_state()` / `load_state()` to snapshot and restore test environments.
6. **Use pytest fixtures** -- Wrap `MockRevit` in a pytest fixture for clean setup and teardown.

---

## Next Steps

- **[Core API]({{ '/reference/api/core/' | relative_url }})**: The `RevitAPI` interface that mock objects simulate
- **[Element API]({{ '/reference/api/element-api/' | relative_url }})**: The `Element` class that `MockElement` mirrors
- **[Transaction API]({{ '/reference/api/transaction-api/' | relative_url }})**: Transaction patterns to test
- **[Event System]({{ '/reference/api/events/' | relative_url }})**: Event-driven patterns to test with `trigger_event()`
