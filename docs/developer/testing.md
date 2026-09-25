---
layout: page
title: Testing Guide
description: Learn how to run tests, use MockRevit utilities, write new test cases, and configure pytest for the RevitPy framework. No Revit installation required.
doc_tier: developer
---

RevitPy uses **pytest** as its test framework. All tests run without an actual Revit installation thanks to the mock infrastructure in both `revitpy/testing/` and the `tests/conftest.py` fixtures.

## Test Directory Structure

The test suite (all Python; the C# add-in is verified by compiling it):

```
tests/
  conftest.py             # Global fixtures, marker auto-assignment by path
  api/                    # Core API: RevitAPI, typed elements, transactions, queries
  revit/                  # revitpy.revit adapters (fake Autodesk.Revit.DB) and host helpers
  orm/                    # ORM: cache, change tracker, element set, query builder,
                          #   persistence (unit of work), validation, benchmarks
  ai/                     # MCP server, protocol, tools, safety guard, prompts
  cloud/                  # APS auth, client, jobs, batch, CI, webhooks (+ hardening tests)
  extract/                # Quantities, materials, costs, schedules, exporters
  ifc/                    # Mapper, exporter (incl. real ifcopenshell), importer,
                          #   IDS validator, BCF, diff
  interop/                # Speckle client, sync, mapper, diff, merge, subscriptions
  sustainability/         # Carbon, EPD (+ matching), compliance, materials, reports
  events/                 # Class-based handlers, native Revit event bridge
  performance/            # test_comprehensive_performance.py (slow stress tests)
  test_examples.py        # Runs every script in examples/
```

`tests/revit/` runs the live-Revit adapters against a fake `Autodesk.Revit.DB` namespace. The adapters accept an injected `db` for this purpose, so no Revit or pythonnet is needed. Tests that need the optional integrations (ifcopenshell, ifctester, specklepy) are skipped when those packages are missing.

CI (`.github/workflows/ci.yml`) runs `pytest tests/ --cov=revitpy` on Python 3.11, 3.12 and 3.13 without optional integrations. A separate job runs `pytest tests/` with `pip install -e ".[dev,all]"`.

## Pytest Configuration

The project-wide pytest settings live in `pyproject.toml` (there is no `pytest.ini`):

```toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-ra -q --strict-markers --strict-config -m 'not slow'"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [ ... ]
asyncio_mode = "auto"
```

Key points:

- `-m 'not slow'`: long-running stress tests are **excluded by default**. Run them with `pytest -m slow`. A `-m` on the command line replaces the default.
- `--strict-markers`: using an unregistered marker is an error.
- `--strict-config`: configuration warnings are errors.
- `asyncio_mode = "auto"`: async test functions are detected automatically, so you don't need `@pytest.mark.asyncio`.

### Registered Markers

All markers are registered in `pyproject.toml`: `slow`, `integration`, `unit`, `performance`, `benchmark`, `security`, `regression`, `compatibility`, `mock_revit`, `real_revit`, `e2e`. `tests/conftest.py` registers the same names again and adds the path-based auto-marking.

| Marker | Description |
|---|---|
| `slow` | Long-running tests, excluded by default (run with `-m slow`) |
| `unit` / `integration` / `e2e` | Test level; also auto-assigned from the file path |
| `performance` / `benchmark` | Performance and benchmark tests |
| `security` | Security-focused tests |
| `mock_revit` | Tests using the mock Revit environment |
| `real_revit` | Tests requiring an actual Revit installation (auto-skipped when Revit is unavailable) |
| `compatibility` / `regression` | Cross-version and regression tests |

The `conftest.py` hook `pytest_collection_modifyitems` assigns markers based on file path. For example, files whose path contains `performance` get the `performance` marker.

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

The ORM conftest marks `performance_benchmarks` tests as non-strict `xfail` because they are timing-sensitive.

## Running Tests

```bash
# Default suite (slow tests excluded)
pytest

# Only the slow stress tests / absolutely everything
pytest -m slow
pytest -m "slow or not slow"

# One area
pytest tests/api tests/revit
pytest tests/orm/ -q --tb=short

# By marker
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

### Testing Code That Uses `RevitAPI`

Connect `RevitAPI` to `MockRevit().application` and your code runs unchanged. Typed queries, nested transactions and rollback all work, because `MockDocument.StartTransaction` snapshots and restores parameter values:

```python
from revitpy import RevitAPI
from revitpy.api import Wall
from revitpy.testing import MockRevit


def test_rename_walls_rolls_back_on_error():
    mock = MockRevit()
    mock.create_document("Test.rvt")
    mock.create_element(name="W1", category="OST_Walls")

    api = RevitAPI()
    api.connect(mock.application)
    wall = api.query(Wall).first()

    try:
        with api.transaction("Rename"):
            wall.name = "Renamed"
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert api.query(Wall).first().name == "W1"
```

Mock parameter values set with `create_element(parameters=...)` are returned by `Element.get_parameter_value()` as **strings** (for example `10.0` becomes `"10.0"`), because `MockParameter` has no storage type. Compare numbers accordingly, or read `MockElement.GetParameterValue(name).value` directly.

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

@pytest.mark.real_revit
def test_against_live_model():
    """Skipped automatically unless Revit is available."""
    ...
```

All markers used in tests must be registered (via `pyproject.toml` or `conftest.py`) because `--strict-markers` is enabled.
