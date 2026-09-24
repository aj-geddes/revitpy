---
layout: page
title: Development Setup
description: Set up a local development environment for contributing to RevitPy. Covers Python prerequisites, pip installation, pre-commit hooks, and tool config.
doc_tier: developer
---

This guide walks through setting up a local development environment for RevitPy.

## Prerequisites

- **Python 3.11, 3.12 or 3.13.** `pyproject.toml` specifies `requires-python = ">=3.11"`. CI tests 3.11, 3.12 and 3.13.
- **Git.**
- **pip** (bundled with Python).
- *Optional, for the Revit add-in:* the **.NET SDK 10.x**, which can build every add-in target (net48, net8.0-windows, net10.0-windows) on Windows or Linux.
- *Optional, for the docs site:* Ruby with Bundler (Jekyll / GitHub Pages).

No Revit installation is required for Python development or testing. The `revitpy.testing` module provides `MockRevit`, `MockDocument`, `MockElement` and `MockApplication`, which simulate the Revit environment. Running against a live model needs Windows, Revit 2024–2027 and the add-in (see [Getting Started]({{ '/user/getting-started/' | relative_url }})).

## Clone and Install

```bash
git clone https://github.com/aj-geddes/revitpy.git
cd revitpy
pip install -e ".[dev]"
```

The `[dev]` extra installs everything needed for development:

| Package | Minimum version | Purpose |
|---|---|---|
| pytest | >= 7.0.0 | Test runner |
| pytest-asyncio | >= 0.23.0 | Async test support |
| pytest-cov | >= 4.0.0 | Coverage reporting |
| pytest-mock | >= 3.10.0 | Mocking utilities |
| mypy | >= 1.10.0 | Static type checking |
| ruff | >= 0.15.4 | Linting and formatting |
| pre-commit | >= 3.0.0 | Git hook management |
| psutil | >= 5.9.0 | Optional memory metrics in `revitpy.performance`; used by test fixtures |

Optional integration extras:

- **`ifc`**: `ifcopenshell>=0.8.0`, `ifctester>=0.8.0`, `defusedxml>=0.7.1`
- **`interop`**: `specklepy>=3.0.0`. This pulls in `gql`, which pins `websockets<12`.
- **`all`**: both of the above

```bash
pip install -e ".[dev,all]"   # what the "optional integrations" CI job installs
```

Tests for IFC and Speckle are skipped automatically when those packages are missing. There is no `docs` extra: the documentation site is Jekyll (see [Documentation Site](#documentation-site)).

## Running Tests

Tests live under `tests/`. The pytest configuration is in `pyproject.toml` (there is no `pytest.ini`):

```toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q --strict-markers --strict-config -m 'not slow'"
testpaths = ["tests"]
asyncio_mode = "auto"
# markers = [...]  slow, integration, unit, performance, benchmark, security, ...
```

Run the default suite. Slow stress tests are excluded by the `-m 'not slow'` in `addopts`:

```bash
pytest
```

Run the slow tests. A `-m` on the command line overrides the default:

```bash
pytest -m slow
pytest -m "slow or not slow"   # everything
```

Other useful selections:

```bash
pytest tests/api tests/revit   # core API + live-Revit adapter tests (mocked pythonnet)
pytest tests/orm -q --tb=short
pytest -m performance
pytest --cov=revitpy --cov-report=term-missing
```

Coverage is configured in `pyproject.toml` under `[tool.coverage.run]` with `source = ["revitpy"]` and `branch = true`.

## Building the Revit Add-in

`src/RevitPy.Addin` is the only C# project that is built (`RevitPy.sln` contains just this project). Build one Revit version at a time:

```bash
dotnet build src/RevitPy.Addin/RevitPy.Addin.csproj -c Release -p:RevitVersion=2024   # net48
dotnet build src/RevitPy.Addin/RevitPy.Addin.csproj -c Release -p:RevitVersion=2025   # net8.0-windows
dotnet build src/RevitPy.Addin/RevitPy.Addin.csproj -c Release -p:RevitVersion=2026   # net8.0-windows
dotnet build src/RevitPy.Addin/RevitPy.Addin.csproj -c Release -p:RevitVersion=2027   # net10.0-windows
```

Output goes to `src/RevitPy.Addin/bin/Release/<RevitVersion>/`. The Revit API reference assemblies come from the `Nice3point.Revit.Api.*` NuGet packages, and `EnableWindowsTargeting` is set, so the build also works on Linux (CI builds all four versions on `ubuntu-latest`). Warnings are treated as errors.

To install on a Windows machine with Revit (build, copy to `%APPDATA%\Autodesk\Revit\Addins\<version>\`, and optionally write `%APPDATA%\RevitPy\settings.ini`):

```powershell
./scripts/install-addin.ps1 -RevitVersion 2025
```

See the script for its other parameters. Then install `revitpy` into the Python environment that the add-in loads (`pip install -e .` into a venv, and point `python_path` at its `site-packages`).

`RevitPy.Addin` is the only C# project.

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

hatch-vcs derives the version from Git tags. `revitpy.__version__` reads the installed distribution's metadata and falls back to `"0.0.0+unknown"` when you run from a source tree that isn't installed. `revitpy version` prints it.

## CLI Entry Point

The project registers a CLI entry point:

```toml
[project.scripts]
revitpy = "revitpy.cli:main"
```

After installing the package, the `revitpy` command is available on the PATH:

```bash
revitpy version
revitpy doctor          # add --json for machine-readable output
revitpy mcp-serve --host 127.0.0.1 --port 8765 --token "$REVITPY_MCP_TOKEN"
```

## Documentation Site

The docs in `docs/` are a Jekyll site published with GitHub Pages at `https://aj-geddes.github.io/revitpy/`. To preview locally:

```bash
cd docs
bundle install
bundle exec jekyll serve   # http://localhost:4000/revitpy/
```

Keep each page's front matter (`layout`, `title`, `description`, `doc_tier`) intact. `ruff format` is configured to skip Markdown files.
