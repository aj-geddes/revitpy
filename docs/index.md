---
layout: default
title: RevitPy Documentation
description: Modern Python Framework for Revit Development
---

<section class="hero">
    <div class="hero-content">
        <span class="hero-badge">v1.0.0 - Enterprise Ready</span>
        <h1 class="hero-title">RevitPy</h1>
        <p class="hero-subtitle">
            The modern, enterprise-ready Python framework that transforms how you develop, deploy, and manage extensions for Autodesk Revit.
        </p>
        <div class="hero-cta">
            <a href="{{ '/getting-started/' | relative_url }}" class="btn btn-primary">Get Started</a>
            <a href="{{ '/examples/' | relative_url }}" class="btn btn-secondary">View Examples</a>
        </div>
    </div>
</section>

<div class="container" markdown="1">
<div class="main-content" markdown="1">

## What is RevitPy?

RevitPy is a comprehensive Python framework designed to modernize Revit automation development. Built on Python 3.11+ with enterprise-grade architecture, RevitPy provides developers with intuitive APIs, advanced ORM capabilities, and professional-grade tooling that makes Revit development productive, maintainable, and scalable.

## Key Features

<section class="features">
    <div class="features-grid">
        <div class="feature-card">
            <div class="feature-icon">&#128640;</div>
            <h3 class="feature-title">Modern Python</h3>
            <p class="feature-description">Python 3.11+ with full async/await support, type annotations, and the latest language features.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">&#128269;</div>
            <h3 class="feature-title">Intuitive ORM</h3>
            <p class="feature-description">LINQ-style queries for Revit elements with relationship navigation and intelligent caching.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">&#9889;</div>
            <h3 class="feature-title">Hot Reload</h3>
            <p class="feature-description">Instant code updates during development without restarting Revit.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">&#128187;</div>
            <h3 class="feature-title">VS Code Integration</h3>
            <p class="feature-description">Full IntelliSense, debugging, and project management in Visual Studio Code.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">&#128274;</div>
            <h3 class="feature-title">Type Safety</h3>
            <p class="feature-description">Complete type annotations for improved code quality and IDE support.</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">&#127970;</div>
            <h3 class="feature-title">Enterprise Ready</h3>
            <p class="feature-description">MSI installer, Group Policy support, security scanning, and audit capabilities.</p>
        </div>
    </div>
</section>

## Quick Start

Get up and running in minutes:

```bash
# Install RevitPy
pip install revitpy

# Configure Revit integration
revitpy doctor --install

# Create your first project
revitpy create my-first-script --template basic-script
cd my-first-script

# Run in development mode
revitpy dev --watch
```

## Code Example

Query elements with modern ORM syntax:

```python
from revitpy import RevitContext

# Query walls with modern ORM syntax
with RevitContext() as context:
    walls = context.elements.where(
        lambda e: e.Category == 'Walls' and e.Height > 10.0
    )

    for wall in walls:
        print(f"Wall: {wall.Name}, Height: {wall.Height}")
```

### Advanced Filtering with Relationships

```python
from revitpy import RevitContext

with RevitContext() as context:
    # Find rooms with specific area requirements
    large_rooms = (context.elements
                   .of_category('Rooms')
                   .where(lambda r: r.Area > 500)
                   .include('Boundaries.Wall')
                   .to_list())

    for room in large_rooms:
        wall_count = len(room.Boundaries)
        print(f"Room {room.Name}: {room.Area} sq ft, {wall_count} walls")
```

### Async Operations

```python
import asyncio
from revitpy import AsyncRevitContext

async def process_elements():
    async with AsyncRevitContext() as context:
        # Process large datasets asynchronously
        elements = await context.elements.where(
            lambda e: e.Category == 'Windows'
        ).to_list_async()

        tasks = [update_element(elem) for elem in elements]
        results = await asyncio.gather(*tasks)
        return results

async def update_element(element):
    await asyncio.sleep(0.1)
    return f"Processed {element.Name}"
```

## Component Overview

| Component | Purpose | Key Features |
|-----------|---------|--------------|
| **Core API** | Primary developer interface | Element access, transactions, utilities |
| **ORM Layer** | Object-relational mapping | LINQ-style queries, relationships, caching |
| **Extension System** | Plugin architecture | Dependency injection, lifecycle management |
| **Async Support** | Asynchronous operations | Progress tracking, cancellation, task queues |
| **.NET Bridge** | Python-Revit interop | Type conversion, memory management, error handling |
| **Package Manager** | Distribution system | Secure packages, dependency resolution |
| **VS Code Extension** | Development environment | IntelliSense, debugging, project management |

## What Makes RevitPy Different?

### From PyRevit
- **Modern Python**: Python 3.11+ vs IronPython 2.7
- **Type Safety**: Full type annotations and IntelliSense support
- **ORM Queries**: LINQ-style syntax vs manual element collection
- **Async Support**: Native async/await vs synchronous only
- **Package Management**: Secure distribution vs manual file copying
- **Enterprise Ready**: MSI installer, security, monitoring vs basic deployment

### From Dynamo
- **Full Python**: Complete Python ecosystem vs limited nodes
- **Professional IDE**: VS Code integration vs visual scripting
- **Version Control**: Git-friendly text files vs binary graphs
- **Debugging**: Full debugger support vs limited error messages
- **Team Collaboration**: Standard development practices vs sharing graphs

### From RevitPythonShell
- **Modern Runtime**: Python 3.11+ vs Python 2.7/3.x
- **Framework Features**: ORM, extensions, async vs basic shell
- **Development Tools**: Full IDE integration vs simple console
- **Package Management**: Secure packages vs manual installation
- **Enterprise Support**: Professional deployment vs individual setup

## Performance Benchmarks

RevitPy delivers significant performance improvements over traditional approaches:

| Operation | PyRevit | RevitPy | Improvement |
|-----------|---------|---------|-------------|
| Element Query (1000 elements) | 450ms | 120ms | **3.8x faster** |
| Parameter Access | 25ms | 8ms | **3.1x faster** |
| Bulk Updates (500 elements) | 2.1s | 650ms | **3.2x faster** |
| Memory Usage (large model) | 245MB | 89MB | **2.8x less** |
| Startup Time | 850ms | 280ms | **3.0x faster** |

*Benchmarks performed on Revit 2024, Intel i7-12700K, 32GB RAM*

## Quick Navigation

<div class="examples-grid">
    <a href="{{ '/getting-started/' | relative_url }}" class="example-card">
        <div class="example-icon">&#128337;</div>
        <h3 class="example-title">Get Started</h3>
        <p class="example-description">Install RevitPy and create your first script in under 5 minutes.</p>
    </a>
    <a href="{{ '/examples/' | relative_url }}" class="example-card">
        <div class="example-icon">&#128214;</div>
        <h3 class="example-title">Examples</h3>
        <p class="example-description">Real-world examples covering energy analysis, ML, IoT, and more.</p>
    </a>
    <a href="{{ '/pyrevit-integration/' | relative_url }}" class="example-card">
        <div class="example-icon">&#128279;</div>
        <h3 class="example-title">PyRevit Integration</h3>
        <p class="example-description">Migrate from PyRevit with side-by-side code comparisons.</p>
    </a>
    <a href="{{ '/documentation/' | relative_url }}" class="example-card">
        <div class="example-icon">&#128218;</div>
        <h3 class="example-title">API Reference</h3>
        <p class="example-description">Complete API documentation with examples and type information.</p>
    </a>
</div>

## Community & Support

### Get Help & Connect
- **GitHub**: [Issues](https://github.com/aj-geddes/revitpy/issues) for bug reports and feature requests
- **Discussions**: [GitHub Discussions](https://github.com/aj-geddes/revitpy/discussions) for community chat
- **Documentation**: Complete guides, tutorials, and API reference

### Contributing

RevitPy is an open-source project that thrives on community contributions. Whether you're fixing bugs, adding features, improving documentation, or sharing packages, we welcome your involvement!

<div style="margin-top: var(--space-6);">
    <a href="https://github.com/aj-geddes/revitpy/blob/main/CONTRIBUTING.md" class="btn btn-outline">Start Contributing</a>
</div>

## License

RevitPy Framework is released under the **MIT License**, enabling both personal and commercial use.

- **Open Source License**: [MIT License](https://github.com/aj-geddes/revitpy/blob/main/LICENSE)
- **Repository**: [github.com/aj-geddes/revitpy](https://github.com/aj-geddes/revitpy)

---

<section class="cta-section">
    <div class="cta-container">
        <h2 class="cta-title">Ready to Get Started?</h2>
        <p class="cta-description">Transform your Revit development experience with modern Python, enterprise architecture, and professional tooling.</p>
        <a href="{{ '/getting-started/' | relative_url }}" class="btn btn-primary">Install RevitPy</a>
    </div>
</section>

    </div>
</div>
