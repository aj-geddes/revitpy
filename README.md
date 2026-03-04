# RevitPy

[![CI](https://github.com/aj-geddes/revitpy/actions/workflows/ci.yml/badge.svg)](https://github.com/aj-geddes/revitpy/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Development Status](https://img.shields.io/badge/status-alpha-orange.svg)]()

A modern Python framework for Autodesk Revit development featuring LINQ-style queries, an ORM layer with change tracking, an event system, extension framework, async support, quantity extraction, IFC interoperability, AI agent integration, sustainability analytics, Speckle connectivity, and cloud automation.

> **Status**: Alpha (Development Status 3). The API surface is functional but may change before 1.0.

## Installation

```bash
pip install revitpy
```

For development:

```bash
git clone https://github.com/aj-geddes/revitpy.git
cd revitpy
pip install -e ".[dev]"
```

## Key Features

### LINQ-Style Query Builder

Fluent query interface for filtering, sorting, and paginating Revit elements.

```python
from revitpy import RevitAPI

api = RevitAPI()

# Chain filters with a fluent interface
results = (
    api.query()
    .where("category", FilterOperator.EQUALS, "Walls")
    .contains("name", "Exterior")
    .order_by_descending("height")
    .skip(0)
    .take(50)
    .execute()
)
```

### ORM with Change Tracking

Entity framework-inspired ORM with Pydantic validation, caching, and relationship management.

```python
from revitpy.orm import create_context, RevitContext

context = create_context(provider)

# Query through the ORM
walls = context.all(WallElement)
tall_walls = context.where(WallElement, lambda w: w.height > 10)

# Change tracking
context.attach(element)
element.name = "Updated Wall"
count = context.save_changes()  # Persists tracked changes
```

### Event System

Priority-based event dispatching with sync and async handler support.

```python
from revitpy import EventManager, event_handler

@event_handler(EventType.ELEMENT_CHANGED, priority=EventPriority.HIGH)
def on_element_changed(event_data):
    print(f"Element {event_data.element_id} was modified")

manager = EventManager.get_instance()
manager.register_class_handlers(my_handler_instance)
```

### Extension Framework

Plugin architecture with lifecycle management and dependency injection.

```python
from revitpy import Extension

class MyExtension(Extension):
    async def load(self):
        self.log_info("Extension loading")

    async def activate(self):
        self.log_info("Extension active")

    async def deactivate(self):
        pass

    async def dispose(self):
        pass
```

### Transaction Management

Context manager support for safe, rollback-capable transactions.

```python
from revitpy import RevitAPI

api = RevitAPI()

with api.transaction("Rename Walls") as txn:
    for element in elements:
        element.name = f"Wall-{element.id}"
    # Auto-commits on exit, rolls back on exception
```

### Testing Without Revit

Mock environment for unit testing outside of Revit.

```python
from revitpy import MockRevit

mock = MockRevit()
doc = mock.create_document("Test.rvt")
element = mock.create_element(name="Test Wall", category="Walls")

assert element.Name == "Test Wall"
assert doc.GetElementCount() == 1
```

### Quantity Extraction

Extract quantities, materials, costs, and export data from Revit elements.

```python
from revitpy.extract import QuantityExtractor, DataExporter

extractor = QuantityExtractor()
items = extractor.extract(elements)
grouped = extractor.extract_grouped(elements, group_by=AggregationLevel.LEVEL)

exporter = DataExporter()
exporter.to_csv([item.__dict__ for item in items], Path("takeoff.csv"))
```

### IFC Interoperability

Bidirectional IFC workflows via IfcOpenShell (optional).

```python
from revitpy.ifc import IfcExporter, IfcVersion

exporter = IfcExporter()
exporter.export(elements, Path("model.ifc"), version=IfcVersion.IFC4)
```

### AI & MCP Server

Expose RevitPy operations as MCP tools for AI agents with safety guardrails.

```python
from revitpy.ai import McpServer, RevitTools, SafetyGuard

tools = RevitTools()
guard = SafetyGuard()

async with McpServer(tools, safety_guard=guard) as server:
    await server.start()
```

### Sustainability & Carbon Analytics

Embodied carbon calculations, EPD database, and compliance checking.

```python
from revitpy.sustainability import CarbonCalculator, ComplianceChecker

calculator = CarbonCalculator()
results = calculator.calculate(materials)
summary = calculator.summarize(results)
benchmark = calculator.benchmark(summary, building_area_m2=5000.0)
```

### Cloud & Design Automation

Submit Design Automation jobs to Autodesk Platform Services.

```python
from revitpy.cloud import ApsClient, JobManager

client = ApsClient(credentials)
jobs = JobManager(client)
job_id = await jobs.submit(config)
result = await jobs.wait_for_completion(job_id)
```

## Architecture

```
revitpy/
  api/             Core API: RevitAPI, Element, Transaction, QueryBuilder
  orm/             ORM layer: RevitContext, change tracking, caching, validation
  events/          Event system: manager, engine, decorators, filters
  extensions/      Plugin framework: Extension, ExtensionManager, DI
  async_support/   Async: AsyncRevit, TaskQueue, progress, cancellation
  performance/     Optimizer, benchmarks, memory management
  testing/         MockRevit, MockDocument, MockElement
  config.py        Configuration management
  extract/         Quantity takeoff, material aggregation, cost estimation, data export
  ifc/             IFC export/import, element mapping, IDS validation, BCF, diff
  ai/              MCP server, tool registration, safety guardrails, prompt templates
  sustainability/  Carbon calculations, EPD database, compliance checking, reports
  interop/         Speckle sync, type mapping, diff, merge, subscriptions
  cloud/           APS Design Automation, batch processing, CI/CD helpers
```

## Requirements

- Python 3.11+
- See [pyproject.toml](pyproject.toml) for full dependency list

Optional dependencies:

```bash
pip install revitpy[ifc]          # IFC support (ifcopenshell)
pip install revitpy[interop]      # Speckle connectivity (specklepy)
pip install revitpy[all]          # All optional dependencies
```

## Development

```bash
# Run tests
pytest tests/

# Lint and format
ruff check revitpy/ tests/
ruff format revitpy/ tests/

# Type check
mypy revitpy/

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

## Documentation

Full documentation is available at [aj-geddes.github.io/revitpy](https://aj-geddes.github.io/revitpy/).

- [Getting Started](https://aj-geddes.github.io/revitpy/user/getting-started/)
- [API Reference](https://aj-geddes.github.io/revitpy/developer/api-reference/)
- [User Guide](https://aj-geddes.github.io/revitpy/user/)
- [Contributing](https://aj-geddes.github.io/revitpy/developer/contributing/)

## License

MIT License. See [LICENSE](LICENSE) for details.
