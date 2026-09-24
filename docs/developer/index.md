---
layout: page
title: Developer Documentation
description: Comprehensive guide for developers contributing to the RevitPy framework. Covers architecture, development setup, API reference, testing, and code style.
doc_tier: developer
---

This section covers everything needed to contribute to RevitPy: understanding the architecture, setting up a development environment, running tests, and following project conventions.

## Contents

- [Architecture Overview]({{ '/developer/architecture/' | relative_url }}) -- Layered module design, directory structure, and dependency graph.
- [Development Setup]({{ '/developer/setup/' | relative_url }}) -- Prerequisites, installation, and tool configuration.
- [API Reference]({{ '/developer/api-reference/' | relative_url }}) -- Complete API reference for all public classes and methods.
- [Testing Guide]({{ '/developer/testing/' | relative_url }}) -- Test framework, fixtures, mocks, and how to write new tests.
- [Contributing]({{ '/developer/contributing/' | relative_url }}) -- Fork/clone workflow, branch naming, PR process, and CI pipeline.
- [Code Style]({{ '/developer/code-style/' | relative_url }}) -- Ruff rules, mypy settings, naming conventions, and import ordering.

## Project at a Glance

RevitPy is a CPython framework for Autodesk Revit development. It connects to a live Revit session through pythonnet adapters (`revitpy.revit`). Inside Revit it is hosted by a C# add-in (`src/RevitPy.Addin`) or by pyRevit. The package is structured as a layered architecture with a core API wrapper, an ORM layer for LINQ-style querying, an event system, an extensions framework, async support, performance utilities, and a testing toolkit. Six domain modules extend the framework with specialised capabilities: quantity extraction (`revitpy.extract`), IFC interoperability (`revitpy.ifc`), AI/MCP integration (`revitpy.ai`), sustainability analysis (`revitpy.sustainability`), Speckle interoperability (`revitpy.interop`), and cloud automation (`revitpy.cloud`).

Key facts drawn from the codebase:

| Detail | Value |
|---|---|
| Python requirement | >= 3.11 (CI: 3.11, 3.12, 3.13) |
| Revit add-in | `src/RevitPy.Addin`, Revit 2024–2027, built with the .NET SDK |
| Build system | Hatchling with hatch-vcs |
| Version scheme | VCS-based (hatch-vcs) |
| License | MIT |
| Status | Alpha (`Development Status :: 3 - Alpha`) |
| CI | GitHub Actions -- lint, type-check, test, optional-integration tests, security, add-in build |
| Linter / Formatter | Ruff |
| Type checker | mypy |
| Test runner | pytest |

The canonical source of truth for dependencies and tool configuration is `pyproject.toml`.
