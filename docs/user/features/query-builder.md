---
layout: page
title: Query Builder
description: Guide to the RevitPy LINQ-style QueryBuilder for filtering, sorting, and paginating Revit elements. Covers filter operators, chaining, and terminal ops.
doc_tier: user
---

# Query Builder

RevitPy provides a LINQ-style `QueryBuilder` for querying Revit elements. It supports filtering, sorting, pagination, and several terminal operations to retrieve results.

The `QueryBuilder` is defined in `revitpy.api.query` and is accessible from the `RevitAPI` class.

## Creating Queries

There are several ways to create a query.

### From RevitAPI

```python
from revitpy import RevitAPI

api = RevitAPI()
api.connect(revit_application)

# Query all elements
query = api.elements

# Query a specific element type
query = api.query(WallElement)
```

### From the Query Factory

The `Query` class provides static factory methods:

```python
from revitpy.api.query import Query

# From an element provider
query = Query.from_provider(provider)

# From a list of elements
query = Query.from_elements(element_list)

# Typed query
query = Query.of_type(provider, WallElement)
```

## Filter Methods

All filter methods return a new `QueryBuilder`, so they can be chained.

### where

The general-purpose filter method. Accepts a property name, a `FilterOperator`, and an optional value:

```python
from revitpy.api.query import FilterOperator

query.where("Name", FilterOperator.EQUALS, "Wall-1")
query.where("Height", FilterOperator.GREATER_THAN, 3.0)
query.where("Comments", FilterOperator.CONTAINS, "structural", case_sensitive=False)
```

**Signature:**

```python
def where(
    self,
    property_name: str,
    operator: FilterOperator,
    value: Any = None,
    case_sensitive: bool = True,
) -> QueryBuilder[T]
```

### Convenience Filter Methods

These methods wrap `where` for common operations:

| Method | Equivalent FilterOperator | Example |
|---|---|---|
| `equals(prop, value)` | `EQUALS` | `query.equals("Name", "Wall-1")` |
| `not_equals(prop, value)` | `NOT_EQUALS` | `query.not_equals("Type", "Default")` |
| `contains(prop, value)` | `CONTAINS` | `query.contains("Name", "Wall")` |
| `starts_with(prop, value)` | `STARTS_WITH` | `query.starts_with("Name", "W")` |
| `ends_with(prop, value)` | `ENDS_WITH` | `query.ends_with("Name", "-1")` |
| `in_values(prop, values)` | `IN` | `query.in_values("Type", ["A", "B"])` |
| `is_null(prop)` | `IS_NULL` | `query.is_null("Comments")` |
| `is_not_null(prop)` | `IS_NOT_NULL` | `query.is_not_null("Mark")` |
| `regex(prop, pattern)` | `REGEX` | `query.regex("Name", r"Wall-\d+")` |

All string-based filters (`equals`, `not_equals`, `contains`, `starts_with`, `ends_with`, `regex`) accept an optional `case_sensitive` parameter that defaults to `True`.

### FilterOperator Enum

The `FilterOperator` enum defines all supported comparison operators:

| Value | Description |
|---|---|
| `EQUALS` | Exact equality |
| `NOT_EQUALS` | Inequality |
| `GREATER_THAN` | Greater than |
| `LESS_THAN` | Less than |
| `GREATER_EQUAL` | Greater than or equal |
| `LESS_EQUAL` | Less than or equal |
| `CONTAINS` | String contains substring |
| `STARTS_WITH` | String starts with prefix |
| `ENDS_WITH` | String ends with suffix |
| `IN` | Value is in a list |
| `NOT_IN` | Value is not in a list |
| `IS_NULL` | Value is None |
| `IS_NOT_NULL` | Value is not None |
| `REGEX` | Matches a regular expression |

## Sorting

### order_by

Sort by a property name with a specified direction:

```python
from revitpy.api.query import SortDirection

query.order_by("Name", SortDirection.ASCENDING)
query.order_by("Height", SortDirection.DESCENDING)
```

### order_by_ascending / order_by_descending

Convenience methods that set the direction explicitly:

```python
query.order_by_ascending("Name")
query.order_by_descending("Height")
```

Multiple sort criteria can be chained. They are applied in the order they are added.

### SortDirection Enum

| Value | Description |
|---|---|
| `ASCENDING` | Sort in ascending order (A-Z, 0-9) |
| `DESCENDING` | Sort in descending order (Z-A, 9-0) |

## Pagination

### skip

Skip a number of elements from the beginning of the result set:

```python
query.skip(10)
```

### take

Limit the number of elements returned:

```python
query.take(25)
```

### Combining skip and take

```python
# Get elements 11-35 (page 2, 25 per page)
results = query.order_by_ascending("Name").skip(10).take(25).execute()
```

### distinct

Get distinct elements, optionally by a property name:

```python
# Distinct elements (by element identity)
query.distinct()

# Distinct by a specific property
query.distinct("Type")
```

## Terminal Operations

Terminal operations execute the query and return results. Once called, the query is evaluated against the element provider.

### execute

Executes the query and returns an `ElementSet`:

```python
element_set = query.equals("Type", "Wall").execute()
```

### count

Returns the number of matching elements:

```python
total = query.equals("Type", "Wall").count()
```

### first

Returns the first matching element. Raises `ElementNotFoundError` if no elements match:

```python
element = query.equals("Name", "Wall-1").first()
```

### first_or_default

Returns the first matching element, or a default value if none match:

```python
element = query.equals("Name", "Wall-1").first_or_default(default=None)
```

### single

Returns the single matching element. Raises an error if zero or more than one element matches:

```python
element = query.equals("Name", "Wall-1").single()
```

### to_list

Executes the query and returns results as a plain Python list:

```python
elements = query.equals("Type", "Wall").to_list()
```

### any

Returns `True` if at least one element matches the query:

```python
has_walls = query.equals("Type", "Wall").any()
```

## Chaining Example

Filters, sorts, and pagination can be chained together in a single expression:

```python
results = (
    api.elements
    .contains("Name", "Wall", case_sensitive=False)
    .is_not_null("Comments")
    .order_by_ascending("Name")
    .skip(0)
    .take(50)
    .execute()
)

for element in results:
    print(f"{element.name}: {element.get_parameter_value('Comments')}")
```

## ElementSet

The `execute()` method returns an `ElementSet`, which is a generic collection with additional operations:

- `count` -- Property returning the number of elements.
- `where(predicate)` -- Filter with a callable predicate.
- `select(selector)` -- Transform elements with a callable selector.
- `first(predicate=None)` -- Get the first element, optionally matching a predicate.
- `first_or_default(predicate=None, default=None)` -- Get the first element or a default.
- `single(predicate=None)` -- Get the single matching element.
- `to_list()` -- Convert to a plain list.
- `any(predicate=None)` -- Check if any elements match.
- `all(predicate)` -- Check if all elements match a predicate.
- `order_by(key_selector)` -- Sort by a key function.
- `group_by(key_selector)` -- Group into a dictionary keyed by the selector.

`ElementSet` supports iteration, `len()`, and indexing with `[]`.
