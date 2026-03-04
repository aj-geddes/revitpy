---
layout: page
title: Contributing
description: Learn how to contribute to RevitPy with the fork-and-clone workflow, branch naming conventions, code quality standards, and the full CI/CD pipeline.
doc_tier: developer
---

# Contributing to RevitPy

This guide covers the workflow for contributing code to the RevitPy project.

## Getting Started

1. Fork the repository on GitHub: `https://github.com/revitpy/revitpy`
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
pytest tests/orm/ -q --tb=short
```

For the full suite:

```bash
pytest
```

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

The CI workflow (`.github/workflows/ci.yml`) runs on every push to `main` and on every pull request targeting `main`. It consists of four jobs:

### 1. Lint

Runs on Python 3.11 and 3.12.

```
pip install -e ".[dev]"
ruff check revitpy/ tests/
ruff format --check revitpy/ tests/
```

### 2. Type Check

Runs on Python 3.11 and 3.12.

```
pip install -e ".[dev]"
mypy revitpy
```

### 3. Test

Runs on Python 3.11 and 3.12.

```
pip install -e ".[dev]"
pytest tests/orm/ -q --tb=short
```

### 4. Security

Runs on Python 3.12 only.

```
pip install -e ".[dev]" pip-audit
pip-audit
ruff check --select S revitpy/ tests/
```

This job audits installed dependencies for known vulnerabilities (`pip-audit`) and runs the Bandit-derived security rules from ruff (`S` rule set).

All four jobs must pass for a pull request to be merge-ready.

## Commit Messages

Write clear, concise commit messages. Use the imperative mood ("Add wall validation" not "Added wall validation"). If the change is non-trivial, include a brief description in the commit body.

## Adding Dependencies

Runtime dependencies are listed under `[project.dependencies]` in `pyproject.toml`. Development dependencies go under `[project.optional-dependencies.dev]`. If you need to add a dependency:

1. Add it to the appropriate section in `pyproject.toml`.
2. Document why the dependency is needed in your PR description.
3. Be aware that CI runs `pip-audit` -- any dependency with a known vulnerability will cause the security job to fail.

## Project Status

RevitPy is at `Development Status :: 3 - Alpha`. The API is not yet stable. Breaking changes may occur between releases. When making changes, consider backward compatibility but prioritise getting the design right.
