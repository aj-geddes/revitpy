"""
Unit tests for ElementQueryTool.

These tests demonstrate best practices for testing RevitPy applications:
- Mocking Revit API dependencies
- Testing error handling
- Validating data processing
- Performance testing
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.element_query import ElementQueryTool
from src.utils import MockDocument, MockElement, MockRevitPy


class TestElementQueryTool(unittest.TestCase):
    """Test suite for ElementQueryTool class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock RevitPy environment
        self.mock_revit = MockRevitPy()
        self.mock_doc = MockDocument()

        # Patch RevitPy imports
        with patch("src.element_query.RevitAPI", return_value=self.mock_revit):
            self.mock_revit.get_active_document = Mock(return_value=self.mock_doc)
            self.query_tool = ElementQueryTool(
                log_level="ERROR"
            )  # Suppress logs in tests

    def test_initialization_success(self):
        """Test successful initialization."""
        self.assertIsNotNone(self.query_tool.revit)
        self.assertIsNotNone(self.query_tool.doc)
        self.assertEqual(self.query_tool.doc.Title, "Mock Document")
        self.assertEqual(self.query_tool.stats["queries_executed"], 0)

    def test_initialization_no_document(self):
        """Test initialization failure when no document is available."""
        with patch("src.element_query.RevitAPI") as mock_api:
            mock_api.return_value.get_active_document.return_value = None

            with pytest.raises(Exception):  # Should raise RevitPyException
                ElementQueryTool()

    def test_get_elements_by_category_success(self):
        """Test successful element querying by category."""
        # Mock FilteredElementCollector
        with patch("src.element_query.FilteredElementCollector") as mock_collector:
            mock_elements = [
                MockElement(1, "Walls", "Wall 1"),
                MockElement(2, "Walls", "Wall 2"),
            ]

            mock_collector_instance = Mock()
            mock_collector.return_value = mock_collector_instance
            mock_collector_instance.of_category.return_value = mock_collector_instance
            mock_collector_instance.where_element_is_not_element_type.return_value = (
                mock_collector_instance
            )
            mock_collector_instance.to_elements.return_value = mock_elements

            result = self.query_tool.get_elements_by_category("Walls")

            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].Name, "Wall 1")
            self.assertEqual(result[1].Name, "Wall 2")
            self.assertEqual(self.query_tool.stats["queries_executed"], 1)
            self.assertEqual(self.query_tool.stats["elements_processed"], 2)

    def test_get_elements_by_category_with_types(self):
        """Test element querying including element types."""
        with patch("src.element_query.FilteredElementCollector") as mock_collector:
            mock_elements = [MockElement(1, "Walls", "Wall Type 1")]

            mock_collector_instance = Mock()
            mock_collector.return_value = mock_collector_instance
            mock_collector_instance.of_category.return_value = mock_collector_instance
            mock_collector_instance.to_elements.return_value = mock_elements

            result = self.query_tool.get_elements_by_category(
                "Walls", include_types=True
            )

            self.assertEqual(len(result), 1)
            # Verify that where_element_is_not_element_type was NOT called
            mock_collector_instance.where_element_is_not_element_type.assert_not_called()

    def test_get_elements_by_category_error(self):
        """Test error handling in category querying."""
        with patch(
            "src.element_query.FilteredElementCollector",
            side_effect=Exception("Test error"),
        ):
            with pytest.raises(Exception):  # Should raise RevitPyException
                self.query_tool.get_elements_by_category("InvalidCategory")

            self.assertEqual(self.query_tool.stats["errors_encountered"], 1)

    def test_get_elements_by_ids_success(self):
        """Test successful element retrieval by IDs."""

        # Mock document GetElement method
        def mock_get_element(element_id):
            if element_id == 1:
                return MockElement(1, "Walls", "Wall 1")
            elif element_id == 2:
                return MockElement(2, "Doors", "Door 1")
            return None

        self.mock_doc.GetElement = Mock(side_effect=mock_get_element)

        result = self.query_tool.get_elements_by_ids([1, 2, 999])  # 999 doesn't exist

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].Id.IntegerValue, 1)
        self.assertEqual(result[1].Id.IntegerValue, 2)

    def test_get_elements_by_ids_string_conversion(self):
        """Test element retrieval with string IDs."""

        def mock_get_element(element_id):
            if element_id == 1:
                return MockElement(1, "Walls", "Wall 1")
            return None

        self.mock_doc.GetElement = Mock(side_effect=mock_get_element)

        result = self.query_tool.get_elements_by_ids(["1"])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].Id.IntegerValue, 1)

    def test_display_element_properties(self):
        """Test element property display."""
        element = MockElement(123, "Walls", "Test Wall")

        properties = self.query_tool.display_element_properties(element)

        self.assertIsInstance(properties, dict)
        self.assertEqual(properties["id"], 123)
        self.assertEqual(properties["category"], "Walls")
        self.assertEqual(properties["name"], "Test Wall")
        self.assertIn("parameters", properties)
        self.assertIn("location", properties)

    def test_display_element_properties_error(self):
        """Test error handling in property display."""
        # Create a mock element that raises exceptions
        mock_element = Mock()
        mock_element.Id.IntegerValue = 123
        mock_element.Category = None
        mock_element.Name = None

        # Make property access raise an exception
        mock_element.Location = Mock(side_effect=Exception("Test error"))

        properties = self.query_tool.display_element_properties(mock_element)

        # Should return empty dict on error
        self.assertEqual(properties, {})
        self.assertGreater(self.query_tool.stats["errors_encountered"], 0)

    def test_get_element_parameters(self):
        """Test parameter retrieval."""
        element = MockElement(1, "Walls", "Test Wall")

        # Test getting all parameters
        all_params = self.query_tool.get_element_parameters(element)
        self.assertIsInstance(all_params, dict)
        self.assertIn("Height", all_params)
        self.assertIn("Width", all_params)

        # Test getting specific parameters
        specific_params = self.query_tool.get_element_parameters(
            element, ["Height", "NonExistent"]
        )
        self.assertEqual(specific_params["Height"], 3000.0)
        self.assertIsNone(specific_params["NonExistent"])

    def test_search_elements_by_name(self):
        """Test element search by name pattern."""
        with patch("src.element_query.FilteredElementCollector") as mock_collector:
            mock_elements = [
                MockElement(1, "Walls", "Wall Type A"),
                MockElement(2, "Walls", "Wall Type B"),
                MockElement(3, "Doors", "Door Type A"),
            ]

            mock_collector_instance = Mock()
            mock_collector.return_value = mock_collector_instance
            mock_collector_instance.where_element_is_not_element_type.return_value = (
                mock_collector_instance
            )
            mock_collector_instance.to_elements.return_value = mock_elements

            # Case insensitive search
            result = self.query_tool.search_elements_by_name("wall")
            self.assertEqual(len(result), 2)

            # Case sensitive search
            result = self.query_tool.search_elements_by_name(
                "Wall", case_sensitive=True
            )
            self.assertEqual(len(result), 2)

            # No matches
            result = self.query_tool.search_elements_by_name("xyz")
            self.assertEqual(len(result), 0)

    def test_get_statistics(self):
        """Test statistics retrieval."""
        # Initial statistics
        stats = self.query_tool.get_statistics()
        self.assertEqual(stats["queries_executed"], 0)
        self.assertEqual(stats["elements_processed"], 0)
        self.assertEqual(stats["errors_encountered"], 0)

        # After a query
        with patch("src.element_query.FilteredElementCollector") as mock_collector:
            mock_collector_instance = Mock()
            mock_collector.return_value = mock_collector_instance
            mock_collector_instance.of_category.return_value = mock_collector_instance
            mock_collector_instance.where_element_is_not_element_type.return_value = (
                mock_collector_instance
            )
            mock_collector_instance.to_elements.return_value = [
                MockElement(1, "Walls", "Wall")
            ]

            self.query_tool.get_elements_by_category("Walls")

        stats = self.query_tool.get_statistics()
        self.assertEqual(stats["queries_executed"], 1)
        self.assertEqual(stats["elements_processed"], 1)
        self.assertGreater(stats["total_processing_time"], 0)
        self.assertGreaterEqual(stats["average_processing_time"], 0)

    def test_reset_statistics(self):
        """Test statistics reset."""
        # Execute a query to generate stats
        with patch("src.element_query.FilteredElementCollector") as mock_collector:
            mock_collector_instance = Mock()
            mock_collector.return_value = mock_collector_instance
            mock_collector_instance.of_category.return_value = mock_collector_instance
            mock_collector_instance.where_element_is_not_element_type.return_value = (
                mock_collector_instance
            )
            mock_collector_instance.to_elements.return_value = [
                MockElement(1, "Walls", "Wall")
            ]

            self.query_tool.get_elements_by_category("Walls")

        # Verify stats are not zero
        self.assertGreater(self.query_tool.stats["queries_executed"], 0)

        # Reset and verify
        self.query_tool.reset_statistics()
        self.assertEqual(self.query_tool.stats["queries_executed"], 0)
        self.assertEqual(self.query_tool.stats["elements_processed"], 0)

    def test_config_loading(self):
        """Test configuration file loading."""
        # Test with missing config file
        query_tool = ElementQueryTool(config_file="nonexistent.yaml")
        self.assertIsNotNone(query_tool.config)
        self.assertIn("max_results", query_tool.config)

        # Test with valid config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
max_results: 5000
timeout: 600
include_geometry: false
            """)
            config_path = f.name

        try:
            with patch("src.element_query.RevitAPI"):
                with patch(
                    "src.element_query.RevitAPI.return_value.get_active_document",
                    return_value=self.mock_doc,
                ):
                    query_tool = ElementQueryTool(config_file=config_path)
                    self.assertEqual(query_tool.config["max_results"], 5000)
                    self.assertEqual(query_tool.config["timeout"], 600)
                    self.assertFalse(query_tool.config["include_geometry"])
        finally:
            Path(config_path).unlink()

    def test_private_helper_methods(self):
        """Test private helper methods."""
        element = MockElement(1, "Walls", "Test Wall")

        # Test _get_element_type
        element_type = self.query_tool._get_element_type(element)
        self.assertIsNone(element_type)  # Mock returns -1

        # Test _get_element_level
        level = self.query_tool._get_element_level(element)
        self.assertIsNone(level)  # No level parameter in mock

        # Test _get_element_location
        location = self.query_tool._get_element_location(element)
        self.assertIsNotNone(location)
        self.assertEqual(location["type"], "Point")
        self.assertIn("x", location)

        # Test _get_parameter_value
        param = element.Parameters[0]  # Height parameter
        value = self.query_tool._get_parameter_value(param)
        self.assertEqual(value, 3000.0)


class TestElementQueryToolIntegration(unittest.TestCase):
    """Integration tests for ElementQueryTool."""

    def setUp(self):
        """Set up integration test fixtures."""
        # Use mock environment for integration tests
        with patch("src.element_query.RevitAPI") as mock_api:
            mock_doc = MockDocument()
            mock_api.return_value.get_active_document.return_value = mock_doc
            self.query_tool = ElementQueryTool(log_level="ERROR")

    def test_end_to_end_query_workflow(self):
        """Test complete query workflow."""
        with patch("src.element_query.FilteredElementCollector") as mock_collector:
            # Setup mock elements
            mock_elements = [
                MockElement(1, "Walls", "Exterior Wall"),
                MockElement(2, "Walls", "Interior Wall"),
                MockElement(3, "Doors", "Entry Door"),
            ]

            mock_collector_instance = Mock()
            mock_collector.return_value = mock_collector_instance
            mock_collector_instance.of_category.return_value = mock_collector_instance
            mock_collector_instance.where_element_is_not_element_type.return_value = (
                mock_collector_instance
            )
            mock_collector_instance.to_elements.return_value = mock_elements

            # Execute complete workflow
            elements = self.query_tool.get_elements_by_category("Walls")
            self.assertEqual(len(elements), 3)

            # Process element properties
            properties_list = []
            for element in elements:
                properties = self.query_tool.display_element_properties(element)
                properties_list.append(properties)

            self.assertEqual(len(properties_list), 3)

            # Verify statistics
            stats = self.query_tool.get_statistics()
            self.assertGreater(stats["queries_executed"], 0)
            self.assertGreater(stats["elements_processed"], 0)


if __name__ == "__main__":
    unittest.main()
