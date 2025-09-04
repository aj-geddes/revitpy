# Basic Element Query Tool

A comprehensive example demonstrating fundamental RevitPy capabilities for querying and displaying Revit elements. This sample project showcases best practices for element access, filtering, and property management.

## Features

- Basic element querying and filtering
- Element property access and display
- Category-based element selection
- Parameter reading and validation
- Error handling and logging
- Performance monitoring
- Export results to various formats

## What You'll Learn

- How to connect to the Revit API through RevitPy
- Element filtering using built-in and custom filters
- Accessing element properties and parameters
- Best practices for error handling
- Logging and debugging techniques
- Performance optimization strategies

## Project Structure

```
basic-element-query/
├── README.md
├── requirements.txt
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── element_query.py
│   ├── filters.py
│   └── utils.py
├── tests/
│   ├── __init__.py
│   ├── test_element_query.py
│   └── test_filters.py
├── config/
│   └── settings.yaml
└── examples/
    ├── basic_usage.py
    ├── advanced_filtering.py
    └── batch_processing.py
```

## Quick Start

### Prerequisites

- RevitPy installed and configured
- Revit 2022 or later
- Python 3.9+

### Installation

1. Navigate to this directory:
   ```bash
   cd /home/aj/hvs/revitpy/examples/basic-element-query
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure settings (optional):
   ```bash
   cp config/settings.yaml.example config/settings.yaml
   # Edit settings as needed
   ```

### Running the Examples

#### Basic Usage
```python
from src.element_query import ElementQueryTool

# Initialize the tool
query_tool = ElementQueryTool()

# Get all walls in the model
walls = query_tool.get_elements_by_category("Walls")
print(f"Found {len(walls)} walls")

# Display wall properties
for wall in walls[:5]:  # Show first 5
    query_tool.display_element_properties(wall)
```

#### Advanced Filtering
```python
from src.filters import CustomElementFilter

# Create custom filter for specific wall types
wall_filter = CustomElementFilter()
structural_walls = wall_filter.filter_by_parameter(
    elements=walls,
    parameter_name="Structural Usage",
    parameter_value="Bearing"
)

print(f"Found {len(structural_walls)} structural walls")
```

## Code Examples

### 1. Basic Element Querying

```python
import logging
from typing import List, Optional, Any
from revitpy import RevitAPI, Element, FilteredElementCollector
from revitpy.exceptions import RevitPyException

class ElementQueryTool:
    """
    A tool for querying and analyzing Revit elements.
    
    This class demonstrates best practices for:
    - Element collection and filtering
    - Parameter access and validation
    - Error handling and logging
    - Performance optimization
    """
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = self._setup_logging(log_level)
        self.revit = RevitAPI()
        self.doc = self.revit.get_active_document()
        
        if not self.doc:
            raise RevitPyException("No active Revit document found")
    
    def get_elements_by_category(self, category_name: str) -> List[Element]:
        """
        Get all elements of a specific category.
        
        Args:
            category_name: Name of the Revit category (e.g., "Walls", "Doors")
            
        Returns:
            List of elements in the specified category
            
        Raises:
            RevitPyException: If category not found or query fails
        """
        try:
            self.logger.info(f"Querying elements in category: {category_name}")
            
            # Use FilteredElementCollector for efficient querying
            collector = FilteredElementCollector(self.doc)
            
            # Apply category filter
            elements = collector.of_category(category_name).to_elements()
            
            self.logger.info(f"Found {len(elements)} elements in {category_name}")
            return elements
            
        except Exception as e:
            self.logger.error(f"Failed to query category {category_name}: {str(e)}")
            raise RevitPyException(f"Category query failed: {str(e)}")
```

### 2. Element Property Access

```python
def display_element_properties(self, element: Element) -> dict:
    """
    Display comprehensive element properties.
    
    Args:
        element: Revit element to analyze
        
    Returns:
        Dictionary of element properties
    """
    try:
        properties = {
            'id': element.Id.IntegerValue,
            'category': element.Category.Name if element.Category else 'Unknown',
            'name': element.Name or 'Unnamed',
            'level': self._get_element_level(element),
            'location': self._get_element_location(element),
            'parameters': self._get_element_parameters(element)
        }
        
        # Log the properties
        self.logger.info(f"Element {properties['id']} ({properties['category']})")
        self.logger.info(f"  Name: {properties['name']}")
        self.logger.info(f"  Level: {properties['level']}")
        self.logger.info(f"  Parameters: {len(properties['parameters'])}")
        
        return properties
        
    except Exception as e:
        self.logger.error(f"Failed to get properties for element {element.Id}: {str(e)}")
        return {}
```

### 3. Custom Filtering

```python
class CustomElementFilter:
    """
    Custom filtering utilities for Revit elements.
    
    Demonstrates advanced filtering techniques:
    - Parameter-based filtering
    - Geometric filtering
    - Combined filter conditions
    """
    
    def filter_by_parameter(self, elements: List[Element], 
                          parameter_name: str, 
                          parameter_value: Any) -> List[Element]:
        """
        Filter elements by parameter value.
        
        Args:
            elements: List of elements to filter
            parameter_name: Name of parameter to check
            parameter_value: Value to match
            
        Returns:
            Filtered list of elements
        """
        filtered = []
        
        for element in elements:
            try:
                param = element.LookupParameter(parameter_name)
                if param and self._parameter_matches(param, parameter_value):
                    filtered.append(element)
                    
            except Exception as e:
                logging.warning(f"Error accessing parameter {parameter_name} on element {element.Id}: {e}")
        
        return filtered
    
    def filter_by_location(self, elements: List[Element], 
                         bounds: dict) -> List[Element]:
        """
        Filter elements by location bounds.
        
        Args:
            elements: List of elements to filter
            bounds: Dictionary with 'min' and 'max' XYZ coordinates
            
        Returns:
            Elements within the specified bounds
        """
        filtered = []
        
        for element in elements:
            try:
                location = element.Location
                if location and self._is_within_bounds(location, bounds):
                    filtered.append(element)
                    
            except Exception as e:
                logging.warning(f"Error checking location for element {element.Id}: {e}")
        
        return filtered
```

## Advanced Examples

### Batch Processing with Progress Tracking

```python
from tqdm import tqdm
import time

def process_elements_batch(self, elements: List[Element], 
                         batch_size: int = 100) -> dict:
    """
    Process elements in batches with progress tracking.
    
    Args:
        elements: List of elements to process
        batch_size: Number of elements per batch
        
    Returns:
        Dictionary with processing results and statistics
    """
    results = {
        'processed': 0,
        'errors': 0,
        'data': [],
        'processing_time': 0
    }
    
    start_time = time.time()
    
    # Process in batches
    for i in tqdm(range(0, len(elements), batch_size), 
                  desc="Processing elements"):
        batch = elements[i:i + batch_size]
        
        for element in batch:
            try:
                # Process individual element
                element_data = self.display_element_properties(element)
                results['data'].append(element_data)
                results['processed'] += 1
                
            except Exception as e:
                self.logger.error(f"Error processing element {element.Id}: {e}")
                results['errors'] += 1
    
    results['processing_time'] = time.time() - start_time
    
    self.logger.info(f"Batch processing complete:")
    self.logger.info(f"  Processed: {results['processed']} elements")
    self.logger.info(f"  Errors: {results['errors']} elements")
    self.logger.info(f"  Time: {results['processing_time']:.2f} seconds")
    
    return results
```

### Export Results

```python
import json
import csv
from pathlib import Path

def export_results(self, results: dict, format: str = "json", 
                  output_path: str = None) -> str:
    """
    Export query results to various formats.
    
    Args:
        results: Results dictionary from element processing
        format: Export format ('json', 'csv', 'xml')
        output_path: Optional custom output path
        
    Returns:
        Path to the exported file
    """
    if not output_path:
        timestamp = int(time.time())
        output_path = f"element_query_results_{timestamp}.{format}"
    
    output_file = Path(output_path)
    
    try:
        if format.lower() == "json":
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
                
        elif format.lower() == "csv":
            self._export_to_csv(results, output_file)
            
        elif format.lower() == "xml":
            self._export_to_xml(results, output_file)
            
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        self.logger.info(f"Results exported to {output_file}")
        return str(output_file)
        
    except Exception as e:
        self.logger.error(f"Export failed: {e}")
        raise RevitPyException(f"Export failed: {e}")
```

## Testing

This example includes comprehensive tests demonstrating testing best practices:

```python
import unittest
from unittest.mock import Mock, patch
from src.element_query import ElementQueryTool

class TestElementQuery(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_revit = Mock()
        self.mock_doc = Mock()
        
        with patch('src.element_query.RevitAPI', return_value=self.mock_revit):
            self.mock_revit.get_active_document.return_value = self.mock_doc
            self.query_tool = ElementQueryTool()
    
    def test_get_elements_by_category(self):
        """Test basic category querying."""
        # Mock the FilteredElementCollector
        mock_collector = Mock()
        mock_elements = [Mock(), Mock(), Mock()]
        
        with patch('src.element_query.FilteredElementCollector', 
                  return_value=mock_collector):
            mock_collector.of_category.return_value = mock_collector
            mock_collector.to_elements.return_value = mock_elements
            
            result = self.query_tool.get_elements_by_category("Walls")
            
            self.assertEqual(len(result), 3)
            mock_collector.of_category.assert_called_once_with("Walls")
    
    def test_error_handling(self):
        """Test error handling in element queries."""
        with patch('src.element_query.FilteredElementCollector', 
                  side_effect=Exception("Test error")):
            with self.assertRaises(RevitPyException):
                self.query_tool.get_elements_by_category("Walls")

if __name__ == '__main__':
    unittest.main()
```

## Performance Considerations

1. **Efficient Filtering**: Use built-in Revit filters whenever possible
2. **Batch Processing**: Process large element sets in batches
3. **Memory Management**: Clean up references to large objects
4. **Caching**: Cache frequently accessed data
5. **Progress Reporting**: Keep users informed during long operations

## Best Practices Demonstrated

1. **Error Handling**: Comprehensive exception handling with meaningful messages
2. **Logging**: Structured logging for debugging and monitoring
3. **Type Hints**: Full type annotations for better code documentation
4. **Documentation**: Clear docstrings and comments
5. **Testing**: Unit tests with mocking for Revit dependencies
6. **Configuration**: External configuration files for flexibility
7. **Performance**: Efficient algorithms and progress reporting

## Common Issues and Solutions

### Issue: "No active document"
**Solution**: Ensure Revit has an open document before running the script.

### Issue: Parameter not found
**Solution**: Check parameter spelling and availability in the current model.

### Issue: Slow performance
**Solution**: Use more specific filters and batch processing for large datasets.

## Next Steps

After mastering this example, explore:
- Parameter Management Utility
- Geometry Analysis Extension  
- WebView2 UI Panel integration
- Data Export/Import capabilities
- Model Validation techniques

## Contributing

Feel free to extend this example with additional features or improvements. Follow the existing code patterns and ensure all changes include tests.