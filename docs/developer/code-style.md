---
layout: page
title: Code Style Guide
description: Code style conventions for the RevitPy framework based on ruff and mypy configuration. Covers naming, imports, type annotations, and docstring patterns.
doc_tier: developer
---

# Code Style Guide

RevitPy enforces style through **ruff** (linting and formatting) and **mypy** (type checking). The authoritative configuration lives in `pyproject.toml`. This page summarises the rules and supplements them with conventions observed in the codebase.

## Ruff Configuration

### General Settings

```toml
[tool.ruff]
target-version = "py311"
line-length = 88
extend-exclude = ["cli/templates/"]
```

- Target Python version is **3.11**, so modern syntax (`X | Y` unions, `match` statements, etc.) is acceptable.
- Maximum line length is **88 characters** (the `ruff format` default, matching Black).
- The `cli/templates/` directory is excluded from linting.

### Enabled Rule Sets

```toml
[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort (import sorting)
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "S",   # flake8-bandit (security)
]
```

| Code | Rule set | What it checks |
|---|---|---|
| `E` | pycodestyle | Whitespace, indentation, syntax style |
| `W` | pycodestyle | Style warnings |
| `F` | pyflakes | Unused imports, undefined names, etc. |
| `I` | isort | Import ordering and grouping |
| `B` | flake8-bugbear | Common Python pitfalls |
| `C4` | flake8-comprehensions | Unnecessary list/dict/set comprehension patterns |
| `UP` | pyupgrade | Python version upgrade opportunities |
| `S` | flake8-bandit | Security-related issues |

### Ignored Rules

The following rules are currently suppressed project-wide:

| Code | Reason |
|---|---|
| `E501` | Line length handled by `ruff format` |
| `B008` | Function calls in argument defaults (used intentionally) |
| `C901` | Function complexity (not enforced) |
| `B904` | `raise ... from` within `except` (TODO: fix) |
| `E722` | Bare `except` (TODO: fix) |
| `E741` | Ambiguous variable names |
| `UP007` | `X \| Y` union syntax for type annotations |
| `B007` | Unused loop variable |
| `B023` | Function not binding loop variable |
| `B017` | `pytest.raises(Exception)` |
| `F811` | Redefinition of unused name |
| `S110` | `try-except-pass` |
| `S112` | `try-except-continue` |
| `S603` | Subprocess call without shell=True check |
| `S607` | Partial executable path in subprocess |
| `N802` | Function name should be lowercase |
| `N805` | First argument should be `self` |

Rules marked "TODO" indicate known technical debt.

### Per-File Ignores

```toml
[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]                          # Unused imports (re-exports)
"tests/**/*" = ["S101", "D", "F401", "E402"]      # assert, docstrings, imports
"**/tests/**/*" = ["S101", "S105", "S106", "D", "F401", "E402"]
"bridge/**/*" = ["F401", "E402"]
"revitpy/performance/**/*" = ["F401"]
"cli/**/*" = ["F401", "E402", "B904"]
"revitpy-package-manager/**/*" = ["F401", "E402", "F403", "F405", "S"]
"proof-of-concepts/**/*" = ["S311"]
```

Notable: `S101` (`assert` usage) is allowed in tests but flagged elsewhere.

## Import Ordering

The `I` (isort) rule set is enabled. Ruff sorts imports into the standard groups:

1. Standard library
2. Third-party packages
3. Local (first-party) imports

Within each group, imports are sorted alphabetically. Observed codebase pattern:

```python
from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from loguru import logger
from pydantic import BaseModel, validator

from .element import Element, ElementSet
from .exceptions import RevitAPIError, TransactionError
```

`from __future__ import annotations` is used consistently as the first import in modules that need it.

## mypy Configuration

```toml
[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_no_return = true
strict_equality = true
show_error_codes = true
```

### Active Strictness Flags

| Flag | Effect |
|---|---|
| `check_untyped_defs` | Type-check function bodies even without annotations |
| `no_implicit_optional` | `def f(x: str = None)` is an error; use `x: str \| None = None` |
| `warn_redundant_casts` | Warn on unnecessary `cast()` calls |
| `warn_no_return` | Warn when a function might not return |
| `strict_equality` | Flag comparisons between incompatible types |
| `show_error_codes` | Display error codes in output for targeted suppression |

### Disabled Error Codes

The following error codes are currently disabled to allow incremental adoption. The comment in `pyproject.toml` says: "Relax rules with many pre-existing violations; tighten incrementally."

```
attr-defined, assignment, var-annotated, valid-type, operator,
arg-type, misc, union-attr, override, return-value, index,
call-overload, no-redef, exit-return, has-type, dict-item,
truthy-function, type-var, type-abstract, import-untyped
```

New code should aim to pass with these checks enabled where practical. Avoid introducing new violations even if they would currently be suppressed.

## Type Annotation Conventions

Patterns observed throughout the codebase:

- **`from __future__ import annotations`** is used in most modules to enable PEP 604 union syntax (`X | Y`) in all Python 3.11+ contexts.
- **`TypeVar`** is used for generic classes. Example from `revitpy/api/query.py`:

  ```python
  T = TypeVar("T", bound=Element)
  ```

- **Protocols** define interfaces. The codebase uses `typing.Protocol` extensively:

  ```python
  class IRevitApplication(Protocol):
      @property
      def ActiveDocument(self) -> Any: ...

  class IElementProvider(Protocol):
      def get_all_elements(self) -> list[Element]: ...
  ```

- **`@runtime_checkable`** is used on `IElementProvider` to allow `isinstance` checks.

- **Return types** are annotated on all public methods. `None` return is written explicitly:

  ```python
  def disconnect(self) -> None:
  ```

- **Optional parameters** use the `X | None` syntax (not `Optional[X]`):

  ```python
  def __init__(self, revit_application: IRevitApplication | None = None) -> None:
  ```

## Naming Conventions

Patterns observed in the codebase:

| Kind | Convention | Examples |
|---|---|---|
| Classes | PascalCase | `RevitAPI`, `ElementSet`, `QueryBuilder`, `TransactionGroup` |
| Protocols / Interfaces | `I` prefix + PascalCase | `IRevitApplication`, `IRevitDocument`, `IElementProvider`, `ITransactionProvider` |
| Enums | PascalCase class, UPPER_SNAKE values | `TransactionStatus.NOT_STARTED`, `FilterOperator.EQUALS` |
| Functions / methods | snake_case | `get_parameter_value`, `start_transaction` |
| Private methods | underscore prefix | `_convert_from_revit`, `_ensure_evaluated` |
| Constants | UPPER_SNAKE_CASE | `PERFORMANCE_THRESHOLDS`, `REVIT_VERSIONS` |
| Type variables | Single uppercase letter or short name | `T`, `R`, `E`, `P` |
| Module-level "constants" | prefixed underscore + UPPER_SNAKE | `_LAZY_EVAL_THRESHOLD`, `_KNOWN_FAILURES` |
| Dataclasses | PascalCase | `DocumentInfo`, `TransactionOptions`, `FilterCriteria` |

Note: `N802` (function name should be lowercase) and `N805` (first argument should be `self`) are currently ignored. Some mock classes use PascalCase method names (e.g., `GetParameterValue`, `SetParameterValue`) to match the Revit API surface.

## Docstring Conventions

- Modules have a top-level docstring explaining the module's purpose.
- Classes have a docstring describing their role. Example:

  ```python
  class RevitAPI:
      """
      Main RevitPy API class providing high-level interface to Revit.
      """
  ```

- Public methods have docstrings with `Args:`, `Returns:`, and `Raises:` sections where appropriate. Example from `Element.get_parameter_value`:

  ```python
  def get_parameter_value(self, parameter_name: str, use_cache: bool = True) -> Any:
      """
      Get parameter value with caching and type conversion.

      Args:
          parameter_name: Name of the parameter
          use_cache: Whether to use cached values

      Returns:
          Parameter value with appropriate Python type

      Raises:
          ElementNotFoundError: If parameter doesn't exist
      """
  ```

- The `D` (pydocstyle) rule set is **not** in the `select` list, so docstring format is not enforced by ruff. The patterns above are conventions, not hard requirements.

## Context Managers

Both `Transaction` and `TransactionGroup` implement `__enter__` / `__exit__` and `__aenter__` / `__aexit__`, supporting both sync and async usage:

```python
with api.transaction("Update walls") as txn:
    ...

async with api.transaction("Async update") as txn:
    ...
```

`RevitContext` in the ORM layer is also a context manager that calls `dispose()` on exit.

## Error Handling

All custom exceptions inherit from `RevitAPIError`, which accepts a `message` and an optional `cause` (the underlying exception). Subclasses add domain-specific fields:

```python
class TransactionError(RevitAPIError):
    def __init__(self, message, transaction_name=None, cause=None):
        ...

class ElementNotFoundError(RevitAPIError):
    def __init__(self, element_id=None, element_type=None, cause=None):
        ...
```

Use `raise ... from e` when re-raising (note: `B904` is currently ignored but this is marked as technical debt to fix).

## Logging

The codebase uses **loguru** (`from loguru import logger`) consistently. Log levels observed:

- `logger.debug(...)` -- internal operations (transaction start/commit, cache hits, query execution).
- `logger.info(...)` -- significant operations (document opened, changes saved).
- `logger.warning(...)` -- recoverable issues (parameter read failure, commit handler failure).
- `logger.error(...)` -- operation failures that will raise an exception.
