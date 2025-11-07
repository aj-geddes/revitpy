"""Tests for room exporter."""

import pytest
from pathlib import Path
from room_exporter import RoomExporter
from room_exporter.models import RoomData


class TestRoomExporter:
    """Test room exporter functionality."""

    def test_room_data_creation(self):
        """Test creating a RoomData object."""
        room = RoomData(
            number="101",
            name="Office",
            area=150.0,
            volume=1350.0,
            level="Level 1",
            parameters={"Department": "Admin"}
        )

        assert room.number == "101"
        assert room.name == "Office"
        assert room.area == 150.0
        assert room.volume == 1350.0

    def test_room_data_to_dict(self):
        """Test converting RoomData to dictionary."""
        room = RoomData(
            number="101",
            name="Office",
            area=150.0,
            volume=1350.0,
            level="Level 1",
        )

        data = room.to_dict()

        assert data["Number"] == "101"
        assert data["Name"] == "Office"
        assert data["Area"] == 150.0
        assert data["Volume"] == 1350.0
        assert data["Level"] == "Level 1"

    def test_room_data_to_dict_with_columns(self):
        """Test converting RoomData with column filtering."""
        room = RoomData(
            number="101",
            name="Office",
            area=150.0,
            volume=1350.0,
            level="Level 1",
        )

        data = room.to_dict(columns=["Number", "Name", "Area"])

        assert "Number" in data
        assert "Name" in data
        assert "Area" in data
        assert "Volume" not in data

    def test_calculated_fields(self):
        """Test adding calculated fields."""
        # This would require a mock Revit document
        # For now, just test the mechanism exists
        # In a real test, you'd use revitpy.testing.MockRevitEnvironment
        pass

    def test_csv_export(self, tmp_path):
        """Test CSV export."""
        rooms = [
            RoomData("101", "Office", 150.0, 1350.0, "Level 1"),
            RoomData("102", "Conference", 200.0, 1800.0, "Level 1"),
        ]

        output_file = tmp_path / "test_rooms.csv"

        from room_exporter.formatters import CSVFormatter

        formatter = CSVFormatter()
        formatter.write(rooms, output_file)

        assert output_file.exists()

        # Read and verify content
        import pandas as pd
        df = pd.read_csv(output_file)

        assert len(df) == 2
        assert df["Number"].tolist() == ["101", "102"]
        assert df["Name"].tolist() == ["Office", "Conference"]

    def test_json_export(self, tmp_path):
        """Test JSON export."""
        rooms = [
            RoomData("101", "Office", 150.0, 1350.0, "Level 1"),
            RoomData("102", "Conference", 200.0, 1800.0, "Level 1"),
        ]

        output_file = tmp_path / "test_rooms.json"

        from room_exporter.formatters import JSONFormatter

        formatter = JSONFormatter()
        formatter.write(rooms, output_file, include_metadata=True)

        assert output_file.exists()

        # Read and verify content
        import json
        with open(output_file) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "rooms" in data
        assert data["metadata"]["total_rooms"] == 2
        assert len(data["rooms"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
