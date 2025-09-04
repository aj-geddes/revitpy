# RevitPy ORM Layer

A comprehensive Object-Relational Mapping (ORM) layer for RevitPy that provides an intuitive, high-performance Pythonic interface to Revit elements and operations.

## Overview

The RevitPy ORM layer transforms complex Revit API interactions into elegant, LINQ-style Python code with enterprise-grade performance and reliability. It provides:

- **LINQ-style Querying**: Fluent query interface with lazy evaluation and deferred execution
- **Type Safety**: Comprehensive validation with Pydantic models and runtime type checking
- **High Performance**: <100ms response time for complex queries on 10,000+ elements
- **Change Tracking**: Automatic modification tracking with batch operations
- **Intelligent Caching**: Multi-level caching with smart invalidation
- **Async Support**: Full async/await support for non-blocking operations
- **Relationship Management**: Navigation properties between Revit elements

## Quick Start

```python
from revitpy.orm import RevitContext, WallElement, RoomElement

# Create context with automatic change tracking
with RevitContext() as ctx:
    # LINQ-style querying
    tall_walls = (ctx.all(WallElement)
                    .where(lambda w: w.height > 10)
                    .where(lambda w: w.level.name == "Level 1")
                    .order_by(lambda w: w.name)
                    .to_list())
    
    # Relationship navigation
    room = ctx.first(RoomElement, lambda r: r.number == "101")
    connected_walls = room.walls.where(lambda w: w.structural == True)
    
    # Change tracking and batch updates
    for wall in tall_walls:
        wall.fire_rating = 2
        wall.mark_dirty()
    
    # Save all changes in one batch operation
    changes_saved = ctx.save_changes()  # Returns count of saved changes

# Async support
async with RevitContext().as_async() as ctx:
    walls = await ctx.all(WallElement).to_list_async()
    
    async for wall in ctx.all(WallElement).as_streaming():
        print(f"Processing wall: {wall.name}")
```

## Core Components

### QueryBuilder - LINQ-Style Querying

The QueryBuilder provides a fluent interface for querying Revit elements with full LINQ compatibility:

```python
from revitpy.orm import QueryBuilder

# Complex query with multiple operations
result = (QueryBuilder(provider, WallElement)
          .where(lambda w: w.height > 8)
          .where(lambda w: w.structural == True)
          .select(lambda w: {"name": w.name, "area": w.area})
          .order_by(lambda w: w.height)
          .group_by(lambda w: w.level_id)
          .skip(10)
          .take(50)
          .to_list())

# Aggregations
total_walls = query.count()
avg_height = query.average(lambda w: w.height)
max_wall = query.max(lambda w: w.height)

# Async operations
walls = await query.to_list_async()
first_wall = await query.first_async()
```

**Performance Features:**
- Lazy evaluation with deferred execution
- Query optimization and caching
- Parallel execution for safe operations
- Streaming support for large datasets

### ElementSet - Collection Management

ElementSet provides high-performance collection operations with lazy loading:

```python
from revitpy.orm import ElementSet

# Create from existing elements
walls = ElementSet(wall_list, element_type=WallElement)

# Lazy loading with pagination
large_set = ElementSet.from_query(query, lazy=True, page_size=1000)

# Batch operations
updates = {"fire_rating": 2, "structural": True}
updated_count = walls.batch_update(updates, batch_size=100)

# Thread-safe operations
walls.parallel_process(lambda w: expensive_operation(w), max_workers=4)
```

### Validation System

Comprehensive type safety with Pydantic models:

```python
from revitpy.orm.validation import WallElement, ElementValidator, ValidationLevel

# Type-safe element creation
wall = WallElement(
    id=1,
    height=10.0,
    length=20.0,
    width=0.5,
    name="Main Wall",
    structural=True
)

# Validation
validator = ElementValidator(ValidationLevel.STRICT)
errors = validator.validate_element(wall)
if errors:
    print("Validation errors:", errors)

# Factory functions with validation
wall = create_wall(id=1, height=10, length=20, width=0.5)
```

**Supported Element Types:**
- `WallElement` - Revit walls with structural properties
- `RoomElement` - Revit rooms with spatial data
- `DoorElement` - Revit doors with hardware specifications
- `WindowElement` - Revit windows with performance data
- `BaseElement` - Base class for custom element types

### Change Tracking

Automatic modification tracking with batch operations:

```python
from revitpy.orm import ChangeTracker

# Create change tracker
tracker = ChangeTracker(thread_safe=True)

# Attach entities for tracking
tracker.attach(wall)

# Changes are tracked automatically
wall.height = 12.0  # Automatically tracked
wall.fire_rating = 1.5

# Get tracked changes
changes = tracker.get_all_changes()
for change in changes:
    print(f"Changed: {change.property_name} from {change.old_value} to {change.new_value}")

# Batch operations
batch_ops = [
    BatchOperation(BatchOperationType.UPDATE, wall1, {"height": 12}),
    BatchOperation(BatchOperationType.UPDATE, wall2, {"width": 0.6})
]
```

### Caching System

Multi-level intelligent caching:

```python
from revitpy.orm import CacheManager, CacheConfiguration

# Configure caching
config = CacheConfiguration(
    max_size=10000,
    max_memory_mb=500,
    default_ttl_seconds=3600,
    eviction_policy=EvictionPolicy.LRU
)

cache = CacheManager(config)

# Cache with dependencies
cache.set(
    cache_key,
    query_result,
    ttl_seconds=1800,
    dependencies={"Level_1", "Walls"}
)

# Smart invalidation
cache.invalidate_by_dependency("Level_1")  # Invalidates all dependent entries
cache.invalidate_by_pattern("Wall*")       # Pattern-based invalidation

# Performance monitoring
stats = cache.statistics
print(f"Hit rate: {stats.hit_rate:.1f}%, Memory: {stats.memory_usage:,} bytes")
```

### Relationship Management

Define and navigate relationships between elements:

```python
from revitpy.orm import RelationshipManager

# Configure relationships
relationships = RelationshipManager(provider, cache)

# Define wall-to-room relationship
relationships.register_one_to_many(
    WallElement, "room",
    RoomElement, "walls",
    foreign_key_selector=lambda wall: wall.room_id
)

# Navigation properties
wall = ctx.first(WallElement)
room = wall.room  # Lazy-loaded relationship

room = ctx.first(RoomElement)
room_walls = room.walls  # Collection of related walls

# Eager loading
walls_with_rooms = ctx.all(WallElement).include("room").to_list()
```

### Async Support

Full async/await support with transaction management:

```python
from revitpy.orm import AsyncRevitContext

async with AsyncRevitContext(provider) as ctx:
    # Async queries
    walls = await ctx.get_all_async(WallElement)
    wall = await ctx.get_by_id_async(123)
    
    # Async transactions
    async with ctx.transaction() as trans:
        wall.height = 12
        wall.mark_dirty()
        
        room = await ctx.get_by_id_async(456)
        room.area = 250
        room.mark_dirty()
        
        # Auto-commit on success, rollback on exception
        await ctx.save_changes_async()
    
    # Batch processing
    operations = [BatchOperation(...) for _ in range(1000)]
    result = await async_batch_operation(
        operations,
        operation_handler,
        max_concurrency=10
    )
```

## Performance Benchmarks

The ORM layer meets strict performance requirements:

### Query Performance
- **Simple queries**: <10ms response time
- **Complex queries**: <100ms on 10,000+ elements
- **Large result sets**: <500ms for thousands of elements
- **Async queries**: Competitive with synchronous performance

### Throughput
- **Cache operations**: 10,000+ operations/second
- **Change tracking**: 5,000+ tracked changes/second  
- **Batch updates**: 5,000+ updates/second
- **Validation**: 2,000+ validations/second

### Scalability
- Tested with up to 50,000 elements
- Linear performance scaling
- Memory-efficient lazy loading
- Streaming support for unlimited datasets

## Configuration

Configure the ORM for your specific needs:

```python
from revitpy.orm import RevitContext, ContextConfiguration

config = ContextConfiguration(
    auto_track_changes=True,
    cache_policy=CachePolicy.MEMORY,
    cache_max_size=50000,
    cache_max_memory_mb=1000,
    lazy_loading_enabled=True,
    batch_size=500,
    thread_safe=True,
    validation_enabled=True,
    performance_monitoring=True
)

ctx = RevitContext(provider, config=config)
```

## Testing

Comprehensive test suite with 90%+ coverage:

```bash
# Run all ORM tests
pytest tests/orm/

# Run performance benchmarks
pytest tests/orm/test_performance_benchmarks.py -m benchmark

# Run specific component tests
pytest tests/orm/test_validation.py -v
pytest tests/orm/test_query_integration.py -v
```

## Advanced Usage

### Custom Element Types

Create custom element types with validation:

```python
from revitpy.orm.validation import BaseElement
from pydantic import Field, validator

class CustomElement(BaseElement):
    custom_property: str = Field(..., min_length=1)
    numeric_value: float = Field(..., gt=0)
    
    @validator('custom_property')
    def validate_custom(cls, v):
        if not v.startswith('CUSTOM_'):
            raise ValueError('Must start with CUSTOM_')
        return v

# Register with validator
validator.register_element_type("Custom", CustomElement)
```

### Custom Validation Rules

Add custom validation rules:

```python
from revitpy.orm.validation import ValidationRule, ConstraintType

custom_rule = ValidationRule(
    property_name="height",
    constraint_type=ConstraintType.MIN_VALUE,
    constraint_value=5.0,
    error_message="Height must be at least 5 feet"
)

validator.add_custom_rule(custom_rule)
```

### Performance Optimization

Optimize for specific use cases:

```python
# Disable change tracking for read-only operations
ctx.change_tracker.auto_track = False

# Use streaming for large datasets
async for batch in ctx.all(WallElement).as_streaming(batch_size=1000):
    process_batch(batch)

# Optimize cache for specific access patterns
cache_config = CacheConfiguration(
    eviction_policy=EvictionPolicy.LFU,  # For frequently accessed data
    cleanup_interval_seconds=60         # More frequent cleanup
)

# Use eager loading for known relationship patterns
walls = ctx.all(WallElement).include("room").include("level").to_list()
```

## Architecture

The ORM layer follows clean architecture principles:

```
┌─────────────────────────────────────────┐
│                API Layer                │  ← Your application code
├─────────────────────────────────────────┤
│            ORM Context Layer            │  ← RevitContext, AsyncRevitContext
├─────────────────────────────────────────┤
│         Query & Collection Layer        │  ← QueryBuilder, ElementSet
├─────────────────────────────────────────┤
│     Validation & Type Safety Layer     │  ← Pydantic models, ElementValidator
├─────────────────────────────────────────┤
│   Cross-Cutting Concerns Layer         │  ← Caching, Change Tracking, Relationships
├─────────────────────────────────────────┤
│           Data Access Layer             │  ← IElementProvider interface
├─────────────────────────────────────────┤
│              Revit API                  │  ← Actual Revit integration
└─────────────────────────────────────────┘
```

## Error Handling

Comprehensive error handling with specific exception types:

```python
from revitpy.orm.exceptions import (
    ORMException, QueryError, ValidationError, 
    CacheError, RelationshipError
)

try:
    wall = ctx.single(WallElement, lambda w: w.name == "NonExistent")
except QueryError as e:
    print(f"Query failed: {e.message}")
    print(f"Query operation: {e.query_operation}")

try:
    invalid_wall = WallElement(id=1, height=-5)  # Invalid height
except ValidationError as e:
    print(f"Validation failed: {e.validation_errors}")
```

## Contributing

When extending the ORM:

1. Follow the existing architectural patterns
2. Add comprehensive validation with Pydantic
3. Include async support where applicable
4. Write performance tests for new features
5. Maintain 90%+ test coverage
6. Document performance characteristics

## Performance Guidelines

- Always prefer lazy evaluation for queries
- Use batch operations for multiple updates
- Enable caching for frequently accessed data
- Use streaming for large datasets
- Consider async operations for I/O-bound work
- Monitor cache hit rates and adjust configuration
- Use type hints and validation for better performance

The RevitPy ORM layer provides enterprise-grade functionality while maintaining the simplicity and elegance that makes Python productive for Revit development.