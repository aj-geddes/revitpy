# Basic Script Template

A minimal RevitPy script template for simple automation tasks and quick prototyping. This template provides essential boilerplate code and best practices for standalone RevitPy scripts.

## Features

- **Minimal Setup**: Essential code structure with minimal dependencies
- **Error Handling**: Comprehensive error handling patterns
- **Logging**: Structured logging configuration
- **Configuration**: Basic configuration management
- **CLI Interface**: Optional command-line interface
- **Documentation**: Clear documentation structure and examples
- **Testing**: Basic test framework setup
- **Best Practices**: Code quality standards and patterns

## Template Structure

```
basic-script/
├── README.md
├── requirements.txt
├── script.py                 # Main script file
├── config.yaml              # Configuration file
├── tests/
│   ├── __init__.py
│   └── test_script.py
├── utils/
│   ├── __init__.py
│   ├── logging_config.py
│   └── helpers.py
└── examples/
    ├── simple_usage.py
    └── advanced_usage.py
```

## Quick Start

### Using the Template

1. **Copy the template**:
   ```bash
   cp -r /home/aj/hvs/revitpy/templates/basic-script my-script
   cd my-script
   ```

2. **Customize the template**:
   - Edit `script.py` with your logic
   - Update `config.yaml` with your settings
   - Modify `requirements.txt` for your dependencies
   - Update `README.md` with your script documentation

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run your script**:
   ```bash
   python script.py
   ```

### CLI Usage

```bash
# Basic execution
python script.py

# With configuration file
python script.py --config custom_config.yaml

# With logging level
python script.py --log-level DEBUG

# Show help
python script.py --help
```

## Template Content

### Main Script (`script.py`)

```python
#!/usr/bin/env python3
"""
RevitPy Basic Script Template

A minimal template for RevitPy automation scripts.
Customize this template for your specific needs.

Author: Your Name
Created: Date
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Add utils to path
sys.path.append(str(Path(__file__).parent / 'utils'))

from logging_config import setup_logging
from helpers import load_config, validate_revit_connection

try:
    from revitpy import RevitAPI, FilteredElementCollector
    from revitpy.exceptions import RevitPyException
except ImportError:
    print("RevitPy not available. Running in development mode.")
    RevitAPI = None
    RevitPyException = Exception


class BasicScript:
    """
    Basic RevitPy script class.
    
    This template provides a foundation for RevitPy automation scripts
    with proper error handling, logging, and configuration management.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        """Initialize the script."""
        # Load configuration
        self.config = load_config(config_file or "config.yaml")
        
        # Setup logging
        self.logger = setup_logging(
            level=self.config.get('logging', {}).get('level', 'INFO'),
            log_file=self.config.get('logging', {}).get('file')
        )
        
        # Initialize RevitPy connection
        self.revit = None
        self.doc = None
        self._connect_to_revit()
        
        self.logger.info("BasicScript initialized successfully")
    
    def _connect_to_revit(self):
        """Establish connection to Revit."""
        if not RevitAPI:
            self.logger.warning("RevitPy not available - running in development mode")
            return
        
        try:
            self.revit = RevitAPI()
            self.doc = self.revit.get_active_document()
            
            if not self.doc:
                raise RevitPyException("No active Revit document found")
            
            self.logger.info(f"Connected to document: {self.doc.Title}")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Revit: {e}")
            raise
    
    def run(self) -> Dict[str, Any]:
        """
        Main script execution logic.
        
        Customize this method with your specific automation logic.
        
        Returns:
            Dictionary with execution results
        """
        results = {
            'success': False,
            'message': '',
            'data': {},
            'statistics': {}
        }
        
        try:
            self.logger.info("Starting script execution...")
            
            # ==========================================
            # CUSTOMIZE THIS SECTION WITH YOUR LOGIC
            # ==========================================
            
            # Example: Get all walls in the model
            if self.doc:
                collector = FilteredElementCollector(self.doc)
                walls = collector.of_category("Walls").where_element_is_not_element_type().to_elements()
                
                self.logger.info(f"Found {len(walls)} walls in the model")
                
                # Example: Process walls
                processed_walls = []
                for wall in walls:
                    wall_data = {
                        'id': wall.Id.IntegerValue,
                        'name': wall.Name or 'Unnamed',
                        'category': wall.Category.Name if wall.Category else 'Unknown'
                    }
                    processed_walls.append(wall_data)
                
                results['data'] = {
                    'walls': processed_walls,
                    'wall_count': len(walls)
                }
            
            # ==========================================
            # END CUSTOMIZATION SECTION
            # ==========================================
            
            results['success'] = True
            results['message'] = 'Script executed successfully'
            results['statistics'] = {
                'elements_processed': len(results['data'].get('walls', [])),
                'execution_time': 'Not implemented'  # Add timing if needed
            }
            
            self.logger.info("Script execution completed successfully")
            
        except Exception as e:
            results['success'] = False
            results['message'] = f'Script execution failed: {str(e)}'
            self.logger.error(f"Script execution failed: {e}", exc_info=True)
        
        return results
    
    def cleanup(self):
        """Cleanup resources and finalize execution."""
        self.logger.info("Cleaning up resources...")
        # Add any cleanup logic here
        
    def validate_environment(self) -> bool:
        """Validate the execution environment."""
        if not validate_revit_connection(self.revit, self.doc):
            self.logger.error("Revit environment validation failed")
            return False
        
        # Add any additional validation logic here
        return True


def main():
    """Main entry point with CLI argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='RevitPy Basic Script')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate environment, don\'t execute')
    
    args = parser.parse_args()
    
    try:
        # Initialize script
        script = BasicScript(args.config)
        
        # Override log level if specified
        if args.log_level:
            logging.getLogger().setLevel(args.log_level)
        
        # Validate environment
        if not script.validate_environment():
            print("Environment validation failed. Exiting.")
            return 1
        
        if args.validate_only:
            print("Environment validation successful.")
            return 0
        
        # Execute script
        results = script.run()
        
        # Cleanup
        script.cleanup()
        
        # Report results
        if results['success']:
            print(f"SUCCESS: {results['message']}")
            if results.get('statistics'):
                print("Statistics:")
                for key, value in results['statistics'].items():
                    print(f"  {key}: {value}")
            return 0
        else:
            print(f"FAILED: {results['message']}")
            return 1
            
    except KeyboardInterrupt:
        print("\nScript interrupted by user")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

### Configuration (`config.yaml`)

```yaml
# Basic Script Configuration

# General settings
general:
  script_name: "Basic RevitPy Script"
  version: "1.0.0"
  author: "Your Name"

# Logging configuration
logging:
  level: "INFO"           # DEBUG, INFO, WARNING, ERROR
  file: null             # Log file path (null for console only)
  format: "detailed"     # simple, detailed
  
# Script-specific settings
script:
  timeout_seconds: 300
  max_elements: 10000
  validate_elements: true
  
# Output settings
output:
  save_results: false
  output_directory: "output"
  result_format: "json"   # json, csv, txt
```

### Utilities (`utils/helpers.py`)

```python
"""Helper utilities for basic scripts."""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(config_file: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    config_path = Path(config_file)
    
    if not config_path.exists():
        logging.warning(f"Config file not found: {config_file}. Using defaults.")
        return get_default_config()
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Merge with defaults
        default_config = get_default_config()
        return merge_configs(default_config, config)
        
    except Exception as e:
        logging.error(f"Error loading config file {config_file}: {e}")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """Get default configuration."""
    return {
        'general': {
            'script_name': 'Basic RevitPy Script',
            'version': '1.0.0',
            'author': 'RevitPy User'
        },
        'logging': {
            'level': 'INFO',
            'file': None,
            'format': 'detailed'
        },
        'script': {
            'timeout_seconds': 300,
            'max_elements': 10000,
            'validate_elements': True
        },
        'output': {
            'save_results': False,
            'output_directory': 'output',
            'result_format': 'json'
        }
    }


def merge_configs(default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Merge user configuration with defaults."""
    result = default.copy()
    
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    
    return result


def validate_revit_connection(revit_api, document) -> bool:
    """
    Validate Revit connection.
    
    Args:
        revit_api: RevitAPI instance
        document: Revit document
        
    Returns:
        True if valid, False otherwise
    """
    if not revit_api:
        logging.warning("RevitAPI not available")
        return False
    
    if not document:
        logging.error("No active Revit document")
        return False
    
    try:
        # Basic document validation
        title = document.Title
        logging.info(f"Document validation successful: {title}")
        return True
        
    except Exception as e:
        logging.error(f"Document validation failed: {e}")
        return False


def save_results(results: Dict[str, Any], output_path: str, format: str = "json"):
    """
    Save results to file.
    
    Args:
        results: Results dictionary
        output_path: Output file path
        format: Output format (json, yaml, txt)
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        if format.lower() == "json":
            import json
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
        
        elif format.lower() == "yaml":
            with open(output_file, 'w') as f:
                yaml.dump(results, f, default_flow_style=False)
        
        elif format.lower() == "txt":
            with open(output_file, 'w') as f:
                f.write(str(results))
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logging.info(f"Results saved to {output_file}")
        
    except Exception as e:
        logging.error(f"Failed to save results: {e}")
        raise
```

## Customization Guide

### Adding Your Logic

Replace the example logic in the `run()` method:

```python
def run(self) -> Dict[str, Any]:
    """Your custom logic goes here."""
    results = {'success': False, 'message': '', 'data': {}}
    
    try:
        # Your RevitPy automation logic here
        # Example: Query elements, modify parameters, create geometry, etc.
        
        # Update results
        results['success'] = True
        results['message'] = 'Custom operation completed'
        
    except Exception as e:
        results['message'] = f'Operation failed: {e}'
        self.logger.error(f"Operation failed: {e}")
    
    return results
```

### Adding Configuration Options

Extend `config.yaml` with your settings:

```yaml
# Your custom settings
custom:
  element_filter: "Height > 10"
  target_category: "Walls"
  batch_size: 50
  export_results: true
```

Access in your script:

```python
custom_settings = self.config.get('custom', {})
element_filter = custom_settings.get('element_filter')
```

### Adding Dependencies

Update `requirements.txt` with additional packages:

```txt
# Add your dependencies
pandas>=1.5.0
openpyxl>=3.0.10
requests>=2.28.0
```

## Testing

Run tests to validate your script:

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Test Template (`tests/test_script.py`)

```python
import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from script import BasicScript


class TestBasicScript:
    
    def test_initialization(self):
        """Test script initialization."""
        with patch('script.RevitAPI'):
            script = BasicScript()
            assert script.config is not None
            assert script.logger is not None
    
    def test_run_method(self):
        """Test script execution."""
        with patch('script.RevitAPI'):
            script = BasicScript()
            results = script.run()
            
            assert 'success' in results
            assert 'message' in results
            assert 'data' in results
    
    def test_validate_environment(self):
        """Test environment validation."""
        with patch('script.RevitAPI'):
            script = BasicScript()
            # Add validation tests here
```

## Best Practices

1. **Error Handling**: Always wrap RevitPy operations in try-catch blocks
2. **Logging**: Use structured logging for debugging and monitoring
3. **Configuration**: Use external configuration files for flexibility
4. **Validation**: Validate inputs and environment before execution
5. **Documentation**: Document your customizations clearly
6. **Testing**: Write tests for your custom logic
7. **Version Control**: Use git to track changes to your script

## Common Use Cases

- **Element Queries**: Find and filter elements by various criteria
- **Parameter Updates**: Bulk update element parameters
- **Data Export**: Export model data to external formats
- **Model Analysis**: Analyze model properties and statistics
- **Quality Checks**: Validate model compliance with standards

## Next Steps

1. **Copy and customize this template** for your specific needs
2. **Explore advanced templates** for more complex scenarios
3. **Review the example projects** for inspiration and patterns
4. **Join the RevitPy community** for support and best practices

This template provides a solid foundation for RevitPy automation scripts while maintaining simplicity and flexibility for customization.