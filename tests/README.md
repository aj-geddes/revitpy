# RevitPy Testing Suite

This directory contains the comprehensive testing suite for RevitPy, designed to ensure enterprise-grade quality and reliability through multiple testing layers.

## Overview

The RevitPy testing framework provides:

- **90%+ code coverage** across all components
- **Multi-language testing** (Python and C#)
- **Performance benchmarking** with regression detection
- **Security vulnerability testing**
- **Cross-platform compatibility testing**
- **Mock Revit environment** for testing without Revit installation
- **Automated CI/CD integration** with GitHub Actions

## Test Structure

```
tests/
├── conftest.py                 # Global test configuration and fixtures
├── pytest.ini                 # Pytest configuration
├── unit/                       # Unit tests (fast, isolated)
│   ├── python/                 # Python framework unit tests
│   │   ├── test_api_wrapper.py
│   │   ├── test_orm_models.py
│   │   └── ...
│   ├── csharp/                 # C# bridge unit tests
│   │   ├── BridgeTests.cs
│   │   └── ...
│   └── cli/                    # CLI tools unit tests
├── integration/                # Integration tests
│   ├── bridge/                 # Python-C# integration
│   │   └── test_bridge_integration.py
│   ├── e2e/                    # End-to-end workflows
│   └── compatibility/          # Cross-version testing
├── performance/                # Performance tests
│   ├── benchmarks/             # Performance benchmarks
│   │   └── test_api_performance.py
│   └── load/                   # Load testing
├── security/                   # Security tests
│   ├── auth/                   # Authentication tests
│   └── validation/             # Input validation tests
│       └── test_input_validation.py
└── fixtures/                   # Test data and utilities
    ├── mock_revit/             # Mock Revit environment
    └── test_data/              # Sample test data
```

## Test Categories

### Unit Tests
Fast, isolated tests that verify individual components:
- **Python Framework**: API wrapper, ORM models, query builder
- **C# Bridge**: Communication layer, type conversion, transactions
- **CLI Tools**: Command-line interface functionality

**Run with:** `pytest tests/unit/ -m unit`

### Integration Tests
Tests that verify component interactions:
- **Bridge Integration**: Python-C# communication
- **E2E Workflows**: Complete user scenarios
- **Compatibility**: Cross-version compatibility

**Run with:** `pytest tests/integration/ -m integration`

### Performance Tests
Benchmarks and performance regression detection:
- **API Performance**: Response time benchmarks
- **Memory Usage**: Memory leak detection
- **Concurrency**: Thread safety testing
- **Scalability**: High-load performance

**Run with:** `pytest tests/performance/ -m performance --benchmark-only`

### Security Tests
Security vulnerability detection and prevention:
- **Input Validation**: SQL injection, XSS, path traversal
- **Authentication**: Access control testing
- **Data Sanitization**: Input sanitization verification
- **Dependency Security**: Vulnerable dependency detection

**Run with:** `pytest tests/security/ -m security`

## Test Markers

Tests are categorized using pytest markers:

```python
@pytest.mark.unit          # Unit tests
@pytest.mark.integration   # Integration tests
@pytest.mark.e2e          # End-to-end tests
@pytest.mark.performance  # Performance tests
@pytest.mark.security     # Security tests
@pytest.mark.slow         # Slow-running tests
@pytest.mark.bridge       # Bridge functionality tests
@pytest.mark.mock_revit   # Tests using mock Revit
@pytest.mark.real_revit   # Tests requiring actual Revit
@pytest.mark.compatibility # Cross-version tests
@pytest.mark.regression   # Regression tests
```

## Running Tests

### Quick Start
```bash
# Install test dependencies
pip install -e .[dev,test]

# Run all unit tests
pytest tests/unit/

# Run with coverage
pytest --cov=revitpy --cov-report=html

# Run specific test categories
pytest -m "unit and not slow"
pytest -m "integration"
pytest -m "performance"
pytest -m "security"
```

### Common Test Commands

```bash
# Fast test suite (unit tests only)
pytest tests/unit/ -v

# Standard test suite (unit + integration)
pytest tests/unit/ tests/integration/ -m "not slow"

# Full test suite (all tests)
pytest

# Performance benchmarks
pytest tests/performance/ --benchmark-only

# Security tests
pytest tests/security/ -v

# Tests with coverage report
pytest --cov=revitpy --cov-report=html --cov-report=term-missing

# Parallel test execution
pytest -n auto  # Automatic core detection
pytest -n 4     # Use 4 cores

# Specific test file
pytest tests/unit/python/test_api_wrapper.py -v

# Specific test method
pytest tests/unit/python/test_api_wrapper.py::TestRevitAPIWrapper::test_connect_success -v
```

### Test Configuration

Tests can be configured through environment variables:

```bash
# Test database URL (for integration tests)
export TEST_DATABASE_URL="postgresql://user:password@localhost/test_db"

# Revit version for compatibility tests
export REVIT_VERSION="2024"

# Test mode
export REVITPY_TEST_MODE="integration"

# Enable debug logging
export REVITPY_LOG_LEVEL="DEBUG"
```

## Mock Revit Environment

The testing suite includes a comprehensive mock Revit environment that allows testing without requiring Revit installation:

### Features
- **Mock Elements**: Wall, Door, Window, and other Revit elements
- **Mock Parameters**: Element parameters with type conversion
- **Mock Transactions**: Transaction management simulation
- **Mock Document**: Document operations and element queries
- **Mock Application**: Revit application simulation

### Usage
```python
def test_with_mock_revit(mock_revit_doc, mock_revit_elements):
    # Use mock Revit document
    wall = mock_revit_elements[0]  # First mock element (wall)

    # Test element operations
    assert wall.height == 3000.0
    wall.height = 3500.0
    assert wall.height == 3500.0

    # Test parameter access
    height_param = wall.get_parameter("Height")
    assert height_param.value == 3500.0
```

## Performance Testing

### Benchmarks
Performance tests use `pytest-benchmark` for accurate measurements:

```python
@pytest.mark.benchmark
def test_api_call_performance(benchmark, api_wrapper):
    result = benchmark(api_wrapper.call_api, "GetElement", {"elementId": 123})
    assert result is not None
```

### Performance Thresholds
- **API Call Response**: < 10ms average
- **Element Creation**: > 2000 elements/second
- **Memory Usage**: < 5KB per element
- **Concurrent Operations**: > 250 calls/second

### Memory Leak Detection
```python
def test_memory_usage(memory_leak_detector):
    memory_leak_detector.start()

    # Perform operations
    for i in range(1000):
        perform_operation(i)

    # Check for leaks
    stats = memory_leak_detector.check()
    assert stats["memory_increase_mb"] < 10  # Less than 10MB increase
```

## Security Testing

### Vulnerability Detection
Security tests check for common vulnerabilities:

```python
@pytest.mark.security
@pytest.mark.parametrize("malicious_input", [
    "'; DROP TABLE elements; --",
    "<script>alert('xss')</script>",
    "../../../etc/passwd"
])
def test_input_validation(validator, malicious_input):
    with pytest.raises(RevitSecurityError):
        validator.validate_input(malicious_input)
```

### Security Scanners
- **Bandit**: Python security linter
- **Safety**: Dependency vulnerability scanner
- **Custom Scanners**: Application-specific security checks

## Continuous Integration

### GitHub Actions Workflow
The test suite is integrated with GitHub Actions for automated testing:

- **On Push**: Unit tests
- **On PR**: Unit + integration tests
- **Nightly**: Full test suite including performance and security
- **Manual**: Configurable test level selection

### Test Matrix
- **Python Versions**: 3.11, 3.12
- **Operating Systems**: Ubuntu, Windows, macOS
- **Revit Versions**: 2022, 2023, 2024, 2025

### Coverage Reports
- **Codecov Integration**: Automatic coverage reporting
- **Coverage Gates**: 90% minimum coverage required
- **Trend Tracking**: Coverage trend monitoring

## Test Data Management

### Fixtures
Centralized test data management:

```python
@pytest.fixture
def sample_wall_data():
    return {
        "Id": 12345,
        "Name": "Test Wall",
        "Category": "Walls",
        "Parameters": {"Height": 3000.0, "Width": 200.0}
    }
```

### Factories
Dynamic test data generation:

```python
class ElementFactory:
    @staticmethod
    def create_wall(height=3000.0, width=200.0):
        return {
            "Id": random.randint(1000, 9999),
            "Category": "Walls",
            "Parameters": {"Height": height, "Width": width}
        }
```

## Debugging Tests

### Debug Mode
```bash
# Run with debug output
pytest -v --tb=long --capture=no

# Run single test with debugging
pytest tests/unit/python/test_api_wrapper.py::test_connect_success -v -s

# Debug with pdb
pytest --pdb
pytest --pdb-trace  # Drop into debugger on first line
```

### Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

def test_with_logging(caplog):
    with caplog.at_level(logging.DEBUG):
        # Test code here
        pass

    assert "Expected log message" in caplog.text
```

## Best Practices

### Writing Tests
1. **AAA Pattern**: Arrange, Act, Assert
2. **Descriptive Names**: Test names should describe the scenario
3. **Single Responsibility**: One assertion per test (when possible)
4. **Independent Tests**: Tests should not depend on each other
5. **Mock External Dependencies**: Use mocks for external services

### Test Organization
1. **Logical Grouping**: Group related tests in classes
2. **Appropriate Markers**: Use markers for categorization
3. **Fixture Reuse**: Maximize fixture reuse across tests
4. **Documentation**: Document complex test scenarios

### Performance Considerations
1. **Parallel Execution**: Use `pytest-xdist` for parallel tests
2. **Test Isolation**: Avoid shared state between tests
3. **Resource Cleanup**: Properly clean up resources
4. **Mock Heavy Operations**: Mock expensive operations

## Maintenance

### Regular Tasks
1. **Update Dependencies**: Keep test dependencies current
2. **Review Coverage**: Monitor coverage trends
3. **Performance Baselines**: Update performance baselines
4. **Security Scans**: Regular security vulnerability scans

### Test Health Monitoring
- **Flaky Test Detection**: Identify and fix unstable tests
- **Performance Regression**: Monitor test execution time
- **Coverage Trends**: Track coverage changes over time
- **Failure Analysis**: Analyze test failure patterns

## Troubleshooting

### Common Issues

#### Test Discovery Problems
```bash
# If tests aren't discovered
pytest --collect-only

# Check test path configuration
cat pytest.ini
```

#### Import Errors
```bash
# Install in development mode
pip install -e .

# Check Python path
python -c "import sys; print(sys.path)"
```

#### Performance Test Failures
```bash
# Run with increased timeout
pytest tests/performance/ --benchmark-min-rounds=1

# Check system resources
htop  # or Task Manager on Windows
```

#### Mock Revit Issues
```bash
# Clear test cache
pytest --cache-clear

# Verbose mock debugging
pytest -v -s -m mock_revit
```

### Getting Help
- **Documentation**: Check inline test documentation
- **Issues**: Create GitHub issues for test problems
- **Discussions**: Use GitHub Discussions for questions
- **Contributing**: See CONTRIBUTING.md for test contribution guidelines

## Contributing

When contributing tests:
1. Follow the existing test structure
2. Add appropriate markers
3. Include docstrings for test classes and complex tests
4. Update this README if adding new test categories
5. Ensure tests are cross-platform compatible
6. Add performance benchmarks for new features

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-benchmark](https://pytest-benchmark.readthedocs.io/)
- [FluentAssertions](https://fluentassertions.com/) (C# tests)
- [xUnit](https://xunit.net/) (C# test framework)
- [Codecov](https://codecov.io/) (Coverage reporting)
