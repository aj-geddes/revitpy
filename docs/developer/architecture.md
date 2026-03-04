---
layout: page
title: Architecture Overview
description: Explore the layered architecture of the RevitPy framework with module responsibilities, directory structure, dependency graph, and design patterns.
doc_tier: developer
---

# Architecture Overview

RevitPy is organised as a set of layered Python packages inside the top-level `revitpy/` directory. Each layer has a clear responsibility and a well-defined dependency direction: higher layers depend on lower layers, never the reverse.

## Layer Diagram

```
+-------------------------------------------------------+
|                   User Scripts / Plugins               |
+-------------------------------------------------------+
        |               |               |
        v               v               v
+---------------+ +-----------+ +-------------------+
|  ORM Layer    | |  Events   | |  Extensions       |
| revitpy/orm/  | | revitpy/  | | revitpy/          |
|               | | events/   | | extensions/       |
+-------+-------+ +-----+-----+ +--------+----------+
        |               |                |
        v               v                v
+-------------------------------------------------------+
|               Core API Layer (revitpy/api/)            |
+-------------------------------------------------------+
        |               |               |
        v               v               v
+---------------+ +-----------+ +-------------------+
| Async Support | |Performance| | Testing Utilities |
| revitpy/      | | revitpy/  | | revitpy/testing/  |
| async_support/| |performance|                     |
+---------------+ +-----------+ +-------------------+
        |
        v
+-------------------------------------------------------+
|            Revit Application (via IronPython / .NET)   |
+-------------------------------------------------------+

Domain Modules (depend on Core API):

+----------+ +-----+ +------+ +----------------+ +---------+ +-------+
| Extract  | | IFC | |  AI  | |Sustainability  | | Interop | | Cloud |
| revitpy/ | |revit| |revit | | revitpy/       | | revitpy/| |revitpy|
| extract/ | |py/  | |py/   | | sustainability/| | interop/| |/cloud/|
|          | |ifc/ | |ai/   | |                | |         | |       |
+----------+ +-----+ +------+ +----------------+ +---------+ +-------+
```

## Directory Structure

The following listing reflects the actual contents of the repository. Filenames are taken directly from the source tree.

```
revitpy/
  __init__.py              # Public API: RevitAPI, Element, Transaction,
                           #   AsyncRevit, EventManager, Extension,
                           #   MockRevit, Config, QueryBuilder, ElementSet
  config.py                # Config and ConfigManager classes

  api/
    __init__.py
    wrapper.py             # RevitAPI, RevitDocumentProvider, DocumentInfo
    element.py             # Element, ElementSet, ElementId, ParameterValue,
                           #   ElementProperty, ElementMetaclass
    transaction.py         # Transaction, TransactionGroup, TransactionOptions,
                           #   TransactionStatus, transaction_scope,
                           #   async_transaction_scope, retry_transaction
    query.py               # QueryBuilder (API-level), Query factory,
                           #   FilterCriteria, FilterOperator, SortCriteria
    exceptions.py          # RevitAPIError, TransactionError,
                           #   ElementNotFoundError, ValidationError,
                           #   PermissionError, ModelError, ConnectionError

  orm/
    __init__.py
    context.py             # RevitContext, ContextConfiguration,
                           #   create_context, create_async_context
    query_builder.py       # ORM QueryBuilder (lazy evaluation, async,
                           #   query plans, streaming), LazyQueryExecutor,
                           #   QueryPlan, StreamingQuery
    element_set.py         # ORM-level ElementSet
    cache.py               # CacheManager, CacheConfiguration
    change_tracker.py      # ChangeTracker
    relationships.py       # RelationshipManager
    async_support.py       # AsyncRevitContext
    validation.py          # WallElement, RoomElement, validation rules
    decorators.py          # ORM decorators
    types.py               # CachePolicy, ElementState, LoadStrategy,
                           #   QueryMode, IElementProvider, IUnitOfWork,
                           #   IQueryable, IAsyncQueryable, type aliases
    exceptions.py          # ORMException, QueryError, RelationshipError

  events/
    __init__.py
    manager.py             # EventManager
    handlers.py            # Event handler base classes
    dispatcher.py          # Event dispatching logic
    decorators.py          # @event_handler and related decorators
    filters.py             # Event filtering
    types.py               # Event type definitions

  extensions/
    __init__.py
    extension.py           # Extension base class
    manager.py             # ExtensionManager
    loader.py              # Extension loading
    registry.py            # Extension registry
    lifecycle.py           # Extension lifecycle management
    dependency_injection.py# DI container for extensions
    decorators.py          # Extension decorators

  async_support/
    __init__.py
    async_revit.py         # AsyncRevit
    decorators.py          # @async_transaction and related decorators
    context_managers.py    # Async context managers
    task_queue.py          # Task queue for async operations
    cancellation.py        # Cancellation token support
    progress.py            # Async progress reporting

  performance/
    __init__.py
    monitoring.py          # Performance monitoring
    optimizer.py           # Query and operation optimiser
    benchmarks.py          # Benchmarking utilities
    memory.py              # Memory profiling utilities

  testing/
    __init__.py            # Exports: MockRevit, MockDocument,
                           #   MockElement, MockApplication
    mock_revit.py          # MockRevit, MockApplication, MockDocument,
                           #   MockElement, MockTransaction, MockParameter,
                           #   MockElementId

  extract/
    __init__.py
    engine.py              # QuantityEngine, TakeoffConfig
    materials.py           # MaterialAggregator, MaterialReport
    cost.py                # CostEstimator, RateTable
    export.py              # DataExporter (CSV, Excel, JSON)

  ifc/
    __init__.py
    exporter.py            # IFCExporter, ExportConfig
    importer.py            # IFCImporter, ImportMapping
    mapper.py              # ElementMapper, TypeMapping
    ids.py                 # IDSValidator, IDSSpecification
    bcf.py                 # BCFManager, BCFIssue, BCFViewpoint
    diff.py                # IFCDiff, ChangeSet

  ai/
    __init__.py
    server.py              # MCPServer, ServerConfig
    tools.py               # ToolRegistry, tool decorator
    guardrails.py          # SafetyGuardrails, PermissionPolicy
    prompts.py             # PromptTemplate, PromptLibrary

  sustainability/
    __init__.py
    carbon.py              # CarbonCalculator, CarbonResult
    epd.py                 # EPDDatabase, EPDRecord
    compliance.py          # ComplianceChecker, Standard
    reports.py             # SustainabilityReport, ReportConfig

  interop/
    __init__.py
    connector.py           # SpeckleConnector, ConnectionConfig
    mapper.py              # TypeMapper, ObjectConverter
    diff.py                # SpeckleDiff, MergeStrategy
    subscriptions.py       # StreamSubscription, RealtimeSync

  cloud/
    __init__.py
    automation.py          # DesignAutomation, JobConfig
    batch.py               # BatchProcessor, BatchJob
    cicd.py                # CICDHelper, PipelineConfig
```

## Module Responsibilities

### Core API Layer (`revitpy/api/`)

The lowest application-level layer. It wraps the Revit .NET API behind Python protocols and provides:

- **`RevitAPI`** (`wrapper.py`) -- main entry point. Manages connection lifecycle (`connect` / `disconnect`), document operations (`open_document`, `create_document`, `save_document`, `close_document`), and serves as a factory for queries and transactions. Uses `weakref`-based document caching.
- **`Element`** (`element.py`) -- Pythonic element wrapper with parameter caching, change tracking (`is_dirty`, `changes`, `save_changes`, `discard_changes`), and automatic type conversion between Revit and Python types. Uses a custom metaclass (`ElementMetaclass`) for property registration.
- **`ElementSet`** (`element.py`) -- generic collection with LINQ-style operations (`where`, `select`, `first`, `single`, `any`, `all`, `order_by`, `group_by`) and lazy evaluation.
- **`Transaction` / `TransactionGroup`** (`transaction.py`) -- context-manager-based transaction wrappers supporting both sync and async usage, commit/rollback handlers, operation batching, and retry logic via the `retry_transaction` helper.
- **`QueryBuilder`** (`query.py`) -- fluent query interface with filter operators (`EQUALS`, `CONTAINS`, `REGEX`, etc.), sorting, pagination (`skip` / `take`), and distinct.
- **Exceptions** (`exceptions.py`) -- hierarchy rooted at `RevitAPIError` with specialised subclasses: `TransactionError`, `ElementNotFoundError`, `ValidationError`, `PermissionError`, `ModelError`, `ConnectionError`.

Protocols (`IRevitApplication`, `IRevitDocument`, `IRevitElement`, `IElementProvider`, `ITransactionProvider`) decouple the framework from the concrete Revit runtime, making testing possible without Revit installed.

### ORM Layer (`revitpy/orm/`)

A higher-level layer on top of the core API, inspired by Entity Framework patterns:

- **`RevitContext`** (`context.py`) -- orchestrates querying, change tracking, caching, and relationships. Supports thread-safe mode, configurable cache policies (`CachePolicy.MEMORY`, `CachePolicy.NONE`), and an async facade via `as_async()`. Acts as a Unit of Work: `save_changes()` commits all tracked changes; `reject_changes()` discards them. Disposable via context manager.
- **ORM `QueryBuilder`** (`query_builder.py`) -- enhanced query builder with `QueryPlan`-based optimization (filters reordered before projections), lazy evaluation through generator chains, query-result caching (keyed by MD5 hash of the plan), async execution (`to_list_async`, `first_async`, `count_async`), and streaming support via `StreamingQuery`.
- **`CacheManager`** / **`ChangeTracker`** / **`RelationshipManager`** -- internal components for caching, dirty-tracking, and navigating entity relationships.

### Events System (`revitpy/events/`)

Publish-subscribe event system. The `EventManager` class is exported from the top-level package. The `@event_handler` decorator registers handler functions. Includes event filtering and a dispatcher.

### Extensions Framework (`revitpy/extensions/`)

Plugin architecture. The `Extension` base class defines the extension contract; `ExtensionManager` handles discovery, loading, lifecycle, and dependency injection.

### Async Support (`revitpy/async_support/`)

Wraps Revit operations for use with `async`/`await`. `AsyncRevit` is the main class. Includes decorators (e.g., `@async_transaction`), a task queue, cancellation tokens, and progress reporting.

### Performance Module (`revitpy/performance/`)

Monitoring, benchmarking, memory profiling, and an optimiser. Used internally by the ORM query engine and available for user scripts.

### Testing Utilities (`revitpy/testing/`)

`MockRevit` provides a complete mock Revit environment (application, documents, elements, transactions, parameters) so that tests run without an actual Revit installation. Exported at the top level for user test suites.

### Configuration (`revitpy/config.py`)

`Config` is a dictionary-backed configuration container with attribute access. `ConfigManager` loads YAML files and exposes the active config.

### Quantity Extraction (`revitpy/extract/`)

Quantity takeoff engine for BIM data extraction. Provides material aggregation pipelines, cost estimation with configurable rate tables, and multi-format data export (CSV, Excel, JSON). Designed for integration into automated quantity surveying workflows.

### IFC Interop (`revitpy/ifc/`)

IFC import/export layer with bidirectional element mapping between Revit and IFC entities. Includes IDS (Information Delivery Specification) validation, BCF (BIM Collaboration Format) issue tracking, and model diff capabilities for detecting changes between IFC versions.

### AI & MCP Server (`revitpy/ai/`)

Model Context Protocol server that exposes RevitPy operations as AI-callable tools. Provides a tool registration API, safety guardrails for destructive operations, and prompt templates for common Revit automation tasks. Enables AI-assisted BIM workflows through structured tool invocation.

### Sustainability (`revitpy/sustainability/`)

Embodied carbon calculation engine with EPD (Environmental Product Declaration) database integration. Supports compliance checking against standards (EN 15978, LEED, BREEAM) and generates sustainability reports with material-level carbon breakdowns.

### Speckle Interop (`revitpy/interop/`)

Speckle connector for collaborative BIM data exchange. Handles type mapping between RevitPy elements and Speckle objects, diff and merge operations for model synchronisation, and real-time subscriptions for live updates from Speckle streams.

### Cloud Automation (`revitpy/cloud/`)

APS (Autodesk Platform Services) Design Automation integration for headless Revit processing. Includes batch job orchestration, cloud-based model processing pipelines, and CI/CD helper utilities for automated build-and-check workflows.

## Dependency Graph

Arrows point from dependent to dependency.

```
revitpy/__init__.py
    |
    +---> revitpy/api/  (RevitAPI, Element, Transaction)
    +---> revitpy/orm/  (QueryBuilder, ElementSet)
    +---> revitpy/events/  (EventManager, event_handler)
    +---> revitpy/extensions/  (ExtensionManager, Extension)
    +---> revitpy/async_support/  (AsyncRevit, async_transaction)
    +---> revitpy/testing/  (MockRevit)
    +---> revitpy/config.py  (Config, ConfigManager)

revitpy/orm/ ---> revitpy/api/  (uses Element, ElementSet protocols)
revitpy/events/ ---> revitpy/api/  (event types reference API objects)
revitpy/extensions/ ---> revitpy/api/  (extensions operate on API objects)
revitpy/async_support/ ---> revitpy/api/  (wraps synchronous API)
revitpy/testing/ ---> (standalone; no internal dependencies)
revitpy/performance/ ---> (standalone utilities)
revitpy/extract/ ---> revitpy/api/  (reads element parameters for takeoff)
revitpy/ifc/ ---> revitpy/api/  (maps Element to IFC entities)
revitpy/ai/ ---> revitpy/api/  (exposes API operations as MCP tools)
revitpy/sustainability/ ---> revitpy/extract/  (uses material data for carbon calc)
revitpy/interop/ ---> revitpy/api/  (converts Element to Speckle objects)
revitpy/cloud/ ---> revitpy/api/  (orchestrates headless Revit jobs)
```

## Third-Party Dependencies

All runtime dependencies are declared in `pyproject.toml`:

| Package | Minimum version | Purpose |
|---|---|---|
| pydantic | >= 2.0.0 | Data validation (e.g., `ParameterValue`) |
| typing-extensions | >= 4.0.0 | Backported type hints |
| asyncio-mqtt | >= 0.11.0 | MQTT-based messaging |
| aiofiles | >= 23.0.0 | Async file I/O |
| loguru | >= 0.7.0 | Logging throughout the framework |
| httpx | >= 0.24.0 | HTTP client |
| websockets | >= 11.0.0 | WebSocket support |
| pyyaml | >= 6.0.0 | YAML configuration loading |
| click | >= 8.0.0 | CLI (`revitpy` entry point) |
| rich | >= 13.0.0 | Rich terminal output |
| jinja2 | >= 3.0.0 | Template rendering |
