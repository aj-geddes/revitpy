"""Main room data exporter implementation."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import pandas as pd
from revitpy.api import Query, Transaction
from revitpy.api.wrapper import RevitDocument

from .models import ExportOptions, RoomData
from .formatters import CSVFormatter, ExcelFormatter, JSONFormatter


class RoomExporter:
    """Export room data from Revit models to various formats."""

    def __init__(self, document: RevitDocument):
        """Initialize the exporter.

        Args:
            document: Revit document to export from
        """
        self.doc = document
        self._calculated_fields: Dict[str, Callable] = {}
        self.query = Query(document)

    def add_calculated_field(self, field_name: str, calculator: Callable[[Any], Any]) -> None:
        """Add a calculated field to the export.

        Args:
            field_name: Name of the calculated field
            calculator: Function that takes a room and returns the calculated value
        """
        self._calculated_fields[field_name] = calculator

    def get_all_rooms(
        self,
        filter_level: Optional[str] = None,
        filter_parameter: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> List[RoomData]:
        """Get all rooms with optional filtering.

        Args:
            filter_level: Filter by level name
            filter_parameter: Parameter name to filter by
            filter_value: Value to match for the filter parameter

        Returns:
            List of room data objects
        """
        # Query all rooms
        rooms = self.query.get_elements_by_category("Rooms")

        room_data_list = []

        for room in rooms:
            # Skip unplaced or unenclosed rooms
            if not hasattr(room, "Area") or room.Area <= 0:
                continue

            # Apply level filter
            if filter_level:
                level = self.query.get_parameter_value(room, "Level")
                if level != filter_level:
                    continue

            # Apply custom parameter filter
            if filter_parameter and filter_value:
                param_value = self.query.get_parameter_value(room, filter_parameter)
                if param_value != filter_value:
                    continue

            # Extract room data
            room_data = self._extract_room_data(room)
            room_data_list.append(room_data)

        return room_data_list

    def _extract_room_data(self, room: Any) -> RoomData:
        """Extract data from a room element.

        Args:
            room: Room element

        Returns:
            RoomData object
        """
        # Get basic properties
        number = self.query.get_parameter_value(room, "Number") or ""
        name = self.query.get_parameter_value(room, "Name") or ""
        area = getattr(room, "Area", 0.0)
        volume = getattr(room, "Volume", 0.0)
        level = self.query.get_parameter_value(room, "Level") or ""

        # Get location
        location = room.Location
        if location and hasattr(location, "Point"):
            center_x = location.Point.X
            center_y = location.Point.Y
            center_z = location.Point.Z
        else:
            center_x = center_y = center_z = 0.0

        # Extract all parameters
        parameters = {}
        for param in room.Parameters:
            try:
                param_name = param.Definition.Name
                param_value = param.AsValueString() or param.AsString() or str(param.AsDouble())
                parameters[param_name] = param_value
            except:
                continue

        # Create room data object
        room_data = RoomData(
            number=number,
            name=name,
            area=area,
            volume=volume,
            level=level,
            center_x=center_x,
            center_y=center_y,
            center_z=center_z,
            parameters=parameters,
        )

        # Add calculated fields
        for field_name, calculator in self._calculated_fields.items():
            try:
                room_data.parameters[field_name] = calculator(room)
            except Exception:
                room_data.parameters[field_name] = None

        return room_data

    def export_to_csv(
        self,
        output_path: Union[str, Path],
        columns: Optional[List[str]] = None,
        **filter_kwargs,
    ) -> None:
        """Export room data to CSV format.

        Args:
            output_path: Path to output CSV file
            columns: List of columns to include (default: all)
            **filter_kwargs: Filtering options (filter_level, filter_parameter, filter_value)
        """
        rooms = self.get_all_rooms(**filter_kwargs)

        if not rooms:
            print("No rooms found to export")
            return

        formatter = CSVFormatter()
        formatter.write(rooms, output_path, columns)

        print(f"✅ Exported {len(rooms)} rooms to {output_path}")

    def export_to_excel(
        self,
        output_path: Union[str, Path],
        include_formatting: bool = True,
        include_summary: bool = True,
        **filter_kwargs,
    ) -> None:
        """Export room data to Excel format.

        Args:
            output_path: Path to output Excel file
            include_formatting: Apply formatting to the Excel file
            include_summary: Include a summary sheet
            **filter_kwargs: Filtering options
        """
        rooms = self.get_all_rooms(**filter_kwargs)

        if not rooms:
            print("No rooms found to export")
            return

        formatter = ExcelFormatter()
        formatter.write(
            rooms,
            output_path,
            include_formatting=include_formatting,
            include_summary=include_summary,
        )

        print(f"✅ Exported {len(rooms)} rooms to {output_path}")

    def export_to_json(
        self,
        output_path: Union[str, Path],
        include_metadata: bool = True,
        pretty_print: bool = True,
        **filter_kwargs,
    ) -> None:
        """Export room data to JSON format.

        Args:
            output_path: Path to output JSON file
            include_metadata: Include metadata in the export
            pretty_print: Format JSON with indentation
            **filter_kwargs: Filtering options
        """
        rooms = self.get_all_rooms(**filter_kwargs)

        if not rooms:
            print("No rooms found to export")
            return

        formatter = JSONFormatter()
        formatter.write(
            rooms,
            output_path,
            include_metadata=include_metadata,
            pretty_print=pretty_print,
        )

        print(f"✅ Exported {len(rooms)} rooms to {output_path}")

    async def export_to_csv_async(
        self,
        output_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **filter_kwargs,
    ) -> None:
        """Async export to CSV with progress reporting.

        Args:
            output_path: Path to output CSV file
            progress_callback: Callback function for progress updates
            **filter_kwargs: Filtering options
        """
        import asyncio

        rooms = self.get_all_rooms(**filter_kwargs)

        if not rooms:
            print("No rooms found to export")
            return

        # Simulate async processing with progress
        total = len(rooms)
        for i, room in enumerate(rooms, 1):
            if progress_callback:
                progress_callback(i, total)
            await asyncio.sleep(0)  # Yield control

        # Write to file
        self.export_to_csv(output_path, **filter_kwargs)
