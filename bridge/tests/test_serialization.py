"""
Tests for data serialization and deserialization functionality.
"""

import json
from unittest.mock import Mock, patch

import pytest

from ..core.exceptions import SerializationError
from ..serialization.element_serializer import (
    ElementSerializationConfig,
    ElementSerializer,
)
from ..serialization.geometry_serializer import GeometrySerializer
from ..serialization.parameter_serializer import ParameterSerializer


class TestElementSerializer:
    """Test element serialization functionality."""

    @pytest.fixture
    def serializer(self):
        """Create element serializer for testing."""
        config = ElementSerializationConfig(
            compression_enabled=True,
            batch_size=10,
            include_geometry=True,
            include_parameters=True,
        )
        return ElementSerializer(config)

    def test_single_element_serialization(
        self, serializer, mock_revit_element, sample_element_data
    ):
        """Test serializing a single element."""
        # Mock the element extraction
        with patch.object(
            serializer, "_extract_element_data", return_value=sample_element_data
        ):
            serialized = serializer.serialize_element(mock_revit_element)

            assert "id" in serialized
            assert serialized["id"] == "12345"
            assert serialized["category"] == "Walls"
            assert "parameters" in serialized
            assert "geometry" in serialized

    def test_multiple_elements_serialization(self, serializer, mock_revit_elements):
        """Test serializing multiple elements."""
        with patch.object(serializer, "_extract_element_data") as mock_extract:
            # Mock return different data for each element
            mock_extract.side_effect = [
                {"id": f"1000{i}", "category": "TestCategory", "name": f"Element {i}"}
                for i in range(len(mock_revit_elements))
            ]

            serialized = serializer.serialize_elements(mock_revit_elements)

            assert len(serialized) == len(mock_revit_elements)
            assert all("id" in element for element in serialized)

    def test_batch_serialization(self, serializer):
        """Test batch serialization functionality."""
        # Create large number of mock elements
        elements = [Mock() for _ in range(25)]

        with patch.object(serializer, "_extract_element_data") as mock_extract:
            mock_extract.side_effect = [
                {"id": f"batch_{i}", "category": "TestCategory"} for i in range(25)
            ]

            # Process in batches
            batches = list(serializer.serialize_elements_streaming(elements))

            # Should create multiple batches (batch_size=10)
            assert len(batches) >= 3

            # Total elements should match input
            total_elements = sum(len(batch) for batch in batches)
            assert total_elements == 25

    def test_compression_functionality(self, temp_dir):
        """Test compression of serialized data."""
        # Create serializer with compression enabled
        config = ElementSerializationConfig(compression_enabled=True)
        serializer = ElementSerializer(config)

        test_data = {"large_data": "x" * 1000}  # Create compressible data

        compressed_file = temp_dir / "compressed_test.json.gz"
        serializer.save_compressed(test_data, compressed_file)

        assert compressed_file.exists()

        # Verify compressed file is smaller than uncompressed
        uncompressed_size = len(json.dumps(test_data))
        compressed_size = compressed_file.stat().st_size
        assert compressed_size < uncompressed_size

        # Verify data can be loaded back
        loaded_data = serializer.load_compressed(compressed_file)
        assert loaded_data == test_data

    def test_parameter_extraction(self, serializer, mock_revit_element):
        """Test parameter extraction from elements."""
        # Mock parameter values
        mock_param = Mock()
        mock_param.AsString = Mock(return_value="Test Value")
        mock_param.AsDouble = Mock(return_value=123.45)
        mock_param.StorageType = "String"

        mock_revit_element.Parameters = [mock_param]
        mock_revit_element.LookupParameter.return_value = mock_param

        # Test parameter extraction
        with patch.object(serializer, "_get_parameter_info") as mock_param_info:
            mock_param_info.return_value = {
                "name": "Test Parameter",
                "value": "Test Value",
                "type": "Text",
                "unit": None,
            }

            params = serializer._extract_parameters(mock_revit_element)

            assert isinstance(params, dict)
            assert len(params) > 0

    def test_geometry_extraction(self, serializer, mock_revit_element):
        """Test geometry extraction from elements."""
        # Mock geometry
        mock_geometry = Mock()
        mock_geometry.Volume = 1000.0
        mock_geometry.SurfaceArea = 500.0

        mock_revit_element.get_Geometry.return_value = [mock_geometry]

        with patch.object(serializer, "_extract_geometry_data") as mock_geo_extract:
            mock_geo_extract.return_value = {
                "type": "solid",
                "volume": 1000.0,
                "area": 500.0,
            }

            geometry = serializer._extract_geometry(mock_revit_element)

            assert geometry is not None
            assert geometry["volume"] == 1000.0

    def test_serialization_error_handling(self, serializer):
        """Test error handling during serialization."""
        # Create problematic element that will cause errors
        problematic_element = Mock()
        problematic_element.Id.IntegerValue = 999
        problematic_element.Category.Name.side_effect = Exception("Access error")

        with pytest.raises(SerializationError):
            serializer.serialize_element(problematic_element)

    def test_deserialization(self, serializer, sample_element_data):
        """Test deserializing element data."""
        # Test basic deserialization
        element_dict = serializer.deserialize_element(sample_element_data)

        assert element_dict["id"] == sample_element_data["id"]
        assert element_dict["category"] == sample_element_data["category"]
        assert "parameters" in element_dict
        assert "geometry" in element_dict

    def test_format_version_handling(self, serializer):
        """Test handling of different format versions."""
        # Test current version
        data_v1 = {"format_version": "1.0", "id": "123", "category": "Walls"}
        result = serializer.deserialize_element(data_v1)
        assert result is not None

        # Test unsupported version
        data_future = {"format_version": "2.0", "id": "123", "category": "Walls"}
        with pytest.raises(SerializationError):
            serializer.deserialize_element(data_future)


class TestGeometrySerializer:
    """Test geometry serialization functionality."""

    @pytest.fixture
    def geometry_serializer(self):
        """Create geometry serializer for testing."""
        return GeometrySerializer()

    def test_solid_geometry_serialization(self, geometry_serializer):
        """Test serializing solid geometry."""
        # Mock solid geometry
        mock_solid = Mock()
        mock_solid.Volume = 1000.0
        mock_solid.SurfaceArea = 600.0
        mock_solid.Edges.Size = 12
        mock_solid.Faces.Size = 6

        serialized = geometry_serializer.serialize_solid(mock_solid)

        assert serialized["type"] == "solid"
        assert serialized["volume"] == 1000.0
        assert serialized["surface_area"] == 600.0
        assert serialized["edge_count"] == 12
        assert serialized["face_count"] == 6

    def test_curve_geometry_serialization(self, geometry_serializer):
        """Test serializing curve geometry."""
        mock_curve = Mock()
        mock_curve.Length = 5000.0
        mock_curve.IsBound = True

        # Mock curve points
        start_point = Mock()
        start_point.X, start_point.Y, start_point.Z = 0.0, 0.0, 0.0
        end_point = Mock()
        end_point.X, end_point.Y, end_point.Z = 5000.0, 0.0, 0.0

        mock_curve.GetEndPoint.side_effect = [start_point, end_point]

        serialized = geometry_serializer.serialize_curve(mock_curve)

        assert serialized["type"] == "curve"
        assert serialized["length"] == 5000.0
        assert serialized["is_bound"] is True
        assert len(serialized["points"]) == 2

    def test_mesh_geometry_serialization(self, geometry_serializer):
        """Test serializing mesh geometry."""
        mock_mesh = Mock()
        mock_mesh.NumTriangles = 100
        mock_mesh.Vertices.Size = 60

        # Mock vertices
        vertices = []
        for i in range(3):
            vertex = Mock()
            vertex.X, vertex.Y, vertex.Z = i * 100, i * 100, 0
            vertices.append(vertex)

        mock_mesh.Vertices = vertices

        serialized = geometry_serializer.serialize_mesh(mock_mesh)

        assert serialized["type"] == "mesh"
        assert serialized["triangle_count"] == 100
        assert serialized["vertex_count"] == 60
        assert len(serialized["vertices"]) == 3


class TestParameterSerializer:
    """Test parameter serialization functionality."""

    @pytest.fixture
    def param_serializer(self):
        """Create parameter serializer for testing."""
        return ParameterSerializer()

    def test_string_parameter_serialization(self, param_serializer):
        """Test serializing string parameters."""
        mock_param = Mock()
        mock_param.Definition.Name = "Material"
        mock_param.AsString.return_value = "Concrete"
        mock_param.StorageType = "String"
        mock_param.IsReadOnly = False

        serialized = param_serializer.serialize_parameter(mock_param)

        assert serialized["name"] == "Material"
        assert serialized["value"] == "Concrete"
        assert serialized["type"] == "Text"
        assert serialized["read_only"] is False

    def test_numeric_parameter_serialization(self, param_serializer):
        """Test serializing numeric parameters."""
        mock_param = Mock()
        mock_param.Definition.Name = "Height"
        mock_param.AsDouble.return_value = 3000.0  # mm
        mock_param.StorageType = "Double"
        mock_param.DisplayUnitType = "Millimeters"

        # Mock unit conversion
        mock_param.Definition.UnitType = "Length"

        serialized = param_serializer.serialize_parameter(mock_param)

        assert serialized["name"] == "Height"
        assert serialized["value"] == 3000.0
        assert serialized["type"] == "Length"
        assert serialized["unit"] == "mm"

    def test_integer_parameter_serialization(self, param_serializer):
        """Test serializing integer parameters."""
        mock_param = Mock()
        mock_param.Definition.Name = "Count"
        mock_param.AsInteger.return_value = 5
        mock_param.StorageType = "Integer"

        serialized = param_serializer.serialize_parameter(mock_param)

        assert serialized["name"] == "Count"
        assert serialized["value"] == 5
        assert serialized["type"] == "Integer"

    def test_element_id_parameter_serialization(self, param_serializer):
        """Test serializing element ID parameters."""
        mock_param = Mock()
        mock_param.Definition.Name = "Associated Element"
        mock_element_id = Mock()
        mock_element_id.IntegerValue = 98765
        mock_param.AsElementId.return_value = mock_element_id
        mock_param.StorageType = "ElementId"

        serialized = param_serializer.serialize_parameter(mock_param)

        assert serialized["name"] == "Associated Element"
        assert serialized["value"] == "98765"
        assert serialized["type"] == "ElementId"

    def test_parameter_deserialization(self, param_serializer):
        """Test deserializing parameters."""
        param_data = {
            "name": "Height",
            "value": 3000.0,
            "type": "Length",
            "unit": "mm",
            "read_only": False,
        }

        deserialized = param_serializer.deserialize_parameter(param_data)

        assert deserialized["name"] == "Height"
        assert deserialized["value"] == 3000.0
        assert deserialized["type"] == "Length"

    def test_invalid_parameter_handling(self, param_serializer):
        """Test handling of invalid parameters."""
        mock_param = Mock()
        mock_param.Definition.Name = "Invalid"
        mock_param.AsString.side_effect = Exception("Cannot access")
        mock_param.AsDouble.side_effect = Exception("Cannot access")
        mock_param.AsInteger.side_effect = Exception("Cannot access")
        mock_param.StorageType = "Unknown"

        serialized = param_serializer.serialize_parameter(mock_param)

        # Should handle gracefully
        assert serialized["name"] == "Invalid"
        assert serialized["value"] is None
        assert "error" in serialized
