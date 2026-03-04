---
layout: page
title: User Guide
description: Complete user guide for RevitPy, a modern Python framework for Autodesk Revit development. Covers queries, ORM, events, extensions, and async support.
doc_tier: user
---

# RevitPy User Guide

RevitPy is a modern Python framework for Autodesk Revit development. It provides a Pythonic interface over the Revit API with support for async operations, an event system, an ORM layer, an extension framework, and testing utilities.

## Who This Guide Is For

This guide is for Python developers who are building tools, scripts, or plugins for Autodesk Revit. It assumes familiarity with Python 3.11+ and basic knowledge of the Revit application.

## Requirements

- Python 3.11 or later
- Autodesk Revit (for production use; not required for testing with `MockRevit`)

## Guide Contents

- [Getting Started](getting-started) -- Installation, basic setup, and your first queries and transactions.
- [Configuration](configuration) -- Reference for `Config`, `ConfigManager`, `TransactionOptions`, `ContextConfiguration`, `CacheConfiguration`, and `ExtensionManagerConfig`.

### Feature Guides

- [Query Builder](features/query-builder) -- LINQ-style query builder for filtering, sorting, and paginating Revit elements.
- [ORM](features/orm) -- The `RevitContext` ORM layer with change tracking, caching, relationships, and async support.
- [Events](features/events) -- Event system with `EventManager`, decorators, priorities, filters, and async dispatch.
- [Extensions](features/extensions) -- Extension framework with lifecycle management, decorators, and dependency injection.
- [Async Support](features/async) -- `AsyncRevit` class, async transactions, background tasks, progress reporting, and cancellation.
- [Testing](features/testing) -- `MockRevit` environment for testing without a Revit installation.
- [Quantity Extraction](features/extract) -- Quantity takeoff engine with material aggregation, cost estimation, and data export.
- [IFC Interop](features/ifc) -- IFC export/import, element mapping, IDS validation, BCF issue tracking, and model diff.
- [AI & MCP Server](features/ai) -- Model Context Protocol server with tool registration, safety guardrails, and prompt templates.
- [Sustainability](features/sustainability) -- Embodied carbon calculations, EPD database integration, compliance checking, and reports.
- [Speckle Interop](features/interop) -- Speckle sync with type mapping, diff, merge, and real-time subscriptions.
- [Cloud Automation](features/cloud) -- APS Design Automation, batch processing, and CI/CD helpers.

### Reference

- [FAQ](faq) -- Frequently asked questions about RevitPy.
- [Troubleshooting](troubleshooting) -- Common errors, exception classes, and how to resolve issues.
