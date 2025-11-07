---
layout: api
title: Query API Reference
description: Query API Reference reference documentation
---

# Query API Reference

The `Query` class provides a high-level interface for querying Revit elements.

## Class: Query

```python
from revitpy.api import Query

query = Query(document)
```

### Constructor

```python
def __init__(self, document: RevitDocument)
```

**Parameters:**
- `document` (RevitDocument): The Revit document to query

**Example:**
```python
from revitpy.api import Query
from revitpy.api.wrapper import get_active_document

doc = get_active_document()
query = Query(doc)
```

## Methods

### get_elements_by_category

Get all elements of a specific category.

```python
def get_elements_by_category(
    self,
    category_name: str,
    doc: Optional[RevitDocument] = None
) -> List[Element]
```

**Parameters:**
- `category_name` (str): Name of the category (e.g., "Walls", "Doors", "Windows")
- `doc` (Optional[RevitDocument]): Document to query (defaults to constructor document)

**Returns:**
- `List[Element]`: List of matching elements

**Example:**
```python
# Get all walls
walls = query.get_elements_by_category("Walls")

# Get all doors
doors = query.get_elements_by_category("Doors")

# Get elements from specific document
other_walls = query.get_elements_by_category("Walls", doc=other_doc)
```

**Supported Categories:**
- Walls
- Floors
- Roofs
- Doors
- Windows
- Rooms
- Spaces
- Furniture
- And many more...

### get_elements_by_class

Get elements by their Revit API class type.

```python
def get_elements_by_class(
    self,
    class_name: str,
    doc: Optional[RevitDocument] = None
) -> List[Element]
```

**Parameters:**
- `class_name` (str): Revit API class name (e.g., "Wall", "Floor", "FamilyInstance")
- `doc` (Optional[RevitDocument]): Document to query

**Returns:**
- `List[Element]`: List of matching elements

**Example:**
```python
# Get all walls by class
walls = query.get_elements_by_class("Wall")

# Get all family instances
instances = query.get_elements_by_class("FamilyInstance")

# Get all levels
levels = query.get_elements_by_class("Level")
```

### get_parameter_value

Get the value of a parameter from an element.

```python
def get_parameter_value(
    self,
    element: Element,
    parameter_name: str
) -> Optional[Any]
```

**Parameters:**
- `element` (Element): The element to query
- `parameter_name` (str): Name of the parameter

**Returns:**
- `Optional[Any]`: Parameter value or None if not found

**Example:**
```python
wall = walls[0]

# Get parameter values
wall_type = query.get_parameter_value(wall, "Type")
length = query.get_parameter_value(wall, "Length")
height = query.get_parameter_value(wall, "Unconnected Height")
level = query.get_parameter_value(wall, "Base Constraint")
comments = query.get_parameter_value(wall, "Comments")

print(f"Wall: {wall_type}")
print(f"Length: {length} ft")
print(f"Height: {height} ft")
print(f"Level: {level}")
```

**Common Parameters by Category:**

**Walls:**
- Type, Length, Height, Area, Volume
- Base Constraint, Top Constraint
- Structural Usage, Function

**Doors:**
- Type, Width, Height
- From Room, To Room
- Fire Rating, Comments

**Rooms:**
- Number, Name, Area, Volume
- Level, Department, Occupancy
- Ceiling Finish, Floor Finish, Wall Finish

### get_all_parameters

Get all parameters from an element.

```python
def get_all_parameters(
    self,
    element: Element
) -> Dict[str, Any]
```

**Parameters:**
- `element` (Element): The element to query

**Returns:**
- `Dict[str, Any]`: Dictionary of parameter names to values

**Example:**
```python
wall = walls[0]

# Get all parameters
params = query.get_all_parameters(wall)

for param_name, param_value in params.items():
    print(f"{param_name}: {param_value}")
```

### filter_elements

Filter elements by custom criteria.

```python
def filter_elements(
    self,
    elements: List[Element],
    filter_func: Callable[[Element], bool]
) -> List[Element]
```

**Parameters:**
- `elements` (List[Element]): Elements to filter
- `filter_func` (Callable): Function that returns True for elements to keep

**Returns:**
- `List[Element]`: Filtered list of elements

**Example:**
```python
# Get all walls
walls = query.get_elements_by_category("Walls")

# Filter walls longer than 20 feet
long_walls = query.filter_elements(
    walls,
    lambda w: float(query.get_parameter_value(w, "Length") or 0) > 20.0
)

# Filter by level
level1_walls = query.filter_elements(
    walls,
    lambda w: query.get_parameter_value(w, "Base Constraint") == "Level 1"
)

# Complex filter
exterior_load_bearing_walls = query.filter_elements(
    walls,
    lambda w: (
        query.get_parameter_value(w, "Function") == "Exterior" and
        query.get_parameter_value(w, "Structural Usage") == "Bearing"
    )
)
```

### get_element_by_id

Get an element by its Element ID.

```python
def get_element_by_id(
    self,
    element_id: Union[int, ElementId],
    doc: Optional[RevitDocument] = None
) -> Optional[Element]
```

**Parameters:**
- `element_id` (Union[int, ElementId]): Element ID as integer or ElementId object
- `doc` (Optional[RevitDocument]): Document to query

**Returns:**
- `Optional[Element]`: Element or None if not found

**Example:**
```python
# Get element by integer ID
element = query.get_element_by_id(123456)

# Get element by ElementId object
from Autodesk.Revit.DB import ElementId
elem_id = ElementId(123456)
element = query.get_element_by_id(elem_id)

# Get from specific document
element = query.get_element_by_id(123456, doc=other_doc)
```

## Properties

### document

The Revit document being queried.

```python
@property
def document(self) -> RevitDocument
```

**Example:**
```python
query = Query(doc)

# Access the document
print(f"Querying: {query.document.Title}")
print(f"Path: {query.document.PathName}")
```

## Best Practices

### 1. Reuse Query Objects

Create one `Query` object and reuse it:

```python
# Good
query = Query(doc)
walls = query.get_elements_by_category("Walls")
doors = query.get_elements_by_category("Doors")

# Avoid
walls = Query(doc).get_elements_by_category("Walls")
doors = Query(doc).get_elements_by_category("Doors")  # Creates new Query
```

### 2. Check for None Values

Always check parameter values:

```python
# Good
length = query.get_parameter_value(wall, "Length")
if length is not None:
    print(f"Length: {length}")

# Better
length = query.get_parameter_value(wall, "Length") or 0.0
```

### 3. Use Appropriate Methods

Choose the right query method:

```python
# For categories (most common)
walls = query.get_elements_by_category("Walls")

# For specific classes
levels = query.get_elements_by_class("Level")

# For filtering
long_walls = query.filter_elements(walls, lambda w: w.Length > 20)
```

### 4. Cache Results

Cache query results if reusing:

```python
# Get walls once
walls = query.get_elements_by_category("Walls")

# Reuse the list
for wall in walls:
    process_wall(wall)

for wall in walls:
    analyze_wall(wall)
```

## Error Handling

```python
try:
    walls = query.get_elements_by_category("Walls")

    for wall in walls:
        length = query.get_parameter_value(wall, "Length")
        if length is None:
            print(f"Wall {wall.Id} has no length parameter")
            continue

        print(f"Wall length: {length}")

except Exception as e:
    print(f"Query failed: {e}")
```

## See Also

- [ElementQuery (ORM)](orm.md) - LINQ-style queries
- [Transaction API](transaction.md) - Modifying elements
- [Wrapper API](wrapper.md) - Document access
