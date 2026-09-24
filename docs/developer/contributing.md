---
layout: page
title: Contributing
description: Learn how to contribute to RevitPy with the fork-and-clone workflow, branch naming conventions, code quality standards, and the full CI/CD pipeline.
doc_tier: developer
---

# Contributing to RevitPy

This guide covers the workflow for contributing code to the RevitPy project.

## Getting Started

1. Fork the repository on GitHub: `https://github.com/aj-geddes/revitpy`
2. Clone your fork:

   ```bash
   git clone https://github.com/<your-username>/revitpy.git
   cd revitpy
   ```

3. Install in development mode:

   ```bash
   pip install -e ".[dev]"
   ```

4. Install pre-commit hooks:

   ```bash
   pre-commit install
   pre-commit install --hook-type pre-push
   ```

## Branch Naming

Create a branch from `main` for your work. Use a descriptive prefix:

| Prefix | Use case |
|---|---|
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `refactor/` | Code restructuring without behaviour change |
| `docs/` | Documentation changes |
| `test/` | Test additions or improvements |
| `chore/` | Build, CI, dependency updates |

Example:

```bash
git checkout -b feature/add-wall-parameter-validation
```

## Making Changes

### Code Quality Tools

All code must pass the following checks before merging. These are enforced both by pre-commit hooks and by CI.

**Ruff linting:**

```bash
ruff check revitpy/ tests/
```

Auto-fix where possible:

```bash
ruff check --fix revitpy/ tests/
```

**Ruff formatting:**

```bash
ruff format --check revitpy/ tests/
```

Apply formatting:

```bash
ruff format revitpy/ tests/
```

**mypy type checking:**

```bash
mypy revitpy
```

**Tests:**

```bash
pytest            # default suite; slow stress tests are excluded
pytest -m slow    # the slow tests, when you touch performance-sensitive code
```

If you changed IFC or Speckle code, install the integrations and run their tests too: `pip install -e ".[dev,all]"`, then `pytest tests/ifc tests/interop`.

**Revit add-in** (only when you change `src/RevitPy.Addin`). This needs the .NET SDK 10.x, which builds every target:

```bash
dotnet build src/RevitPy.Addin/RevitPy.Addin.csproj -c Release -p:RevitVersion=2024
dotnet build src/RevitPy.Addin/RevitPy.Addin.csproj -c Release -p:RevitVersion=2027
```

Warnings are errors. `src/RevitPy.Addin` is the only C# project.

**Docs:** keep `README.md`, `CHANGELOG.md` and `docs/` in sync with behaviour changes. Add an entry under `[Unreleased]` in `CHANGELOG.md`.

### Pre-commit Hooks

If you installed the hooks (see above), these tools run automatically:

- **On commit:** ruff lint (with auto-fix), ruff format, mypy, trailing-whitespace removal, end-of-file newline, YAML validation, large-file check, merge-conflict detection, case-conflict detection, LF line-ending enforcement.
- **On push:** pytest runs the full test suite (`pytest tests/ -x -q --no-header`).

If a hook fails, fix the issue and re-stage your changes before committing again.

## Submitting a Pull Request

1. Push your branch to your fork:

   ```bash
   git push -u origin feature/add-wall-parameter-validation
   ```

2. Open a pull request against the `main` branch of the upstream repository.

3. In the PR description, explain:
   - What the change does and why.
   - How it was tested.
   - Any breaking changes or migration notes.

4. Wait for CI to pass. Address any review feedback.

## CI Pipeline

The CI workflow (`.github/workflows/ci.yml`) runs on every push to `main` and on every pull request targeting `main`:

| Job | Python / platform | Commands |
|---|---|---|
| **Lint** | 3.12 | `ruff check revitpy/ tests/`, `ruff format --check revitpy/ tests/` |
| **Type Check** | 3.11, 3.13 | `mypy revitpy` |
| **Test** | 3.11, 3.12, 3.13 | `pytest tests/ --cov=revitpy` (optional integrations not installed, so those tests skip) |
| **Test with optional integrations** | 3.12 | `pip install -e ".[dev,all]"`, then `pytest tests/` |
| **Security** | 3.12 | `pip-audit --skip-editable`, `ruff check --select S revitpy/ tests/` |
| **Revit add-in** | .NET 10, ubuntu | `dotnet build src/RevitPy.Addin/RevitPy.Addin.csproj -c Release -p:RevitVersion=<2024-2027>`, uploads the DLLs and manifest as artifacts |

The security job audits installed dependencies for known vulnerabilities (`pip-audit`) and runs the Bandit-derived `S` rules from ruff.

All jobs must pass for a pull request to be merge-ready.

## Commit Messages

Write clear, concise commit messages. Use the imperative mood ("Add wall validation" not "Added wall validation"). If the change is non-trivial, include a brief description in the commit body.

## Adding Dependencies

Runtime dependencies are listed under `[project.dependencies]` in `pyproject.toml`. Development dependencies go under `[project.optional-dependencies.dev]`. If you need to add a dependency:

1. Add it to the appropriate section in `pyproject.toml`.
2. Document why the dependency is needed in your PR description.
3. Be aware that CI runs `pip-audit` -- any dependency with a known vulnerability will cause the security job to fail.

## Project Status

RevitPy is at `Development Status :: 3 - Alpha`. The API is not yet stable. Breaking changes may occur between releases. When making changes, consider backward compatibility but prioritise getting the design right.
