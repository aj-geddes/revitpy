# API Reference

Welcome to the comprehensive API reference for RevitPy Framework. This section provides detailed documentation for all public APIs, classes, methods, and functions available in RevitPy.

## Overview

RevitPy's API is organized into several key modules:

- **[Core API](api/core.md)**: Essential classes and functions for Revit interaction
- **[ORM Layer](api/orm.md)**: Object-relational mapping for intuitive element queries  
- **[Extensions](api/extensions.md)**: Plugin architecture and extension management
- **[Async Support](api/async.md)**: Asynchronous programming capabilities
- **[CLI Tools](cli/index.md)**: Command-line interface documentation

## Quick Reference

### Core Classes

| Class | Purpose | Example Usage |
|-------|---------|---------------|
| `RevitContext` | Main entry point for Revit operations | `with RevitContext() as ctx:` |
| `ElementSet` | Collection of Revit elements | `walls = ctx.elements.of_category('Walls')` |
| `QueryBuilder` | LINQ-style query construction | `.where(lambda e: e.Height > 10)` |
| `Transaction` | Manage Revit transactions | `with ctx.transaction("Update"):` |

### Common Operations

```python
# Basic element access
from revitpy import RevitContext

with RevitContext() as context:
    # Get all walls
    walls = context.elements.of_category('Walls')
    
    # Query with filtering
    tall_walls = walls.where(lambda w: w.Height > 10.0)
    
    # Execute transaction
    with context.transaction("Update Walls") as txn:
        for wall in tall_walls:
            wall.set_parameter("Comments", "Tall wall")
        txn.commit()
```

### Advanced Queries

```python
# Complex filtering with relationships
rooms = (context.elements
         .of_category('Rooms')
         .where(lambda r: r.Area > 100)
         .include('Boundaries.Wall')  # Eager loading
         .order_by(lambda r: r.Area)
         .to_list())

# Async operations
async def process_elements():
    async with AsyncRevitContext() as context:
        elements = await context.elements.where(
            lambda e: e.Category == 'Windows'
        ).to_list_async()
        return elements
```

## API Conventions

### Naming Conventions
- **Classes**: PascalCase (`RevitContext`, `ElementSet`)
- **Methods**: snake_case (`get_parameter`, `set_parameter`)  
- **Properties**: PascalCase (`Name`, `Height`, `Area`)
- **Constants**: UPPER_SNAKE_CASE (`DEFAULT_TIMEOUT`)

### Error Handling
All RevitPy APIs use structured exceptions:

```python
from revitpy.exceptions import (
    RevitPyException,      # Base exception
    ElementNotFound,       # Element access errors
    TransactionFailed,     # Transaction errors
    ValidationError        # Input validation errors
)

try:
    element = context.get_element_by_id(element_id)
except ElementNotFound as e:
    print(f"Element not found: {e.message}")
    print(f"Suggestions: {e.suggestions}")
```

### Type Annotations
RevitPy provides complete type annotations for better IDE support:

```python
from typing import List, Optional
from revitpy import RevitContext, Element

def get_walls_by_type(context: RevitContext, 
                     wall_type: str) -> List[Element]:
    """Get walls of a specific type.
    
    Args:
        context: The Revit context
        wall_type: Name of the wall type to filter by
        
    Returns:
        List of wall elements matching the type
        
    Raises:
        ValidationError: If wall_type is empty or invalid
    """
    return context.elements.where(
        lambda w: w.WallType.Name == wall_type
    ).to_list()
```

## Module Structure

```
revitpy/
├── __init__.py           # Main exports
├── api/                  # Core API classes
│   ├── element.py       # Element manipulation
│   ├── query.py         # Query execution  
│   ├── transaction.py   # Transaction management
│   └── wrapper.py       # Revit API wrapper
├── orm/                  # ORM layer
│   ├── context.py       # RevitContext class
│   ├── element_set.py   # ElementSet class
│   ├── query_builder.py # QueryBuilder class
│   └── relationships.py # Relationship handling
├── extensions/           # Extension system
│   ├── manager.py       # Extension management
│   ├── registry.py      # Extension registry
│   └── loader.py        # Dynamic loading
├── async_support/        # Async capabilities
│   ├── async_revit.py   # Async context
│   ├── decorators.py    # Async decorators
│   └── progress.py      # Progress tracking
└── utils/               # Utility functions
```

## Performance Considerations

### Best Practices
1. **Use transactions efficiently**: Group related operations
2. **Minimize element creation**: Reuse existing elements when possible  
3. **Batch operations**: Use bulk methods for large datasets
4. **Cache frequently accessed data**: Store results to avoid repeated queries
5. **Dispose resources**: Use context managers (`with` statements)

### Performance Monitoring
```python
from revitpy.utils import performance_monitor

@performance_monitor.track
def process_walls(context: RevitContext) -> None:
    """Process walls with performance tracking."""
    walls = context.elements.of_category('Walls')
    
    # Performance metrics are automatically collected
    with context.transaction("Update Walls"):
        for wall in walls:
            wall.set_parameter("Processed", True)

# View performance metrics
metrics = performance_monitor.get_metrics("process_walls")
print(f"Average execution time: {metrics.avg_time:.2f}ms")
print(f"Memory usage: {metrics.memory_usage:.2f}MB")
```

## Testing APIs

RevitPy provides comprehensive testing utilities:

```python
from revitpy.testing import MockRevitContext, create_mock_element

def test_wall_processing():
    """Test wall processing with mock data."""
    with MockRevitContext() as mock_context:
        # Create mock walls
        wall1 = create_mock_element('Wall', height=10.0)
        wall2 = create_mock_element('Wall', height=15.0)
        mock_context.add_elements([wall1, wall2])
        
        # Test your code
        tall_walls = mock_context.elements.where(
            lambda w: w.Height > 12.0
        ).to_list()
        
        assert len(tall_walls) == 1
        assert tall_walls[0].Height == 15.0
```

## Next Steps

- **[Core API](api/core.md)**: Learn about the fundamental RevitPy classes
- **[ORM Documentation](api/orm.md)**: Master the object-relational mapping layer
- **[Extension Development](api/extensions.md)**: Build plugins and extensions
- **[CLI Reference](cli/index.md)**: Command-line tools and usage
- **[Examples Repository](https://github.com/highvelocitysolutions/revitpy/tree/main/examples)**: Real-world code examples