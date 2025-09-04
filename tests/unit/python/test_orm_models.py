"""Unit tests for RevitPy ORM models and relationships.

This module tests the object-relational mapping functionality
that provides Pythonic access to Revit elements.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from typing import Dict, List, Any

from revitpy.orm.models import Element, Wall, Door, Window, Parameter
from revitpy.orm.session import RevitSession
from revitpy.orm.query import QueryBuilder, ElementQuery
from revitpy.orm.relationships import ElementRelationship
from revitpy.api.exceptions import RevitElementNotFoundError, RevitValidationError


class TestElement:
    """Test suite for base Element ORM model."""
    
    @pytest.fixture
    def mock_element_data(self):
        """Mock element data from Revit."""
        return {
            "Id": 12345,
            "Name": "Test Wall",
            "Category": "Walls",
            "Parameters": {
                "Height": 3000.0,
                "Width": 200.0,
                "Material": "Concrete"
            },
            "Location": {
                "X": 0.0,
                "Y": 0.0,
                "Z": 0.0
            },
            "BoundingBox": {
                "Min": {"X": -100.0, "Y": -100.0, "Z": 0.0},
                "Max": {"X": 100.0, "Y": 100.0, "Z": 3000.0}
            }
        }
    
    @pytest.fixture
    def mock_session(self):
        """Mock RevitSession for testing."""
        session = MagicMock(spec=RevitSession)
        session.api_wrapper = MagicMock()
        session.api_wrapper.call_api = MagicMock()
        return session
    
    @pytest.mark.unit
    def test_element_creation_from_data(self, mock_element_data, mock_session):
        """Test creating Element from Revit data."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        assert element.id == 12345
        assert element.name == "Test Wall"
        assert element.category == "Walls"
        assert element.session == mock_session
        assert not element._dirty
        assert not element._deleted
    
    @pytest.mark.unit
    def test_element_attribute_access(self, mock_element_data, mock_session):
        """Test accessing element attributes."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        # Test direct attribute access
        assert element.height == 3000.0
        assert element.width == 200.0
        assert element.material == "Concrete"
    
    @pytest.mark.unit
    def test_element_attribute_modification(self, mock_element_data, mock_session):
        """Test modifying element attributes."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        # Modify attribute
        element.height = 3500.0
        
        assert element.height == 3500.0
        assert element._dirty
        assert "Height" in element._changed_parameters
    
    @pytest.mark.unit
    def test_element_parameter_access(self, mock_element_data, mock_session):
        """Test accessing parameters through Parameter objects."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        height_param = element.get_parameter("Height")
        assert isinstance(height_param, Parameter)
        assert height_param.name == "Height"
        assert height_param.value == 3000.0
        assert height_param.element == element
    
    @pytest.mark.unit
    def test_element_parameter_modification(self, mock_element_data, mock_session):
        """Test modifying parameters."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        height_param = element.get_parameter("Height")
        height_param.value = 3200.0
        
        assert element.height == 3200.0
        assert element._dirty
    
    @pytest.mark.unit
    def test_element_nonexistent_parameter(self, mock_element_data, mock_session):
        """Test accessing non-existent parameters."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        param = element.get_parameter("NonExistentParam")
        assert param is None
        
        with pytest.raises(AttributeError):
            _ = element.nonexistent_attr
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_element_save(self, mock_element_data, mock_session):
        """Test saving modified element."""
        element = Element.from_data(mock_element_data, session=mock_session)
        element.height = 3500.0
        
        mock_session.api_wrapper.call_api.return_value = {"success": True}
        
        await element.save()
        
        mock_session.api_wrapper.call_api.assert_called_once_with(
            "UpdateElement",
            {
                "elementId": 12345,
                "parameters": {"Height": 3500.0}
            }
        )
        assert not element._dirty
        assert len(element._changed_parameters) == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_element_save_no_changes(self, mock_element_data, mock_session):
        """Test saving element with no changes."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        await element.save()
        
        mock_session.api_wrapper.call_api.assert_not_called()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_element_delete(self, mock_element_data, mock_session):
        """Test deleting element."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        mock_session.api_wrapper.call_api.return_value = {"success": True}
        
        await element.delete()
        
        mock_session.api_wrapper.call_api.assert_called_once_with(
            "DeleteElement",
            {"elementId": 12345}
        )
        assert element._deleted
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_element_refresh(self, mock_element_data, mock_session):
        """Test refreshing element data from Revit."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        # Modify locally
        element.height = 3500.0
        
        # Fresh data from Revit
        fresh_data = mock_element_data.copy()
        fresh_data["Parameters"]["Height"] = 4000.0
        mock_session.api_wrapper.call_api.return_value = fresh_data
        
        await element.refresh()
        
        assert element.height == 4000.0
        assert not element._dirty
        mock_session.api_wrapper.call_api.assert_called_once_with(
            "GetElement",
            {"elementId": 12345}
        )
    
    @pytest.mark.unit
    def test_element_location_property(self, mock_element_data, mock_session):
        """Test element location property."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        location = element.location
        assert location.x == 0.0
        assert location.y == 0.0
        assert location.z == 0.0
    
    @pytest.mark.unit
    def test_element_bounding_box_property(self, mock_element_data, mock_session):
        """Test element bounding box property."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        bbox = element.bounding_box
        assert bbox.min.x == -100.0
        assert bbox.max.z == 3000.0
        assert bbox.volume == 200.0 * 200.0 * 3000.0
    
    @pytest.mark.unit
    def test_element_repr(self, mock_element_data, mock_session):
        """Test element string representation."""
        element = Element.from_data(mock_element_data, session=mock_session)
        
        repr_str = repr(element)
        assert "Element(id=12345" in repr_str
        assert "name='Test Wall'" in repr_str


class TestWallModel:
    """Test suite for Wall model (specialized Element)."""
    
    @pytest.fixture
    def mock_wall_data(self):
        """Mock wall data from Revit."""
        return {
            "Id": 67890,
            "Name": "Basic Wall",
            "Category": "Walls",
            "Parameters": {
                "Height": 3000.0,
                "Width": 200.0,
                "Length": 5000.0,
                "Area": 15.0,  # m²
                "Volume": 3.0,  # m³
                "WallType": "Generic - 200mm",
                "BaseConstraint": "Level 1",
                "TopConstraint": "Level 2",
                "BaseOffset": 0.0,
                "TopOffset": 0.0
            },
            "Location": {
                "StartPoint": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "EndPoint": {"X": 5000.0, "Y": 0.0, "Z": 0.0},
                "Curve": "Line"
            },
            "Compound": {
                "Layers": [
                    {"Material": "Concrete", "Thickness": 200.0}
                ]
            }
        }
    
    @pytest.fixture
    def mock_session(self):
        """Mock RevitSession for testing."""
        session = MagicMock(spec=RevitSession)
        session.api_wrapper = MagicMock()
        return session
    
    @pytest.mark.unit
    def test_wall_creation(self, mock_wall_data, mock_session):
        """Test creating Wall from Revit data."""
        wall = Wall.from_data(mock_wall_data, session=mock_session)
        
        assert isinstance(wall, Wall)
        assert wall.id == 67890
        assert wall.category == "Walls"
        assert wall.height == 3000.0
        assert wall.length == 5000.0
        assert wall.area == 15.0
    
    @pytest.mark.unit
    def test_wall_specific_properties(self, mock_wall_data, mock_session):
        """Test wall-specific properties."""
        wall = Wall.from_data(mock_wall_data, session=mock_session)
        
        assert wall.wall_type == "Generic - 200mm"
        assert wall.base_constraint == "Level 1"
        assert wall.top_constraint == "Level 2"
        assert wall.base_offset == 0.0
        assert wall.top_offset == 0.0
    
    @pytest.mark.unit
    def test_wall_location_curve(self, mock_wall_data, mock_session):
        """Test wall location curve properties."""
        wall = Wall.from_data(mock_wall_data, session=mock_session)
        
        location = wall.location_curve
        assert location.start_point.x == 0.0
        assert location.end_point.x == 5000.0
        assert location.curve_type == "Line"
        assert location.length == 5000.0
    
    @pytest.mark.unit
    def test_wall_compound_structure(self, mock_wall_data, mock_session):
        """Test wall compound structure access."""
        wall = Wall.from_data(mock_wall_data, session=mock_session)
        
        layers = wall.compound_structure.layers
        assert len(layers) == 1
        assert layers[0].material == "Concrete"
        assert layers[0].thickness == 200.0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_wall_relationships(self, mock_wall_data, mock_session):
        """Test wall relationships (doors, windows)."""
        wall = Wall.from_data(mock_wall_data, session=mock_session)
        
        # Mock related elements
        mock_session.api_wrapper.call_api.return_value = [
            {"Id": 1001, "Category": "Doors", "Name": "Single Door"},
            {"Id": 1002, "Category": "Windows", "Name": "Fixed Window"}
        ]
        
        hosted_elements = await wall.get_hosted_elements()
        
        assert len(hosted_elements) == 2
        mock_session.api_wrapper.call_api.assert_called_once_with(
            "GetHostedElements",
            {"hostId": 67890}
        )


class TestParameter:
    """Test suite for Parameter class."""
    
    @pytest.fixture
    def mock_element(self):
        """Mock element for parameter testing."""
        element = MagicMock(spec=Element)
        element.id = 12345
        element._dirty = False
        element._changed_parameters = set()
        return element
    
    @pytest.mark.unit
    def test_parameter_creation(self, mock_element):
        """Test creating Parameter instance."""
        param = Parameter(
            name="Height",
            value=3000.0,
            unit="mm",
            parameter_type="Length",
            element=mock_element,
            read_only=False
        )
        
        assert param.name == "Height"
        assert param.value == 3000.0
        assert param.unit == "mm"
        assert param.parameter_type == "Length"
        assert param.element == mock_element
        assert not param.read_only
    
    @pytest.mark.unit
    def test_parameter_value_modification(self, mock_element):
        """Test modifying parameter value."""
        param = Parameter("Height", 3000.0, element=mock_element)
        
        param.value = 3500.0
        
        assert param.value == 3500.0
        assert mock_element._dirty
        assert "Height" in mock_element._changed_parameters
    
    @pytest.mark.unit
    def test_readonly_parameter_modification(self, mock_element):
        """Test modifying read-only parameter."""
        param = Parameter("Area", 15.0, element=mock_element, read_only=True)
        
        with pytest.raises(RevitValidationError):
            param.value = 20.0
    
    @pytest.mark.unit
    def test_parameter_type_validation(self, mock_element):
        """Test parameter type validation."""
        length_param = Parameter("Height", 3000.0, parameter_type="Length", element=mock_element)
        
        # Valid value
        length_param.value = 3500.0
        
        # Invalid type
        with pytest.raises(RevitValidationError):
            length_param.value = "not a number"
    
    @pytest.mark.unit
    def test_parameter_unit_conversion(self, mock_element):
        """Test parameter unit conversion."""
        param = Parameter("Height", 3000.0, unit="mm", element=mock_element)
        
        # Convert to meters
        meters_value = param.get_value_in_unit("m")
        assert meters_value == 3.0
        
        # Set value in different unit
        param.set_value_in_unit(3.5, "m")
        assert param.value == 3500.0
    
    @pytest.mark.unit
    def test_parameter_repr(self, mock_element):
        """Test parameter string representation."""
        param = Parameter("Height", 3000.0, unit="mm", element=mock_element)
        
        repr_str = repr(param)
        assert "Parameter(name='Height'" in repr_str
        assert "value=3000.0" in repr_str
        assert "unit='mm'" in repr_str


class TestQueryBuilder:
    """Test suite for QueryBuilder class."""
    
    @pytest.fixture
    def mock_session(self):
        """Mock RevitSession for testing."""
        session = MagicMock(spec=RevitSession)
        session.api_wrapper = MagicMock()
        return session
    
    @pytest.mark.unit
    def test_query_builder_creation(self, mock_session):
        """Test creating QueryBuilder."""
        query = QueryBuilder(session=mock_session)
        
        assert query.session == mock_session
        assert len(query._filters) == 0
        assert query._element_type is None
        assert query._limit is None
    
    @pytest.mark.unit
    def test_query_filter_by_category(self, mock_session):
        """Test filtering by category."""
        query = QueryBuilder(session=mock_session)
        result_query = query.filter_by_category("Walls")
        
        assert result_query is query  # Fluent interface
        assert len(query._filters) == 1
        assert query._filters[0]["type"] == "category"
        assert query._filters[0]["value"] == "Walls"
    
    @pytest.mark.unit
    def test_query_filter_by_parameter(self, mock_session):
        """Test filtering by parameter value."""
        query = QueryBuilder(session=mock_session)
        result_query = query.filter_by_parameter("Height", ">", 3000.0)
        
        assert result_query is query
        assert len(query._filters) == 1
        filter_obj = query._filters[0]
        assert filter_obj["type"] == "parameter"
        assert filter_obj["parameter"] == "Height"
        assert filter_obj["operator"] == ">"
        assert filter_obj["value"] == 3000.0
    
    @pytest.mark.unit
    def test_query_chaining(self, mock_session):
        """Test chaining multiple filters."""
        query = (QueryBuilder(session=mock_session)
                .filter_by_category("Walls")
                .filter_by_parameter("Height", ">", 2500.0)
                .filter_by_parameter("Width", "<=", 300.0)
                .limit(10))
        
        assert len(query._filters) == 3
        assert query._limit == 10
    
    @pytest.mark.unit
    def test_query_of_type(self, mock_session):
        """Test filtering by element type."""
        query = QueryBuilder(session=mock_session).of_type(Wall)
        
        assert query._element_type == Wall
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_query_execution(self, mock_session):
        """Test executing query."""
        mock_session.api_wrapper.call_api.return_value = [
            {
                "Id": 1001,
                "Category": "Walls",
                "Name": "Wall 1",
                "Parameters": {"Height": 3000.0}
            },
            {
                "Id": 1002,
                "Category": "Walls",  
                "Name": "Wall 2",
                "Parameters": {"Height": 3200.0}
            }
        ]
        
        query = (QueryBuilder(session=mock_session)
                .filter_by_category("Walls")
                .of_type(Wall))
        
        results = await query.all()
        
        assert len(results) == 2
        assert all(isinstance(result, Wall) for result in results)
        assert results[0].id == 1001
        assert results[1].id == 1002
        
        mock_session.api_wrapper.call_api.assert_called_once_with(
            "QueryElements",
            {
                "filters": [{"type": "category", "value": "Walls"}],
                "element_type": "Wall",
                "limit": None
            }
        )
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_query_first(self, mock_session):
        """Test getting first result from query."""
        mock_session.api_wrapper.call_api.return_value = [
            {
                "Id": 1001,
                "Category": "Walls",
                "Name": "Wall 1",
                "Parameters": {"Height": 3000.0}
            }
        ]
        
        query = QueryBuilder(session=mock_session).filter_by_category("Walls")
        result = await query.first()
        
        assert isinstance(result, Element)
        assert result.id == 1001
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_query_first_no_results(self, mock_session):
        """Test getting first result when no results exist."""
        mock_session.api_wrapper.call_api.return_value = []
        
        query = QueryBuilder(session=mock_session).filter_by_category("NonExistent")
        result = await query.first()
        
        assert result is None
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_query_count(self, mock_session):
        """Test counting query results."""
        mock_session.api_wrapper.call_api.return_value = {"count": 42}
        
        query = QueryBuilder(session=mock_session).filter_by_category("Walls")
        count = await query.count()
        
        assert count == 42
        mock_session.api_wrapper.call_api.assert_called_once_with(
            "CountElements",
            {
                "filters": [{"type": "category", "value": "Walls"}],
                "element_type": None
            }
        )


class TestElementRelationships:
    """Test suite for element relationships."""
    
    @pytest.fixture
    def mock_session(self):
        """Mock RevitSession for testing."""
        session = MagicMock(spec=RevitSession)
        session.api_wrapper = MagicMock()
        return session
    
    @pytest.fixture
    def mock_wall(self, mock_session):
        """Mock wall element."""
        wall_data = {
            "Id": 12345,
            "Category": "Walls",
            "Name": "Test Wall",
            "Parameters": {"Height": 3000.0}
        }
        return Wall.from_data(wall_data, session=mock_session)
    
    @pytest.fixture
    def mock_door(self, mock_session):
        """Mock door element."""
        door_data = {
            "Id": 67890,
            "Category": "Doors",
            "Name": "Test Door",
            "Parameters": {"Height": 2100.0, "HostId": 12345}
        }
        return Door.from_data(door_data, session=mock_session)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_host_relationship(self, mock_wall, mock_door, mock_session):
        """Test host-hosted relationship."""
        mock_session.api_wrapper.call_api.return_value = {
            "Id": 12345,
            "Category": "Walls",
            "Name": "Test Wall",
            "Parameters": {"Height": 3000.0}
        }
        
        # Get host of door
        host = await mock_door.get_host()
        
        assert isinstance(host, Wall)
        assert host.id == 12345
        mock_session.api_wrapper.call_api.assert_called_once_with(
            "GetElement",
            {"elementId": 12345}
        )
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hosted_elements_relationship(self, mock_wall, mock_session):
        """Test getting hosted elements."""
        mock_session.api_wrapper.call_api.return_value = [
            {
                "Id": 67890,
                "Category": "Doors",
                "Name": "Test Door",
                "Parameters": {"Height": 2100.0}
            },
            {
                "Id": 67891,
                "Category": "Windows",
                "Name": "Test Window", 
                "Parameters": {"Height": 1500.0}
            }
        ]
        
        hosted_elements = await mock_wall.get_hosted_elements()
        
        assert len(hosted_elements) == 2
        assert isinstance(hosted_elements[0], Door)
        assert isinstance(hosted_elements[1], Window)
        
    @pytest.mark.unit
    def test_relationship_caching(self, mock_wall):
        """Test that relationships are cached."""
        # This would test the caching mechanism for related elements
        pass


@pytest.mark.performance
class TestORMPerformance:
    """Performance tests for ORM functionality."""
    
    @pytest.mark.asyncio
    async def test_bulk_element_creation_performance(self, performance_monitor):
        """Test performance of creating many elements."""
        with performance_monitor.measure():
            elements = []
            for i in range(1000):
                element_data = {
                    "Id": i,
                    "Category": "Walls",
                    "Name": f"Wall {i}",
                    "Parameters": {"Height": 3000.0 + i}
                }
                elements.append(Element.from_data(element_data))
        
        metrics = performance_monitor.last_metrics
        # Should create 1000 elements in less than 1 second
        assert metrics["execution_time"] < 1.0
    
    @pytest.mark.asyncio 
    async def test_parameter_access_performance(self, performance_monitor):
        """Test performance of parameter access."""
        element_data = {
            "Id": 1,
            "Category": "Walls", 
            "Name": "Test Wall",
            "Parameters": {f"Param{i}": i * 10.0 for i in range(100)}
        }
        element = Element.from_data(element_data)
        
        with performance_monitor.measure():
            # Access all parameters multiple times
            for _ in range(100):
                for i in range(100):
                    _ = getattr(element, f"param{i}", None)
        
        metrics = performance_monitor.last_metrics
        # Should complete parameter access in reasonable time
        assert metrics["execution_time"] < 2.0