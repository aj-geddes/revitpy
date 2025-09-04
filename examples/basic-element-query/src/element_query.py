"""
Element Query Tool - Core functionality for querying Revit elements.

This module demonstrates best practices for:
- Element collection and filtering
- Parameter access and validation  
- Error handling and logging
- Performance optimization
"""

import logging
import time
from typing import List, Optional, Any, Dict, Union
from pathlib import Path

try:
    # RevitPy imports
    from revitpy import RevitAPI, Element, FilteredElementCollector
    from revitpy.exceptions import RevitPyException
    from revitpy.utils import TransactionManager
except ImportError:
    # Mock imports for development/testing
    from .utils import MockRevitPy as RevitAPI
    from .utils import MockElement as Element
    from .utils import MockFilteredElementCollector as FilteredElementCollector
    from .utils import MockRevitPyException as RevitPyException
    from .utils import MockTransactionManager as TransactionManager

from .utils import setup_logging, format_element_data


class ElementQueryTool:
    """
    A comprehensive tool for querying and analyzing Revit elements.
    
    This class demonstrates best practices for:
    - Element collection and filtering
    - Parameter access and validation
    - Error handling and logging
    - Performance optimization
    - Result export and reporting
    """
    
    def __init__(self, log_level: str = "INFO", config_file: Optional[str] = None):
        """
        Initialize the Element Query Tool.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            config_file: Optional configuration file path
        """
        self.logger = setup_logging(log_level)
        self.config = self._load_config(config_file)
        
        # Initialize RevitPy connection
        try:
            self.revit = RevitAPI()
            self.doc = self.revit.get_active_document()
            
            if not self.doc:
                raise RevitPyException("No active Revit document found")
                
            self.logger.info("Successfully connected to Revit document")
            self.logger.info(f"Document: {self.doc.Title}")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Revit: {str(e)}")
            raise RevitPyException(f"Revit connection failed: {str(e)}")
        
        # Initialize statistics
        self.stats = {
            'queries_executed': 0,
            'elements_processed': 0,
            'errors_encountered': 0,
            'total_processing_time': 0
        }
    
    def get_elements_by_category(self, category_name: str, 
                               include_types: bool = False) -> List[Element]:
        """
        Get all elements of a specific category.
        
        Args:
            category_name: Name of the Revit category (e.g., "Walls", "Doors")
            include_types: Whether to include type elements (families)
            
        Returns:
            List of elements in the specified category
            
        Raises:
            RevitPyException: If category not found or query fails
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Querying elements in category: {category_name}")
            
            # Use FilteredElementCollector for efficient querying
            collector = FilteredElementCollector(self.doc)
            
            # Apply category filter
            if include_types:
                collector = collector.of_category(category_name)
            else:
                collector = collector.of_category(category_name).where_element_is_not_element_type()
            
            elements = collector.to_elements()
            
            # Update statistics
            self.stats['queries_executed'] += 1
            self.stats['elements_processed'] += len(elements)
            self.stats['total_processing_time'] += time.time() - start_time
            
            self.logger.info(f"Found {len(elements)} elements in {category_name}")
            return elements
            
        except Exception as e:
            self.stats['errors_encountered'] += 1
            self.logger.error(f"Failed to query category {category_name}: {str(e)}")
            raise RevitPyException(f"Category query failed: {str(e)}")
    
    def get_elements_by_ids(self, element_ids: List[Union[int, str]]) -> List[Element]:
        """
        Get elements by their IDs.
        
        Args:
            element_ids: List of element IDs (integers or strings)
            
        Returns:
            List of found elements
        """
        elements = []
        
        for element_id in element_ids:
            try:
                if isinstance(element_id, str):
                    element_id = int(element_id)
                
                element = self.doc.GetElement(element_id)
                if element:
                    elements.append(element)
                else:
                    self.logger.warning(f"Element with ID {element_id} not found")
                    
            except Exception as e:
                self.logger.error(f"Error retrieving element {element_id}: {e}")
                self.stats['errors_encountered'] += 1
        
        self.logger.info(f"Retrieved {len(elements)} elements from {len(element_ids)} IDs")
        return elements
    
    def display_element_properties(self, element: Element) -> Dict[str, Any]:
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
                'element_type': self._get_element_type(element),
                'level': self._get_element_level(element),
                'location': self._get_element_location(element),
                'geometry': self._get_element_geometry_info(element),
                'parameters': self._get_element_parameters(element),
                'materials': self._get_element_materials(element)
            }
            
            # Format and log the properties
            formatted_info = format_element_data(properties)
            self.logger.info(f"Element Analysis: {formatted_info}")
            
            return properties
            
        except Exception as e:
            self.logger.error(f"Failed to get properties for element {element.Id}: {str(e)}")
            self.stats['errors_encountered'] += 1
            return {}
    
    def get_element_parameters(self, element: Element, 
                             parameter_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get specific parameters from an element.
        
        Args:
            element: Revit element
            parameter_names: List of specific parameter names to retrieve (all if None)
            
        Returns:
            Dictionary of parameter names and values
        """
        parameters = {}
        
        try:
            if parameter_names:
                # Get specific parameters
                for param_name in parameter_names:
                    param = element.LookupParameter(param_name)
                    if param:
                        parameters[param_name] = self._get_parameter_value(param)
                    else:
                        parameters[param_name] = None
                        self.logger.debug(f"Parameter '{param_name}' not found on element {element.Id}")
            else:
                # Get all parameters
                for param in element.Parameters:
                    param_name = param.Definition.Name
                    parameters[param_name] = self._get_parameter_value(param)
            
            return parameters
            
        except Exception as e:
            self.logger.error(f"Error getting parameters for element {element.Id}: {e}")
            return {}
    
    def search_elements_by_name(self, name_pattern: str, 
                              case_sensitive: bool = False) -> List[Element]:
        """
        Search for elements by name pattern.
        
        Args:
            name_pattern: Pattern to search for in element names
            case_sensitive: Whether search should be case sensitive
            
        Returns:
            List of matching elements
        """
        matching_elements = []
        
        try:
            # Get all elements
            collector = FilteredElementCollector(self.doc)
            all_elements = collector.where_element_is_not_element_type().to_elements()
            
            if not case_sensitive:
                name_pattern = name_pattern.lower()
            
            for element in all_elements:
                element_name = element.Name or ""
                
                if not case_sensitive:
                    element_name = element_name.lower()
                
                if name_pattern in element_name:
                    matching_elements.append(element)
            
            self.logger.info(f"Found {len(matching_elements)} elements matching '{name_pattern}'")
            return matching_elements
            
        except Exception as e:
            self.logger.error(f"Error searching elements by name: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get query tool usage statistics.
        
        Returns:
            Dictionary with usage statistics
        """
        return {
            **self.stats,
            'average_processing_time': (
                self.stats['total_processing_time'] / max(self.stats['queries_executed'], 1)
            ),
            'error_rate': (
                self.stats['errors_encountered'] / max(self.stats['elements_processed'], 1) * 100
            )
        }
    
    def reset_statistics(self):
        """Reset usage statistics."""
        self.stats = {
            'queries_executed': 0,
            'elements_processed': 0,
            'errors_encountered': 0,
            'total_processing_time': 0
        }
        self.logger.info("Statistics reset")
    
    # Private helper methods
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        default_config = {
            'max_results': 10000,
            'timeout': 300,
            'include_geometry': True,
            'include_materials': True,
            'batch_size': 100
        }
        
        if config_file:
            try:
                import yaml
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                return {**default_config, **config}
            except Exception as e:
                self.logger.warning(f"Failed to load config file {config_file}: {e}")
        
        return default_config
    
    def _get_element_type(self, element: Element) -> Optional[str]:
        """Get the element type name."""
        try:
            element_type = element.GetTypeId()
            if element_type and element_type.IntegerValue != -1:
                type_element = self.doc.GetElement(element_type)
                return type_element.Name if type_element else None
            return None
        except:
            return None
    
    def _get_element_level(self, element: Element) -> Optional[str]:
        """Get the level name associated with the element."""
        try:
            level_param = element.LookupParameter("Level")
            if level_param and level_param.HasValue:
                level_id = level_param.AsElementId()
                if level_id and level_id.IntegerValue != -1:
                    level = self.doc.GetElement(level_id)
                    return level.Name if level else None
            return None
        except:
            return None
    
    def _get_element_location(self, element: Element) -> Optional[Dict[str, float]]:
        """Get element location information."""
        try:
            location = element.Location
            if location:
                # Handle different location types
                if hasattr(location, 'Point'):
                    # LocationPoint
                    point = location.Point
                    return {
                        'type': 'Point',
                        'x': point.X,
                        'y': point.Y,
                        'z': point.Z
                    }
                elif hasattr(location, 'Curve'):
                    # LocationCurve
                    curve = location.Curve
                    start = curve.GetEndPoint(0)
                    end = curve.GetEndPoint(1)
                    return {
                        'type': 'Curve',
                        'start': {'x': start.X, 'y': start.Y, 'z': start.Z},
                        'end': {'x': end.X, 'y': end.Y, 'z': end.Z},
                        'length': curve.Length
                    }
            return None
        except:
            return None
    
    def _get_element_geometry_info(self, element: Element) -> Optional[Dict[str, Any]]:
        """Get basic geometry information."""
        if not self.config.get('include_geometry', True):
            return None
            
        try:
            geometry_info = {}
            
            # Get bounding box
            bbox = element.get_BoundingBox(None)
            if bbox:
                geometry_info['bounding_box'] = {
                    'min': {'x': bbox.Min.X, 'y': bbox.Min.Y, 'z': bbox.Min.Z},
                    'max': {'x': bbox.Max.X, 'y': bbox.Max.Y, 'z': bbox.Max.Z}
                }
            
            # Get geometry element
            geometry = element.get_Geometry(None)
            if geometry:
                geometry_info['has_geometry'] = True
                geometry_info['geometry_objects'] = sum(1 for _ in geometry)
            
            return geometry_info if geometry_info else None
            
        except:
            return None
    
    def _get_element_parameters(self, element: Element) -> Dict[str, Any]:
        """Get all parameters for an element."""
        parameters = {}
        
        try:
            for param in element.Parameters:
                param_name = param.Definition.Name
                parameters[param_name] = self._get_parameter_value(param)
            
            return parameters
            
        except Exception as e:
            self.logger.error(f"Error getting parameters: {e}")
            return {}
    
    def _get_parameter_value(self, parameter) -> Any:
        """Get the value from a parameter based on its storage type."""
        try:
            if not parameter.HasValue:
                return None
            
            storage_type = parameter.StorageType
            
            if storage_type.ToString() == "String":
                return parameter.AsString()
            elif storage_type.ToString() == "Integer":
                return parameter.AsInteger()
            elif storage_type.ToString() == "Double":
                return parameter.AsDouble()
            elif storage_type.ToString() == "ElementId":
                element_id = parameter.AsElementId()
                if element_id and element_id.IntegerValue != -1:
                    referenced_element = self.doc.GetElement(element_id)
                    return referenced_element.Name if referenced_element else str(element_id.IntegerValue)
                return None
            else:
                return parameter.AsValueString()
                
        except Exception as e:
            self.logger.debug(f"Error getting parameter value: {e}")
            return None
    
    def _get_element_materials(self, element: Element) -> Optional[List[str]]:
        """Get materials associated with the element."""
        if not self.config.get('include_materials', True):
            return None
            
        try:
            materials = []
            
            # Get material IDs from element
            material_ids = element.GetMaterialIds(False)
            
            for material_id in material_ids:
                if material_id and material_id.IntegerValue != -1:
                    material = self.doc.GetElement(material_id)
                    if material:
                        materials.append(material.Name)
            
            return materials if materials else None
            
        except:
            return None