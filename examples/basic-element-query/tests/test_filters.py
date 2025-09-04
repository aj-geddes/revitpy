"""
Unit tests for CustomElementFilter and filter conditions.

These tests demonstrate comprehensive testing of filtering functionality:
- Parameter filtering
- Geometry filtering
- Category filtering
- Complex filter combinations
"""

import unittest
from unittest.mock import Mock, patch
import pytest

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.filters import (
    CustomElementFilter, 
    ParameterFilter, 
    GeometryFilter, 
    CategoryFilter
)
from src.utils import MockElement, MockParameter


class TestParameterFilter(unittest.TestCase):
    """Test suite for ParameterFilter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.elements = [
            MockElement(1, "Walls", "Wall A"),
            MockElement(2, "Walls", "Wall B"),  
            MockElement(3, "Doors", "Door A")
        ]
        
        # Add custom parameters to elements
        self.elements[0].Parameters.append(MockParameter("Type Mark", "W1"))
        self.elements[0].Parameters.append(MockParameter("Area", 100.5))
        
        self.elements[1].Parameters.append(MockParameter("Type Mark", "W2"))
        self.elements[1].Parameters.append(MockParameter("Area", 75.0))
        
        self.elements[2].Parameters.append(MockParameter("Type Mark", "D1"))
        self.elements[2].Parameters.append(MockParameter("Area", 25.0))
    
    def test_equals_filter_string(self):
        """Test equals comparison with string parameters."""
        filter_condition = ParameterFilter("Type Mark", "W1", "equals")
        
        self.assertTrue(filter_condition.matches(self.elements[0]))
        self.assertFalse(filter_condition.matches(self.elements[1]))
        self.assertFalse(filter_condition.matches(self.elements[2]))
    
    def test_equals_filter_case_insensitive(self):
        """Test case insensitive equals comparison."""
        filter_condition = ParameterFilter("Type Mark", "w1", "equals", case_sensitive=False)
        
        self.assertTrue(filter_condition.matches(self.elements[0]))
        self.assertFalse(filter_condition.matches(self.elements[1]))
    
    def test_contains_filter(self):
        """Test contains comparison."""
        filter_condition = ParameterFilter("Type Mark", "W", "contains")
        
        self.assertTrue(filter_condition.matches(self.elements[0]))  # W1 contains W
        self.assertTrue(filter_condition.matches(self.elements[1]))  # W2 contains W
        self.assertFalse(filter_condition.matches(self.elements[2]))  # D1 doesn't contain W
    
    def test_numeric_comparisons(self):
        """Test numeric comparison filters."""
        # Greater than
        greater_filter = ParameterFilter("Area", 80, "greater")
        self.assertTrue(greater_filter.matches(self.elements[0]))  # 100.5 > 80
        self.assertFalse(greater_filter.matches(self.elements[1]))  # 75 < 80
        
        # Less than
        less_filter = ParameterFilter("Area", 80, "less")
        self.assertFalse(less_filter.matches(self.elements[0]))  # 100.5 > 80
        self.assertTrue(less_filter.matches(self.elements[1]))  # 75 < 80
        
        # Greater or equal
        gte_filter = ParameterFilter("Area", 75, "greater_or_equal")
        self.assertTrue(gte_filter.matches(self.elements[0]))  # 100.5 >= 75
        self.assertTrue(gte_filter.matches(self.elements[1]))  # 75 >= 75
        self.assertFalse(gte_filter.matches(self.elements[2]))  # 25 < 75
    
    def test_not_equals_filter(self):
        """Test not equals comparison."""
        filter_condition = ParameterFilter("Type Mark", "W1", "not_equals")
        
        self.assertFalse(filter_condition.matches(self.elements[0]))
        self.assertTrue(filter_condition.matches(self.elements[1]))
        self.assertTrue(filter_condition.matches(self.elements[2]))
    
    def test_missing_parameter(self):
        """Test behavior with missing parameters."""
        filter_condition = ParameterFilter("NonExistentParam", "value", "equals")
        
        # Should return False for all elements since parameter doesn't exist
        for element in self.elements:
            self.assertFalse(filter_condition.matches(element))
    
    def test_invalid_comparison_type(self):
        """Test invalid comparison type."""
        with pytest.raises(ValueError):
            filter_condition = ParameterFilter("Type Mark", "W1", "invalid_comparison")
            filter_condition.matches(self.elements[0])


class TestGeometryFilter(unittest.TestCase):
    """Test suite for GeometryFilter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.elements = [
            MockElement(1, "Walls", "Wall A"),
            MockElement(2, "Walls", "Wall B"),
            MockElement(3, "Doors", "Door A")
        ]
        
        # Add area parameters
        self.elements[0].Parameters.append(MockParameter("Area", 100.0))
        self.elements[1].Parameters.append(MockParameter("Area", 200.0))
        self.elements[2].Parameters.append(MockParameter("Area", 50.0))
        
        # Add volume parameters  
        self.elements[0].Parameters.append(MockParameter("Volume", 1000.0))
        self.elements[1].Parameters.append(MockParameter("Volume", 2000.0))
        self.elements[2].Parameters.append(MockParameter("Volume", 500.0))
    
    def test_bounds_filter_point_location(self):
        """Test bounds filtering with point locations."""
        bounds = {
            'min': {'x': -5, 'y': -5, 'z': -1},
            'max': {'x': 5, 'y': 5, 'z': 1}
        }
        
        filter_condition = GeometryFilter(bounds=bounds)
        
        # Mock elements have location at (0,0,0) so should be within bounds
        for element in self.elements:
            self.assertTrue(filter_condition.matches(element))
    
    def test_bounds_filter_out_of_bounds(self):
        """Test bounds filtering with out-of-bounds elements."""
        bounds = {
            'min': {'x': 10, 'y': 10, 'z': 10},
            'max': {'x': 20, 'y': 20, 'z': 20}
        }
        
        filter_condition = GeometryFilter(bounds=bounds)
        
        # Mock elements at (0,0,0) should be out of bounds
        for element in self.elements:
            self.assertFalse(filter_condition.matches(element))
    
    def test_area_constraints(self):
        """Test area constraint filtering."""
        # Minimum area filter
        min_area_filter = GeometryFilter(min_area=150.0)
        self.assertFalse(min_area_filter.matches(self.elements[0]))  # 100 < 150
        self.assertTrue(min_area_filter.matches(self.elements[1]))   # 200 > 150
        self.assertFalse(min_area_filter.matches(self.elements[2]))  # 50 < 150
        
        # Maximum area filter
        max_area_filter = GeometryFilter(max_area=150.0)
        self.assertTrue(max_area_filter.matches(self.elements[0]))   # 100 < 150
        self.assertFalse(max_area_filter.matches(self.elements[1]))  # 200 > 150
        self.assertTrue(max_area_filter.matches(self.elements[2]))   # 50 < 150
        
        # Range filter
        range_filter = GeometryFilter(min_area=75.0, max_area=150.0)
        self.assertTrue(range_filter.matches(self.elements[0]))      # 100 in range
        self.assertFalse(range_filter.matches(self.elements[1]))     # 200 > 150
        self.assertFalse(range_filter.matches(self.elements[2]))     # 50 < 75
    
    def test_volume_constraints(self):
        """Test volume constraint filtering."""
        # Minimum volume filter
        min_vol_filter = GeometryFilter(min_volume=1500.0)
        self.assertFalse(min_vol_filter.matches(self.elements[0]))   # 1000 < 1500
        self.assertTrue(min_vol_filter.matches(self.elements[1]))    # 2000 > 1500
        self.assertFalse(min_vol_filter.matches(self.elements[2]))   # 500 < 1500
        
        # Maximum volume filter
        max_vol_filter = GeometryFilter(max_volume=1500.0)
        self.assertTrue(max_vol_filter.matches(self.elements[0]))    # 1000 < 1500
        self.assertFalse(max_vol_filter.matches(self.elements[1]))   # 2000 > 1500
        self.assertTrue(max_vol_filter.matches(self.elements[2]))    # 500 < 1500
    
    def test_combined_constraints(self):
        """Test combined geometry constraints."""
        bounds = {
            'min': {'x': -10, 'y': -10, 'z': -10},
            'max': {'x': 10, 'y': 10, 'z': 10}
        }
        
        filter_condition = GeometryFilter(
            bounds=bounds,
            min_area=75.0,
            max_volume=1500.0
        )
        
        # Element 0: within bounds, area 100 (>75), volume 1000 (<1500) - should match
        self.assertTrue(filter_condition.matches(self.elements[0]))
        
        # Element 1: within bounds, area 200 (>75), volume 2000 (>1500) - should not match
        self.assertFalse(filter_condition.matches(self.elements[1]))
        
        # Element 2: within bounds, area 50 (<75), volume 500 (<1500) - should not match  
        self.assertFalse(filter_condition.matches(self.elements[2]))


class TestCategoryFilter(unittest.TestCase):
    """Test suite for CategoryFilter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.elements = [
            MockElement(1, "Walls", "Wall A"),
            MockElement(2, "Walls", "Wall B"),
            MockElement(3, "Doors", "Door A"),
            MockElement(4, "Windows", "Window A")
        ]
    
    def test_include_single_category(self):
        """Test including a single category."""
        filter_condition = CategoryFilter("Walls")
        
        self.assertTrue(filter_condition.matches(self.elements[0]))
        self.assertTrue(filter_condition.matches(self.elements[1]))
        self.assertFalse(filter_condition.matches(self.elements[2]))
        self.assertFalse(filter_condition.matches(self.elements[3]))
    
    def test_include_multiple_categories(self):
        """Test including multiple categories."""
        filter_condition = CategoryFilter(["Walls", "Doors"])
        
        self.assertTrue(filter_condition.matches(self.elements[0]))
        self.assertTrue(filter_condition.matches(self.elements[1]))
        self.assertTrue(filter_condition.matches(self.elements[2]))
        self.assertFalse(filter_condition.matches(self.elements[3]))
    
    def test_exclude_categories(self):
        """Test excluding categories."""
        filter_condition = CategoryFilter(["Walls"], exclude=True)
        
        self.assertFalse(filter_condition.matches(self.elements[0]))
        self.assertFalse(filter_condition.matches(self.elements[1]))
        self.assertTrue(filter_condition.matches(self.elements[2]))
        self.assertTrue(filter_condition.matches(self.elements[3]))
    
    def test_element_without_category(self):
        """Test element without category."""
        # Create element with no category
        element_no_cat = MockElement(5, None, "No Category Element")
        element_no_cat.Category = None
        
        include_filter = CategoryFilter("Walls")
        exclude_filter = CategoryFilter("Walls", exclude=True)
        
        # Element with no category should not match include filter
        self.assertFalse(include_filter.matches(element_no_cat))
        
        # Element with no category should match exclude filter (no category = excluded from "Walls")
        self.assertTrue(exclude_filter.matches(element_no_cat))


class TestCustomElementFilter(unittest.TestCase):
    """Test suite for CustomElementFilter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.elements = [
            MockElement(1, "Walls", "Exterior Wall"),
            MockElement(2, "Walls", "Interior Wall"),
            MockElement(3, "Doors", "Entry Door"),
            MockElement(4, "Windows", "Window A")
        ]
        
        # Add parameters to elements
        self.elements[0].Parameters.extend([
            MockParameter("Type Mark", "EW1"),
            MockParameter("Area", 150.0),
            MockParameter("Structural Usage", "Bearing")
        ])
        
        self.elements[1].Parameters.extend([
            MockParameter("Type Mark", "IW1"),
            MockParameter("Area", 100.0),
            MockParameter("Structural Usage", "Non-bearing")
        ])
        
        self.elements[2].Parameters.extend([
            MockParameter("Type Mark", "D1"),
            MockParameter("Area", 20.0)
        ])
        
        self.elements[3].Parameters.extend([
            MockParameter("Type Mark", "W1"),
            MockParameter("Area", 15.0)
        ])
    
    def test_single_parameter_filter(self):
        """Test filtering with single parameter condition."""
        element_filter = CustomElementFilter()
        element_filter.add_parameter_filter("Type Mark", "EW1", "equals")
        
        result = element_filter.filter_elements(self.elements)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].Name, "Exterior Wall")
    
    def test_multiple_parameter_filters_and(self):
        """Test multiple parameter filters with AND logic."""
        element_filter = CustomElementFilter()
        element_filter.add_parameter_filter("Area", 75.0, "greater")
        element_filter.add_parameter_filter("Structural Usage", "Bearing", "equals")
        element_filter.set_logic("AND")
        
        result = element_filter.filter_elements(self.elements)
        
        # Only exterior wall has area > 75 AND structural usage = "Bearing"
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].Name, "Exterior Wall")
    
    def test_multiple_parameter_filters_or(self):
        """Test multiple parameter filters with OR logic."""
        element_filter = CustomElementFilter()
        element_filter.add_parameter_filter("Type Mark", "EW1", "equals")
        element_filter.add_parameter_filter("Type Mark", "D1", "equals")
        element_filter.set_logic("OR")
        
        result = element_filter.filter_elements(self.elements)
        
        # Should match exterior wall OR door
        self.assertEqual(len(result), 2)
        names = [e.Name for e in result]
        self.assertIn("Exterior Wall", names)
        self.assertIn("Entry Door", names)
    
    def test_category_and_parameter_filter(self):
        """Test combining category and parameter filters."""
        element_filter = CustomElementFilter()
        element_filter.add_category_filter("Walls")
        element_filter.add_parameter_filter("Area", 120.0, "greater")
        element_filter.set_logic("AND")
        
        result = element_filter.filter_elements(self.elements)
        
        # Only exterior wall is a wall with area > 120
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].Name, "Exterior Wall")
    
    def test_geometry_filter_integration(self):
        """Test geometry filter integration."""
        element_filter = CustomElementFilter()
        element_filter.add_geometry_filter(min_area=50.0, max_area=120.0)
        
        result = element_filter.filter_elements(self.elements)
        
        # Elements with area between 50 and 120: Interior Wall (100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].Name, "Interior Wall")
    
    def test_complex_filter_creation(self):
        """Test complex filter creation with multiple criteria."""
        criteria = {
            'categories': ['Walls', 'Doors'],
            'parameter_filters': [
                {'parameter_name': 'Area', 'value': 30, 'comparison': 'greater'}
            ],
            'logic': 'AND',
            'elements': self.elements
        }
        
        element_filter = CustomElementFilter()
        result = element_filter.create_complex_filter(**criteria)
        
        # Walls and doors with area > 30: both walls and door
        self.assertEqual(len(result), 3)
        names = [e.Name for e in result]
        self.assertIn("Exterior Wall", names)
        self.assertIn("Interior Wall", names)
        self.assertIn("Entry Door", names)
    
    def test_filter_summary(self):
        """Test filter summary generation."""
        element_filter = CustomElementFilter()
        element_filter.add_parameter_filter("Type Mark", "W1", "contains")
        element_filter.add_category_filter(["Walls"], exclude=True)
        element_filter.set_logic("OR")
        
        summary = element_filter.get_filter_summary()
        
        self.assertIn("OR", summary)
        self.assertIn("Parameter 'Type Mark'", summary)
        self.assertIn("Category filter", summary)
        self.assertIn("exclude", summary)
    
    def test_legacy_methods(self):
        """Test legacy filter methods for backward compatibility."""
        element_filter = CustomElementFilter()
        
        # Test filter_by_parameter
        result = element_filter.filter_by_parameter(
            self.elements, "Type Mark", "EW1", "equals"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].Name, "Exterior Wall")
        
        # Test filter_by_location
        bounds = {
            'min': {'x': -10, 'y': -10, 'z': -10},
            'max': {'x': 10, 'y': 10, 'z': 10}
        }
        result = element_filter.filter_by_location(self.elements, bounds)
        # All mock elements are at (0,0,0) so should all be within bounds
        self.assertEqual(len(result), len(self.elements))
    
    def test_no_conditions(self):
        """Test filter with no conditions."""
        element_filter = CustomElementFilter()
        
        result = element_filter.filter_elements(self.elements)
        
        # Should return all elements when no conditions are specified
        self.assertEqual(len(result), len(self.elements))
    
    def test_method_chaining(self):
        """Test method chaining functionality."""
        result = (CustomElementFilter()
                 .add_category_filter("Walls")
                 .add_parameter_filter("Area", 120.0, "greater")
                 .set_logic("AND")
                 .filter_elements(self.elements))
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].Name, "Exterior Wall")
    
    def test_invalid_logic(self):
        """Test invalid logic setting."""
        element_filter = CustomElementFilter()
        
        with pytest.raises(ValueError):
            element_filter.set_logic("INVALID")


if __name__ == '__main__':
    unittest.main()