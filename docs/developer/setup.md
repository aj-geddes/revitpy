---
layout: page
title: Development Setup
description: Set up a local development environment for contributing to RevitPy. Covers Python prerequisites, pip installation, pre-commit hooks, and tool config.
doc_tier: developer
---

# Development Setup

This guide walks through setting up a local development environment for RevitPy.

## Prerequisites

- **Python 3.11 or 3.12.** The project's `pyproject.toml` specifies `requires-python = ">=3.11"`. CI tests against both 3.11 and 3.12.
- **Git.**
- **pip** (bundled with Python).

No Revit installation is required for development or testing. The `revitpy.testing` module provides `MockRevit`, `MockDocument`, `MockElement`, and `MockApplication` classes that simulate the Revit environment.

## Clone and Install

```bash
git clone https://github.com/revitpy/revitpy.git
cd revitpy
pip install -e ".[dev]"
```

The `[dev]` extra installs everything needed for development:

| Package | Minimum version | Purpose |
|---|---|---|
| pytest | >= 7.0.0 | Test runner |
| pytest-asyncio | >= 0.21.0 | Async test support |
| pytest-cov | >= 4.0.0 | Coverage reporting |
| pytest-mock | >= 3.10.0 | Mocking utilities |
| mypy | >= 1.0.0 | Static type checking |
| ruff | >= 0.0.260 | Linting and formatting |
| pre-commit | >= 3.0.0 | Git hook management |
| psutil | >= 5.9.0 | Process/memory utilities for test fixtures |

There are two additional optional extras defined in `pyproject.toml`:

- **`testing`** -- adds `hypothesis >= 6.0.0` and `factory-boy >= 3.2.0` on top of the core test packages.
- **`docs`** -- adds `mkdocs`, `mkdocs-material`, `mkdocstrings[python]`, and `mkdocs-autorefs` for documentation builds.

Install them as needed:

```bash
pip install -e ".[testing]"
pip install -e ".[docs]"
```

## Running Tests

Tests live under the `tests/` directory. The pytest configuration in `pyproject.toml` sets:

```toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q --strict-markers --strict-config"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
```

Run the full suite:

```bash
pytest
```

Run only ORM tests (this is what CI runs):

```bash
pytest tests/orm/ -q --tb=short
```

Run tests by marker (markers are defined in `pyproject.toml` and registered in `tests/conftest.py`):

```bash
pytest -m unit          # Unit tests
pytest -m integration   # Integration tests
pytest -m performance   # Performance / benchmark tests
pytest -m security      # Security tests
pytest -m "not slow"    # Skip slow tests
```

Run with coverage:

```bash
pytest --cov=revitpy --cov-report=term-missing
```

Coverage is configured in `pyproject.toml` under `[tool.coverage.run]` with `source = ["revitpy"]` and `branch = true`.

## Running Linters

### Ruff (linting)

```bash
ruff check revitpy/ tests/
```

To auto-fix issues:

```bash
ruff check --fix revitpy/ tests/
```

### Ruff (formatting)

Check formatting without modifying files:

```bash
ruff format --check revitpy/ tests/
```

Apply formatting:

```bash
ruff format revitpy/ tests/
```

### mypy (type checking)

```bash
mypy revitpy
```

The mypy configuration in `pyproject.toml` targets Python 3.11 with `ignore_missing_imports = true`, `check_untyped_defs = true`, and several other strictness flags. A set of error codes is currently disabled via `disable_error_code` to allow incremental tightening. See `pyproject.toml` section `[tool.mypy]` for the full list.

## Pre-commit Hooks

The project uses [pre-commit](https://pre-commit.com/) to run checks automatically on commit and push. The configuration is in `.pre-commit-config.yaml`.

Install the hooks:

```bash
pre-commit install
pre-commit install --hook-type pre-push
```

What runs on **commit**:

| Hook | Source | What it does |
|---|---|---|
| `ruff` | astral-sh/ruff-pre-commit | Lint with auto-fix, scoped to `revitpy/` and `tests/` |
| `ruff-format` | astral-sh/ruff-pre-commit | Format check, scoped to `revitpy/` and `tests/` |
| `mypy` | pre-commit/mirrors-mypy | Type-check `revitpy/` (with pydantic, types-PyYAML, types-aiofiles stubs) |
| `trailing-whitespace` | pre-commit-hooks | Remove trailing whitespace |
| `end-of-file-fixer` | pre-commit-hooks | Ensure files end with a newline |
| `check-yaml` | pre-commit-hooks | Validate YAML syntax |
| `check-added-large-files` | pre-commit-hooks | Block files larger than 1000 KB |
| `check-merge-conflict` | pre-commit-hooks | Detect merge conflict markers |
| `check-case-conflict` | pre-commit-hooks | Detect case-insensitive filename conflicts |
| `mixed-line-ending` | pre-commit-hooks | Enforce LF line endings |

What runs on **push**:

| Hook | Source | What it does |
|---|---|---|
| `pytest` | local | Run `pytest tests/ -x -q --no-header` |

Run all hooks manually against every file:

```bash
pre-commit run --all-files
```

## Build System

RevitPy uses **Hatchling** as its build backend with **hatch-vcs** for automatic versioning from Git tags:

```toml
[build-system]
requires = ["hatchling", "hatch-vcs"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"
```

The `__version__` in `revitpy/__init__.py` is currently hard-coded to `"0.1.0"`. When building a distribution, hatch-vcs derives the version from Git tags.

## CLI Entry Point

The project registers a CLI entry point:

```toml
[project.scripts]
revitpy = "revitpy.cli:main"
```

After installing the package, the `revitpy` command is available on the PATH.
