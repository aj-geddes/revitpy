"""
Utility functions and mock classes for the Basic Element Query Tool.

This module provides:
- Logging configuration
- Data formatting utilities  
- Mock classes for development/testing
- Common helper functions
"""

import logging
import sys
import json
import csv
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored output
init(autoreset=True)


def setup_logging(log_level: str = "INFO", 
                 log_file: Optional[str] = None,
                 format_style: str = "detailed") -> logging.Logger:
    """
    Set up structured logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
        format_style: Logging format style ("simple", "detailed", "json")
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("revitpy.element_query")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatters based on style
    if format_style == "simple":
        formatter = logging.Formatter(
            f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - '
            f'{Fore.YELLOW}%(name)s{Style.RESET_ALL} - '
            f'%(levelname)s - %(message)s'
        )
    elif format_style == "json":
        formatter = JsonFormatter()
    else:  # detailed
        formatter = ColoredFormatter(
            f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - '
            f'{Fore.YELLOW}%(name)s{Style.RESET_ALL} - '
            f'%(levelname)s - {Fore.GREEN}%(funcName)s:%(lineno)d{Style.RESET_ALL} - %(message)s'
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        ))
        logger.addHandler(file_handler)
    
    return logger


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored output based on log level."""
    
    COLORS = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.MAGENTA,
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{log_color}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_entry = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


def format_element_data(properties: Dict[str, Any], 
                       format_type: str = "summary") -> str:
    """
    Format element data for display.
    
    Args:
        properties: Element properties dictionary
        format_type: Format type ("summary", "detailed", "json")
        
    Returns:
        Formatted string representation
    """
    if format_type == "json":
        return json.dumps(properties, indent=2, default=str)
    
    elif format_type == "detailed":
        lines = []
        lines.append(f"Element ID: {properties.get('id', 'Unknown')}")
        lines.append(f"Category: {properties.get('category', 'Unknown')}")
        lines.append(f"Name: {properties.get('name', 'Unnamed')}")
        lines.append(f"Type: {properties.get('element_type', 'Unknown')}")
        lines.append(f"Level: {properties.get('level', 'Unknown')}")
        
        # Location information
        location = properties.get('location')
        if location:
            if location.get('type') == 'Point':
                lines.append(f"Location: ({location['x']:.2f}, {location['y']:.2f}, {location['z']:.2f})")
            elif location.get('type') == 'Curve':
                lines.append(f"Start: ({location['start']['x']:.2f}, {location['start']['y']:.2f}, {location['start']['z']:.2f})")
                lines.append(f"End: ({location['end']['x']:.2f}, {location['end']['y']:.2f}, {location['end']['z']:.2f})")
                lines.append(f"Length: {location.get('length', 0):.2f}")
        
        # Parameters
        parameters = properties.get('parameters', {})
        if parameters:
            lines.append("Parameters:")
            for param_name, param_value in list(parameters.items())[:5]:  # Show first 5
                lines.append(f"  {param_name}: {param_value}")
            if len(parameters) > 5:
                lines.append(f"  ... and {len(parameters) - 5} more parameters")
        
        # Materials
        materials = properties.get('materials')
        if materials:
            lines.append(f"Materials: {', '.join(materials)}")
        
        return "\n".join(lines)
    
    else:  # summary
        return (f"Element {properties.get('id')} ({properties.get('category')}) - "
                f"{properties.get('name', 'Unnamed')}")


def export_to_file(data: Union[List[Dict], Dict], 
                  output_path: Union[str, Path],
                  file_format: str = "json") -> bool:
    """
    Export data to various file formats.
    
    Args:
        data: Data to export
        output_path: Output file path
        file_format: Export format ("json", "csv", "xml")
        
    Returns:
        True if successful, False otherwise
    """
    output_path = Path(output_path)
    
    try:
        if file_format.lower() == "json":
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        
        elif file_format.lower() == "csv":
            if isinstance(data, list) and data:
                with open(output_path, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
            else:
                raise ValueError("CSV export requires a list of dictionaries")
        
        elif file_format.lower() == "xml":
            _export_to_xml(data, output_path)
        
        else:
            raise ValueError(f"Unsupported format: {file_format}")
        
        return True
        
    except Exception as e:
        logging.error(f"Export failed: {e}")
        return False


def _export_to_xml(data: Union[List[Dict], Dict], output_path: Path):
    """Export data to XML format."""
    root = ET.Element("elements")
    
    if isinstance(data, list):
        for item in data:
            element = ET.SubElement(root, "element")
            _dict_to_xml(item, element)
    else:
        _dict_to_xml(data, root)
    
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)


def _dict_to_xml(dictionary: Dict, parent: ET.Element):
    """Convert dictionary to XML elements."""
    for key, value in dictionary.items():
        child = ET.SubElement(parent, str(key).replace(' ', '_'))
        
        if isinstance(value, dict):
            _dict_to_xml(value, child)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    sub_child = ET.SubElement(child, "item")
                    _dict_to_xml(item, sub_child)
                else:
                    sub_child = ET.SubElement(child, "item")
                    sub_child.text = str(item)
        else:
            child.text = str(value) if value is not None else ""


def validate_element_data(element_data: Dict[str, Any]) -> List[str]:
    """
    Validate element data and return list of issues.
    
    Args:
        element_data: Element data dictionary
        
    Returns:
        List of validation issues (empty if valid)
    """
    issues = []
    
    # Required fields
    required_fields = ['id', 'category']
    for field in required_fields:
        if field not in element_data or element_data[field] is None:
            issues.append(f"Missing required field: {field}")
    
    # Data type validation
    if 'id' in element_data:
        try:
            int(element_data['id'])
        except (ValueError, TypeError):
            issues.append("Element ID must be a valid integer")
    
    # Location validation
    if 'location' in element_data and element_data['location']:
        location = element_data['location']
        if 'type' not in location:
            issues.append("Location missing type information")
        elif location['type'] == 'Point':
            for coord in ['x', 'y', 'z']:
                if coord not in location:
                    issues.append(f"Point location missing {coord} coordinate")
        elif location['type'] == 'Curve':
            for endpoint in ['start', 'end']:
                if endpoint not in location:
                    issues.append(f"Curve location missing {endpoint} point")
    
    return issues


def get_performance_stats(func):
    """Decorator to collect performance statistics."""
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        # Log performance data
        logger = logging.getLogger(__name__)
        logger.debug(f"{func.__name__} took {end_time - start_time:.4f} seconds")
        
        return result
    
    return wrapper


# Mock classes for development and testing

class MockRevitPy:
    """Mock RevitPy API for development and testing."""
    
    def get_active_document(self):
        return MockDocument()


class MockDocument:
    """Mock Revit document."""
    
    def __init__(self):
        self.Title = "Mock Document"
        self._elements = self._create_mock_elements()
    
    def GetElement(self, element_id):
        """Get element by ID."""
        for element in self._elements:
            if element.Id.IntegerValue == int(element_id):
                return element
        return None
    
    def _create_mock_elements(self):
        """Create mock elements for testing."""
        elements = []
        
        # Create mock walls
        for i in range(1, 6):
            element = MockElement(i, "Walls", f"Wall {i}")
            elements.append(element)
        
        # Create mock doors
        for i in range(6, 9):
            element = MockElement(i, "Doors", f"Door {i-5}")
            elements.append(element)
        
        return elements


class MockElement:
    """Mock Revit element."""
    
    def __init__(self, element_id: int, category: str, name: str):
        self.Id = MockElementId(element_id)
        self.Category = MockCategory(category)
        self.Name = name
        self.Location = MockLocation()
        self.Parameters = [MockParameter("Height", 3000), MockParameter("Width", 1000)]
    
    def LookupParameter(self, param_name: str):
        """Look up parameter by name."""
        for param in self.Parameters:
            if param.Definition.Name == param_name:
                return param
        return None
    
    def GetTypeId(self):
        return MockElementId(-1)
    
    def get_BoundingBox(self, view):
        return MockBoundingBox()
    
    def get_Geometry(self, options):
        return MockGeometryElement()
    
    def GetMaterialIds(self, paint_materials):
        return [MockElementId(100), MockElementId(101)]


class MockElementId:
    """Mock element ID."""
    
    def __init__(self, value: int):
        self.IntegerValue = value


class MockCategory:
    """Mock category."""
    
    def __init__(self, name: str):
        self.Name = name


class MockLocation:
    """Mock location."""
    
    def __init__(self):
        self.Point = MockXYZ(0, 0, 0)


class MockXYZ:
    """Mock XYZ point."""
    
    def __init__(self, x: float, y: float, z: float):
        self.X = x
        self.Y = y
        self.Z = z


class MockParameter:
    """Mock parameter."""
    
    def __init__(self, name: str, value: Any):
        self.Definition = MockParameterDefinition(name)
        self._value = value
        self.HasValue = True
        self.StorageType = MockStorageType("Double" if isinstance(value, (int, float)) else "String")
    
    def AsString(self):
        return str(self._value)
    
    def AsInteger(self):
        return int(self._value)
    
    def AsDouble(self):
        return float(self._value)
    
    def AsElementId(self):
        return MockElementId(int(self._value) if isinstance(self._value, (int, float)) else -1)
    
    def AsValueString(self):
        return str(self._value)


class MockParameterDefinition:
    """Mock parameter definition."""
    
    def __init__(self, name: str):
        self.Name = name


class MockStorageType:
    """Mock storage type."""
    
    def __init__(self, type_name: str):
        self._type_name = type_name
    
    def ToString(self):
        return self._type_name


class MockBoundingBox:
    """Mock bounding box."""
    
    def __init__(self):
        self.Min = MockXYZ(-10, -10, 0)
        self.Max = MockXYZ(10, 10, 10)


class MockBoundingBoxXYZ:
    """Mock bounding box XYZ."""
    
    def __init__(self):
        self.Min = MockXYZ(-10, -10, 0)
        self.Max = MockXYZ(10, 10, 10)


class MockGeometryElement:
    """Mock geometry element."""
    
    def __iter__(self):
        return iter([MockGeometryObject(), MockGeometryObject()])


class MockGeometryObject:
    """Mock geometry object."""
    pass


class MockFilteredElementCollector:
    """Mock filtered element collector."""
    
    def __init__(self, document):
        self.document = document
        self._elements = document._elements
    
    def of_category(self, category_name: str):
        """Filter by category."""
        filtered = [e for e in self._elements if e.Category.Name == category_name]
        new_collector = MockFilteredElementCollector(self.document)
        new_collector._elements = filtered
        return new_collector
    
    def where_element_is_not_element_type(self):
        """Filter out element types."""
        return self
    
    def to_elements(self):
        """Return elements list."""
        return self._elements


class MockRevitPyException(Exception):
    """Mock RevitPy exception."""
    pass


class MockTransactionManager:
    """Mock transaction manager."""
    
    def __init__(self, document):
        self.document = document
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass