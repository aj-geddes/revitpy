# Quickstart: Build a Wall Analyzer in 10 Minutes

This quickstart tutorial will teach you RevitPy basics by building a practical wall analyzer tool. You'll learn:

- Reading element properties
- Working with parameters
- Exporting data
- Adding a UI

## Step 1: Setup (1 minute)

Create a new project:

```bash
revitpy create wall-analyzer --template basic-script
cd wall-analyzer
```

## Step 2: Query Walls (2 minutes)

Create `wall_analyzer.py`:

```python
"""Wall analyzer for RevitPy."""

from revitpy.api import Query
from revitpy.api.wrapper import get_active_document

def analyze_walls():
    """Analyze all walls in the active document."""
    # Get active document
    doc = get_active_document()

    # Create query interface
    query = Query(doc)

    # Get all walls
    walls = query.get_elements_by_category("Walls")

    print(f"📊 Found {len(walls)} walls")
    print("=" * 50)

    # Analyze each wall
    for wall in walls:
        analyze_single_wall(query, wall)

def analyze_single_wall(query, wall):
    """Analyze a single wall."""
    # Get wall properties
    wall_id = wall.Id.IntegerValue
    wall_type = query.get_parameter_value(wall, "Type")
    level = query.get_parameter_value(wall, "Base Constraint")
    length = query.get_parameter_value(wall, "Length")
    height = query.get_parameter_value(wall, "Unconnected Height")
    area = query.get_parameter_value(wall, "Area")

    # Print wall info
    print(f"""
Wall ID: {wall_id}
Type: {wall_type}
Level: {level}
Length: {length} ft
Height: {height} ft
Area: {area} sq ft
---
    """)

if __name__ == "__main__":
    analyze_walls()
```

Run it:

```bash
revitpy run wall_analyzer.py
```

## Step 3: Add Data Export (3 minutes)

Enhance the script to export data:

```python
"""Wall analyzer with CSV export."""

import csv
from pathlib import Path
from revitpy.api import Query
from revitpy.api.wrapper import get_active_document

def analyze_and_export_walls(output_file="walls.csv"):
    """Analyze walls and export to CSV."""
    doc = get_active_document()
    query = Query(doc)
    walls = query.get_elements_by_category("Walls")

    # Collect wall data
    wall_data = []
    for wall in walls:
        data = {
            "ID": wall.Id.IntegerValue,
            "Type": query.get_parameter_value(wall, "Type") or "",
            "Level": query.get_parameter_value(wall, "Base Constraint") or "",
            "Length": query.get_parameter_value(wall, "Length") or 0.0,
            "Height": query.get_parameter_value(wall, "Unconnected Height") or 0.0,
            "Area": query.get_parameter_value(wall, "Area") or 0.0,
            "Volume": query.get_parameter_value(wall, "Volume") or 0.0,
        }
        wall_data.append(data)

    # Write to CSV
    output_path = Path(output_file)
    with open(output_path, "w", newline="") as f:
        if wall_data:
            writer = csv.DictWriter(f, fieldnames=wall_data[0].keys())
            writer.writeheader()
            writer.writerows(wall_data)

    print(f"✅ Exported {len(wall_data)} walls to {output_path}")

    # Print summary statistics
    print_summary(wall_data)

def print_summary(wall_data):
    """Print summary statistics."""
    total_length = sum(float(w["Length"]) for w in wall_data)
    total_area = sum(float(w["Area"]) for w in wall_data)
    total_volume = sum(float(w["Volume"]) for w in wall_data)

    print("\n📈 Summary Statistics:")
    print(f"Total Walls: {len(wall_data)}")
    print(f"Total Length: {total_length:.2f} ft")
    print(f"Total Area: {total_area:.2f} sq ft")
    print(f"Total Volume: {total_volume:.2f} cu ft")

if __name__ == "__main__":
    analyze_and_export_walls()
```

## Step 4: Add Filtering (2 minutes)

Add the ability to filter walls:

```python
"""Wall analyzer with filtering."""

from typing import Optional
from revitpy.api import Query
from revitpy.api.wrapper import get_active_document

def analyze_walls_filtered(
    level_filter: Optional[str] = None,
    min_length: float = 0.0,
    output_file: str = "walls.csv"
):
    """Analyze walls with optional filtering.

    Args:
        level_filter: Only include walls on this level
        min_length: Only include walls longer than this
        output_file: Output CSV file path
    """
    doc = get_active_document()
    query = Query(doc)
    walls = query.get_elements_by_category("Walls")

    # Filter walls
    filtered_walls = []
    for wall in walls:
        # Check level filter
        if level_filter:
            level = query.get_parameter_value(wall, "Base Constraint")
            if level != level_filter:
                continue

        # Check length filter
        length = float(query.get_parameter_value(wall, "Length") or 0.0)
        if length < min_length:
            continue

        filtered_walls.append(wall)

    print(f"📊 Found {len(walls)} total walls")
    print(f"✅ {len(filtered_walls)} walls match filters")

    # Export filtered walls
    export_walls(query, filtered_walls, output_file)

def export_walls(query, walls, output_file):
    """Export walls to CSV."""
    import csv
    from pathlib import Path

    wall_data = []
    for wall in walls:
        data = {
            "ID": wall.Id.IntegerValue,
            "Type": query.get_parameter_value(wall, "Type") or "",
            "Level": query.get_parameter_value(wall, "Base Constraint") or "",
            "Length": query.get_parameter_value(wall, "Length") or 0.0,
            "Height": query.get_parameter_value(wall, "Unconnected Height") or 0.0,
            "Area": query.get_parameter_value(wall, "Area") or 0.0,
        }
        wall_data.append(data)

    output_path = Path(output_file)
    with open(output_path, "w", newline="") as f:
        if wall_data:
            writer = csv.DictWriter(f, fieldnames=wall_data[0].keys())
            writer.writeheader()
            writer.writerows(wall_data)

    print(f"✅ Exported to {output_path}")

# Example usage
if __name__ == "__main__":
    # Export all walls on Level 1 that are longer than 10 ft
    analyze_walls_filtered(
        level_filter="Level 1",
        min_length=10.0,
        output_file="level1_long_walls.csv"
    )
```

## Step 5: Use the ORM (2 minutes)

Refactor to use RevitPy's ORM for cleaner code:

```python
"""Wall analyzer using RevitPy ORM."""

from revitpy.orm import ElementQuery
from revitpy.api.wrapper import get_active_document

def analyze_with_orm():
    """Analyze walls using the ORM."""
    doc = get_active_document()

    # Query walls using LINQ-style syntax
    walls = (ElementQuery(doc)
        .of_category("Walls")
        .where(lambda w: w.Length > 10.0)  # Only long walls
        .order_by(lambda w: w.Area)  # Order by area
        .to_list())

    print(f"Found {len(walls)} walls longer than 10 ft")

    # Project to custom format
    wall_data = (ElementQuery(doc)
        .of_category("Walls")
        .where(lambda w: w.Length > 10.0)
        .select(lambda w: {
            "id": w.Id.IntegerValue,
            "type": w.WallType.Name,
            "length": w.Length,
            "area": w.Area,
            "level": w.LevelId
        })
        .to_list())

    # Export to CSV
    import pandas as pd
    df = pd.DataFrame(wall_data)
    df.to_csv("walls_orm.csv", index=False)

    print("✅ Exported using ORM")

if __name__ == "__main__":
    analyze_with_orm()
```

## Complete Solution

Here's the final, production-ready version:

```python
"""Professional wall analyzer with all features."""

from pathlib import Path
from typing import Optional, List, Dict, Any
import csv
import json
from datetime import datetime

from revitpy.api import Query, Transaction
from revitpy.api.wrapper import get_active_document
from revitpy.orm import ElementQuery


class WallAnalyzer:
    """Analyze and export wall data from Revit models."""

    def __init__(self, document=None):
        """Initialize analyzer."""
        self.doc = document or get_active_document()
        self.query = Query(self.doc)

    def get_walls(
        self,
        level_filter: Optional[str] = None,
        min_length: float = 0.0,
        wall_type_filter: Optional[str] = None,
    ) -> List[Any]:
        """Get walls with optional filtering."""
        # Build ORM query
        q = ElementQuery(self.doc).of_category("Walls")

        # Apply filters
        if min_length > 0:
            q = q.where(lambda w: w.Length >= min_length)

        if level_filter:
            q = q.where(lambda w: w.Level == level_filter)

        if wall_type_filter:
            q = q.where(lambda w: w.WallType.Name == wall_type_filter)

        return q.to_list()

    def analyze(self, walls: List[Any]) -> Dict[str, Any]:
        """Generate analysis statistics."""
        if not walls:
            return {"count": 0}

        total_length = sum(w.Length for w in walls)
        total_area = sum(w.Area for w in walls)
        total_volume = sum(w.Volume for w in walls)

        return {
            "count": len(walls),
            "total_length": total_length,
            "total_area": total_area,
            "total_volume": total_volume,
            "average_length": total_length / len(walls),
            "average_area": total_area / len(walls),
        }

    def export_csv(self, walls: List[Any], output_file: Path) -> None:
        """Export walls to CSV."""
        wall_data = []
        for wall in walls:
            data = {
                "ID": wall.Id.IntegerValue,
                "Type": wall.WallType.Name,
                "Level": self.query.get_parameter_value(wall, "Base Constraint"),
                "Length": wall.Length,
                "Height": wall.Height,
                "Area": wall.Area,
                "Volume": wall.Volume,
            }
            wall_data.append(data)

        with open(output_file, "w", newline="") as f:
            if wall_data:
                writer = csv.DictWriter(f, fieldnames=wall_data[0].keys())
                writer.writeheader()
                writer.writerows(wall_data)

    def export_json(
        self,
        walls: List[Any],
        output_file: Path,
        include_analysis: bool = True
    ) -> None:
        """Export walls to JSON with optional analysis."""
        wall_data = [
            {
                "id": w.Id.IntegerValue,
                "type": w.WallType.Name,
                "length": w.Length,
                "area": w.Area,
                "volume": w.Volume,
            }
            for w in walls
        ]

        output = {
            "exported_at": datetime.now().isoformat(),
            "document": self.doc.Title,
            "walls": wall_data,
        }

        if include_analysis:
            output["analysis"] = self.analyze(walls)

        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)

    def mark_walls(self, walls: List[Any], mark_value: str) -> None:
        """Mark walls with a specific value."""
        with Transaction(self.doc, "Mark Walls") as t:
            for wall in walls:
                wall.get_Parameter("Mark").Set(mark_value)

        print(f"✅ Marked {len(walls)} walls with '{mark_value}'")


# Example usage
def main():
    """Main entry point."""
    analyzer = WallAnalyzer()

    # Get filtered walls
    walls = analyzer.get_walls(
        level_filter="Level 1",
        min_length=10.0
    )

    print(f"📊 Found {len(walls)} walls matching criteria")

    # Analyze
    stats = analyzer.analyze(walls)
    print(f"📈 Analysis:")
    print(f"  Total Length: {stats['total_length']:.2f} ft")
    print(f"  Total Area: {stats['total_area']:.2f} sq ft")
    print(f"  Average Length: {stats['average_length']:.2f} ft")

    # Export
    analyzer.export_csv(walls, Path("walls.csv"))
    analyzer.export_json(walls, Path("walls.json"))

    print("✅ Export complete!")


if __name__ == "__main__":
    main()
```

## What You've Learned

In just 10 minutes, you've learned:

- ✅ Querying Revit elements
- ✅ Reading element parameters
- ✅ Filtering and sorting elements
- ✅ Exporting data to CSV and JSON
- ✅ Using the RevitPy ORM
- ✅ Modifying elements with transactions
- ✅ Building reusable classes

## Next Steps

- **[Advanced Querying](advanced-queries.md)** - Complex element queries
- **[Async Operations](async-tutorial.md)** - Build responsive tools
- **[Testing Guide](testing-guide.md)** - Test your addons
- **[UI Development](ui-development.md)** - Add user interfaces

## Complete Code

The complete wall analyzer is available in the examples:
- `examples/wall-analyzer/` - Full source code
- Includes tests, documentation, and packaging
