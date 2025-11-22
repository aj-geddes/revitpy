# RevitPy-PyRevit Bridge Test Suite

This comprehensive test suite validates all functionality of the RevitPy-PyRevit interoperability bridge, ensuring reliable operation across all components and workflows.

## Test Structure

### Core Components (`test_core_bridge.py`)
- **BridgeConfig**: Configuration management and validation
- **BridgeManager**: Main bridge coordinator functionality
- **Exception Handling**: Custom exception classes and error handling

### Serialization (`test_serialization.py`)
- **ElementSerializer**: Element data serialization/deserialization
- **GeometrySerializer**: 3D geometry processing
- **ParameterSerializer**: Revit parameter handling
- **Compression**: Data compression and optimization

### Communication (`test_communication.py`)
- **NamedPipeServer/Client**: High-performance local IPC
- **WebSocketServer/Client**: Real-time bidirectional communication
- **FileExchangeHandler**: File-based batch processing
- **Protocol Performance**: Throughput and latency testing

### PyRevit Integration (`test_pyrevit_integration.py`)
- **RevitPyBridge**: Main PyRevit interface
- **ElementSelector**: Interactive element selection
- **BridgeUIHelpers**: User interface components
- **AnalysisClient**: High-level analysis workflows

### Workflows (`test_workflows.py`)
- **BuildingPerformanceWorkflow**: Energy and thermal analysis
- **SpaceOptimizationWorkflow**: ML-powered layout optimization
- **RealTimeMonitoringWorkflow**: IoT sensor integration
- **End-to-End Testing**: Complete workflow validation

### Performance (`test_performance.py`)
- **Serialization Performance**: Large dataset handling
- **Communication Throughput**: Protocol performance under load
- **Memory Usage**: Resource management validation
- **Stress Testing**: System behavior under extreme conditions

## Running Tests

### Prerequisites

Install required testing dependencies:
```bash
pip install pytest pytest-asyncio pytest-cov pytest-json-report
```

### Quick Start

```bash
# Run all tests
python -m bridge.tests.run_tests all

# Run smoke tests (quick validation)
python -m bridge.tests.run_tests smoke

# Run specific test category
python -m bridge.tests.run_tests unit
python -m bridge.tests.run_tests integration
python -m bridge.tests.run_tests performance
```

### Advanced Usage

```bash
# Generate coverage report
python -m bridge.tests.run_tests all --coverage

# Run specific test
python -m bridge.tests.run_tests specific --test test_core_bridge.py::TestBridgeManager

# Quiet mode with cleanup
python -m bridge.tests.run_tests unit --quiet --cleanup

# Validate environment and generate comprehensive report
python -m bridge.tests.run_tests report --validate
```

### Test Runner Options

| Option | Description |
|--------|-------------|
| `--coverage` | Generate code coverage report |
| `--quiet` | Suppress verbose output |
| `--cleanup` | Clean test artifacts before running |
| `--validate` | Validate test environment |
| `--test` | Specify single test (for specific mode) |

## Test Categories

### Unit Tests (Fast)
- Core component functionality
- Individual class and method testing
- Mock-based isolation testing
- **Runtime**: ~30 seconds

### Integration Tests (Medium)
- Multi-component interaction testing
- Workflow validation
- Cross-system communication
- **Runtime**: ~2-3 minutes

### Performance Tests (Slow)
- Large dataset processing
- Stress testing under load
- Memory and resource usage
- **Runtime**: ~5-10 minutes

### Smoke Tests (Very Fast)
- Basic functionality validation
- Quick health check
- Regression detection
- **Runtime**: ~10 seconds

## Mock Components

The test suite includes comprehensive mock components for testing without dependencies:

### Mock Revit Elements
```python
@pytest.fixture
def mock_revit_element():
    element = Mock()
    element.Id.IntegerValue = 12345
    element.Category.Name = "Walls"
    element.Name = "Basic Wall"
    return element
```

### Mock PyRevit UI
```python
@pytest.fixture
def mock_pyrevit_ui():
    ui_mock = Mock()
    ui_mock.TaskDialog.Show = Mock(return_value="Yes")
    return {"UI": ui_mock, "forms": Mock()}
```

### Sample Test Data
- **Element Data**: Realistic Revit element structures
- **Analysis Requests**: Complete analysis workflow data
- **Sensor Data**: IoT sensor readings for monitoring tests
- **Performance Data**: Large datasets for performance testing

## Configuration

Test configuration is managed through `TEST_CONFIG` in `__init__.py`:

```python
TEST_CONFIG = {
    'use_mock_revit': True,
    'test_data_dir': Path(__file__).parent / 'test_data',
    'temp_dir': Path(__file__).parent / 'temp',
    'timeout_seconds': 30,
    'max_test_elements': 100
}
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Bridge Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      - name: Run tests
        run: python -m bridge.tests.run_tests all --coverage
```

## Performance Benchmarks

### Expected Performance Metrics

| Component | Metric | Target | Test |
|-----------|--------|--------|------|
| Element Serialization | Throughput | >100 elements/sec | test_large_dataset_serialization |
| WebSocket Communication | Requests | >50 req/sec | test_websocket_throughput |
| Data Compression | Ratio | >50% reduction | test_compression_efficiency |
| Memory Usage | Growth | <200MB under load | test_memory_usage_under_load |

### Stress Test Scenarios

1. **High Volume Serialization**: 1000+ elements with geometry
2. **Concurrent Communication**: 10 simultaneous client connections
3. **Memory Pressure**: Multiple large datasets in memory
4. **Connection Cycling**: Rapid connect/disconnect cycles
5. **Malformed Data**: Invalid input handling

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Ensure bridge module is in path
export PYTHONPATH="${PYTHONPATH}:/path/to/revitpy"
```

**Async Test Failures**
```bash
# Install asyncio support
pip install pytest-asyncio
```

**Coverage Report Issues**
```bash
# Install coverage tools
pip install pytest-cov coverage
```

### Test Data Management

Test data is automatically created in:
- `tests/test_data/` - Persistent test data
- `tests/temp/` - Temporary files (cleaned up)

### Debug Mode

Enable debug output:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

### Adding New Tests

1. **Create test file**: Follow `test_*.py` naming convention
2. **Use fixtures**: Leverage existing fixtures for consistency
3. **Mock dependencies**: Use provided mock components
4. **Document tests**: Clear docstrings and comments
5. **Performance tests**: Include timing assertions where appropriate

### Test Best Practices

- **Isolation**: Each test should be independent
- **Deterministic**: Tests should produce consistent results
- **Fast execution**: Unit tests should complete quickly
- **Clear assertions**: Specific, meaningful test conditions
- **Error testing**: Include negative test cases

## Results and Reporting

### Test Reports

The test suite generates multiple report formats:

- **Console Output**: Real-time test execution status
- **JSON Report**: Machine-readable results (`test_report.json`)
- **Coverage Report**: HTML coverage analysis (`htmlcov/`)
- **Performance Metrics**: Timing and throughput data

### Success Criteria

- **Unit Tests**: >95% pass rate
- **Integration Tests**: >90% pass rate
- **Performance Tests**: Meet benchmark targets
- **Coverage**: >80% code coverage
- **No Memory Leaks**: Stable memory usage under load

---

*This test suite ensures the RevitPy-PyRevit bridge maintains high quality and reliability across all usage scenarios.*
