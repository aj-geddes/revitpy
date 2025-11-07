# Getting Started with RevitPy

Welcome to RevitPy! This guide will help you get up and running with modern Python development for Autodesk Revit.

## What is RevitPy?

RevitPy is a modern Python framework that brings **Python 3.11+** capabilities to Revit development. Unlike PyRevit (which uses IronPython 2.7), RevitPy gives you access to:

- ✅ Modern Python ecosystem (NumPy, Pandas, TensorFlow, etc.)
- ✅ Async/await for responsive applications
- ✅ Type hints and modern language features
- ✅ Access to cutting-edge AI/ML libraries
- ✅ Full Python package ecosystem via pip

## Installation

### Prerequisites

- **Python 3.11 or higher**
- **Autodesk Revit 2021-2025**
- **Windows** (primary), macOS and Linux (experimental)

### Quick Install

```bash
# Install RevitPy using pip
pip install revitpy

# Verify installation
revitpy --version
```

### Install from Source

```bash
# Clone the repository
git clone https://github.com/revitpy/revitpy.git
cd revitpy

# Install in development mode
pip install -e .

# Install with all optional dependencies
pip install -e ".[dev,docs,test]"
```

### Verify Installation

```bash
# Check RevitPy installation
revitpy doctor

# This will verify:
# - Python version
# - RevitPy installation
# - Revit API availability
# - Dependencies
```

## Your First RevitPy Script

### 1. Create a New Project

```bash
# Create a new RevitPy project from template
revitpy create my-first-addon --template basic-script

cd my-first-addon
```

### 2. Write Your First Script

Create `main.py`:

```python
"""My first RevitPy script."""

from revitpy.api import Query, Transaction
from revitpy.api.wrapper import get_active_document

def main():
    # Get the active Revit document
    doc = get_active_document()

    # Create a query interface
    query = Query(doc)

    # Get all walls in the document
    walls = query.get_elements_by_category("Walls")

    print(f"Found {len(walls)} walls in the document")

    # Print details of each wall
    for wall in walls:
        wall_type = query.get_parameter_value(wall, "Type")
        height = query.get_parameter_value(wall, "Unconnected Height")

        print(f"Wall Type: {wall_type}, Height: {height}")

if __name__ == "__main__":
    main()
```

### 3. Run Your Script

```bash
# Run the script in Revit
revitpy run main.py

# Or use the development server with hot reload
revitpy dev main.py
```

## Core Concepts

### Document Access

RevitPy provides safe, convenient access to Revit documents:

```python
from revitpy.api.wrapper import get_active_document, get_all_documents

# Get the active document
doc = get_active_document()

# Get all open documents
docs = get_all_documents()

# Access document properties
print(f"Document title: {doc.Title}")
print(f"Document path: {doc.PathName}")
```

### Querying Elements

Use the Query interface for LINQ-style element queries:

```python
from revitpy.api import Query

query = Query(doc)

# Get elements by category
walls = query.get_elements_by_category("Walls")
doors = query.get_elements_by_category("Doors")

# Get elements by type
all_walls = query.get_elements_by_class("Wall")

# Get parameter values
for wall in walls:
    level = query.get_parameter_value(wall, "Level")
    length = query.get_parameter_value(wall, "Length")
    print(f"Wall on {level}: {length} ft")
```

### Transactions

Wrap modifications in transactions:

```python
from revitpy.api import Transaction

# Simple transaction
with Transaction(doc, "Modify Walls") as t:
    for wall in walls:
        # Modify wall parameters
        wall.get_Parameter("Comments").Set("Modified by RevitPy")

# Transaction with error handling
tx = Transaction(doc, "Complex Modification")
try:
    tx.start()

    # Make changes
    for wall in walls:
        wall.get_Parameter("Mark").Set("A")

    tx.commit()
except Exception as e:
    tx.rollback()
    print(f"Transaction failed: {e}")
```

### Using the ORM

RevitPy includes a powerful ORM for type-safe element access:

```python
from revitpy.orm import ElementQuery

# Query walls with LINQ-style syntax
walls = (ElementQuery(doc)
    .of_category("Walls")
    .where(lambda w: w.Height > 10.0)
    .order_by(lambda w: w.Length)
    .to_list())

# Get single element
main_wall = (ElementQuery(doc)
    .of_category("Walls")
    .where(lambda w: w.Mark == "W-001")
    .first())

# Use projections
wall_data = (ElementQuery(doc)
    .of_category("Walls")
    .select(lambda w: {
        "id": w.Id,
        "type": w.WallType,
        "length": w.Length,
        "height": w.Height
    })
    .to_list())
```

### Async Operations

Use async/await for responsive applications:

```python
import asyncio
from revitpy.async_support import async_query

async def process_elements():
    """Process elements asynchronously."""
    # Get all walls asynchronously
    walls = await async_query.get_elements_by_category_async(
        doc, "Walls"
    )

    # Process walls concurrently
    tasks = [process_wall(wall) for wall in walls]
    results = await asyncio.gather(*tasks)

    return results

async def process_wall(wall):
    """Process a single wall."""
    # Simulate async operation
    await asyncio.sleep(0.1)
    return {
        "id": wall.Id,
        "type": wall.WallType.Name
    }

# Run async function
results = asyncio.run(process_elements())
```

## Development Workflow

### 1. Development Server

Use the development server for hot reload:

```bash
# Start dev server
revitpy dev main.py

# Opens WebSocket connection to Revit
# Auto-reloads on file changes
# Provides real-time feedback
```

### 2. Testing

Write tests using the mock Revit environment:

```python
import pytest
from revitpy.testing import MockRevitEnvironment

def test_wall_query():
    """Test querying walls."""
    # Create mock environment
    env = MockRevitEnvironment()
    doc = env.create_mock_document()

    # Create mock walls
    env.create_mock_element(doc, "Walls", {"Length": 10.0})
    env.create_mock_element(doc, "Walls", {"Length": 20.0})

    # Test your code
    from revitpy.api import Query
    query = Query(doc)
    walls = query.get_elements_by_category("Walls")

    assert len(walls) == 2
```

### 3. Building & Publishing

```bash
# Build your addon
revitpy build

# Validate package
revitpy validate dist/my-addon-1.0.0.tar.gz

# Publish to registry
revitpy publish dist/my-addon-1.0.0.tar.gz
```

## Next Steps

Now that you have RevitPy installed and understand the basics:

1. **[First Script Tutorial](../tutorials/first-script.md)** - Build your first complete addon
2. **[ORM Guide](../guides/orm-guide.md)** - Learn advanced querying techniques
3. **[Async Guide](../guides/async-guide.md)** - Build responsive applications
4. **[API Reference](../reference/api/index.md)** - Explore the complete API

## Common Issues

### Python Version

RevitPy requires Python 3.11+. Check your version:

```bash
python --version
# Should show 3.11.0 or higher
```

### Revit API Not Found

If you get errors about missing Revit API:

```bash
# Run the doctor command to diagnose
revitpy doctor

# Set REVIT_API_PATH if needed
export REVIT_API_PATH="/path/to/revit/api"
```

### Import Errors

If you get import errors:

```bash
# Reinstall RevitPy
pip uninstall revitpy
pip install revitpy

# Or install from source
pip install -e .
```

## Getting Help

- **Documentation**: [https://docs.revitpy.org](https://docs.revitpy.org)
- **Discord**: [https://discord.gg/revitpy](https://discord.gg/revitpy)
- **GitHub Issues**: [https://github.com/revitpy/revitpy/issues](https://github.com/revitpy/revitpy/issues)
- **Stack Overflow**: Tag your questions with `revitpy`

## Summary

You now have RevitPy installed and know the basics:

- ✅ Document access
- ✅ Element querying
- ✅ Transactions
- ✅ ORM usage
- ✅ Async operations
- ✅ Development workflow

Continue learning with our [tutorials](../tutorials/index.md) and [API reference](../reference/api/index.md)!
