# RevitPy Example Projects

A comprehensive collection of example projects demonstrating RevitPy capabilities and best practices. These examples serve as both learning resources and practical starting points for real-world RevitPy development.

## Quick Navigation

- [**Basic Element Query Tool**](#basic-element-query-tool) - Fundamental element querying and filtering
- [**Parameter Management Utility**](#parameter-management-utility) - Advanced parameter operations
- [**Geometry Analysis Extension**](#geometry-analysis-extension) - Geometric operations and analysis
- [**WebView2 UI Panel Example**](#webview2-ui-panel-example) - Modern web-based UI integration
- [**Data Export/Import Tool**](#data-export-import-tool) - Comprehensive data workflows
- [**Model Validation Suite**](#model-validation-suite) - Automated quality control

## Project Overview

### Basic Element Query Tool
**Location**: `/home/aj/hvs/revitpy/examples/basic-element-query/`

**What you'll learn**:
- Fundamental RevitPy API usage
- Element querying and filtering techniques
- Parameter access and property management
- Error handling and logging best practices
- Performance optimization strategies

**Key Features**:
- Simple element queries by category
- Advanced filtering with custom conditions
- Element property analysis and display
- Export results to various formats
- Comprehensive error handling examples
- Performance benchmarking

**Best for**: Beginners learning RevitPy fundamentals

```bash
cd /home/aj/hvs/revitpy/examples/basic-element-query
pip install -r requirements.txt
python examples/basic_usage.py
```

### Parameter Management Utility
**Location**: `/home/aj/hvs/revitpy/examples/parameter-management/`

**What you'll learn**:
- Reading and writing all parameter types
- Bulk parameter operations and transaction management
- Data validation and error recovery
- CSV/Excel import/export with mapping
- Shared parameter creation and management
- Change tracking and audit trails

**Key Features**:
- Comprehensive parameter CRUD operations
- Bulk processing with progress tracking
- Data import/export with validation
- Shared parameter management
- Parameter change history
- Unit conversion and handling

**Best for**: Data management and BIM workflows

```bash
cd /home/aj/hvs/revitpy/examples/parameter-management
pip install -r requirements.txt
python examples/basic_operations.py
```

### Geometry Analysis Extension
**Location**: `/home/aj/hvs/revitpy/examples/geometry-analysis/`

**What you'll learn**:
- Advanced geometry operations and analysis
- Solid modeling and boolean operations
- Geometric calculations and measurements
- Spatial analysis and collision detection
- Performance optimization for complex geometry
- Integration with external geometry libraries

**Key Features**:
- Geometric property calculations
- Solid boolean operations (union, intersect, subtract)
- Distance and interference analysis
- Volume and area calculations with precision
- Point-in-polygon and spatial queries
- Geometric validation and repair

**Best for**: Advanced geometric analysis and spatial operations

### WebView2 UI Panel Example
**Location**: `/home/aj/hvs/revitpy/examples/webview-ui-panel/`

**What you'll learn**:
- Modern web-based UI development for Revit add-ins
- Bidirectional communication between Python and JavaScript
- React/Vue.js integration with RevitPy
- Real-time data updates and user interactions
- Responsive design and accessibility compliance
- WebSocket communication patterns

**Key Features**:
- Modern React-based UI panel
- Real-time data synchronization
- Interactive element selection
- Parameter editing interface
- Progress tracking and notifications
- Responsive design for different screen sizes

**Best for**: Creating modern, interactive user interfaces

### Data Export/Import Tool
**Location**: `/home/aj/hvs/revitpy/examples/data-export-import/`

**What you'll learn**:
- Comprehensive data export to multiple formats
- Robust import with validation and error handling
- Large dataset processing and optimization
- Integration with external databases and APIs
- Scheduled operations and batch processing
- Data transformation and mapping

**Key Features**:
- Export to Excel, CSV, JSON, XML, PDF formats
- Import with data validation and conflict resolution
- Database integration (SQL Server, PostgreSQL, etc.)
- API integration for cloud services
- Scheduled exports and automated workflows
- Data mapping and transformation tools

**Best for**: Data integration and reporting workflows

### Model Validation Suite
**Location**: `/home/aj/hvs/revitpy/examples/model-validation/`

**What you'll learn**:
- Automated model quality control
- Custom validation rule development
- Reporting and visualization of issues
- Integration with project standards
- Performance optimization for large models
- Continuous integration workflows

**Key Features**:
- Comprehensive model validation rules
- Visual issue reporting and highlighting
- Custom rule development framework
- Integration with project templates
- Automated quality reports
- Performance dashboards

**Best for**: Quality assurance and compliance checking

## Getting Started

### Prerequisites

1. **RevitPy Installation**: Ensure RevitPy is properly installed and configured
2. **Revit Version**: Revit 2022 or later recommended
3. **Python Environment**: Python 3.9+ with pip
4. **Development Tools**: VS Code with RevitPy extension (recommended)

### Universal Setup Steps

For any example project:

1. **Navigate to the project directory**:
   ```bash
   cd /home/aj/hvs/revitpy/examples/[project-name]/
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure settings (optional)**:
   ```bash
   cp config/settings.yaml.example config/settings.yaml
   # Edit configuration as needed
   ```

4. **Run the example**:
   ```bash
   # Basic usage
   python examples/basic_usage.py

   # Advanced features
   python examples/advanced_features.py

   # Interactive mode
   python src/main.py interactive
   ```

### Using the CLI Tools

Most examples include command-line interfaces:

```bash
# Query elements
python src/main.py query-category --category "Walls" --output results.json

# Filter with conditions
python src/main.py filter --parameter "Height" --value "10" --comparison "greater"

# Batch operations
python src/main.py batch-process --input data.csv --operation "update-parameters"

# Interactive exploration
python src/main.py interactive
```

## Learning Path

### For Beginners
1. Start with **Basic Element Query Tool**
2. Learn parameter handling with **Parameter Management Utility**
3. Explore UI development with **WebView2 UI Panel Example**

### For Intermediate Users
1. Master geometric operations with **Geometry Analysis Extension**
2. Build data workflows with **Data Export/Import Tool**
3. Implement quality control with **Model Validation Suite**

### For Advanced Users
1. Combine examples to build complex workflows
2. Extend examples with custom functionality
3. Contribute improvements and new examples

## Code Quality Standards

All examples follow consistent quality standards:

- **Type Hints**: Full type annotations for better documentation
- **Error Handling**: Comprehensive exception handling with recovery
- **Logging**: Structured logging for debugging and monitoring
- **Testing**: Unit and integration tests with >80% coverage
- **Documentation**: Clear docstrings and inline comments
- **Performance**: Optimized algorithms and memory management
- **Security**: Input validation and secure coding practices

## Testing Examples

Each example includes comprehensive tests:

```bash
# Run all tests for an example
cd /home/aj/hvs/revitpy/examples/basic-element-query
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test categories
pytest tests/ -m "unit"
pytest tests/ -m "integration"
```

## Performance Benchmarks

Examples include performance testing and benchmarks:

```bash
# Run performance tests
python tests/performance/benchmark_queries.py

# Generate performance report
python tests/performance/generate_report.py
```

## Configuration Management

Each example supports flexible configuration:

```yaml
# config/settings.yaml
general:
  log_level: "INFO"
  timeout: 300

performance:
  batch_size: 100
  parallel_processing: true

output:
  format: "json"
  include_metadata: true
```

## Common Patterns

### Error Handling Pattern
```python
try:
    elements = query_tool.get_elements_by_category("Walls")
    for element in elements:
        # Process element
        pass
except RevitPyException as e:
    logger.error(f"RevitPy operation failed: {e}")
    # Handle gracefully
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    # Log and re-raise or handle
```

### Progress Tracking Pattern
```python
from tqdm import tqdm

for element in tqdm(elements, desc="Processing elements"):
    try:
        # Process element
        results.append(process_element(element))
    except Exception as e:
        errors.append({'element': element.Id, 'error': str(e)})
```

### Configuration Pattern
```python
def load_config(config_file: str = None) -> Dict[str, Any]:
    """Load configuration with defaults."""
    default_config = get_default_config()

    if config_file and Path(config_file).exists():
        with open(config_file) as f:
            user_config = yaml.safe_load(f)
        return merge_configs(default_config, user_config)

    return default_config
```

## Integration Examples

### Using Multiple Examples Together

```python
# Combine element query with parameter management
from basic_element_query import ElementQueryTool
from parameter_management import ParameterManager

query_tool = ElementQueryTool()
param_manager = ParameterManager()

# Query elements
walls = query_tool.get_elements_by_category("Walls")

# Update parameters
for wall in walls:
    param_manager.set_parameter(wall, "Fire Rating", "2 Hour")
```

### External Integration

```python
# Integration with external systems
import requests
from data_export_import import DataExporter

exporter = DataExporter()
data = exporter.export_to_dict(elements)

# Send to external API
response = requests.post('https://api.example.com/bim-data', json=data)
```

## Contributing to Examples

We welcome contributions to improve and extend these examples:

1. **Bug Fixes**: Report and fix issues you encounter
2. **New Features**: Add functionality that would benefit others
3. **Performance Improvements**: Optimize existing code
4. **Documentation**: Improve clarity and add examples
5. **New Examples**: Contribute entirely new example projects

### Contribution Guidelines

1. **Follow Code Standards**: Use consistent formatting and documentation
2. **Add Tests**: Include tests for new functionality
3. **Update Documentation**: Keep README files current
4. **Performance Impact**: Consider performance implications
5. **Backward Compatibility**: Maintain compatibility where possible

## Support and Resources

### Getting Help

1. **Documentation**: Start with project README files
2. **Code Comments**: Examples include detailed inline documentation
3. **Test Cases**: Review tests for usage patterns
4. **Community Forums**: Join RevitPy community discussions

### Additional Resources

1. **RevitPy Official Documentation**: Core API reference
2. **Revit API Documentation**: Underlying Revit API details
3. **Python Best Practices**: General Python development guidelines
4. **BIM Standards**: Industry standards and practices

## Troubleshooting

### Common Issues

**Issue**: "RevitPy module not found"
**Solution**: Ensure RevitPy is installed and properly configured

**Issue**: "No active Revit document"
**Solution**: Open a Revit document before running examples

**Issue**: "Permission denied errors"
**Solution**: Check Revit security settings and file permissions

**Issue**: "Performance is slow"
**Solution**: Review batch sizes and enable parallel processing where appropriate

### Debug Mode

Enable detailed logging for troubleshooting:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)

# Or via configuration
config = {'logging': {'level': 'DEBUG'}}
```

## Next Steps

1. **Explore Examples**: Start with examples matching your needs
2. **Customize Code**: Adapt examples for your specific requirements
3. **Build Projects**: Use examples as foundation for larger projects
4. **Share Knowledge**: Contribute improvements back to the community
5. **Advance Skills**: Move to more complex examples and custom development

These examples provide comprehensive coverage of RevitPy capabilities while demonstrating best practices and real-world patterns. Use them as learning tools, starting points for your projects, and references for best practices in RevitPy development.
