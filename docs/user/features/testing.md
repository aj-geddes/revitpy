---
layout: page
title: Testing
description: Guide to testing RevitPy code without a Revit installation using MockRevit, MockDocument, and MockElement. Includes pytest fixtures and serialization.
doc_tier: user
---

# Testing

RevitPy provides a mock Revit environment so you can test your code without an actual Revit installation. The testing utilities are in `revitpy.testing.mock_revit`.

## MockRevit

`MockRevit` is the top-level class that simulates the Revit environment. It wraps a `MockApplication` and provides convenience methods for creating test documents and elements.

```python
from revitpy import MockRevit

mock = MockRevit()
```

### Creating Documents

```python
doc = mock.create_document("TestProject.rvt")

# Access the active document
active = mock.active_document  # Returns a MockDocument or None
```

### Creating Elements

```python
# Create a single element
element = mock.create_element(
    name="Wall-1",
    category="Walls",
    element_type="Wall",
    parameters={"Height": 3.0, "Comments": "Test wall"},
)

# Create multiple elements
elements = mock.create_elements(
    count=10,
    name_prefix="Wall",
    category="Walls",
    element_type="Wall",
)
```

If there is an active document, `create_element` and `create_elements` automatically add the elements to it.

### Resetting State

```python
mock.reset()  # Clears all documents, fixtures, and event handlers
```

### Statistics

```python
stats = mock.get_statistics()
# Returns: {
#   "documents": 1,
#   "total_elements": 10,
#   "fixtures": 0,
#   "event_handlers": 0,
#   "has_active_document": True,
# }
```

## MockDocument

`MockDocument` simulates a Revit document with element storage and basic operations.

```python
from revitpy.testing.mock_revit import MockDocument

doc = MockDocument(
    title="TestProject.rvt",
    path="/path/to/TestProject.rvt",
    is_family_document=False,
)
```

### Key Methods

```python
# Create an element in the document
element = doc.CreateElement(
    name="Floor-1",
    category="Floors",
    element_type="Floor",
)

# Add an existing element
doc.AddElement(element)

# Get all elements
all_elements = doc.GetElements()

# Get by ID
element = doc.GetElement(element_id)

# Get by category or type
walls = doc.GetElementsByCategory("Walls")
floors = doc.GetElementsByType("Floor")

# Delete elements
doc.Delete([element_id_1, element_id_2])

# Document operations
doc.Save()
doc.Close(save_changes=True)

# State queries
doc.IsModified()
doc.GetElementCount()
```

### Transactions

```python
txn = doc.StartTransaction("My Transaction")
# txn.is_started is True
txn.Commit()
# txn.is_committed is True
```

### Serialization

Documents and elements can be saved to and loaded from JSON:

```python
# Save to dictionary
data = doc.to_dict()

# Restore from dictionary
doc = MockDocument.from_dict(data)
```

## MockElement

`MockElement` simulates a Revit element with parameters and properties.

```python
from revitpy.testing.mock_revit import MockElement

element = MockElement(
    element_id=1001,
    name="Wall-1",
    category="Walls",
    element_type="Wall",
)
```

### Parameters

Every `MockElement` starts with these default parameters: `Name`, `Category`, `Type`, `Comments`, and `Mark`.

```python
# Get parameter value (returns a MockParameter object)
param = element.GetParameterValue("Comments")

# Set parameter value
element.SetParameterValue("Comments", "Updated")

# Check if parameter exists
element.HasParameter("Height")

# Get all parameters
params = element.GetAllParameters()

# Get/set the parameter object directly
param_obj = element.GetParameter("Comments")
element.SetParameter("Height", MockParameter("Height", 3.0, type_name="Double"))
```

### Properties

```python
element.SetProperty("custom_flag", True)
value = element.GetProperty("custom_flag")
```

### Key Attributes

- `element.Id` -- A `MockElementId` with an `IntegerValue` attribute.
- `element.Name` -- Element name string.
- `element.Category` -- Category string.
- `element.ElementType` -- Element type string.

### Serialization

```python
data = element.to_dict()
element = MockElement.from_dict(data)
```

## MockApplication

`MockApplication` simulates the Revit application with document management.

```python
from revitpy.testing.mock_revit import MockApplication

app = MockApplication()

# Access via MockRevit
app = mock.application

# Open/create documents
doc = app.OpenDocumentFile("path/to/file.rvt")
doc = app.CreateDocument()

# Active document
active = app.ActiveDocument

# List open documents
docs = app.GetOpenDocuments()

# Close a document
app.CloseDocument(doc)
```

## Using with RevitAPI

Connect `MockRevit` to `RevitAPI` for integration testing:

```python
from revitpy import RevitAPI, MockRevit

mock = MockRevit()
doc = mock.create_document("Test.rvt")
mock.create_elements(count=5, name_prefix="Wall", category="Walls", element_type="Wall")

api = RevitAPI()
api.connect(mock.application)

# Now use the API as normal
results = api.elements.equals("Category", "Walls").execute()
assert results.count == 5
```

## Fixtures

`MockRevit` supports named fixtures for reusable test data:

```python
# Load fixture data
mock.load_fixture("test_walls", {"count": 10, "category": "Walls"})

# Retrieve fixture data
fixture = mock.get_fixture("test_walls")
```

## Saving and Loading State

Save the entire mock environment to a JSON file for reproducible tests:

```python
# Save state
mock.save_state("test_state.json")

# Load state
mock.load_state("test_state.json")
```

The saved state includes all documents, their elements, the active document, and fixtures.

## Event Testing

Test event handlers with `MockRevit`:

```python
mock.add_event_handler(my_handler_function)
mock.trigger_event("element_created", {"element_id": 1001})
```

## Integration with pytest

Here is an example of using `MockRevit` as a pytest fixture:

```python
import pytest
from revitpy import RevitAPI, MockRevit

@pytest.fixture
def mock_revit():
    """Create a fresh MockRevit environment for each test."""
    mock = MockRevit()
    mock.create_document("TestProject.rvt")
    yield mock
    mock.reset()

@pytest.fixture
def api(mock_revit):
    """Create a connected RevitAPI instance."""
    api = RevitAPI()
    api.connect(mock_revit.application)
    yield api
    api.disconnect()

def test_query_elements(api, mock_revit):
    mock_revit.create_elements(count=3, name_prefix="Wall", element_type="Wall")
    results = api.elements.equals("Type", "Wall").to_list()
    assert len(results) == 3

def test_transaction(api, mock_revit):
    mock_revit.create_element(name="Test", element_type="Wall")
    with api.transaction("Update") as txn:
        element = api.elements.first()
        element.set_parameter_value("Comments", "Tested")
    assert txn.status.value == "committed"

def test_element_parameters(mock_revit):
    element = mock_revit.create_element(
        name="Floor-1",
        parameters={"Area": 50.0, "Level": "Level 1"},
    )
    assert element.GetParameterValue("Area").value == 50.0
    assert element.GetParameterValue("Level").value == "Level 1"
```
