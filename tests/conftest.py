"""Global pytest configuration and shared fixtures for RevitPy testing.

This file provides enterprise-grade testing infrastructure including:
- Mock Revit environment for testing without Revit installation
- Performance benchmarking fixtures
- Security testing utilities
- Cross-platform compatibility fixtures
- Memory leak detection
- Concurrent operation testing
"""

import asyncio
import gc
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psutil
import pytest

# =============================================================================
# Session Configuration
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


def pytest_configure(config):
    """Configure custom pytest markers and settings."""
    # Register custom markers
    markers = [
        "unit: Unit tests (fast, isolated, no external dependencies)",
        "integration: Integration tests (slower, may require external resources)",
        "e2e: End-to-end tests (full workflow tests)",
        "performance: Performance and benchmark tests",
        "security: Security-focused tests",
        "slow: Tests that take more than 10 seconds",
        "bridge: Tests for Python-C# bridge functionality",
        "mock_revit: Tests using mock Revit environment",
        "real_revit: Tests requiring actual Revit installation",
        "compatibility: Cross-version compatibility tests",
        "regression: Regression tests for bug fixes",
    ]

    for marker in markers:
        config.addinivalue_line("markers", marker)

    # Configure test collection
    config.option.collectonly = False


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add automatic markers and skip conditions."""
    for item in items:
        # Auto-mark tests based on file path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
        elif "security" in str(item.fspath):
            item.add_marker(pytest.mark.security)

        # Skip real Revit tests if Revit is not available
        if item.get_closest_marker("real_revit") and not _is_revit_available():
            item.add_marker(pytest.mark.skip(reason="Revit not available"))


def _is_revit_available() -> bool:
    """Check if Revit is available on the system."""
    try:
        import clr

        clr.AddReference("RevitAPI")
        return True
    except (ImportError, OSError):
        return False


# =============================================================================
# Mock Revit Environment
# =============================================================================


class MockRevitElement:
    """Mock Revit element for testing."""

    def __init__(self, element_id: int = 1, name: str = "MockElement"):
        self.Id = MockElementId(element_id)
        self.Name = name
        self.Category = MockCategory("MockCategory")
        self.Parameters = []
        self._parameter_values = {}

    def LookupParameter(self, param_name: str):
        """Mock parameter lookup."""
        if param_name in self._parameter_values:
            return MockParameter(param_name, self._parameter_values[param_name])
        return None

    def SetParameterValue(self, param_name: str, value: Any):
        """Set parameter value for testing."""
        self._parameter_values[param_name] = value


class MockElementId:
    """Mock Revit ElementId."""

    def __init__(self, id_value: int):
        self.IntegerValue = id_value

    def __str__(self):
        return str(self.IntegerValue)

    def __int__(self):
        return self.IntegerValue


class MockParameter:
    """Mock Revit parameter."""

    def __init__(self, name: str, value: Any):
        self.Definition = MockParameterDefinition(name)
        self._value = value

    @property
    def AsString(self):
        return str(self._value)

    @property
    def AsDouble(self):
        return float(self._value) if isinstance(self._value, (int, float)) else 0.0

    @property
    def AsInteger(self):
        return int(self._value) if isinstance(self._value, (int, float)) else 0


class MockParameterDefinition:
    """Mock parameter definition."""

    def __init__(self, name: str):
        self.Name = name


class MockCategory:
    """Mock Revit category."""

    def __init__(self, name: str):
        self.Name = name
        self.Id = MockElementId(hash(name) % 1000000)


class MockDocument:
    """Mock Revit document."""

    def __init__(self):
        self.Title = "MockDocument"
        self.PathName = "/mock/path/document.rvt"
        self.IsLinked = False
        self._elements = {}
        self._next_id = 1000

    def GetElement(self, element_id):
        """Get element by ID."""
        if isinstance(element_id, MockElementId):
            element_id = element_id.IntegerValue
        return self._elements.get(element_id)

    def AddMockElement(self, element_type: str = "Wall", **kwargs):
        """Add a mock element for testing."""
        element_id = self._next_id
        self._next_id += 1

        element = MockRevitElement(
            element_id, kwargs.get("name", f"Mock{element_type}")
        )
        self._elements[element_id] = element
        return element

    def Close(self, save_modified: bool = False):
        """Mock document close."""
        pass


class MockTransaction:
    """Mock Revit transaction."""

    def __init__(self, document: MockDocument, name: str):
        self.document = document
        self.name = name
        self._started = False
        self._committed = False

    def Start(self):
        """Start transaction."""
        self._started = True
        return True

    def Commit(self):
        """Commit transaction."""
        if self._started:
            self._committed = True
            return True
        return False

    def RollBack(self):
        """Rollback transaction."""
        self._started = False
        return True

    def __enter__(self):
        self.Start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and self._started:
            self.Commit()
        elif self._started:
            self.RollBack()


class MockRevitApplication:
    """Mock Revit application."""

    def __init__(self):
        self.Documents = MockDocumentCollection()
        self.VersionNumber = "2024"
        self.VersionName = "Autodesk Revit 2024"

    def OpenDocumentFile(self, file_path: str):
        """Open a mock document."""
        doc = MockDocument()
        doc.PathName = file_path
        self.Documents.Add(doc)
        return doc


class MockDocumentCollection:
    """Mock document collection."""

    def __init__(self):
        self._documents = []

    def Add(self, document):
        """Add document to collection."""
        self._documents.append(document)

    def __iter__(self):
        return iter(self._documents)

    def __len__(self):
        return len(self._documents)


@pytest.fixture
def mock_revit_app():
    """Provide a mock Revit application for testing."""
    return MockRevitApplication()


@pytest.fixture
def mock_revit_doc(mock_revit_app):
    """Provide a mock Revit document for testing."""
    doc = MockDocument()
    mock_revit_app.Documents.Add(doc)
    return doc


@pytest.fixture
def mock_revit_elements(mock_revit_doc):
    """Create mock Revit elements for testing."""
    elements = []

    # Create various element types
    wall = mock_revit_doc.AddMockElement("Wall", name="TestWall")
    wall.SetParameterValue("Height", 10.0)
    wall.SetParameterValue("Width", 0.5)
    elements.append(wall)

    door = mock_revit_doc.AddMockElement("Door", name="TestDoor")
    door.SetParameterValue("Height", 7.0)
    door.SetParameterValue("Width", 3.0)
    elements.append(door)

    window = mock_revit_doc.AddMockElement("Window", name="TestWindow")
    window.SetParameterValue("Height", 4.0)
    window.SetParameterValue("Width", 2.0)
    elements.append(window)

    return elements


# =============================================================================
# Performance Testing Fixtures
# =============================================================================


@pytest.fixture
def performance_monitor():
    """Monitor performance metrics during tests."""

    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.start_memory = None
            self.end_memory = None
            self.process = psutil.Process()

        def start(self):
            """Start monitoring."""
            gc.collect()  # Clean up before measurement
            self.start_time = time.perf_counter()
            self.start_memory = self.process.memory_info().rss

        def stop(self):
            """Stop monitoring and return metrics."""
            self.end_time = time.perf_counter()
            self.end_memory = self.process.memory_info().rss

            return {
                "execution_time": self.end_time - self.start_time,
                "memory_used": self.end_memory - self.start_memory,
                "start_memory": self.start_memory,
                "end_memory": self.end_memory,
                "cpu_percent": self.process.cpu_percent(),
                "memory_percent": self.process.memory_percent(),
            }

        @contextmanager
        def measure(self):
            """Context manager for performance measurement."""
            self.start()
            try:
                yield self
            finally:
                metrics = self.stop()
                # Store metrics for later analysis
                self.last_metrics = metrics

    return PerformanceMonitor()


@pytest.fixture
def memory_leak_detector():
    """Detect memory leaks during tests."""

    class MemoryLeakDetector:
        def __init__(self, threshold_mb: float = 10.0):
            self.threshold_mb = threshold_mb
            self.initial_memory = None
            self.process = psutil.Process()

        def start(self):
            """Start memory monitoring."""
            gc.collect()
            self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        def check(self):
            """Check for memory leaks."""
            gc.collect()
            current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - self.initial_memory

            if memory_increase > self.threshold_mb:
                raise AssertionError(
                    f"Memory leak detected: {memory_increase:.2f}MB increase "
                    f"(threshold: {self.threshold_mb}MB)"
                )

            return {
                "initial_memory_mb": self.initial_memory,
                "current_memory_mb": current_memory,
                "memory_increase_mb": memory_increase,
            }

    return MemoryLeakDetector()


# =============================================================================
# Security Testing Fixtures
# =============================================================================


@pytest.fixture
def security_scanner():
    """Security testing utilities."""

    class SecurityScanner:
        def __init__(self):
            self.vulnerabilities = []

        def check_sql_injection(self, query: str) -> bool:
            """Check for potential SQL injection vulnerabilities."""
            dangerous_patterns = [
                "'; DROP TABLE",
                "' OR '1'='1",
                "' UNION SELECT",
                "; DELETE FROM",
                "'; INSERT INTO",
            ]

            for pattern in dangerous_patterns:
                if pattern.lower() in query.lower():
                    self.vulnerabilities.append(
                        {"type": "sql_injection", "pattern": pattern, "query": query}
                    )
                    return True
            return False

        def check_path_traversal(self, path: str) -> bool:
            """Check for path traversal vulnerabilities."""
            dangerous_patterns = [
                "../",
                "..\\",
                "/..",
                "\\..",
                "%2e%2e%2f",
                "%2e%2e%5c",
            ]

            for pattern in dangerous_patterns:
                if pattern.lower() in path.lower():
                    self.vulnerabilities.append(
                        {"type": "path_traversal", "pattern": pattern, "path": path}
                    )
                    return True
            return False

        def check_xss(self, content: str) -> bool:
            """Check for XSS vulnerabilities."""
            dangerous_patterns = [
                "<script",
                "javascript:",
                "onload=",
                "onerror=",
                "onclick=",
                "eval(",
                "alert(",
            ]

            for pattern in dangerous_patterns:
                if pattern.lower() in content.lower():
                    self.vulnerabilities.append(
                        {"type": "xss", "pattern": pattern, "content": content}
                    )
                    return True
            return False

        def get_vulnerabilities(self) -> list[dict]:
            """Get all found vulnerabilities."""
            return self.vulnerabilities.copy()

        def clear_vulnerabilities(self):
            """Clear vulnerability list."""
            self.vulnerabilities.clear()

    return SecurityScanner()


# =============================================================================
# Concurrent Testing Fixtures
# =============================================================================


@pytest.fixture
def concurrent_test_runner():
    """Run tests concurrently to check thread safety."""

    class ConcurrentTestRunner:
        def __init__(self):
            self.results = []
            self.exceptions = []

        def run_concurrent(self, func, args_list: list, max_workers: int = 10):
            """Run function concurrently with different arguments."""
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                futures = []

                for args in args_list:
                    if isinstance(args, tuple):
                        future = executor.submit(func, *args)
                    else:
                        future = executor.submit(func, args)
                    futures.append(future)

                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        self.results.append(result)
                    except Exception as e:
                        self.exceptions.append(e)

            return {
                "results": self.results,
                "exceptions": self.exceptions,
                "success_rate": len(self.results) / len(args_list) if args_list else 0,
            }

        def run_stress_test(self, func, iterations: int = 100, max_workers: int = 20):
            """Run stress test with many concurrent operations."""
            args_list = [i for i in range(iterations)]
            return self.run_concurrent(func, args_list, max_workers)

    return ConcurrentTestRunner()


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_revit_file_data():
    """Sample data that mimics Revit file content."""
    return {
        "project_info": {
            "name": "Test Project",
            "number": "TP001",
            "client": "Test Client",
            "address": "123 Test Street",
        },
        "elements": [
            {
                "id": 1001,
                "type": "Wall",
                "parameters": {
                    "Height": 3000.0,
                    "Width": 200.0,
                    "Material": "Concrete",
                },
            },
            {
                "id": 1002,
                "type": "Door",
                "parameters": {"Height": 2100.0, "Width": 900.0, "Material": "Wood"},
            },
        ],
    }


@pytest.fixture
def compatibility_test_data():
    """Test data for compatibility testing across Revit versions."""
    return {
        "revit_versions": ["2022", "2023", "2024", "2025"],
        "api_changes": {
            "2023": ["NewMethod1", "RemovedMethod1"],
            "2024": ["NewMethod2", "ChangedMethod1"],
            "2025": ["NewMethod3", "RemovedMethod2"],
        },
        "deprecated_features": {
            "2023": ["OldAPI1"],
            "2024": ["OldAPI2", "OldAPI1"],
            "2025": ["OldAPI3", "OldAPI2"],
        },
    }


# =============================================================================
# Error Handling Fixtures
# =============================================================================


@pytest.fixture
def error_injection():
    """Inject errors for testing error handling."""

    class ErrorInjector:
        def __init__(self):
            self.active_errors = {}

        def inject_network_error(self, error_type: str = "timeout"):
            """Inject network errors."""
            errors = {
                "timeout": TimeoutError("Network timeout"),
                "connection": ConnectionError("Connection refused"),
                "dns": OSError("DNS resolution failed"),
            }

            return errors.get(error_type, RuntimeError(f"Unknown error: {error_type}"))

        def inject_file_error(self, error_type: str = "not_found"):
            """Inject file system errors."""
            errors = {
                "not_found": FileNotFoundError("File not found"),
                "permission": PermissionError("Permission denied"),
                "disk_full": OSError("No space left on device"),
            }

            return errors.get(error_type, RuntimeError(f"Unknown error: {error_type}"))

        def inject_memory_error(self):
            """Inject memory errors."""
            return MemoryError("Out of memory")

        @contextmanager
        def patch_method(self, target, method_name, error):
            """Patch a method to raise an error."""
            original_method = getattr(target, method_name)

            def error_method(*args, **kwargs):
                raise error

            setattr(target, method_name, error_method)
            try:
                yield
            finally:
                setattr(target, method_name, original_method)

    return ErrorInjector()


# =============================================================================
# Database Testing Fixtures
# =============================================================================


@pytest.fixture
def test_database():
    """Provide a test database for testing."""
    import sqlite3

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                value REAL
            )
        """)
        conn.commit()

        yield {"path": db_path, "connection": conn}
    finally:
        conn.close()
        os.unlink(db_path)


# =============================================================================
# Test Utilities
# =============================================================================


def assert_performance_within_limits(
    metrics: dict[str, float], max_time: float = None, max_memory_mb: float = None
):
    """Assert that performance metrics are within acceptable limits."""
    if max_time is not None:
        assert (
            metrics["execution_time"] <= max_time
        ), f"Execution time {metrics['execution_time']:.3f}s exceeds limit {max_time}s"

    if max_memory_mb is not None:
        memory_mb = metrics["memory_used"] / 1024 / 1024
        assert (
            memory_mb <= max_memory_mb
        ), f"Memory usage {memory_mb:.2f}MB exceeds limit {max_memory_mb}MB"


def assert_no_security_vulnerabilities(scanner):
    """Assert that no security vulnerabilities were found."""
    vulnerabilities = scanner.get_vulnerabilities()
    assert not vulnerabilities, f"Security vulnerabilities found: {vulnerabilities}"


# =============================================================================
# Parametrized Test Data
# =============================================================================

# Common test parameters
REVIT_VERSIONS = ["2022", "2023", "2024", "2025"]
PYTHON_VERSIONS = ["3.11", "3.12"]
PLATFORMS = ["windows", "linux", "macos"]

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "api_call_max_time": 1.0,  # seconds
    "startup_max_time": 5.0,  # seconds
    "memory_limit_mb": 100.0,  # MB
    "cpu_limit_percent": 80.0,  # %
}
