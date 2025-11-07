# Room Data Exporter

A real-world RevitPy application that exports room data from Revit models to various formats (CSV, Excel, JSON) for analysis and reporting.

## Features

- ✅ Export room data with all parameters
- ✅ Calculate room areas and volumes
- ✅ Export to multiple formats (CSV, Excel, JSON)
- ✅ Filter rooms by level, department, or custom parameters
- ✅ Include placement and boundary information
- ✅ Async processing for large models
- ✅ Progress reporting

## Installation

```bash
# Install the example package
pip install -e .

# Or install dependencies only
pip install -r requirements.txt
```

## Usage

### Basic Export

```python
from room_exporter import RoomExporter

# Create exporter instance
exporter = RoomExporter(doc)

# Export all rooms to CSV
exporter.export_to_csv("rooms.csv")

# Export to Excel with formatting
exporter.export_to_excel("rooms.xlsx", include_formatting=True)

# Export to JSON
exporter.export_to_json("rooms.json")
```

### Filtered Export

```python
# Export only rooms on specific level
exporter.export_to_csv(
    "level1_rooms.csv",
    filter_level="Level 1"
)

# Export rooms by department
exporter.export_to_excel(
    "office_rooms.xlsx",
    filter_parameter="Department",
    filter_value="Office"
)
```

### Async Export for Large Models

```python
import asyncio

async def export_large_model():
    exporter = RoomExporter(doc)

    # Export with progress callback
    def progress_callback(current, total):
        print(f"Processing room {current}/{total}")

    await exporter.export_to_csv_async(
        "large_model_rooms.csv",
        progress_callback=progress_callback
    )

asyncio.run(export_large_model())
```

### Advanced Usage

```python
# Custom column selection
exporter.export_to_csv(
    "custom_rooms.csv",
    columns=[
        "Number",
        "Name",
        "Area",
        "Volume",
        "Level",
        "Department",
        "Occupancy"
    ]
)

# Include geometry data
exporter.export_with_geometry(
    "rooms_with_geometry.json",
    include_boundary_segments=True,
    include_center_point=True
)

# Export with custom calculations
exporter.add_calculated_field(
    "Area_SqFt",
    lambda room: room.Area * 10.764  # Convert to sq ft
)

exporter.export_to_csv("rooms_calculated.csv")
```

## Command-Line Interface

```bash
# Export all rooms from a Revit file
revitpy-room-exporter export model.rvt --output rooms.csv

# Export with filters
revitpy-room-exporter export model.rvt \
    --output rooms.xlsx \
    --level "Level 1" \
    --format excel

# Export with custom parameters
revitpy-room-exporter export model.rvt \
    --output rooms.json \
    --parameters Number,Name,Area,Volume,Department \
    --format json
```

## Output Formats

### CSV Format

```csv
Number,Name,Area,Volume,Level,Department,Occupancy
101,Office,150.5,1355.0,Level 1,Administration,5
102,Conference Room,225.0,2025.0,Level 1,Administration,12
103,Break Room,100.0,900.0,Level 1,Common,8
```

### Excel Format

Includes:
- Formatted headers
- Data validation
- Conditional formatting for areas
- Summary sheet with statistics
- Charts and visualizations

### JSON Format

```json
{
  "metadata": {
    "export_date": "2024-01-15T10:30:00",
    "total_rooms": 150,
    "total_area": 15000.0
  },
  "rooms": [
    {
      "number": "101",
      "name": "Office",
      "area": 150.5,
      "volume": 1355.0,
      "level": "Level 1",
      "department": "Administration",
      "occupancy": 5,
      "boundary": {
        "segments": [
          {"start": [0, 0], "end": [10, 0]},
          {"start": [10, 0], "end": [10, 15]},
          ...
        ],
        "center": [5, 7.5]
      }
    }
  ]
}
```

## API Reference

See [API Documentation](docs/api.md) for detailed API reference.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=room_exporter --cov-report=html

# Run specific test categories
pytest -m unit
pytest -m integration
```

## Requirements

- Python 3.11+
- RevitPy >= 0.1.0
- pandas >= 2.0.0
- openpyxl >= 3.1.0

## License

MIT License - See LICENSE file for details
