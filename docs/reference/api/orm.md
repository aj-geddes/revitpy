---
layout: api
title: ORM Layer
description: ORM Layer reference documentation
---

# ORM Layer

RevitPy's Object-Relational Mapping (ORM) layer provides a modern, intuitive interface for querying and manipulating Revit elements using LINQ-style syntax.

## Overview

The ORM layer abstracts the complexity of the Revit API into familiar patterns:

- **LINQ-style queries**: Fluent API for filtering and querying elements
- **Lazy loading**: Elements are loaded only when accessed
- **Relationship navigation**: Navigate between related elements seamlessly
- **Change tracking**: Automatic tracking of modifications for efficient updates
- **Type safety**: Full type annotations for better IDE support

---

## RevitContext (ORM)

The main ORM context for database-like operations.

### Constructor

```python
RevitContext(document=None, track_changes=False)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `document` | `Document` | Optional Revit document. Uses active document if not specified. |
| `track_changes` | `bool` | Enable automatic change tracking. Default is `False`. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `elements` | `ElementSet` | Query builder for accessing Revit elements |
| `track_changes` | `bool` | Whether change tracking is enabled |
| `enable_caching` | `bool` | Whether query result caching is enabled |

### Methods

#### `save_changes()`
Saves all tracked changes to the Revit document within a transaction.

**Returns:** `int` - Number of elements saved

#### `has_changes()`
Checks if there are any tracked changes pending.

**Returns:** `bool` - True if changes exist

#### `get_changes()`
Returns all tracked changes.

**Returns:** `list[Change]` - List of tracked changes

#### `get_change_tracker()`
Returns the change tracker instance for manual change management.

**Returns:** `ChangeTracker` - The change tracker

#### `clear_cache()`
Clears all cached query results.

---

## ElementSet

Represents a queryable collection of Revit elements.

### Methods

#### `where(predicate)`
Filters elements based on a predicate function.

```python
tall_walls = context.elements.where(lambda w: w.Height > 10.0)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `predicate` | `Callable` | Function that returns True for elements to include |

**Returns:** `ElementSet` - Filtered element set

#### `select(projection)`
Projects elements to a new form.

```python
wall_names = context.elements.select(lambda w: w.Name).to_list()
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `projection` | `Callable` | Function to transform each element |

**Returns:** `ElementSet` - Projected element set

#### `order_by(key_selector)`
Orders elements by a key.

```python
sorted_walls = context.elements.order_by(lambda w: w.Height).to_list()
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `key_selector` | `Callable` | Function to extract the sort key |

**Returns:** `ElementSet` - Ordered element set

#### `then_by(key_selector)`
Performs secondary ordering on already ordered elements.

| Parameter | Type | Description |
|-----------|------|-------------|
| `key_selector` | `Callable` | Function to extract the secondary sort key |

**Returns:** `ElementSet` - Ordered element set

#### `group_by(key_selector)`
Groups elements by a key.

```python
grouped = context.elements.group_by(lambda e: e.Category).to_dict()
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `key_selector` | `Callable` | Function to extract the grouping key |

**Returns:** `ElementSet` - Grouped element set

#### `take(count)`
Returns a specified number of elements.

| Parameter | Type | Description |
|-----------|------|-------------|
| `count` | `int` | Number of elements to take |

**Returns:** `ElementSet` - Limited element set

#### `skip(count)`
Skips a specified number of elements.

| Parameter | Type | Description |
|-----------|------|-------------|
| `count` | `int` | Number of elements to skip |

**Returns:** `ElementSet` - Element set with skipped elements

#### `first()`
Returns the first element.

**Returns:** `Element` - The first element
**Raises:** `ElementNotFound` - If no elements exist

#### `first_or_default(default=None)`
Returns the first element or a default value.

| Parameter | Type | Description |
|-----------|------|-------------|
| `default` | `any` | Value to return if no elements exist |

**Returns:** `Element` or `default` - The first element or default

#### `to_list()`
Executes the query and returns results as a list.

**Returns:** `list[Element]` - List of elements

#### `to_dict()`
Executes the query and returns results as a dictionary.

**Returns:** `dict` - Dictionary of elements

#### `count()`
Returns the number of elements.

**Returns:** `int` - Element count

---

## QueryBuilder

Builds and optimizes queries for execution.

### Methods

#### `where(predicate)`
Adds a filter condition to the query.

| Parameter | Type | Description |
|-----------|------|-------------|
| `predicate` | `Callable` | Filter predicate function |

**Returns:** `QueryBuilder` - The query builder for chaining

#### `include(relationship)`
Includes related elements in the query results (eager loading).

```python
rooms = context.elements.of_category('Rooms').include('Boundaries').to_list()
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `relationship` | `str` | Name of the relationship to include |

**Returns:** `QueryBuilder` - The query builder for chaining

#### `order_by(key_selector)`
Adds ordering to the query.

| Parameter | Type | Description |
|-----------|------|-------------|
| `key_selector` | `Callable` | Sort key function |

**Returns:** `QueryBuilder` - The query builder for chaining

#### `select(projection)`
Adds a projection to the query.

| Parameter | Type | Description |
|-----------|------|-------------|
| `projection` | `Callable` | Projection function |

**Returns:** `QueryBuilder` - The query builder for chaining

#### `build_query()`
Builds the final query for execution.

**Returns:** `Query` - The built query

#### `optimize_query()`
Optimizes the query for better performance.

**Returns:** `QueryBuilder` - The optimized query builder

#### `explain_query()`
Returns the query execution plan.

**Returns:** `QueryPlan` - The execution plan with cost estimation

---

## ChangeTracker

Tracks modifications to elements for efficient updates.

### Methods

#### `track_element(element)`
Begins tracking an element for changes.

| Parameter | Type | Description |
|-----------|------|-------------|
| `element` | `Element` | Element to track |

#### `get_changes()`
Returns all tracked changes.

**Returns:** `list[Change]` - List of changes

#### `has_changes()`
Checks if there are any tracked changes.

**Returns:** `bool` - True if changes exist

#### `accept_changes()`
Accepts all tracked changes and clears the tracker.

#### `reject_changes()`
Rejects all tracked changes and reverts elements.

---

## Query Syntax

### Basic Filtering
```python
from revitpy import RevitContext

with RevitContext() as context:
    # Simple filtering
    tall_walls = context.elements.where(lambda w: w.Height > 10.0)

    # Multiple conditions
    exterior_walls = context.elements.where(
        lambda w: w.Category == 'Walls' and
                 w.get_parameter('Function').AsInteger() == 1
    )

    # Complex expressions
    large_rooms = context.elements.where(
        lambda r: r.Category == 'Rooms' and
                 r.Area > 100 and
                 r.Name.startswith('Office')
    )
```

### Projection and Selection
```python
# Select specific properties
wall_info = (context.elements
             .of_category('Walls')
             .select(lambda w: {
                 'name': w.Name,
                 'height': w.Height,
                 'area': w.get_parameter('Area').AsDouble()
             })
             .to_list())

# Transform results
wall_names = (context.elements
              .of_category('Walls')
              .select(lambda w: w.Name.upper())
              .to_list())
```

### Ordering and Pagination
```python
# Order by single property
sorted_walls = (context.elements
                .of_category('Walls')
                .order_by(lambda w: w.Height)
                .to_list())

# Order by multiple properties
sorted_rooms = (context.elements
                .of_category('Rooms')
                .order_by(lambda r: r.Level.Name)
                .then_by(lambda r: r.Area)
                .to_list())

# Pagination
first_10_walls = (context.elements
                  .of_category('Walls')
                  .order_by(lambda w: w.Name)
                  .take(10)
                  .to_list())

next_10_walls = (context.elements
                 .of_category('Walls')
                 .order_by(lambda w: w.Name)
                 .skip(10)
                 .take(10)
                 .to_list())
```

### Grouping and Aggregation
```python
# Group by category
grouped_elements = (context.elements
                    .group_by(lambda e: e.Category)
                    .to_dict())

# Group with aggregation
room_areas_by_level = (context.elements
                       .of_category('Rooms')
                       .group_by(lambda r: r.Level.Name)
                       .select(lambda g: {
                           'level': g.key,
                           'total_area': sum(r.Area for r in g),
                           'room_count': len(g),
                           'avg_area': sum(r.Area for r in g) / len(g)
                       })
                       .to_list())
```

---

## Relationship Navigation

### Include Related Data
```python
# Eager loading of related elements
rooms_with_boundaries = (context.elements
                         .of_category('Rooms')
                         .include('Boundaries')
                         .include('Boundaries.Wall')
                         .to_list())

for room in rooms_with_boundaries:
    print(f"Room: {room.Name}")
    for boundary in room.Boundaries:
        wall = boundary.Wall  # Already loaded, no additional query
        print(f"  - Wall: {wall.Name}")
```

### Navigation Properties
```python
# Navigate through relationships
def analyze_room_walls(room_id):
    with RevitContext() as context:
        room = context.get_element_by_id(room_id)

        # Navigate to related walls
        boundary_walls = [boundary.Wall for boundary in room.Boundaries]

        # Analyze wall properties
        wall_analysis = {
            'total_walls': len(boundary_walls),
            'total_length': sum(wall.Length for wall in boundary_walls),
            'wall_types': set(wall.WallType.Name for wall in boundary_walls)
        }

        return wall_analysis
```

---

## Change Tracking

### Automatic Change Detection
```python
def update_wall_properties():
    with RevitContext() as context:
        # Enable change tracking
        context.track_changes = True

        walls = context.elements.of_category('Walls').to_list()

        # Modify elements
        for wall in walls:
            if wall.Height < 10:
                wall.set_parameter('Comments', 'Low wall')

        # Check for changes
        if context.has_changes():
            changes = context.get_changes()
            print(f"Modified {len(changes)} elements")

            # Save all changes at once
            context.save_changes()
```

### Manual Change Management
```python
def batch_update_elements(updates):
    with RevitContext() as context:
        tracker = context.get_change_tracker()

        with context.transaction("Batch Update") as txn:
            for element_id, properties in updates.items():
                element = context.get_element_by_id(element_id)
                tracker.track_element(element)

                # Apply updates
                for param, value in properties.items():
                    element.set_parameter(param, value)

            # Verify changes before committing
            changes = tracker.get_changes()
            if len(changes) == len(updates):
                txn.commit()
                tracker.accept_changes()
            else:
                txn.rollback()
                tracker.reject_changes()
```

---

## Performance Optimization

### Query Optimization
```python
from revitpy.orm import QueryOptimizer

def optimized_element_query():
    with RevitContext() as context:
        # The ORM automatically optimizes queries
        query = (context.elements
                .of_category('Walls')
                .where(lambda w: w.Height > 10)
                .include('WallType')
                .order_by(lambda w: w.Name))

        # View query execution plan
        plan = query.explain_query()
        print(f"Estimated cost: {plan.cost}")
        print(f"Index usage: {plan.indexes_used}")

        # Execute optimized query
        results = query.to_list()
```

### Caching Strategies
```python
from revitpy.orm.cache import QueryCache

def cached_element_access():
    with RevitContext() as context:
        # Enable query result caching
        context.enable_caching = True

        # First query - hits the database
        walls = context.elements.of_category('Walls').to_list()

        # Second identical query - uses cache
        walls_cached = context.elements.of_category('Walls').to_list()

        # Clear cache when needed
        context.clear_cache()
```

### Batch Operations
```python
def efficient_bulk_updates(element_updates):
    with RevitContext() as context:
        # Use bulk operations for better performance
        element_ids = list(element_updates.keys())
        elements = context.get_elements_by_ids(element_ids)  # Single query

        with context.transaction("Bulk Update") as txn:
            for element in elements:
                updates = element_updates.get(element.Id)
                if updates:
                    element.update_parameters(updates)  # Batch parameter update

            txn.commit()
```

---

## Advanced Features

### Custom Query Extensions
```python
from revitpy.orm import QueryExtension

class WallQueryExtensions(QueryExtension):
    """Custom query extensions for walls."""

    def exterior_walls(self, query):
        """Filter for exterior walls only."""
        return query.where(lambda w: w.get_parameter('Function').AsInteger() == 1)

    def by_height_range(self, query, min_height, max_height):
        """Filter walls by height range."""
        return query.where(lambda w: min_height <= w.Height <= max_height)

# Register extension
RevitContext.register_extension('Walls', WallQueryExtensions)

# Use custom extensions
with RevitContext() as context:
    exterior_walls = (context.elements
                      .of_category('Walls')
                      .exterior_walls()
                      .by_height_range(8.0, 12.0)
                      .to_list())
```

### Dynamic Queries
```python
def build_dynamic_query(filters):
    """Build queries dynamically based on runtime conditions."""
    with RevitContext() as context:
        query = context.elements.of_category('Rooms')

        # Apply filters dynamically
        if 'min_area' in filters:
            query = query.where(lambda r: r.Area >= filters['min_area'])

        if 'level_name' in filters:
            query = query.where(lambda r: r.Level.Name == filters['level_name'])

        if 'name_pattern' in filters:
            pattern = filters['name_pattern']
            query = query.where(lambda r: pattern in r.Name)

        # Apply ordering if specified
        if 'order_by' in filters:
            if filters['order_by'] == 'area':
                query = query.order_by(lambda r: r.Area)
            elif filters['order_by'] == 'name':
                query = query.order_by(lambda r: r.Name)

        return query.to_list()
```

---

## Testing ORM Operations

### Mock Context for Testing
```python
from revitpy.testing import MockRevitContext, create_mock_element

def test_wall_query():
    """Test wall querying with mock data."""
    with MockRevitContext() as mock_context:
        # Create mock elements
        wall1 = create_mock_element('Wall', Height=8.0, Name='Wall-1')
        wall2 = create_mock_element('Wall', Height=12.0, Name='Wall-2')
        wall3 = create_mock_element('Wall', Height=15.0, Name='Wall-3')

        mock_context.add_elements([wall1, wall2, wall3])

        # Test query
        tall_walls = (mock_context.elements
                      .of_category('Walls')
                      .where(lambda w: w.Height > 10)
                      .order_by(lambda w: w.Height)
                      .to_list())

        # Verify results
        assert len(tall_walls) == 2
        assert tall_walls[0].Height == 12.0
        assert tall_walls[1].Height == 15.0
```

---

## Migration from Traditional Approaches

### Before: Traditional Revit API
```python
from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory

# Traditional approach - verbose and complex
collector = FilteredElementCollector(doc)
walls = collector.OfCategory(BuiltInCategory.OST_Walls).ToElements()

tall_walls = []
for wall in walls:
    height_param = wall.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM)
    if height_param and height_param.AsDouble() > 10.0:
        tall_walls.append(wall)

# Sort manually
tall_walls.sort(key=lambda w: w.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM).AsDouble())
```

### After: RevitPy ORM
```python
from revitpy import RevitContext

# Modern ORM approach - intuitive and concise
with RevitContext() as context:
    tall_walls = (context.elements
                  .of_category('Walls')
                  .where(lambda w: w.Height > 10.0)
                  .order_by(lambda w: w.Height)
                  .to_list())
```

The ORM approach is:
- **70% less code** than traditional approaches
- **Type-safe** with full IntelliSense support
- **More readable** with natural language syntax
- **Automatically optimized** for performance
- **Easier to test** with built-in mocking support

---

## Next Steps

- **[Query Builder]({{ '/reference/api/query-builder/' | relative_url }})**: Deep dive into query construction
- **[Element Sets]({{ '/reference/api/element-sets/' | relative_url }})**: Work with element collections
- **[Relationships]({{ '/reference/api/relationships/' | relative_url }})**: Navigate element relationships
- **[Performance Guide]({{ '/guides/orm-performance/' | relative_url }})**: Optimize ORM usage
