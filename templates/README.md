# RevitPy Project Templates

A comprehensive collection of project templates for common RevitPy development scenarios. These templates provide structured starting points with best practices, proper configuration, and essential boilerplate code.

## Available Templates

- [**Basic Script**](#basic-script-template) - Minimal setup for simple scripts
- [**Complete Add-in**](#complete-add-in-template) - Full-featured Revit add-in
- [**API Integration**](#api-integration-template) - External API integration
- [**Enterprise Extension**](#enterprise-extension-template) - Enterprise-grade development
- [**Testing Suite**](#testing-suite-template) - Comprehensive testing framework

## Template Overview

### Basic Script Template
**Location**: `/home/aj/hvs/revitpy/templates/basic-script/`

**Best for**: Simple automation scripts, quick prototypes, learning projects

**Features**:
- Minimal dependencies and setup
- Essential error handling and logging
- Basic configuration management
- CLI interface with argument parsing
- Simple test framework
- Clear documentation structure

**Use cases**:
- One-time automation tasks
- Quick data extraction scripts
- Learning RevitPy fundamentals
- Proof-of-concept development

```bash
# Create new project from template
cp -r /home/aj/hvs/revitpy/templates/basic-script my-automation-script
cd my-automation-script
pip install -r requirements.txt
# Edit script.py with your logic
python script.py
```

### Complete Add-in Template
**Location**: `/home/aj/hvs/revitpy/templates/complete-addon/`

**Best for**: Professional Revit add-ins with UI, complex functionality

**Features**:
- Full Revit ribbon integration
- Modern UI with WebView2 support
- Configuration and settings management
- Comprehensive logging and error handling
- Automated testing and CI/CD setup
- Professional documentation structure
- Installer creation scripts
- Multi-language support

**Use cases**:
- Commercial Revit add-ins
- Complex automation workflows
- UI-intensive applications
- Multi-user environments

### API Integration Template
**Location**: `/home/aj/hvs/revitpy/templates/api-integration/`

**Best for**: Projects requiring external API integration

**Features**:
- HTTP client configuration and authentication
- Data synchronization patterns
- Error handling and retry logic
- Background processing and queuing
- API rate limiting and throttling
- Data transformation and mapping
- Webhook handling
- Security and credential management

**Use cases**:
- Cloud service integration
- Database synchronization
- Third-party system integration
- Real-time data exchange

### Enterprise Extension Template
**Location**: `/home/aj/hvs/revitpy/templates/enterprise-extension/`

**Best for**: Enterprise-grade development with high reliability requirements

**Features**:
- Advanced logging and monitoring
- Comprehensive error reporting
- Security best practices implementation
- Configuration management for multiple environments
- Automated testing and quality assurance
- Documentation and deployment automation
- Performance monitoring and optimization
- Compliance and audit trail features

**Use cases**:
- Large-scale deployments
- Mission-critical applications
- Regulated industry compliance
- Multi-environment deployments

### Testing Suite Template
**Location**: `/home/aj/hvs/revitpy/templates/testing-suite/`

**Best for**: Projects requiring comprehensive testing frameworks

**Features**:
- Unit testing with mocks
- Integration testing strategies
- Performance testing and benchmarking
- Automated test data generation
- Test reporting and visualization
- Continuous integration setup
- Code coverage analysis
- Test-driven development patterns

**Use cases**:
- Quality-focused development
- Regression testing automation
- Performance validation
- Compliance testing

## Using Templates

### Quick Start

1. **Choose a template** based on your project requirements
2. **Copy the template** to your project directory
3. **Customize** the template for your specific needs
4. **Install dependencies** and configure settings
5. **Start developing** with a solid foundation

### Template Selection Guide

| Template | Complexity | Setup Time | Best For |
|----------|------------|------------|----------|
| Basic Script | Low | 5 minutes | Simple scripts, learning |
| Complete Add-in | High | 30 minutes | Professional add-ins |
| API Integration | Medium | 15 minutes | External integrations |
| Enterprise Extension | High | 45 minutes | Enterprise deployments |
| Testing Suite | Medium | 20 minutes | Test-focused projects |

### Step-by-Step Usage

#### 1. Copy Template
```bash
# Copy template to new project directory
cp -r /home/aj/hvs/revitpy/templates/[template-name] my-new-project
cd my-new-project
```

#### 2. Customize Configuration
```bash
# Rename and edit configuration files
mv config/settings.yaml.template config/settings.yaml
# Edit configuration for your needs
```

#### 3. Update Project Metadata
```bash
# Edit pyproject.toml or setup.py
# Update project name, version, author, etc.
```

#### 4. Install Dependencies
```bash
# Install required packages
pip install -r requirements.txt

# For development dependencies
pip install -r requirements-dev.txt
```

#### 5. Customize Code
```bash
# Replace template code with your logic
# Follow the established patterns and structure
```

#### 6. Run Tests
```bash
# Ensure template works correctly
pytest tests/
```

#### 7. Initialize Version Control
```bash
# Initialize git repository
git init
git add .
git commit -m "Initial project setup from template"
```

## Template Features

### Common Features Across All Templates

- **Error Handling**: Comprehensive exception handling patterns
- **Logging**: Structured logging with configurable levels
- **Configuration**: External configuration file support
- **Documentation**: README templates and code documentation
- **Testing**: Basic test structure and patterns
- **Type Hints**: Full type annotations for better code quality
- **Code Quality**: Pre-configured formatting and linting

### Template-Specific Features

#### Basic Script Template
```python
# Minimal structure with essential patterns
class BasicScript:
    def __init__(self, config_file=None):
        self.config = load_config(config_file)
        self.logger = setup_logging()
        
    def run(self):
        # Your logic here
        pass
```

#### Complete Add-in Template
```python
# Full add-in structure with UI
class RevitAddin:
    def __init__(self):
        self.ribbon_panel = self.create_ribbon_panel()
        self.ui_manager = UIManager()
        
    def create_ribbon_panel(self):
        # Ribbon integration code
        pass
```

#### API Integration Template
```python
# API client with authentication and error handling
class APIClient:
    def __init__(self, config):
        self.session = self.create_authenticated_session()
        self.rate_limiter = RateLimiter()
        
    async def sync_data(self, data):
        # Data synchronization logic
        pass
```

## Customization Guide

### Configuration Customization

Each template includes configuration files that should be customized:

```yaml
# config/settings.yaml
project:
  name: "My RevitPy Project"
  version: "1.0.0"
  author: "Your Name"

logging:
  level: "INFO"
  format: "detailed"

# Add your custom settings here
custom:
  feature_flags:
    enable_advanced_mode: false
  database:
    connection_string: "your_connection_here"
```

### Code Customization

#### Replace Template Logic
```python
# In your main file, replace template methods
def run(self) -> Dict[str, Any]:
    """Replace this method with your business logic."""
    results = {'success': False, 'data': {}}
    
    try:
        # YOUR CUSTOM LOGIC HERE
        # Example: Query Revit elements, process data, etc.
        
        results['success'] = True
        results['data'] = {'processed': 100}
        
    except Exception as e:
        self.logger.error(f"Operation failed: {e}")
        results['error'] = str(e)
    
    return results
```

#### Add Custom Dependencies
```python
# Add to requirements.txt
pandas>=1.5.0
requests>=2.28.0
sqlalchemy>=1.4.46

# Install and use in your code
import pandas as pd
import requests
from sqlalchemy import create_engine
```

#### Extend Configuration
```python
# Add custom configuration sections
def load_custom_config(self):
    """Load project-specific configuration."""
    custom_config = self.config.get('custom', {})
    
    self.feature_flags = custom_config.get('feature_flags', {})
    self.database_url = custom_config.get('database', {}).get('connection_string')
    
    # Validate configuration
    if not self.database_url:
        raise ValueError("Database connection string required")
```

### Testing Customization

#### Add Custom Tests
```python
# tests/test_custom_logic.py
import pytest
from unittest.mock import Mock, patch

class TestCustomLogic:
    
    def test_custom_operation(self):
        """Test your custom business logic."""
        # Arrange
        mock_data = create_test_data()
        
        # Act
        result = your_custom_function(mock_data)
        
        # Assert
        assert result['success'] is True
        assert 'data' in result
```

## Best Practices

### Template Selection
1. **Start Simple**: Begin with Basic Script for learning and prototypes
2. **Grow Gradually**: Move to more complex templates as needs evolve
3. **Match Requirements**: Choose template complexity that matches project scope
4. **Consider Future**: Think about long-term maintenance and scaling needs

### Customization
1. **Preserve Structure**: Keep the template's organizational structure
2. **Follow Patterns**: Use established patterns for consistency
3. **Document Changes**: Document significant customizations clearly
4. **Test Thoroughly**: Test customizations to ensure reliability
5. **Version Control**: Use git to track changes from template baseline

### Development Workflow
1. **Template First**: Always start with appropriate template
2. **Configure Early**: Set up configuration and environment first
3. **Test Often**: Run tests frequently during development
4. **Document Changes**: Keep documentation updated with customizations
5. **Follow Standards**: Maintain code quality standards from template

## Template Development

### Creating New Templates

To create a new template:

1. **Identify Need**: Determine what scenario the template addresses
2. **Design Structure**: Plan directory structure and key files
3. **Implement Features**: Add essential functionality and patterns
4. **Add Documentation**: Include comprehensive README and examples
5. **Test Template**: Verify template works in different scenarios
6. **Add to Collection**: Integrate with existing template system

### Template Standards

All templates should include:

- **README.md**: Comprehensive documentation
- **requirements.txt**: Dependency specifications
- **config/**: Configuration file templates
- **tests/**: Basic test structure
- **examples/**: Usage examples
- **pyproject.toml**: Python project metadata
- **.gitignore**: Appropriate exclusions
- **LICENSE**: License information

## Integration with RevitPy CLI

Templates integrate with the RevitPy CLI for easy project creation:

```bash
# Create new project from template
revitpy create my-project --template basic-script

# List available templates
revitpy templates list

# Show template details
revitpy templates info complete-addon
```

## Support and Resources

### Getting Help with Templates

1. **Template Documentation**: Each template includes detailed README
2. **Example Code**: Templates include working examples
3. **Test Cases**: Review tests for usage patterns
4. **Community Support**: Ask questions in RevitPy forums

### Contributing Templates

We welcome contributions of new templates:

1. **Follow Standards**: Use consistent structure and documentation
2. **Add Value**: Ensure template addresses real development needs
3. **Test Thoroughly**: Verify template works across different scenarios
4. **Document Well**: Provide clear setup and customization instructions

## Troubleshooting

### Common Issues

**Issue**: Template files not copying correctly
**Solution**: Check file permissions and use absolute paths

**Issue**: Dependencies not installing
**Solution**: Verify Python version and pip configuration

**Issue**: Configuration errors
**Solution**: Validate YAML syntax and required settings

**Issue**: Tests failing after customization
**Solution**: Update tests to match your custom logic

### Debug Mode

Enable detailed logging in any template:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)

# Your template code will now show debug information
```

## Next Steps

1. **Explore Templates**: Review templates that match your development needs
2. **Start Project**: Use appropriate template for your next RevitPy project
3. **Customize**: Adapt template to your specific requirements
4. **Share Experience**: Contribute improvements and new templates
5. **Build Portfolio**: Use templates to build consistent, professional projects

Templates provide the foundation for successful RevitPy development by establishing best practices, providing proven patterns, and accelerating project setup. Choose the right template for your needs and customize it to build robust, maintainable RevitPy applications.