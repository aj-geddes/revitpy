---
layout: page
title: Quantity Extraction
description: Extract quantities, material takeoffs, and cost estimates from Revit elements using RevitPy. Supports CSV, JSON, Excel, and Parquet data export formats.
doc_tier: user
---

# Quantity Extraction

RevitPy includes an extraction layer (`revitpy.extract`) for pulling measured quantities, material data, cost estimates, and structured exports from Revit elements. The module is designed around four core classes: `QuantityExtractor`, `MaterialTakeoff`, `CostEstimator`, and `DataExporter`.

## Quick Start

The module provides convenience functions for the most common workflows:

```python
from revitpy.extract import extract_quantities, material_takeoff, estimate_costs, export_data

# Extract quantities from a list of elements
quantities = extract_quantities(elements)

# Material takeoff with aggregation and classification
materials = material_takeoff(elements, aggregate=True, classify=True, classification_system="UniFormat")

# Cost estimation from extracted quantities
cost_summary = estimate_costs(quantities, cost_database={"Walls": 150.0, "Floors": 85.0})

# Export to CSV
from revitpy.extract import ExportConfig, ExportFormat
from pathlib import Path

config = ExportConfig(format=ExportFormat.CSV, output_path=Path("takeoff.csv"))
export_data([{"name": "Wall-1", "area": 25.5}], config=config)
```

## QuantityExtractor

`QuantityExtractor` extracts measured quantities (area, volume, length, count, weight) from duck-typed element objects. Elements are expected to expose attributes such as `area`, `volume`, `length`, `count`, `weight`, `name`, `category`, `level`, and `system`.

### Creating an Extractor

```python
from revitpy.extract import QuantityExtractor

# Basic usage
extractor = QuantityExtractor()

# With an optional RevitContext
extractor = QuantityExtractor(context=my_context)
```

### Extracting Quantities

The `extract` method returns a list of `QuantityItem` dataclasses. By default it extracts all quantity types. Pass `quantity_types` to limit extraction to specific types.

```python
from revitpy.extract import QuantityExtractor, QuantityType

extractor = QuantityExtractor()

# Extract all quantity types
items = extractor.extract(elements)

# Extract only area and volume
items = extractor.extract(elements, quantity_types=[QuantityType.AREA, QuantityType.VOLUME])
```

Each returned `QuantityItem` contains the following fields:

| Field | Type | Description |
|---|---|---|
| `element_id` | `Any` | The element's `id` attribute |
| `element_name` | `str` | The element's `name` attribute |
| `category` | `str` | The element's `category` attribute |
| `quantity_type` | `QuantityType` | The type of quantity extracted |
| `value` | `float` | The numeric quantity value |
| `unit` | `str` | The unit of measurement (e.g. `"m2"`, `"m3"`) |
| `level` | `str` | The element's `level` attribute (optional) |
| `system` | `str` | The element's `system` attribute (optional) |

Default units are assigned per quantity type but can be overridden per element using an attribute named `{attr}_unit` (e.g. `area_unit`).

### Grouped Extraction

Use `extract_grouped` to extract and group results by an aggregation level in a single call:

```python
from revitpy.extract import QuantityExtractor, AggregationLevel

extractor = QuantityExtractor()

# Group by category (default)
grouped = extractor.extract_grouped(elements)
# Returns: {"Walls": [QuantityItem, ...], "Floors": [QuantityItem, ...]}

# Group by level
grouped = extractor.extract_grouped(elements, group_by=AggregationLevel.LEVEL)

# Group by system with specific quantity types
grouped = extractor.extract_grouped(
    elements,
    group_by=AggregationLevel.SYSTEM,
    quantity_types=[QuantityType.LENGTH],
)
```

### Summarizing Quantities

The `summarize` method sums values by quantity type:

```python
items = extractor.extract(elements)
summary = extractor.summarize(items)
# Returns: {"area": 1250.5, "volume": 340.2, "count": 48.0}
```

### Async Extraction

For large element sets, use `extract_async` with an optional progress callback:

```python
import asyncio
from revitpy.extract import QuantityExtractor

extractor = QuantityExtractor()

def on_progress(current: int, total: int) -> None:
    print(f"Processing {current}/{total}")

items = asyncio.run(extractor.extract_async(elements, progress=on_progress))
```

The async method yields control to the event loop every 100 elements to keep the UI responsive.

## MaterialTakeoff

`MaterialTakeoff` extracts material data from elements, aggregates quantities by material name, and classifies materials against industry standard systems.

Elements should expose `material_name` (or `material`), `material_volume`, `material_area`, and `material_mass` attributes. If the material-specific quantity attributes are absent, the extractor falls back to the generic `volume` and `area` attributes.

### Extracting Materials

```python
from revitpy.extract import MaterialTakeoff

takeoff = MaterialTakeoff()
materials = takeoff.extract(elements)

for mat in materials:
    print(f"{mat.material_name}: {mat.volume} m3, {mat.area} m2, {mat.mass} kg")
```

Each `MaterialQuantity` dataclass contains:

| Field | Type | Default | Description |
|---|---|---|---|
| `material_name` | `str` | -- | Name of the material |
| `category` | `str` | -- | Element category |
| `volume` | `float` | `0.0` | Total volume in cubic metres |
| `area` | `float` | `0.0` | Total area in square metres |
| `mass` | `float` | `0.0` | Total mass in kilograms |
| `classification_code` | `str` | `""` | Classification code (after classification) |
| `classification_system` | `str` | `""` | Classification system name (after classification) |

### Aggregating Materials

The `aggregate` method combines entries that share the same `material_name`, summing their volume, area, and mass:

```python
materials = takeoff.extract(elements)
aggregated = takeoff.aggregate(materials)
# One entry per unique material name, with totals summed
```

### Classifying Materials

The `classify` method maps material names to standard classification codes using a built-in lookup table. Two systems are supported: UniFormat and MasterFormat.

```python
materials = takeoff.extract(elements)
aggregated = takeoff.aggregate(materials)

# Classify with UniFormat (default)
classified = takeoff.classify(aggregated, system="UniFormat")

# Classify with MasterFormat
classified = takeoff.classify(aggregated, system="MasterFormat")

for mat in classified:
    print(f"{mat.material_name}: {mat.classification_code} ({mat.classification_system})")
```

Classification uses exact matching first, then partial matching on the lowercased material name. Built-in mappings include common materials such as concrete, steel, wood, masonry, glass, aluminum, gypsum, insulation, carpet, tile, paint, roofing, waterproofing, brick, stone, plaster, copper, asphalt, and gravel.

#### UniFormat Classification Codes (Built-in)

| Material | UniFormat Code |
|---|---|
| Concrete | A1010 |
| Steel | A1020 |
| Wood | A1030 |
| Masonry | A1040 |
| Glass | B2020 |
| Aluminum | B2010 |
| Gypsum | C1010 |
| Insulation | C1020 |
| Roofing | B3010 |

#### MasterFormat Classification Codes (Built-in)

| Material | MasterFormat Code |
|---|---|
| Concrete | 03 00 00 |
| Steel | 05 00 00 |
| Wood | 06 00 00 |
| Masonry | 04 00 00 |
| Glass | 08 80 00 |
| Aluminum | 08 40 00 |
| Gypsum | 09 20 00 |
| Insulation | 07 20 00 |
| Roofing | 07 50 00 |

### Full Pipeline Example

```python
from revitpy.extract import MaterialTakeoff

takeoff = MaterialTakeoff()
materials = takeoff.extract(elements)
aggregated = takeoff.aggregate(materials)
classified = takeoff.classify(aggregated, system="UniFormat")

for mat in classified:
    print(f"{mat.material_name} [{mat.classification_code}]: "
          f"volume={mat.volume:.2f}, area={mat.area:.2f}, mass={mat.mass:.2f}")
```

Or use the convenience function for the same result:

```python
from revitpy.extract import material_takeoff

classified = material_takeoff(
    elements,
    aggregate=True,
    classify=True,
    classification_system="UniFormat",
)
```

## CostEstimator

`CostEstimator` maps extracted quantities to unit costs from a pluggable cost database and produces itemized cost breakdowns with aggregated summaries.

### Setting Up a Cost Database

The cost database maps category or material names (strings) to unit costs (floats). It can be supplied as a dict, or loaded from CSV, JSON, or YAML files.

```python
from revitpy.extract import CostEstimator
from pathlib import Path

# From a dict
estimator = CostEstimator(cost_database={
    "Walls": 150.0,
    "Floors": 85.0,
    "Roofs": 200.0,
    "Doors": 500.0,
    "Windows": 750.0,
})

# From a file path (auto-detected by extension)
estimator = CostEstimator(cost_database=Path("costs.json"))

# Load a database after construction
estimator = CostEstimator()
estimator.load_database(Path("costs.csv"))
```

Supported file formats:

| Format | Extension | Expected Structure |
|---|---|---|
| CSV | `.csv` | Columns: `name` or `category`, `unit_cost` or `cost` |
| JSON | `.json` | Top-level dict `{"name": cost}` or list of `{"name": ..., "unit_cost": ...}` |
| YAML | `.yaml`, `.yml` | Top-level dict mapping names to costs |

### Estimating Costs

Pass a list of `QuantityItem` objects (from `QuantityExtractor`) to the `estimate` method. The estimator looks up unit costs by category name using exact match, case-insensitive match, then partial match.

```python
from revitpy.extract import QuantityExtractor, CostEstimator, AggregationLevel

extractor = QuantityExtractor()
quantities = extractor.extract(elements, quantity_types=[QuantityType.AREA])

estimator = CostEstimator(cost_database={"Walls": 150.0, "Floors": 85.0})
summary = estimator.estimate(quantities, aggregation=AggregationLevel.CATEGORY)

print(f"Total cost: ${summary.total_cost:,.2f}")
print(f"Currency: {summary.currency}")
```

### CostSummary Structure

The `estimate` method returns a `CostSummary` dataclass:

| Field | Type | Description |
|---|---|---|
| `items` | `list[CostItem]` | Itemized cost line items |
| `total_cost` | `float` | Grand total of all line items |
| `by_category` | `dict[str, float]` | Costs aggregated by element category |
| `by_system` | `dict[str, float]` | Costs aggregated by building system |
| `by_level` | `dict[str, float]` | Costs aggregated by level |
| `currency` | `str` | Currency code (default `"USD"`) |

Each `CostItem` contains:

| Field | Type | Description |
|---|---|---|
| `description` | `str` | Formatted as `"element_name - quantity_type"` |
| `quantity` | `float` | The quantity value |
| `unit` | `str` | The unit of measurement |
| `unit_cost` | `float` | The cost per unit |
| `total_cost` | `float` | `quantity * unit_cost` |
| `source` | `CostSource` | Where the cost data came from |
| `category` | `str` | Element category |
| `system` | `str` | Building system |

### Working with Cost Breakdowns

```python
summary = estimator.estimate(quantities)

# Iterate line items
for item in summary.items:
    print(f"{item.description}: {item.quantity} {item.unit} "
          f"x ${item.unit_cost:.2f} = ${item.total_cost:.2f}")

# Category breakdown
for category, cost in summary.by_category.items():
    print(f"{category}: ${cost:,.2f}")

# Level breakdown
for level, cost in summary.by_level.items():
    print(f"{level}: ${cost:,.2f}")
```

## DataExporter

`DataExporter` writes tabular data (lists of dicts) to CSV, JSON, Excel, Parquet, or plain dicts.

### Export Configuration

All exports are configured through the `ExportConfig` dataclass:

| Field | Type | Default | Description |
|---|---|---|---|
| `format` | `ExportFormat` | `ExportFormat.CSV` | Output format |
| `output_path` | `Path` or `None` | `None` | Destination file path (required for file formats) |
| `include_headers` | `bool` | `True` | Include column headers (CSV, Excel) |
| `decimal_places` | `int` | `2` | Rounding precision for float values (CSV, JSON) |
| `sheet_name` | `str` | `"Sheet1"` | Worksheet name (Excel only) |

### Exporting to CSV

```python
from revitpy.extract import DataExporter, ExportConfig, ExportFormat
from pathlib import Path

exporter = DataExporter()
data = [
    {"name": "Wall-1", "category": "Walls", "area": 25.5, "cost": 3825.0},
    {"name": "Floor-1", "category": "Floors", "area": 100.0, "cost": 8500.0},
]

config = ExportConfig(
    format=ExportFormat.CSV,
    output_path=Path("quantities.csv"),
    include_headers=True,
    decimal_places=2,
)
output_path = exporter.export(data, config)
print(f"Exported to {output_path}")
```

### Exporting to JSON

```python
config = ExportConfig(
    format=ExportFormat.JSON,
    output_path=Path("quantities.json"),
    decimal_places=3,
)
output_path = exporter.export(data, config)
```

### Exporting to Excel (Optional Dependency)

Excel export requires the `openpyxl` package. Install it with `pip install openpyxl`.

```python
config = ExportConfig(
    format=ExportFormat.EXCEL,
    output_path=Path("quantities.xlsx"),
    sheet_name="Takeoff Data",
    include_headers=True,
)
output_path = exporter.export(data, config)
```

### Exporting to Parquet (Optional Dependency)

Parquet export requires the `pyarrow` package. Install it with `pip install pyarrow`.

```python
config = ExportConfig(
    format=ExportFormat.PARQUET,
    output_path=Path("quantities.parquet"),
)
output_path = exporter.export(data, config)
```

### Returning Dicts

Use `ExportFormat.DICT` to return a shallow copy of the data as plain dicts, useful for passing into pandas or other downstream tools:

```python
config = ExportConfig(format=ExportFormat.DICT)
rows = exporter.export(data, config)
# Returns: [{"name": "Wall-1", ...}, {"name": "Floor-1", ...}]
```

### Direct Export Methods

`DataExporter` also exposes format-specific methods directly:

```python
exporter = DataExporter()

# CSV
exporter.to_csv(data, Path("out.csv"), include_headers=True, decimal_places=2)

# JSON
exporter.to_json(data, Path("out.json"), decimal_places=2)

# Excel
exporter.to_excel(data, Path("out.xlsx"), sheet_name="Data", include_headers=True)

# Parquet
exporter.to_parquet(data, Path("out.parquet"))

# Dicts (passthrough)
rows = exporter.to_dicts(data)
```

## Enums Reference

### QuantityType

| Value | String | Default Unit | Description |
|---|---|---|---|
| `AREA` | `"area"` | `m2` | Surface area |
| `VOLUME` | `"volume"` | `m3` | Volume |
| `LENGTH` | `"length"` | `m` | Length |
| `COUNT` | `"count"` | `ea` | Element count (defaults to 1 per element) |
| `WEIGHT` | `"weight"` | `kg` | Weight |

### AggregationLevel

| Value | String | Description |
|---|---|---|
| `ELEMENT` | `"element"` | Group by individual element ID |
| `CATEGORY` | `"category"` | Group by element category |
| `LEVEL` | `"level"` | Group by building level |
| `SYSTEM` | `"system"` | Group by building system |
| `BUILDING` | `"building"` | Single group for the entire building |

### ExportFormat

| Value | String | Requires |
|---|---|---|
| `CSV` | `"csv"` | Built-in |
| `JSON` | `"json"` | Built-in |
| `EXCEL` | `"excel"` | `openpyxl` |
| `PARQUET` | `"parquet"` | `pyarrow` |
| `DICT` | `"dict"` | Built-in |

### CostSource

| Value | String | Description |
|---|---|---|
| `CSV_FILE` | `"csv_file"` | Loaded from a CSV file |
| `JSON_FILE` | `"json_file"` | Loaded from a JSON file |
| `YAML_FILE` | `"yaml_file"` | Loaded from a YAML file |
| `MANUAL` | `"manual"` | Supplied directly as a dict |

## End-to-End Example

A complete workflow from quantity extraction through cost estimation to export:

```python
from pathlib import Path
from revitpy.extract import (
    QuantityExtractor,
    MaterialTakeoff,
    CostEstimator,
    DataExporter,
    ExportConfig,
    ExportFormat,
    QuantityType,
    AggregationLevel,
)

# Step 1: Extract quantities
extractor = QuantityExtractor()
quantities = extractor.extract(elements, quantity_types=[QuantityType.AREA, QuantityType.VOLUME])

# Step 2: Material takeoff
takeoff = MaterialTakeoff()
materials = takeoff.extract(elements)
materials = takeoff.aggregate(materials)
materials = takeoff.classify(materials, system="UniFormat")

# Step 3: Cost estimation
estimator = CostEstimator(cost_database=Path("unit_costs.json"))
summary = estimator.estimate(quantities, aggregation=AggregationLevel.CATEGORY)
print(f"Total estimated cost: ${summary.total_cost:,.2f}")

# Step 4: Export cost breakdown
export_data = [
    {
        "description": item.description,
        "quantity": item.quantity,
        "unit": item.unit,
        "unit_cost": item.unit_cost,
        "total_cost": item.total_cost,
        "category": item.category,
    }
    for item in summary.items
]

exporter = DataExporter()
config = ExportConfig(
    format=ExportFormat.CSV,
    output_path=Path("cost_report.csv"),
    decimal_places=2,
)
exporter.export(export_data, config)
```

## Error Handling

The extraction layer defines specific exceptions for each subsystem:

| Exception | Raised By | Description |
|---|---|---|
| `ExtractionError` | `MaterialTakeoff.extract` | General extraction failure |
| `QuantityError` | `QuantityExtractor.extract` | Quantity extraction failure for an element |
| `CostEstimationError` | `CostEstimator.load_database`, `CostEstimator.estimate` | Cost database or estimation failure |
| `ExportError` | `DataExporter.export` and format-specific methods | Export operation failure |
| `ScheduleError` | `ScheduleBuilder` | Schedule building failure |

All exceptions include contextual attributes such as `element_id`, `export_format`, or `output_path` depending on the error type.
