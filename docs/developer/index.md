---
layout: page
title: Developer Documentation
description: Comprehensive guide for developers contributing to the RevitPy framework. Covers architecture, development setup, API reference, testing, and code style.
doc_tier: developer
---

# Developer Documentation

This section covers everything needed to contribute to RevitPy: understanding the architecture, setting up a development environment, running tests, and following project conventions.

## Contents

- [Architecture Overview](architecture.md) -- Layered module design, directory structure, and dependency graph.
- [Development Setup](setup.md) -- Prerequisites, installation, and tool configuration.
- [API Reference](api-reference.md) -- Complete API reference for all public classes and methods.
- [Testing Guide](testing.md) -- Test framework, fixtures, mocks, and how to write new tests.
- [Contributing](contributing.md) -- Fork/clone workflow, branch naming, PR process, and CI pipeline.
- [Code Style](code-style.md) -- Ruff rules, mypy settings, naming conventions, and import ordering.

## Project at a Glance

RevitPy is a Python framework for Autodesk Revit development. The package is structured as a layered architecture with a core API wrapper, an ORM layer for LINQ-style querying, an event system, an extensions framework, async support, performance utilities, and a testing toolkit. Six domain modules extend the framework with specialised capabilities: quantity extraction (`revitpy.extract`), IFC interoperability (`revitpy.ifc`), AI/MCP integration (`revitpy.ai`), sustainability analysis (`revitpy.sustainability`), Speckle interoperability (`revitpy.interop`), and cloud automation (`revitpy.cloud`).

Key facts drawn from the codebase:

| Detail | Value |
|---|---|
| Python requirement | >= 3.11 |
| Build system | Hatchling with hatch-vcs |
| Version scheme | VCS-based (hatch-vcs) |
| License | MIT |
| Status | Alpha (`Development Status :: 3 - Alpha`) |
| CI | GitHub Actions -- lint, type-check, test, security |
| Linter / Formatter | Ruff |
| Type checker | mypy |
| Test runner | pytest |

The canonical source of truth for dependencies and tool configuration is `pyproject.toml`.
