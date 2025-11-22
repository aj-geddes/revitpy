---
layout: default
title: Documentation
description: Complete API reference and documentation for RevitPy. Explore core APIs, ORM, async support, events, extensions, and more.
permalink: /documentation/
---

<div class="container">
  <div class="main-content">
    <div class="page-header">
      <h1 class="page-title">Documentation</h1>
      <p class="page-description">
        Complete API reference and guides for building with RevitPy. Select a topic to get started.
      </p>
    </div>

## API Reference

<div class="examples-grid">
  <a href="{{ '/reference/api/core/' | relative_url }}" class="example-card">
    <div class="example-icon">&#128300;</div>
    <h3 class="example-title">Core API</h3>
    <p class="example-description">
      RevitContext, element access, transactions, and fundamental operations.
    </p>
    <div class="example-tags">
      <span class="example-tag">Essential</span>
    </div>
  </a>

  <a href="{{ '/reference/api/orm/' | relative_url }}" class="example-card">
    <div class="example-icon">&#128269;</div>
    <h3 class="example-title">ORM Layer</h3>
    <p class="example-description">
      LINQ-style queries, relationship navigation, caching, and change tracking.
    </p>
    <div class="example-tags">
      <span class="example-tag">Queries</span>
    </div>
  </a>

  <a href="{{ '/reference/api/async/' | relative_url }}" class="example-card">
    <div class="example-icon">&#9889;</div>
    <h3 class="example-title">Async Support</h3>
    <p class="example-description">
      AsyncRevitContext, task queues, progress tracking, and cancellation.
    </p>
    <div class="example-tags">
      <span class="example-tag">Advanced</span>
    </div>
  </a>

  <a href="{{ '/reference/api/events/' | relative_url }}" class="example-card">
    <div class="example-icon">&#128276;</div>
    <h3 class="example-title">Event System</h3>
    <p class="example-description">
      Event handlers, decorators, filtering, and event-driven architecture.
    </p>
    <div class="example-tags">
      <span class="example-tag">Events</span>
    </div>
  </a>

  <a href="{{ '/reference/api/extensions/' | relative_url }}" class="example-card">
    <div class="example-icon">&#128268;</div>
    <h3 class="example-title">Extensions</h3>
    <p class="example-description">
      Plugin architecture, dependency injection, and extension lifecycle.
    </p>
    <div class="example-tags">
      <span class="example-tag">Plugins</span>
    </div>
  </a>

  <a href="{{ '/reference/api/testing/' | relative_url }}" class="example-card">
    <div class="example-icon">&#128203;</div>
    <h3 class="example-title">Testing</h3>
    <p class="example-description">
      Mock objects, test fixtures, assertions, and testing best practices.
    </p>
    <div class="example-tags">
      <span class="example-tag">Testing</span>
    </div>
  </a>
</div>

## Quick Reference

### RevitContext

The main entry point for all RevitPy operations:

```python
from revitpy import RevitContext

with RevitContext() as context:
    # Access elements
    walls = context.elements.of_category('Walls')

    # Run transactions
    with context.transaction("Update walls"):
        for wall in walls:
            wall.set_parameter('Mark', 'Updated')

    # Access document properties
    print(f"Project: {context.document.Title}")
```

### Query Syntax

Chain methods for powerful filtering:

```python
results = (context.elements
    .of_category('Rooms')
    .where(lambda r: r.Area > 100)
    .where(lambda r: r.Level.Name == 'Level 1')
    .include('Boundaries')
    .order_by(lambda r: r.Area)
    .take(10)
    .to_list())
```

### Async Operations

Process large datasets without blocking:

```python
from revitpy import AsyncRevitContext

async with AsyncRevitContext() as context:
    elements = await context.elements.to_list_async()

    async with context.transaction("Batch update"):
        for elem in elements:
            elem.set_parameter('Processed', True)
        await context.save_changes_async()
```

### Event Handling

React to document changes:

```python
from revitpy.events import event_handler, EventType

@event_handler(EventType.ELEMENT_ADDED)
def on_element_added(event):
    element = event.data['element']
    print(f"New element: {element.Name}")
```

## Guides

### Getting Started
- [Installation]({{ '/getting-started/' | relative_url }}) - Install and configure RevitPy
- [First Project]({{ '/getting-started/#your-first-project' | relative_url }}) - Create your first script
- [VS Code Setup]({{ '/getting-started/#vs-code-integration' | relative_url }}) - Configure your IDE

### Integration
- [PyRevit Integration]({{ '/pyrevit-integration/' | relative_url }}) - Use RevitPy with PyRevit
- [Migration Guide]({{ '/reference/migration/' | relative_url }}) - Migrate from other tools

### Advanced Topics
- Performance Optimization - Write fast, efficient code
- Enterprise Deployment - Deploy at scale
- Custom Extensions - Build plugins

## Class Index

### Core Classes

| Class | Description |
|-------|-------------|
| `RevitContext` | Main context manager for Revit operations |
| `AsyncRevitContext` | Async version of RevitContext |
| `Element` | Base class for all Revit elements |
| `Transaction` | Transaction wrapper with rollback support |
| `Document` | Revit document wrapper |

### ORM Classes

| Class | Description |
|-------|-------------|
| `ElementQuery` | Query builder for elements |
| `ChangeTracker` | Tracks element modifications |
| `CacheManager` | Manages query result caching |
| `Relationship` | Defines element relationships |

### Event Classes

| Class | Description |
|-------|-------------|
| `EventManager` | Central event dispatcher |
| `EventHandler` | Base class for handlers |
| `EventType` | Enumeration of event types |
| `EventFilter` | Filter events by criteria |

### Testing Classes

| Class | Description |
|-------|-------------|
| `MockRevit` | Mock Revit application |
| `MockDocument` | Mock document for testing |
| `MockElement` | Configurable element mock |
| `RevitTestCase` | Base test case class |

## Type Definitions

RevitPy includes comprehensive type definitions for IDE support:

```python
from revitpy.types import (
    ElementId,
    XYZ,
    BoundingBox,
    Parameter,
    Category,
    Level,
    WallElement,
    RoomElement,
    # ... and more
)
```

## Constants and Enums

```python
from revitpy import (
    BuiltInCategory,
    BuiltInParameter,
    UnitType,
    DisplayUnit,
    TransactionStatus,
)

# Example usage
walls = context.elements.of_builtin_category(BuiltInCategory.OST_Walls)
```

## Error Handling

RevitPy provides detailed error types:

```python
from revitpy.exceptions import (
    RevitPyError,           # Base exception
    TransactionError,       # Transaction failures
    ElementNotFoundError,   # Element lookup failures
    ValidationError,        # Parameter validation
    ConnectionError,        # Revit connection issues
)

try:
    with context.transaction("Update"):
        element.set_parameter('Invalid', value)
except ValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Parameter: {e.parameter_name}")
    print(f"Expected: {e.expected_type}")
```

## Configuration

Configure RevitPy behavior:

```python
from revitpy import config

# Performance settings
config.cache.enabled = True
config.cache.max_size = 10000
config.cache.ttl = 300  # seconds

# Logging
config.logging.level = 'INFO'
config.logging.file = 'revitpy.log'

# Transaction behavior
config.transaction.auto_commit = True
config.transaction.timeout = 30
```

## Need Help?

- **GitHub Issues**: [Report bugs](https://github.com/revitpy/revitpy/issues)
- **Discussions**: [Ask questions](https://github.com/revitpy/revitpy/discussions)
- **Examples**: [View examples]({{ '/examples/' | relative_url }})

  </div>
</div>
