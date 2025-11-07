---
layout: api
title: Element API
description: Comprehensive classes and methods for working with Revit elements
---

# Element API

The Element API provides comprehensive classes and methods for working with Revit elements, offering both low-level access and high-level abstractions.

## Overview

The Element API is the foundation for interacting with Revit elements in RevitPy. It provides:

- **Type-safe element wrappers**: Strongly-typed classes for different element types
- **Parameter management**: Easy access to element parameters
- **Geometry operations**: Work with element geometry
- **Lifecycle management**: Create, modify, and delete elements
- **Validation**: Built-in validation for element operations

## Core Classes

### Element

The base class for all Revit element wrappers.

::: revitpy.api.element.Element
    options:
      members:
        - Id
        - Name
        - Category
        - Document
        - UniqueId
        - get_parameter
        - set_parameter
        - get_parameter_value
        - set_parameter_value
        - get_all_parameters
        - get_geometry
        - get_bounding_box
        - delete
        - copy
        - move
        - rotate
        - to_dict
        - from_dict

### ElementId

Represents a unique identifier for a Revit element.

::: revitpy.api.element.ElementId
    options:
      members:
        - __init__
        - value
        - is_valid
        - __eq__
        - __hash__
        - __str__

### ElementWrapper

Wrapper utility for converting between Revit API elements and RevitPy elements.

::: revitpy.api.element.ElementWrapper
    options:
      members:
        - wrap_element
        - unwrap_element
        - is_wrapped
        - get_element_type
        - create_wrapper

### ParameterValue

Represents a parameter value with type information.

::: revitpy.api.element.ParameterValue
    options:
      members:
        - value
        - type
        - storage_type
        - as_string
        - as_double
        - as_integer
        - as_element_id
        - is_null

## Element Type Classes

RevitPy provides specialized classes for different element types with type-specific properties and methods.

### WallElement

::: revitpy.orm.types.WallElement
    options:
      members:
        - Height
        - Width
        - Length
        - Area
        - Volume
        - WallType
        - LocationCurve
        - Flipped
        - get_compound_structure
        - get_layers

### DoorElement

::: revitpy.orm.types.DoorElement
    options:
      members:
        - Height
        - Width
        - FromRoom
        - ToRoom
        - Host
        - Orientation
        - HandOrientation
        - FacingFlipped

### WindowElement

::: revitpy.orm.types.WindowElement
    options:
      members:
        - Height
        - Width
        - Sill_Height
        - Host
        - Orientation
        - HandOrientation
        - FacingFlipped

### RoomElement

::: revitpy.orm.types.RoomElement
    options:
      members:
        - Area
        - Perimeter
        - Volume
        - UnboundedHeight
        - Level
        - Number
        - Department
        - get_boundaries
        - get_boundary_segments

## Usage Examples

### Basic Element Access

```python
from revitpy import RevitContext

def get_element_info(element_id):
    """Get comprehensive information about an element."""
    with RevitContext() as context:
        element = context.get_element_by_id(element_id)

        info = {
            'id': element.Id.value,
            'name': element.Name,
            'category': element.Category,
            'unique_id': element.UniqueId,
            'parameters': {}
        }

        # Get all parameters
        for param in element.get_all_parameters():
            info['parameters'][param.Definition.Name] = param.AsValueString()

        return info
```

### Working with Parameters

```python
def update_element_parameters(element_id, parameters):
    """Update multiple parameters on an element."""
    with RevitContext() as context:
        element = context.get_element_by_id(element_id)

        with context.transaction("Update Parameters") as txn:
            for param_name, value in parameters.items():
                try:
                    element.set_parameter(param_name, value)
                    print(f"Updated {param_name} = {value}")
                except Exception as e:
                    print(f"Failed to update {param_name}: {e}")

            txn.commit()

# Usage
update_element_parameters(
    element_id=123456,
    parameters={
        'Comments': 'Updated via RevitPy',
        'Mark': 'A-101',
        'Phase Created': 'New Construction'
    }
)
```

### Type-Safe Element Operations

```python
from revitpy.orm.types import WallElement, DoorElement

def analyze_wall_with_doors(wall_id):
    """Analyze a wall and its doors using type-safe classes."""
    with RevitContext() as context:
        # Get wall as type-safe WallElement
        wall = context.get_element_by_id(wall_id, WallElement)

        print(f"Wall: {wall.Name}")
        print(f"  Height: {wall.Height:.2f} ft")
        print(f"  Length: {wall.Length:.2f} ft")
        print(f"  Area: {wall.Area:.2f} sq ft")
        print(f"  Wall Type: {wall.WallType.Name}")

        # Get all doors hosted by this wall
        doors = context.elements.where(
            lambda d: isinstance(d, DoorElement) and d.Host.Id == wall.Id
        ).to_list()

        print(f"\nDoors in wall: {len(doors)}")
        for door in doors:
            print(f"  - {door.Name}: {door.Width:.2f}' x {door.Height:.2f}'")
```

### Element Geometry

```python
from Autodesk.Revit.DB import Options

def get_element_geometry_info(element_id):
    """Extract geometry information from an element."""
    with RevitContext() as context:
        element = context.get_element_by_id(element_id)

        # Get geometry with options
        options = Options()
        options.ComputeReferences = True
        options.IncludeNonVisibleObjects = False
        options.DetailLevel = ViewDetailLevel.Fine

        geometry = element.get_geometry(options)

        info = {
            'has_geometry': geometry is not None,
            'solids': [],
            'curves': [],
            'instances': []
        }

        if geometry:
            for geom_obj in geometry:
                if isinstance(geom_obj, Solid):
                    info['solids'].append({
                        'volume': geom_obj.Volume,
                        'surface_area': geom_obj.SurfaceArea,
                        'faces_count': geom_obj.Faces.Size,
                        'edges_count': geom_obj.Edges.Size
                    })
                elif isinstance(geom_obj, Curve):
                    info['curves'].append({
                        'length': geom_obj.Length,
                        'is_bound': geom_obj.IsBound
                    })
                elif isinstance(geom_obj, GeometryInstance):
                    info['instances'].append({
                        'symbol_geometry': geom_obj.SymbolGeometry is not None,
                        'transform': str(geom_obj.Transform)
                    })

        return info
```

### Element Creation

```python
from revitpy.orm.types import WallElement

def create_wall_between_points(start, end, height=10.0):
    """Create a new wall between two points."""
    from Autodesk.Revit.DB import Wall, Line, XYZ

    with RevitContext() as context:
        doc = context.get_active_document()

        # Get default wall type
        wall_types = context.elements.of_category('WallTypes')
        wall_type = wall_types.first()

        with context.transaction("Create Wall") as txn:
            # Create line
            line = Line.CreateBound(
                XYZ(start[0], start[1], 0),
                XYZ(end[0], end[1], 0)
            )

            # Create wall
            wall = Wall.Create(
                doc,
                line,
                wall_type.Id,
                doc.ActiveView.GenLevel.Id,
                height,
                0,
                False,
                False
            )

            txn.commit()

            # Return wrapped element
            return context.wrap_element(wall, WallElement)
```

### Element Modification

```python
def modify_element_location(element_id, translation_vector):
    """Move an element by a translation vector."""
    from Autodesk.Revit.DB import XYZ

    with RevitContext() as context:
        element = context.get_element_by_id(element_id)

        with context.transaction("Move Element") as txn:
            # Create translation vector
            vector = XYZ(
                translation_vector[0],
                translation_vector[1],
                translation_vector[2]
            )

            # Move element
            element.move(vector)

            txn.commit()
            print(f"Moved element {element_id} by {translation_vector}")
```

### Element Deletion

```python
def delete_elements_by_criteria(category, condition):
    """Delete elements that meet specific criteria."""
    with RevitContext() as context:
        # Find elements matching criteria
        elements_to_delete = (
            context.elements
            .of_category(category)
            .where(condition)
            .to_list()
        )

        if not elements_to_delete:
            print("No elements found matching criteria")
            return

        # Confirm deletion
        count = len(elements_to_delete)
        print(f"Found {count} elements to delete")

        with context.transaction("Delete Elements") as txn:
            for element in elements_to_delete:
                element.delete()

            txn.commit()
            print(f"Deleted {count} elements")

# Usage: Delete all walls shorter than 6 feet
delete_elements_by_criteria(
    category='Walls',
    condition=lambda w: w.Height < 6.0
)
```

### Element Copying

```python
def duplicate_element_with_offset(element_id, offset_vector):
    """Create a copy of an element with an offset."""
    from Autodesk.Revit.DB import XYZ

    with RevitContext() as context:
        element = context.get_element_by_id(element_id)

        with context.transaction("Copy Element") as txn:
            # Create offset vector
            offset = XYZ(
                offset_vector[0],
                offset_vector[1],
                offset_vector[2]
            )

            # Copy element
            new_element = element.copy(offset)

            txn.commit()

            return new_element
```

## Advanced Features

### Element Validation

```python
from revitpy.orm.validation import ElementValidator, ValidationLevel

def validate_wall_element(wall_id):
    """Validate a wall element against rules."""
    with RevitContext() as context:
        wall = context.get_element_by_id(wall_id)

        validator = ElementValidator()
        validator.add_rule(
            'height_check',
            lambda w: w.Height >= 8.0,
            "Wall height must be at least 8 feet",
            ValidationLevel.ERROR
        )
        validator.add_rule(
            'comments_check',
            lambda w: w.get_parameter('Comments').AsString() is not None,
            "Wall should have comments",
            ValidationLevel.WARNING
        )

        result = validator.validate(wall)

        if not result.is_valid:
            print("Validation failed:")
            for error in result.errors:
                print(f"  ERROR: {error.message}")
            for warning in result.warnings:
                print(f"  WARNING: {warning.message}")
        else:
            print("Element validation passed")
```

### Element Serialization

```python
import json

def export_elements_to_json(element_ids, output_file):
    """Export elements to JSON format."""
    with RevitContext() as context:
        elements_data = []

        for element_id in element_ids:
            element = context.get_element_by_id(element_id)
            element_dict = element.to_dict()
            elements_data.append(element_dict)

        with open(output_file, 'w') as f:
            json.dump(elements_data, f, indent=2)

        print(f"Exported {len(elements_data)} elements to {output_file}")

def import_elements_from_json(input_file):
    """Import elements from JSON format."""
    with open(input_file, 'r') as f:
        elements_data = json.load(f)

    with RevitContext() as context:
        with context.transaction("Import Elements") as txn:
            imported = []

            for element_dict in elements_data:
                element = Element.from_dict(element_dict, context)
                imported.append(element)

            txn.commit()
            print(f"Imported {len(imported)} elements")
            return imported
```

### Batch Element Processing

```python
from concurrent.futures import ThreadPoolExecutor

def process_elements_in_parallel(element_ids, process_func):
    """Process multiple elements in parallel."""
    with RevitContext() as context:
        # Get all elements first
        elements = [context.get_element_by_id(eid) for eid in element_ids]

        # Process in parallel (read-only operations)
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(process_func, elements))

        return results

# Usage
def analyze_element(element):
    """Analyze a single element."""
    return {
        'id': element.Id.value,
        'name': element.Name,
        'category': element.Category,
        'parameter_count': len(element.get_all_parameters())
    }

element_ids = [123, 456, 789, ...]
results = process_elements_in_parallel(element_ids, analyze_element)
```

## Performance Considerations

### Efficient Parameter Access

```python
# BAD: Multiple database hits
for element in elements:
    height = element.get_parameter('Height').AsDouble()
    width = element.get_parameter('Width').AsDouble()
    area = element.get_parameter('Area').AsDouble()

# GOOD: Cache parameters
for element in elements:
    params = {p.Definition.Name: p for p in element.get_all_parameters()}
    height = params.get('Height', None)
    width = params.get('Width', None)
    area = params.get('Area', None)
```

### Minimize Element Unwrapping

```python
# BAD: Frequent wrapping/unwrapping
for revit_element in revit_elements:
    wrapped = context.wrap_element(revit_element)
    # Do something
    unwrapped = wrapped.unwrap_element()

# GOOD: Work with wrapped elements
wrapped_elements = [context.wrap_element(e) for e in revit_elements]
for element in wrapped_elements:
    # Work directly with wrapped element
    pass
```

### Use Type-Specific Classes

```python
# BAD: Generic element access
elements = context.elements.of_category('Walls').to_list()
for element in elements:
    height = element.get_parameter('Height').AsDouble()  # Slow

# GOOD: Type-specific access
walls = context.elements.of_category('Walls').to_list(WallElement)
for wall in walls:
    height = wall.Height  # Fast, direct property access
```

## Error Handling

```python
from revitpy.api.exceptions import (
    ElementNotFoundError,
    InvalidParameterError,
    ElementDeletionError
)

def safe_element_operations(element_id):
    """Demonstrate error handling for element operations."""
    try:
        with RevitContext() as context:
            element = context.get_element_by_id(element_id)

            # Try to get parameter
            try:
                height = element.get_parameter_value('Height')
            except InvalidParameterError as e:
                print(f"Parameter error: {e}")
                height = None

            # Try to delete element
            try:
                with context.transaction("Delete") as txn:
                    element.delete()
                    txn.commit()
            except ElementDeletionError as e:
                print(f"Cannot delete element: {e}")

    except ElementNotFoundError as e:
        print(f"Element not found: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
```

## Best Practices

1. **Always use context managers**: Ensure proper resource cleanup with `with RevitContext():`
2. **Prefer type-safe classes**: Use `WallElement`, `DoorElement`, etc. for better performance and type safety
3. **Batch operations**: Group related operations in single transactions
4. **Cache frequently accessed data**: Store commonly used elements and parameters
5. **Validate before modifying**: Use validation framework to check element state
6. **Handle errors gracefully**: Use appropriate exception handling for robust code

## Next Steps

- **[Transaction API](transaction-api.md)**: Learn about transaction management
- **[Query Builder](query-builder.md)**: Build complex element queries
- **[Element Sets](element-sets.md)**: Work with collections of elements
- **[ORM Layer](orm.md)**: Use the full ORM capabilities
