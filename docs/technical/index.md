---
layout: page
title: Technical Documentation
description: In-depth technical documentation for software architects and integrators working with RevitPy internals, system design, data models, and infrastructure.
doc_tier: technical
---

# Technical Documentation

This section provides in-depth technical documentation for software architects, system integrators, and senior developers who need to understand RevitPy's internal design, data model, performance characteristics, and security posture.

These documents are derived directly from the source code and reflect the current implementation.

## Contents

| Document | Description |
|---|---|
| [System Design](system-design.md) | Component architecture, design patterns, module dependencies, and technology stack. |
| [Data Model](data-model.md) | ORM entity types, Pydantic validation rules, caching, change tracking, relationships, and query execution. |
| [Performance](performance.md) | Performance targets, optimization strategies, caching architecture, benchmarking framework, and memory management. |
| [Security](security.md) | Input validation, security linting, thread safety, error handling, CI security checks, cloud token management, AI safety model, and webhook verification. |
| [Infrastructure](infrastructure.md) | Cloud deployment architecture, APS Design Automation setup, CI/CD pipelines, and container orchestration for headless Revit processing. |

## Audience

- **Architects** evaluating RevitPy for enterprise Revit automation projects.
- **Integrators** building custom extensions on top of the ORM, event system, or API wrapper layers.
- **Contributors** who need to understand cross-cutting concerns before modifying framework internals.

## Source Layout Reference

The primary modules discussed in these documents live under:

```
revitpy/
  api/          # Revit API wrapper, Element, Transaction, Query
  orm/          # ORM context, QueryBuilder, cache, change tracker, relationships, validation
  events/       # Event system: dispatcher, manager, handlers, types
  performance/  # Optimizer, adaptive cache, object pools, benchmark suite
  extract/      # Quantity takeoff, material aggregation, cost estimation
  ifc/          # IFC export/import, element mapping, IDS, BCF, diff
  ai/           # MCP server, tool registration, safety guardrails
  sustainability/ # Carbon calculations, EPD database, compliance
  interop/      # Speckle connector, type mapping, diff, merge
  cloud/        # APS Design Automation, batch processing, CI/CD
```

Configuration and CI definitions are in `pyproject.toml` and `.github/workflows/ci.yml` respectively.
