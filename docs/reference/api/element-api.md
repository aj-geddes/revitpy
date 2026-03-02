---
layout: api
title: Element API
description: Comprehensive classes and methods for working with Revit elements
---

# Element API

The Element API provides Pythonic wrappers for Revit elements, including type-safe parameter access, change tracking, and LINQ-style collection operations.

**Module:** `revitpy.api.element`

---

## ElementId

Immutable element ID wrapper. Implemented as a frozen dataclass.

### Constructor

```python
ElementId(value: int)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `value` | `int` | The integer element ID. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `value` | `int` | The raw integer ID. |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `__str__()` | `str` | String representation of the ID value. |
| `__int__()` | `int` | Integer conversion, returns `value`. |

Supports equality comparison and hashing, so `ElementId` instances can be used as dictionary keys and in sets.

```python
eid = ElementId(12345)
print(eid)        # "12345"
print(int(eid))   # 12345
```

---

## ParameterValue

Type-safe parameter value container. Built on Pydantic `BaseModel` for automatic validation.

### Constructor

```python
ParameterValue(
    name: str,
    value: Any,
    type_name: str,
    is_read_only: bool = False,
    storage_type: str = "String"
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Parameter name. |
| `value` | `Any` | The parameter value. Validated against `storage_type`. |
| `type_name` | `str` | Python type name of the value. |
| `is_read_only` | `bool` | Whether the parameter is read-only. Default `False`. |
| `storage_type` | `str` | Revit storage type: `"String"`, `"Double"`, or `"Integer"`. Default `"String"`. |

Automatic validation converts values to match the declared `storage_type`. For example, passing a string to a `"Double"` storage type parameter will attempt `float()` conversion.

---

## ElementProperty

Descriptor class for element properties with automatic Revit parameter access and type conversion.

### Constructor

```python
ElementProperty(parameter_name: str, read_only: bool = False)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `parameter_name` | `str` | The Revit parameter name to bind to. |
| `read_only` | `bool` | If `True`, raises `PermissionError` on write attempts. |

When used on an `Element` subclass, reading the attribute calls `get_parameter_value()` and writing calls `set_parameter_value()`.

```python
class WallElement(Element):
    height = ElementProperty("Height", read_only=True)
    comments = ElementProperty("Comments")

wall.comments = "Updated"      # calls set_parameter_value
h = wall.height                # calls get_parameter_value
wall.height = 10.0             # raises PermissionError
```

---

## Element

Pythonic wrapper for Revit elements with automatic type conversion, lazy parameter caching, and change tracking. Uses `ElementMetaclass` to register `ElementProperty` mappings.

### Constructor

```python
Element(revit_element: IRevitElement)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `revit_element` | `IRevitElement` | The underlying Revit element conforming to the `IRevitElement` protocol. |

### Built-in Property Mappings

The base `Element` class maps the following Python attributes to Revit parameters:

| Python Attribute | Revit Parameter |
|-----------------|-----------------|
| `name` | `Name` |
| `family_name` | `Family` |
| `type_name` | `Type` |
| `level` | `Level` |
| `comments` | `Comments` |
| `mark` | `Mark` |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | `ElementId` | The element's unique identifier. |
| `name` | `str` | The element's name (readable and writable). |
| `is_dirty` | `bool` | Whether the element has unsaved changes. |
| `changes` | `dict[str, Any]` | Copy of tracked changes (`{param_name: {"old": ..., "new": ...}}`). |

### Methods

#### `get_parameter_value(parameter_name, use_cache=True)`

Gets a parameter value with caching and automatic type conversion from Revit types to Python types.

| Parameter | Type | Description |
|-----------|------|-------------|
| `parameter_name` | `str` | Name of the parameter. |
| `use_cache` | `bool` | Whether to use cached values. Default `True`. |

**Returns:** The parameter value converted to an appropriate Python type (`str`, `float`, `int`, or the raw value).

**Raises:** `ElementNotFoundError` if the parameter does not exist on the element.

```python
height = element.get_parameter_value("Height")
comments = element.get_parameter_value("Comments", use_cache=False)
```

#### `set_parameter_value(parameter_name, value, track_changes=True)`

Sets a parameter value with type conversion and optional change tracking.

| Parameter | Type | Description |
|-----------|------|-------------|
| `parameter_name` | `str` | Name of the parameter. |
| `value` | `Any` | New value to set. |
| `track_changes` | `bool` | Whether to record this change. Default `True`. |

**Raises:** `ValidationError` if the value is invalid. `PermissionError` if the parameter is read-only.

```python
element.set_parameter_value("Comments", "Updated by RevitPy")
element.set_parameter_value("Height", 12.0)
```

#### `get_all_parameters(refresh_cache=False)`

Returns all parameters for this element.

| Parameter | Type | Description |
|-----------|------|-------------|
| `refresh_cache` | `bool` | Whether to force-refresh the parameter cache. Default `False`. |

**Returns:** `dict[str, ParameterValue]` -- Dictionary of parameter names to `ParameterValue` objects.

```python
params = element.get_all_parameters()
for name, param_value in params.items():
    print(f"{name}: {param_value.value} ({param_value.storage_type})")
```

#### `save_changes()`

Saves all tracked changes. Clears the change tracker and resets `is_dirty` to `False`. No-op if there are no pending changes.

#### `discard_changes()`

Discards all tracked changes and evicts affected parameters from the cache.

#### `refresh()`

Refreshes all element data by clearing the parameter cache, change tracker, and dirty flag.

### Equality and Hashing

Two `Element` instances are equal if they have the same `id`. Elements are hashable and can be used in sets and as dictionary keys.

```python
elem_a == elem_b    # True if elem_a.id == elem_b.id
{elem_a, elem_b}    # set of unique elements
```

---

## ElementSet

Generic collection of elements with LINQ-style operations and lazy evaluation. Operations like `where()`, `select()`, and `order_by()` build up a pipeline that is only executed when results are materialized (via `to_list()`, `first()`, iteration, etc.).

### Constructor

```python
ElementSet(elements: list[T] | None = None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `elements` | `list[T]` or `None` | Initial element list. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `count` | `int` | Number of elements (triggers evaluation). |

### Methods

#### `where(predicate)`

Filters elements using a predicate function.

| Parameter | Type | Description |
|-----------|------|-------------|
| `predicate` | `Callable[[T], bool]` | Function returning `True` for elements to include. |

**Returns:** `ElementSet[T]` -- A new element set with the filter applied (lazy).

```python
tall_walls = wall_set.where(lambda w: w.get_parameter_value("Height") > 10.0)
```

#### `select(selector)`

Transforms elements using a selector function.

| Parameter | Type | Description |
|-----------|------|-------------|
| `selector` | `Callable[[T], Any]` | Transformation function. |

**Returns:** `ElementSet` -- A new element set with the projection applied (lazy).

```python
names = wall_set.select(lambda w: w.name).to_list()
```

#### `order_by(key_selector)`

Orders elements by a key.

| Parameter | Type | Description |
|-----------|------|-------------|
| `key_selector` | `Callable[[T], Any]` | Function to extract the sort key. |

**Returns:** `ElementSet[T]` -- A new ordered element set (lazy).

#### `group_by(key_selector)`

Groups elements by a key. Triggers evaluation immediately.

| Parameter | Type | Description |
|-----------|------|-------------|
| `key_selector` | `Callable[[T], Any]` | Function to extract the grouping key. |

**Returns:** `dict[Any, list[T]]` -- Dictionary mapping keys to lists of elements.

```python
by_level = elements.group_by(lambda e: e.get_parameter_value("Level"))
```

#### `first(predicate=None)`

Returns the first element, optionally matching a predicate.

**Returns:** `T` -- The first element.

**Raises:** `ElementNotFoundError` if the set is empty.

#### `first_or_default(predicate=None, default=None)`

Returns the first element matching a predicate, or the default value.

**Returns:** `T` or the default value.

#### `single(predicate=None)`

Returns the single element matching a predicate.

**Raises:** `ElementNotFoundError` if no elements. `ValidationError` if more than one element matches.

#### `to_list()`

Materializes the query pipeline and returns results as a Python list.

**Returns:** `list[T]`

#### `any(predicate=None)`

Returns `True` if any elements match the predicate (or if the set is non-empty when no predicate is provided).

#### `all(predicate)`

Returns `True` if all elements match the predicate.

### Iteration and Indexing

`ElementSet` supports `for` loops, `len()`, `[]` indexing, and the `in` operator:

```python
for element in element_set:
    print(element.name)

count = len(element_set)
first = element_set[0]
exists = some_element in element_set
```

---

## Usage Examples

### Reading and Modifying Parameters

```python
from revitpy.api.wrapper import RevitAPI

def update_comments(revit_app, element_id, comment):
    with RevitAPI(revit_app) as api:
        api.connect()
        element = api.get_element_by_id(element_id)
        if element is None:
            print("Element not found")
            return

        # Read current value
        old = element.get_parameter_value("Comments")
        print(f"Old comment: {old}")

        # Update within a transaction
        with api.transaction("Update Comment"):
            element.set_parameter_value("Comments", comment)

        print(f"New comment: {element.get_parameter_value('Comments')}")
```

### Working with Change Tracking

```python
from revitpy.api.wrapper import RevitAPI

def tracked_update(revit_app):
    with RevitAPI(revit_app) as api:
        api.connect()
        element = api.get_element_by_id(12345)

        element.set_parameter_value("Mark", "A-101")
        element.set_parameter_value("Comments", "Updated")

        print(f"Dirty: {element.is_dirty}")      # True
        print(f"Changes: {element.changes}")      # {'Mark': {...}, 'Comments': {...}}

        # To persist
        element.save_changes()

        # Or to discard
        # element.discard_changes()
```

### Filtering and Sorting with ElementSet

```python
from revitpy.api.element import ElementSet

def analyze_elements(elements):
    element_set = ElementSet(elements)

    # Chain operations (lazy until to_list)
    results = (
        element_set
        .where(lambda e: e.get_parameter_value("Category") == "Walls")
        .where(lambda e: (e.get_parameter_value("Height") or 0) > 8.0)
        .order_by(lambda e: e.name)
        .to_list()
    )

    for wall in results:
        print(f"{wall.name}: height={wall.get_parameter_value('Height')}")
```

---

## Next Steps

- **[Transaction API]({{ '/reference/api/transaction-api/' | relative_url }})**: Transaction management for modifications
- **[Query API]({{ '/reference/api/query/' | relative_url }})**: Building queries with `QueryBuilder`
- **[ORM Layer]({{ '/reference/api/orm/' | relative_url }})**: Higher-level ORM context with caching and relationships
