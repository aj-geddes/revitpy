---
layout: page
title: Testing Guide
description: Learn how to run tests, use MockRevit utilities, write new test cases, and configure pytest for the RevitPy framework. No Revit installation required.
doc_tier: developer
---

# Testing Guide

RevitPy uses **pytest** as its test framework. All tests run without an actual Revit installation thanks to the mock infrastructure in both `revitpy/testing/` and the `tests/conftest.py` fixtures.

## Test Directory Structure

The actual layout of the `tests/` directory:

```
tests/
  conftest.py                          # Global fixtures and configuration
  README.md

  orm/
    __init__.py
    conftest.py                        # ORM-specific fixtures (MockElementProvider,
                                       #   cache_manager, change_tracker, sample_walls)
    test_cache.py
    test_change_tracker.py
    test_element_set.py
    test_query_builder.py
    test_query_integration.py
    test_validation.py
    test_performance_benchmarks.py

  unit/
    csharp/                            # C# bridge unit tests
    python/                            # Python unit tests

  integration/
    bridge/                            # Python-C# bridge integration tests

  performance/
    benchmarks/                        # Benchmark suites
    test_comprehensive_performance.py  # Performance regression tests

  security/
    auth/                              # Authentication tests
    validation/                        # Input validation security tests

  compatibility/                       # Cross-version compatibility tests
```

CI (`.github/workflows/ci.yml`) runs `pytest tests/orm/ -q --tb=short` in the **test** job.

## Pytest Configuration

The project-wide pytest settings in `pyproject.toml`:

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

Key points:

- `--strict-markers` -- using an unregistered marker is an error.
- `--strict-config` -- configuration warnings are errors.
- `asyncio_mode = "auto"` -- async test functions are detected automatically; no need for the `@pytest.mark.asyncio` decorator in most cases.

### Registered Markers

Markers registered in `pyproject.toml`:

| Marker | Description |
|---|---|
| `slow` | Tests that take a long time; deselect with `-m "not slow"` |
| `integration` | Integration tests |
| `unit` | Unit tests |

Additional markers registered dynamically by `tests/conftest.py`:

| Marker | Description |
|---|---|
| `e2e` | End-to-end workflow tests |
| `performance` | Performance and benchmark tests |
| `security` | Security-focused tests |
| `bridge` | Python-C# bridge tests |
| `mock_revit` | Tests using the mock Revit environment |
| `real_revit` | Tests requiring an actual Revit installation (auto-skipped when Revit is unavailable) |
| `compatibility` | Cross-version compatibility tests |
| `regression` | Regression tests for bug fixes |

The `conftest.py` `pytest_collection_modifyitems` hook automatically assigns markers based on file path (e.g., files under `unit/` get the `unit` marker).

## Mock Utilities

### `revitpy.testing` Module

The `revitpy/testing/` package exports four classes:

| Class | Description |
|---|---|
| `MockRevit` | Top-level mock environment. Owns a `MockApplication`, manages fixtures, event handlers, state serialisation (`save_state` / `load_state`), and provides helpers like `create_document`, `create_element`, `create_elements`, `reset`, `get_statistics`. |
| `MockApplication` | Simulates the Revit application. Properties: `ActiveDocument`. Methods: `OpenDocumentFile`, `CreateDocument`, `GetOpenDocuments`, `CloseDocument`. |
| `MockDocument` | Simulates a Revit document. Methods: `GetElements`, `GetElement`, `CreateElement`, `AddElement`, `Delete`, `Save`, `Close`, `StartTransaction`, `GetElementsByCategory`, `GetElementsByType`. Supports serialisation via `to_dict` / `from_dict`. |
| `MockElement` | Simulates a Revit element with parameters. Methods: `GetParameterValue`, `SetParameterValue`, `GetParameter`, `SetParameter`, `GetAllParameters`, `HasParameter`. Default parameters (Name, Category, Type, Comments, Mark) are created automatically. Supports `to_dict` / `from_dict`. |

Supporting mock classes in the same module: `MockTransaction`, `MockParameter`, `MockElementId`.

### Global Fixtures (`tests/conftest.py`)

The root `conftest.py` provides fixtures available to all tests:

| Fixture | Scope | Description |
|---|---|---|
| `event_loop` | session | Creates a single asyncio event loop for the test session |
| `mock_revit_app` | function | `MockRevitApplication` instance |
| `mock_revit_doc` | function | `MockDocument` added to `mock_revit_app` |
| `mock_revit_elements` | function | Three mock elements (Wall, Door, Window) with parameters set |
| `performance_monitor` | function | `PerformanceMonitor` class with `start()`, `stop()`, and a `measure()` context manager |
| `memory_leak_detector` | function | `MemoryLeakDetector` class with configurable threshold (default 10 MB) |
| `security_scanner` | function | `SecurityScanner` with methods for SQL injection, path traversal, and XSS checks |
| `concurrent_test_runner` | function | `ConcurrentTestRunner` for thread-safety testing |
| `temp_test_dir` | function | Temporary directory (auto-cleaned) |
| `sample_revit_file_data` | function | Dictionary mimicking Revit file content |
| `compatibility_test_data` | function | Test data for cross-version compatibility |
| `error_injection` | function | `ErrorInjector` for simulating network, file, and memory errors |
| `test_database` | function | SQLite test database with a sample table |

Utility functions are also available:

- `assert_performance_within_limits(metrics, max_time, max_memory_mb)` -- assert against performance thresholds.
- `assert_no_security_vulnerabilities(scanner)` -- assert no vulnerabilities found.

Constants: `REVIT_VERSIONS`, `PYTHON_VERSIONS`, `PLATFORMS`, `PERFORMANCE_THRESHOLDS`.

### ORM Fixtures (`tests/orm/conftest.py`)

| Fixture | Description |
|---|---|
| `mock_provider` | `MockElementProvider` pre-populated with three `WallElement` instances (ids 1-3) and three `RoomElement` instances (ids 10-12) |
| `cache_manager` | `CacheManager` with `max_size=1000`, statistics enabled, thread-safe |
| `change_tracker` | Thread-safe `ChangeTracker` |
| `sample_walls` | List of three `WallElement` instances |

The ORM conftest also marks known-failing tests as `xfail` and marks `performance_benchmarks` tests as `xfail` due to timing sensitivity.

## Running Tests

```bash
# Full test suite
pytest

# ORM tests only (what CI runs)
pytest tests/orm/ -q --tb=short

# By marker
pytest -m unit
pytest -m "not slow"
pytest -m performance

# With coverage
pytest --cov=revitpy --cov-report=term-missing

# Stop on first failure
pytest -x

# Verbose output
pytest -v
```

## Writing New Tests

### File and Class Naming

Follow the conventions enforced by `pyproject.toml`:

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Basic Test Example

```python
"""Tests for a hypothetical feature."""

import pytest

from revitpy.testing import MockRevit, MockElement


class TestMyFeature:
    """Tests for MyFeature."""

    def test_basic_operation(self):
        """Verify basic operation works."""
        mock = MockRevit()
        doc = mock.create_document("Test.rvt")
        element = mock.create_element(
            name="TestWall",
            category="Walls",
            element_type="Wall",
            parameters={"Height": 10.0},
        )

        assert element.Name == "TestWall"
        assert element.HasParameter("Height")

    def test_element_parameter_access(self):
        """Verify parameter get/set."""
        elem = MockElement(element_id=42, name="Wall1")
        elem.SetParameterValue("Height", 3000.0)

        param = elem.GetParameterValue("Height")
        assert param.value == 3000.0
```

### Using ORM Fixtures

```python
from revitpy.orm.query_builder import QueryBuilder
from revitpy.orm.validation import WallElement


class TestWallQueries:
    def test_filter_walls_by_height(self, mock_provider):
        """Filter walls taller than 9."""
        qb = QueryBuilder(mock_provider, WallElement)
        results = qb.where(lambda w: w.height > 9).to_list()

        assert len(results) == 2  # Wall 1 (h=10) and Wall 3 (h=12)
```

### Async Tests

Because `asyncio_mode = "auto"` is configured, async test functions are detected automatically:

```python
class TestAsyncOperations:
    async def test_async_query(self, mock_provider, cache_manager):
        """Verify async query execution."""
        qb = QueryBuilder(mock_provider, cache_manager=cache_manager)
        results = await qb.to_list_async()

        assert len(results) > 0
```

### Performance Tests

Use the `performance_monitor` fixture:

```python
class TestPerformance:
    def test_query_speed(self, mock_provider, performance_monitor):
        """Verify query executes within time limit."""
        with performance_monitor.measure():
            qb = QueryBuilder(mock_provider)
            qb.to_list()

        assert performance_monitor.last_metrics["execution_time"] < 1.0
```

### Using Markers

```python
import pytest

@pytest.mark.slow
def test_large_dataset():
    """Test with a large dataset."""
    ...

@pytest.mark.integration
def test_bridge_communication():
    """Test Python-C# bridge."""
    ...
```

All markers used in tests must be registered (via `pyproject.toml` or `conftest.py`) because `--strict-markers` is enabled.
