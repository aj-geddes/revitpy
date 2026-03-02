---
layout: api
title: Query API Reference
description: LINQ-style querying system for Revit elements
---

# Query API Reference

The Query API provides a LINQ-style fluent querying system for Revit elements, with support for filtering, sorting, pagination, and distinct operations.

**Module:** `revitpy.api.query`

---

## FilterOperator

Enumeration of filter operators for query conditions.

```python
class FilterOperator(Enum):
    EQUALS       = "equals"
    NOT_EQUALS   = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN    = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL   = "less_equal"
    CONTAINS     = "contains"
    STARTS_WITH  = "starts_with"
    ENDS_WITH    = "ends_with"
    IN           = "in"
    NOT_IN       = "not_in"
    IS_NULL      = "is_null"
    IS_NOT_NULL  = "is_not_null"
    REGEX        = "regex"
```

---

## SortDirection

Enumeration of sort directions.

```python
class SortDirection(Enum):
    ASCENDING  = "asc"
    DESCENDING = "desc"
```

---

## FilterCriteria

Represents a single filter condition applied to a query.

### Constructor

```python
FilterCriteria(
    property_name: str,
    operator: FilterOperator,
    value: Any = None,
    case_sensitive: bool = True
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `property_name` | `str` | Element parameter name to filter on. |
| `operator` | `FilterOperator` | Comparison operator. |
| `value` | `Any` | Value to compare against. Not used for `IS_NULL`/`IS_NOT_NULL`. |
| `case_sensitive` | `bool` | Whether string comparisons are case-sensitive. Default `True`. |

### Methods

#### `apply(element)`

Tests whether an element matches this filter criteria.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element` | `Element` | The element to test. |

**Returns:** `bool` -- `True` if the element matches.

The method reads the parameter value from the element and applies the operator. Type coercion is attempted automatically (e.g., numeric comparison between `int` and `float`). On error, returns `False`.

---

## SortCriteria

Represents a sort condition.

### Constructor

```python
SortCriteria(
    property_name: str,
    direction: SortDirection = SortDirection.ASCENDING
)
```

### Methods

#### `get_sort_key(element)`

Extracts the sort key value from an element.

**Returns:** The parameter value, or `""` if the parameter is not found.

---

## QueryBuilder

LINQ-style query builder for Revit elements. All filter and sort methods return `self` for fluent chaining. The query is not executed until a terminal method (`execute()`, `to_list()`, `first()`, etc.) is called.

### Constructor

```python
QueryBuilder(provider: IElementProvider, element_type: type[T] | None = None)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | `IElementProvider` | The element source. |
| `element_type` | `type[T]` or `None` | Optional type filter. If set, only elements of this type are queried. |

### Filter Methods

All filter methods return `QueryBuilder[T]` for chaining.

#### `where(property_name, operator, value=None, case_sensitive=True)`

Adds a general filter criteria.

```python
query.where("Height", FilterOperator.GREATER_THAN, 10.0)
```

#### `equals(property_name, value, case_sensitive=True)`

Filter by equality.

```python
query.equals("Category", "Walls")
```

#### `not_equals(property_name, value, case_sensitive=True)`

Filter by inequality.

#### `contains(property_name, value, case_sensitive=True)`

Filter by string containment.

```python
query.contains("Name", "Exterior", case_sensitive=False)
```

#### `starts_with(property_name, value, case_sensitive=True)`

Filter by string prefix.

#### `ends_with(property_name, value, case_sensitive=True)`

Filter by string suffix.

#### `in_values(property_name, values)`

Filter by membership in a list.

```python
query.in_values("Level", ["Level 1", "Level 2"])
```

#### `is_null(property_name)`

Filter for null/None parameter values.

#### `is_not_null(property_name)`

Filter for non-null parameter values.

#### `regex(property_name, pattern, case_sensitive=True)`

Filter by regular expression match.

```python
query.regex("Name", r"Wall-\d{3}")
```

### Sort Methods

All sort methods return `QueryBuilder[T]` for chaining.

#### `order_by(property_name, direction=SortDirection.ASCENDING)`

Adds a sort condition.

#### `order_by_ascending(property_name)`

Sort by property in ascending order. Shorthand for `order_by(prop, SortDirection.ASCENDING)`.

#### `order_by_descending(property_name)`

Sort by property in descending order.

### Pagination Methods

#### `skip(count)`

Skips the first `count` elements.

| Parameter | Type | Description |
|-----------|------|-------------|
| `count` | `int` | Number of elements to skip. |

**Returns:** `QueryBuilder[T]`

#### `take(count)`

Limits results to `count` elements.

| Parameter | Type | Description |
|-----------|------|-------------|
| `count` | `int` | Maximum number of elements to return. |

**Returns:** `QueryBuilder[T]`

```python
# Pagination: page 2 with 10 items per page
page2 = query.skip(10).take(10).to_list()
```

### Other Methods

#### `distinct(property_name=None)`

Returns distinct elements, optionally by a specific property value.

| Parameter | Type | Description |
|-----------|------|-------------|
| `property_name` | `str` or `None` | Property to use for distinctness. |

**Returns:** `QueryBuilder[T]`

### Terminal Methods

These methods execute the query and return results.

#### `execute()`

Executes the query pipeline and returns an `ElementSet`.

**Returns:** `ElementSet[T]`

The execution order is:
1. Fetch elements from the provider (filtered by `element_type` if set).
2. Apply all `FilterCriteria` in order.
3. Apply all `SortCriteria`.
4. Apply `distinct` filtering.
5. Apply `skip` and `take`.

#### `to_list()`

Executes the query and returns a Python list.

**Returns:** `list[T]`

#### `count()`

Executes the query and returns the count of matching elements.

**Returns:** `int`

#### `any()`

Returns `True` if any elements match. Optimized to fetch at most one element.

**Returns:** `bool`

#### `first()`

Returns the first matching element.

**Returns:** `T`

**Raises:** `ElementNotFoundError` if no elements match.

#### `first_or_default(default=None)`

Returns the first matching element or a default value.

**Returns:** `T` or `default`

#### `single()`

Returns the single matching element.

**Raises:** `ElementNotFoundError` if no elements. `ValidationError` if more than one element matches.

---

## Query

Static factory class for creating `QueryBuilder` instances.

### Static Methods

#### `Query.from_provider(provider)`

Creates a query builder from an element provider.

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | `IElementProvider` | The element source. |

**Returns:** `QueryBuilder[Element]`

#### `Query.from_elements(elements)`

Creates a query builder from an existing list of elements.

| Parameter | Type | Description |
|-----------|------|-------------|
| `elements` | `list[Element]` | List of elements to query over. |

**Returns:** `QueryBuilder[Element]`

```python
from revitpy.api.query import Query

# Query over a pre-existing list
results = (
    Query.from_elements(my_elements)
    .equals("Category", "Walls")
    .order_by_ascending("Name")
    .to_list()
)
```

#### `Query.of_type(provider, element_type)`

Creates a typed query builder that only retrieves elements of the specified type.

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | `IElementProvider` | The element source. |
| `element_type` | `type[T]` | Element type to filter for. |

**Returns:** `QueryBuilder[T]`

---

## IElementProvider

Protocol that element sources must implement.

```python
class IElementProvider(Protocol):
    def get_all_elements(self) -> list[Element]: ...
    def get_elements_of_type(self, element_type: type[Element]) -> list[Element]: ...
```

---

## Usage Examples

### Basic Filtering

```python
from revitpy.api.wrapper import RevitAPI

def find_tall_walls(revit_app):
    with RevitAPI(revit_app) as api:
        api.connect()

        tall_walls = (
            api.elements
            .equals("Category", "Walls")
            .where("Height", FilterOperator.GREATER_THAN, 10.0)
            .order_by_ascending("Name")
            .to_list()
        )

        for wall in tall_walls:
            print(f"{wall.name}: {wall.get_parameter_value('Height')}")
```

### Pagination

```python
def get_wall_page(revit_app, page_number, page_size=20):
    with RevitAPI(revit_app) as api:
        api.connect()

        return (
            api.elements
            .equals("Category", "Walls")
            .order_by_ascending("Name")
            .skip(page_number * page_size)
            .take(page_size)
            .to_list()
        )
```

### Querying an Existing List

```python
from revitpy.api.query import Query, FilterOperator

def filter_existing_elements(elements):
    return (
        Query.from_elements(elements)
        .is_not_null("Comments")
        .contains("Comments", "reviewed", case_sensitive=False)
        .to_list()
    )
```

### Regex Filtering

```python
def find_numbered_walls(revit_app):
    with RevitAPI(revit_app) as api:
        api.connect()

        return (
            api.elements
            .equals("Category", "Walls")
            .regex("Name", r"W-\d{3,}")
            .to_list()
        )
```

---

## Best Practices

1. **Reuse `QueryBuilder`** -- Build the query once, then call terminal methods.
2. **Check for `None`** -- Parameter values may be `None`; use `is_not_null` to guard.
3. **Use `any()` for existence checks** -- It is optimized to fetch at most one element.
4. **Apply filters before sorts** -- Reduces the number of elements that need sorting.
5. **Use pagination for large result sets** -- Combine `skip()` and `take()` for memory efficiency.

---

## See Also

- **[Element API]({{ '/reference/api/element-api/' | relative_url }})** -- `ElementSet` LINQ-style operations
- **[ORM Layer]({{ '/reference/api/orm/' | relative_url }})** -- Higher-level ORM queries with caching
- **[Core API]({{ '/reference/api/core/' | relative_url }})** -- `RevitAPI.elements` shorthand
