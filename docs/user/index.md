---
layout: page
title: User Guide
description: Complete user guide for RevitPy, a modern Python framework for Autodesk Revit development. Covers queries, ORM, events, extensions, and async support.
doc_tier: user
---

# RevitPy User Guide

RevitPy is a modern CPython framework for Autodesk Revit development. It provides a Pythonic interface over the Revit API: typed elements, fluent queries and real Revit transactions. On top of that it offers an ORM layer, an event system, an extension framework, async helpers and a mock Revit for testing. It runs inside Revit through the RevitPy add-in or pyRevit's CPython engine.

## Who This Guide Is For

This guide is for Python developers who are building tools, scripts, or plugins for Autodesk Revit. It assumes familiarity with Python 3.11+ and basic knowledge of the Revit application.

## Requirements

- CPython 3.11–3.13 (the add-in can embed 64-bit CPython 3.11–3.14)
- For live models: Windows, Autodesk Revit 2024–2027, and either the RevitPy add-in (`src/RevitPy.Addin`) or pyRevit with a CPython 3.11+ engine
- Not required for development and testing: Revit (use `MockRevit`)

## Guide Contents

- [Getting Started]({{ '/user/getting-started/' | relative_url }}) -- Installation, connecting to Revit (add-in or pyRevit), and your first queries and transactions.
- [Configuration]({{ '/user/configuration/' | relative_url }}) -- Reference for `Config`, `ConfigManager`, `TransactionOptions`, `ContextConfiguration`, `CacheConfiguration`, and `ExtensionManagerConfig`.

### Feature Guides

- [Query Builder]({{ '/user/features/query-builder/' | relative_url }}) -- LINQ-style query builder for filtering, sorting, and paginating Revit elements.
- [ORM]({{ '/user/features/orm/' | relative_url }}) -- The `RevitContext` ORM layer with change tracking, caching, relationships, and async support.
- [Events]({{ '/user/features/events/' | relative_url }}) -- Event system with `EventManager`, decorators, priorities, filters, and async dispatch.
- [Extensions]({{ '/user/features/extensions/' | relative_url }}) -- Extension framework with lifecycle management, decorators, and dependency injection.
- [Async Support]({{ '/user/features/async/' | relative_url }}) -- `AsyncRevit` class, async transactions, background tasks, progress reporting, and cancellation.
- [Testing]({{ '/user/features/testing/' | relative_url }}) -- `MockRevit` environment for testing without a Revit installation.
- [Quantity Extraction]({{ '/user/features/extract/' | relative_url }}) -- Quantity takeoff engine with material aggregation, cost estimation, and data export.
- [IFC Interop]({{ '/user/features/ifc/' | relative_url }}) -- IFC export/import, element mapping, IDS validation, BCF issue tracking, and model diff.
- [AI & MCP Server]({{ '/user/features/ai/' | relative_url }}) -- Model Context Protocol server with tool registration, safety guardrails, and prompt templates.
- [Sustainability]({{ '/user/features/sustainability/' | relative_url }}) -- Embodied carbon calculations, EPD database integration, compliance checking, and reports.
- [Speckle Interop]({{ '/user/features/interop/' | relative_url }}) -- Speckle sync with type mapping, diff, merge, and real-time subscriptions.
- [Cloud Automation]({{ '/user/features/cloud/' | relative_url }}) -- APS Design Automation, batch processing, and CI/CD helpers.

### Reference

- [FAQ]({{ '/user/faq/' | relative_url }}) -- Frequently asked questions about RevitPy.
- [Troubleshooting]({{ '/user/troubleshooting/' | relative_url }}) -- Common errors, exception classes, and how to resolve issues.
