---
layout: default
title: RevitPy Documentation
description: "RevitPy is a modern Python framework for Autodesk Revit development with LINQ-style queries, ORM, async support, IFC, AI agents, and cloud automation."
---

<section class="hero">
    <div class="hero-content">
        <span class="hero-badge">v0.1.0 - Open Source</span>
        <h1 class="hero-title">RevitPy</h1>
        <p class="hero-subtitle">
            A modern Python framework that brings async/await, LINQ-style queries, and comprehensive testing to Autodesk Revit development.
        </p>
        <div class="install-box">
            <code>pip install revitpy</code>
        </div>
        <div class="hero-cta">
            <a href="{{ '/user/getting-started/' | relative_url }}" class="btn btn-primary">Get Started</a>
            <a href="{{ '/developer/api-reference/' | relative_url }}" class="btn btn-secondary">API Reference</a>
        </div>
    </div>
</section>

<div class="container" markdown="1">
<div class="main-content" markdown="1">

## Feature Highlights

<section class="features">
    <div class="features-grid">
        <a href="{{ '/user/features/query-builder/' | relative_url }}" class="feature-card" style="text-decoration:none;color:inherit;">
            <div class="feature-icon">Q</div>
            <h3 class="feature-title">Query Builder</h3>
            <p class="feature-description">LINQ-style fluent queries with filtering, sorting, pagination, and lazy evaluation for Revit elements.</p>
        </a>
        <a href="{{ '/user/features/orm/' | relative_url }}" class="feature-card" style="text-decoration:none;color:inherit;">
            <div class="feature-icon">O</div>
            <h3 class="feature-title">ORM Layer</h3>
            <p class="feature-description">Object-relational mapping with change tracking, caching, relationships, and Pydantic-based validation models.</p>
        </a>
        <a href="{{ '/user/features/events/' | relative_url }}" class="feature-card" style="text-decoration:none;color:inherit;">
            <div class="feature-icon">E</div>
            <h3 class="feature-title">Event System</h3>
            <p class="feature-description">Decorator-based event handlers with priority levels, filtering, throttling, and async dispatch.</p>
        </a>
        <div class="feature-card">
            <div class="feature-icon">X</div>
            <h3 class="feature-title">Extensions</h3>
            <p class="feature-description">Plugin architecture with lifecycle management, dependency injection, and decorator-based registration of commands, services, and tools.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">A</div>
            <h3 class="feature-title">Async Support</h3>
            <p class="feature-description">Native async/await for Revit operations with task queues, progress reporting, and cancellation tokens.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">T</div>
            <h3 class="feature-title">Testing</h3>
            <p class="feature-description">Mock Revit environment with MockDocument, MockElement, and MockApplication for testing without a Revit installation.</p>
        </div>
        <a href="{{ '/user/features/extract/' | relative_url }}" class="feature-card" style="text-decoration:none;color:inherit;">
            <div class="feature-icon">Q</div>
            <h3 class="feature-title">Quantity Extraction</h3>
            <p class="feature-description">Quantity takeoff engine with material aggregation, cost estimation, and multi-format data export for BIM workflows.</p>
        </a>
        <a href="{{ '/user/features/ifc/' | relative_url }}" class="feature-card" style="text-decoration:none;color:inherit;">
            <div class="feature-icon">I</div>
            <h3 class="feature-title">IFC Interop</h3>
            <p class="feature-description">IFC export/import with element mapping, IDS validation, BCF issue tracking, and model diff capabilities.</p>
        </a>
        <a href="{{ '/user/features/ai/' | relative_url }}" class="feature-card" style="text-decoration:none;color:inherit;">
            <div class="feature-icon">M</div>
            <h3 class="feature-title">AI & MCP</h3>
            <p class="feature-description">Model Context Protocol server with tool registration, safety guardrails, and prompt templates for AI-assisted workflows.</p>
        </a>
        <a href="{{ '/user/features/sustainability/' | relative_url }}" class="feature-card" style="text-decoration:none;color:inherit;">
            <div class="feature-icon">S</div>
            <h3 class="feature-title">Sustainability</h3>
            <p class="feature-description">Embodied carbon calculations, EPD database integration, compliance checking, and sustainability reporting.</p>
        </a>
        <a href="{{ '/user/features/interop/' | relative_url }}" class="feature-card" style="text-decoration:none;color:inherit;">
            <div class="feature-icon">P</div>
            <h3 class="feature-title">Speckle Interop</h3>
            <p class="feature-description">Speckle connector with type mapping, diff, merge, and real-time subscriptions for collaborative BIM data exchange.</p>
        </a>
        <a href="{{ '/user/features/cloud/' | relative_url }}" class="feature-card" style="text-decoration:none;color:inherit;">
            <div class="feature-icon">C</div>
            <h3 class="feature-title">Cloud Automation</h3>
            <p class="feature-description">APS Design Automation integration with batch processing, cloud job orchestration, and CI/CD pipeline helpers.</p>
        </a>
    </div>
</section>

## Code Example

Query Revit elements and modify them inside a transaction:

```python
from revitpy import RevitAPI

# Connect to Revit
api = RevitAPI()
api.connect()

# Query walls using the fluent query builder
walls = (api.query("Wall")
         .where("Height", "greater_than", 10.0)
         .order_by("Name")
         .take(50)
         .execute())

# Modify elements inside a transaction
with api.transaction("Update Wall Comments") as txn:
    for wall in walls:
        wall.set_parameter_value("Comments", "Reviewed")
```

### Async Operations

```python
from revitpy import AsyncRevit

async def process_elements():
    revit = AsyncRevit()
    await revit.initialize()

    # Query elements asynchronously
    elements = await revit.query_elements_async(
        element_type="Window"
    )

    # Batch process with progress tracking
    async with revit.progress_scope(len(elements), "Updating windows"):
        await revit.update_elements_async(elements)
```

### Mock Testing

```python
from revitpy import MockRevit

# Create a mock Revit environment -- no Revit installation needed
mock = MockRevit()
doc = mock.create_document("TestProject.rvt")

# Create test elements with parameters
wall = mock.create_element(
    name="Wall-01",
    category="Walls",
    element_type="Wall",
    parameters={"Height": 12.0, "Comments": ""}
)

assert wall.HasParameter("Height")
assert doc.GetElementCount() == 1
```

## Documentation Tiers

<div class="tier-cards">
    <a href="{{ '/developer/' | relative_url }}" class="tier-card">
        <h3>Developer Guide</h3>
        <p>Architecture, API reference, setup instructions, testing strategies, and contribution guidelines for framework developers.</p>
    </a>
    <a href="{{ '/technical/' | relative_url }}" class="tier-card">
        <h3>Technical Reference</h3>
        <p>System design, data models, and internal details for understanding how RevitPy works under the hood.</p>
    </a>
    <a href="{{ '/user/' | relative_url }}" class="tier-card">
        <h3>User Guide</h3>
        <p>Getting started tutorials, feature walkthroughs for the query builder, ORM, and event system.</p>
    </a>
</div>

## Component Overview

| Component | Module | Purpose |
|-----------|--------|---------|
| **Core API** | `revitpy.api` | RevitAPI wrapper, Element, Transaction, QueryBuilder, exceptions |
| **ORM** | `revitpy.orm` | RevitContext, change tracking, caching, relationships, validation models |
| **Events** | `revitpy.events` | EventManager, event types, decorator-based handlers |
| **Extensions** | `revitpy.extensions` | Extension lifecycle, ExtensionManager, decorator registration |
| **Async** | `revitpy.async_support` | AsyncRevit, TaskQueue, ProgressReporter, CancellationToken |
| **Testing** | `revitpy.testing` | MockRevit, MockDocument, MockElement, MockApplication |
| **Performance** | `revitpy.performance` | PerformanceOptimizer, BenchmarkSuite, MemoryManager |
| **Config** | `revitpy.config` | Config, ConfigManager |
| **Extract** | `revitpy.extract` | Quantity takeoff, material aggregation, cost estimation, data export |
| **IFC** | `revitpy.ifc` | IFC export/import, element mapping, IDS validation, BCF, diff |
| **AI** | `revitpy.ai` | MCP server, tool registration, safety guardrails, prompt templates |
| **Sustainability** | `revitpy.sustainability` | Carbon calculations, EPD database, compliance checking, reports |
| **Interop** | `revitpy.interop` | Speckle sync, type mapping, diff, merge, real-time subscriptions |
| **Cloud** | `revitpy.cloud` | APS Design Automation, batch processing, CI/CD helpers |

## Community and Support

- **GitHub**: [Issues](https://github.com/aj-geddes/revitpy/issues) for bug reports and feature requests
- **Discussions**: [GitHub Discussions](https://github.com/aj-geddes/revitpy/discussions) for community chat
- **Contributing**: See the [Contributing Guide]({{ '/developer/contributing/' | relative_url }})

## License

RevitPy is released under the **MIT License**.

- [MIT License](https://github.com/aj-geddes/revitpy/blob/main/LICENSE)
- [Repository](https://github.com/aj-geddes/revitpy)

---

<section class="cta-section">
    <div class="cta-container">
        <h2 class="cta-title">Ready to Get Started?</h2>
        <p class="cta-description">Install RevitPy and start building modern Revit extensions with Python.</p>
        <a href="{{ '/user/getting-started/' | relative_url }}" class="btn btn-primary">Install RevitPy</a>
    </div>
</section>

</div>
</div>
