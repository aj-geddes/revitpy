# Parameter Management Utility

A comprehensive RevitPy example demonstrating advanced parameter management capabilities including reading, writing, validation, and bulk operations on Revit element parameters.

## Features

- **Parameter Reading & Writing**: Access and modify all parameter types
- **Bulk Operations**: Process parameters across multiple elements efficiently
- **Data Validation**: Comprehensive parameter value validation and error handling
- **Import/Export**: CSV and Excel import/export functionality with mapping
- **Shared Parameters**: Create and manage shared parameters and parameter groups
- **Parameter Mapping**: Map external data to Revit parameters with validation
- **Type Parameters**: Handle both instance and type parameters
- **Units Management**: Proper unit handling and conversion
- **Transaction Management**: Safe parameter modifications with rollback capability
- **Audit Trail**: Track parameter changes with comprehensive logging

## What You'll Learn

- How to read and write all Revit parameter types safely
- Best practices for parameter validation and error handling
- Efficient bulk parameter operations and transaction management
- Creating and managing shared parameters programmatically
- Importing/exporting parameter data with proper validation
- Advanced parameter filtering and searching techniques
- Performance optimization for large-scale parameter operations
- Unit handling and conversion between different measurement systems

## Project Structure

```
parameter-management/
├── README.md
├── requirements.txt
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── parameter_manager.py
│   ├── parameter_validator.py
│   ├── bulk_operations.py
│   ├── import_export.py
│   ├── shared_parameters.py
│   └── utils.py
├── tests/
│   ├── __init__.py
│   ├── test_parameter_manager.py
│   ├── test_validator.py
│   └── test_bulk_operations.py
├── config/
│   ├── parameter_config.yaml
│   └── validation_rules.yaml
├── data/
│   ├── sample_parameters.csv
│   ├── parameter_mapping.json
│   └── shared_params_template.txt
└── examples/
    ├── basic_operations.py
    ├── bulk_import_export.py
    ├── shared_param_management.py
    └── validation_examples.py
```

## Quick Start

### Prerequisites

- RevitPy installed and configured
- Revit 2022 or later with an active document
- Python 3.9+

### Installation

1. Navigate to this directory:
   ```bash
   cd /home/aj/hvs/revitpy/examples/parameter-management
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure parameter settings:
   ```bash
   cp config/parameter_config.yaml.example config/parameter_config.yaml
   # Edit configuration as needed
   ```

### Basic Usage

#### Reading Parameters
```python
from src.parameter_manager import ParameterManager

# Initialize manager
param_manager = ParameterManager()

# Get all parameters for an element
element = param_manager.get_element_by_id(123456)
all_params = param_manager.get_all_parameters(element)

# Get specific parameters
specific_params = param_manager.get_parameters(
    element, 
    ["Height", "Width", "Area", "Type Mark"]
)

# Get parameters with metadata
detailed_params = param_manager.get_parameters_detailed(element)
```

#### Writing Parameters
```python
# Set single parameter
param_manager.set_parameter(element, "Type Mark", "W-001")

# Set multiple parameters
parameter_updates = {
    "Comments": "Updated via RevitPy",
    "Mark": "A-001",
    "Phase Created": "New Construction"
}

success = param_manager.set_parameters(element, parameter_updates)
```

#### Bulk Operations
```python
from src.bulk_operations import BulkParameterOperations

bulk_ops = BulkParameterOperations()

# Update multiple elements
elements = param_manager.get_elements_by_category("Walls")
updates = {"Fire Rating": "2 Hour"}

results = bulk_ops.update_parameters_bulk(elements, updates)
```

## Advanced Examples

### 1. Parameter Validation and Error Handling

```python
from src.parameter_validator import ParameterValidator

validator = ParameterValidator()

# Validate parameter values before setting
validation_rules = {
    "Height": {"type": "double", "min": 0, "max": 50},
    "Type Mark": {"type": "string", "pattern": r"^[A-Z]-\d{3}$"},
    "Fire Rating": {"type": "string", "choices": ["1 Hour", "2 Hour", "Non-Rated"]}
}

is_valid, errors = validator.validate_parameters(element, parameter_updates, validation_rules)

if is_valid:
    param_manager.set_parameters(element, parameter_updates)
else:
    print(f"Validation errors: {errors}")
```

### 2. CSV Import/Export with Mapping

```python
from src.import_export import ParameterImportExport

importer = ParameterImportExport()

# Export parameters to CSV
elements = param_manager.get_elements_by_category("Doors")
csv_file = importer.export_to_csv(
    elements,
    parameters=["Type Mark", "Width", "Height", "Fire Rating"],
    output_file="door_parameters.csv"
)

# Import parameters from CSV with validation
import_results = importer.import_from_csv(
    "updated_door_parameters.csv",
    mapping={
        "Element ID": "id",
        "Door Type": "Type Mark", 
        "Door Width": "Width",
        "Door Height": "Height"
    },
    validate=True
)
```

### 3. Shared Parameter Management

```python
from src.shared_parameters import SharedParameterManager

shared_mgr = SharedParameterManager()

# Create new shared parameter
shared_param = shared_mgr.create_shared_parameter(
    name="Custom Rating",
    group="Analysis", 
    parameter_type="Text",
    categories=["Walls", "Floors"]
)

# Add to project
shared_mgr.add_to_project(shared_param, "Instance")

# Bind to categories
shared_mgr.bind_parameter_to_categories(
    shared_param,
    ["Walls", "Floors"],
    binding_type="Instance"
)
```

### 4. Advanced Parameter Operations

```python
# Parameter history tracking
param_manager.enable_change_tracking()

# Make changes
param_manager.set_parameter(element, "Comments", "Updated comment")
param_manager.set_parameter(element, "Phase Created", "Phase 2")

# Get change history
changes = param_manager.get_parameter_changes(element)
for change in changes:
    print(f"{change['parameter']}: {change['old_value']} → {change['new_value']}")

# Rollback changes if needed
param_manager.rollback_changes(element, changes[-1]['timestamp'])
```

### 5. Performance-Optimized Bulk Operations

```python
from src.bulk_operations import BulkParameterOperations

bulk_ops = BulkParameterOperations()

# Process large datasets efficiently
all_walls = param_manager.get_elements_by_category("Walls")

# Batch processing with progress tracking
results = bulk_ops.process_elements_batch(
    elements=all_walls,
    operation="update_parameters",
    parameters={"Fire Rating": "1 Hour", "Comments": "Bulk Update"},
    batch_size=50,
    validate=True,
    show_progress=True
)

print(f"Processed: {results['successful']}, Errors: {results['errors']}")
```

## Data Import/Export Formats

### CSV Format
```csv
Element ID,Category,Type Mark,Width,Height,Area,Comments
123456,Walls,W-001,12.0,9.0,108.0,Exterior wall
123457,Walls,W-002,6.0,9.0,54.0,Interior wall
```

### Excel Format (with multiple sheets)
- **Elements**: Element data and parameters
- **Validation**: Validation rules and constraints
- **Mapping**: Parameter mapping definitions
- **Log**: Import/export operation logs

### JSON Parameter Mapping
```json
{
  "mappings": {
    "external_name": "revit_parameter_name",
    "Wall Type": "Type Mark",
    "Wall Height": "Height", 
    "Wall Width": "Width"
  },
  "validation": {
    "Height": {"min": 0, "max": 50, "units": "feet"},
    "Type Mark": {"pattern": "^[A-Z]-\\d{3}$"}
  }
}
```

## Configuration Options

### Parameter Configuration (`config/parameter_config.yaml`)
```yaml
# General settings
general:
  default_transaction_name: "RevitPy Parameter Update"
  enable_undo: true
  max_batch_size: 100
  timeout_seconds: 300

# Parameter handling
parameters:
  handle_readonly_parameters: "warn"  # ignore, warn, error
  convert_units: true
  validate_before_set: true
  track_changes: false

# Import/Export settings
import_export:
  csv_encoding: "utf-8"
  excel_sheet_names:
    elements: "Elements"
    validation: "Validation"
    mapping: "Mapping"
  backup_before_import: true
  
# Validation settings
validation:
  strict_mode: false
  custom_rules_file: "validation_rules.yaml"
  log_validation_errors: true
```

### Validation Rules (`config/validation_rules.yaml`)
```yaml
parameter_rules:
  Type Mark:
    type: "string"
    required: true
    pattern: "^[A-Z]{1,2}-\\d{3}$"
    
  Height:
    type: "double"
    min_value: 0
    max_value: 50
    units: "feet"
    
  Fire Rating:
    type: "string"
    choices: ["Non-Rated", "1 Hour", "2 Hour", "3 Hour"]
    
  Area:
    type: "double"
    min_value: 0
    readonly: true
```

## Error Handling and Logging

The Parameter Management Utility includes comprehensive error handling:

```python
# Error handling example
try:
    results = param_manager.set_parameters(element, updates)
except ParameterReadOnlyError as e:
    print(f"Cannot modify read-only parameter: {e.parameter_name}")
except ParameterNotFoundError as e:
    print(f"Parameter not found: {e.parameter_name}")
except ParameterValidationError as e:
    print(f"Validation failed: {e.errors}")
except TransactionError as e:
    print(f"Transaction failed: {e.message}")
    # Transaction is automatically rolled back
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/test_parameter_manager.py -v
pytest tests/test_validator.py -v
pytest tests/test_bulk_operations.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Performance Considerations

1. **Batch Operations**: Use bulk operations for multiple elements
2. **Transaction Management**: Group multiple parameter changes in single transactions
3. **Validation**: Balance validation thoroughness with performance needs
4. **Memory Management**: Process large datasets in batches
5. **Caching**: Cache parameter definitions for repeated operations
6. **Progress Tracking**: Use progress indicators for long-running operations

## Best Practices Demonstrated

1. **Safe Parameter Access**: Always check parameter existence and readability
2. **Proper Unit Handling**: Convert units appropriately for different parameter types
3. **Transaction Safety**: Use transactions for all parameter modifications
4. **Comprehensive Validation**: Validate data before attempting modifications
5. **Error Recovery**: Provide rollback capabilities for failed operations
6. **Audit Trails**: Track changes for accountability and debugging
7. **Performance Optimization**: Efficient algorithms for bulk operations
8. **User Feedback**: Progress reporting and clear error messages

## Common Use Cases

- **BIM Data Cleanup**: Standardize parameter values across projects
- **Quality Control**: Validate parameter data against project standards
- **Data Migration**: Import parameter data from external systems
- **Reporting**: Export parameter data for analysis and reporting
- **Automation**: Automate repetitive parameter management tasks
- **Integration**: Sync parameter data with external databases or systems

## Next Steps

After mastering parameter management, explore:
- **Geometry Analysis Extension** for advanced geometric operations
- **Data Export/Import Tool** for comprehensive data workflows  
- **Model Validation Suite** for automated quality control
- **WebView2 UI Panel** for interactive parameter management interfaces

## Troubleshooting

### Common Issues

**Issue**: "Parameter is read-only"
**Solution**: Check parameter definition; use type parameters if instance parameters are read-only

**Issue**: "Invalid parameter value"
**Solution**: Verify data type and units; use validation before setting values

**Issue**: "Transaction failed"
**Solution**: Check for active transactions; ensure proper transaction management

**Issue**: "Shared parameter not found"
**Solution**: Ensure shared parameter file is loaded and parameter is bound to category

## Contributing

Extend this example with additional features:
- Custom validation rules
- Additional import/export formats
- Advanced parameter mapping capabilities
- Integration with external data sources