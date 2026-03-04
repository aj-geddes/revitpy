---
layout: page
title: Sustainability & Carbon Analytics
description: Calculate embodied carbon, integrate EPD databases, check LL97/BERDO/ASHRAE compliance, and generate sustainability reports with RevitPy for green BIM.
doc_tier: user
---

# Sustainability & Carbon Analytics

RevitPy provides a full sustainability analysis module for whole-life carbon assessment, Environmental Product Declaration (EPD) management, building emissions compliance checking, and report generation for green building certification workflows.

## Overview

The `revitpy.sustainability` module provides five core components:

- **`CarbonCalculator`** -- Calculates embodied carbon for building materials using EPD data, aggregates results into building-level summaries, and benchmarks against RIBA 2030 Climate Challenge targets.
- **`EpdDatabase`** -- Manages EPD records with a local cache of generic values, fuzzy keyword matching, and optional async lookup against the EC3 (Embodied Carbon in Construction Calculator) API.
- **`ComplianceChecker`** -- Verifies building performance against LL97, BERDO, EPBD, and ASHRAE 90.1 standards with pass/fail results and improvement recommendations.
- **`SustainabilityReporter`** -- Generates sustainability reports in JSON, CSV, and HTML formats, with certification documentation helpers for LEED, BREEAM, DGNB, and Green Star.
- **`MaterialExtractor`** -- Extracts and classifies material quantities from building elements.

The module also exposes three convenience functions for quick one-off operations:

```python
from revitpy.sustainability import (
    CarbonCalculator,
    EpdDatabase,
    ComplianceChecker,
    SustainabilityReporter,
    MaterialExtractor,
    # Convenience functions
    calculate_carbon,
    check_compliance,
    generate_report,
    # Types and enums
    MaterialData,
    EpdRecord,
    CarbonResult,
    BuildingCarbonSummary,
    ComplianceResult,
    EnergyEnvelopeData,
    CarbonBenchmark,
    LifecycleStage,
    CertificationSystem,
    ComplianceStandard,
    ReportFormat,
)
```

## CarbonCalculator

`CarbonCalculator` computes embodied carbon for building materials by resolving GWP (Global Warming Potential) factors from an EPD database. It supports mass-based and volume-based calculation, building-level summarization, and benchmarking.

### Creating a Calculator

```python
from revitpy.sustainability import CarbonCalculator, EpdDatabase

# With default EPD database
calculator = CarbonCalculator()

# With a custom EPD database
epd_db = EpdDatabase(api_token="your-ec3-token")
calculator = CarbonCalculator(epd_database=epd_db)
```

### Calculating Embodied Carbon

`calculate` takes a list of `MaterialData` and optional lifecycle stages, looks up EPD records, and returns a list of `CarbonResult` instances. The calculator prefers mass-based calculation (`mass_kg * gwp_per_kg`); when mass is zero it falls back to volume-based (`volume_m3 * gwp_per_m3`).

```python
from revitpy.sustainability import MaterialData, LifecycleStage

materials = [
    MaterialData(
        name="Concrete",
        category="Concrete",
        mass_kg=50000.0,
        volume_m3=20.8,
        level="Level 1",
        system="Structure",
    ),
    MaterialData(
        name="Steel",
        category="Metals",
        mass_kg=12000.0,
        volume_m3=1.5,
        level="Level 1",
        system="Structure",
    ),
    MaterialData(
        name="Timber",
        category="Wood",
        mass_kg=3000.0,
        volume_m3=6.0,
        level="Level 2",
        system="Framing",
    ),
]

# Default: A1-A3 product stages
results = calculator.calculate(materials)

# Specify lifecycle stages explicitly
results = calculator.calculate(
    materials,
    lifecycle_stages=[
        LifecycleStage.A1_RAW_MATERIALS,
        LifecycleStage.A2_TRANSPORT,
        LifecycleStage.A3_MANUFACTURING,
        LifecycleStage.A4_TRANSPORT_SITE,
        LifecycleStage.A5_CONSTRUCTION,
    ],
)

for r in results:
    print(f"{r.material.name}: {r.embodied_carbon_kgco2e:.2f} kgCO2e ({r.calculation_method})")
```

Materials without a matching EPD record are silently skipped. If the calculation itself fails, a `CarbonCalculationError` is raised.

### Summarizing Results

`summarize` aggregates a list of `CarbonResult` into a `BuildingCarbonSummary` with totals broken down by material, building system, level, and lifecycle stage:

```python
summary = calculator.summarize(results)

print(f"Total: {summary.total_embodied_carbon_kgco2e:.2f} kgCO2e")
print(f"Materials assessed: {summary.material_count}")
print(f"Calculated: {summary.calculation_date}")

# Breakdowns
for material, carbon in summary.by_material.items():
    print(f"  {material}: {carbon:.2f} kgCO2e")

for system, carbon in summary.by_system.items():
    print(f"  {system}: {carbon:.2f} kgCO2e")

for level, carbon in summary.by_level.items():
    print(f"  {level}: {carbon:.2f} kgCO2e")

for stage, carbon in summary.by_lifecycle_stage.items():
    print(f"  {stage}: {carbon:.2f} kgCO2e")
```

### Benchmarking

`benchmark` compares a building summary against RIBA 2030 Climate Challenge targets. Ratings are assigned based on the ratio of actual to target intensity:

```python
bench = calculator.benchmark(
    summary,
    building_area_m2=2500.0,
    building_type="office",
)

print(f"Actual: {bench.actual_kgco2e_per_m2} kgCO2e/m2")
print(f"Target: {bench.target_kgco2e_per_m2} kgCO2e/m2")
print(f"Source: {bench.benchmark_source}")
print(f"Rating: {bench.rating}")
print(f"Percentile: {bench.percentile}")
```

Benchmark ratings are assigned as follows:

| Ratio (actual/target) | Rating | Percentile |
|---|---|---|
| 0.50 or below | Excellent | 95 |
| 0.51 -- 0.75 | Good | 75 |
| 0.76 -- 1.00 | Acceptable | 50 |
| 1.01 -- 1.25 | Below Average | 25 |
| Above 1.25 | Poor | 10 |

Built-in RIBA 2030 targets (kgCO2e/m2):

| Building Type | Target |
|---|---|
| `residential` | 300.0 |
| `office` | 350.0 |
| `school` | 300.0 |
| `retail` | 350.0 |
| `industrial` | 400.0 |
| `default` | 350.0 |

### Async Calculation

`calculate_async` runs the same calculation with async support and an optional progress callback:

```python
import asyncio

async def main():
    def on_progress(completed: int, total: int):
        print(f"Progress: {completed}/{total}")

    results = await calculator.calculate_async(
        materials,
        lifecycle_stages=[LifecycleStage.A1_RAW_MATERIALS],
        progress=on_progress,
    )

asyncio.run(main())
```

The calculator yields control to the event loop every 50 materials to avoid blocking.

## EpdDatabase

`EpdDatabase` manages Environmental Product Declaration records with a local cache of generic industry-average values, fuzzy keyword matching, and optional async queries against the EC3 API.

### Creating a Database

```python
from revitpy.sustainability import EpdDatabase

# Default: generic values only
epd_db = EpdDatabase()

# With EC3 API token for remote lookups
epd_db = EpdDatabase(api_token="your-ec3-api-token")

# With a local cache file
epd_db = EpdDatabase(cache_path="/path/to/epd_cache.json")
```

### Built-in Generic EPDs

The database ships with generic EPD values (ICE Database / industry averages) for eight common materials:

| Key | Material | Category | GWP/kg | GWP/m3 |
|---|---|---|---|---|
| `concrete` | Concrete | Concrete | 0.13 | 312.0 |
| `steel` | Steel | Metals | 1.55 | 12167.5 |
| `timber` | Timber | Wood | 0.45 | 225.0 |
| `glass` | Glass | Glass | 0.86 | 2150.0 |
| `aluminum` | Aluminum | Metals | 8.24 | 22248.0 |
| `brick` | Brick | Masonry | 0.24 | 432.0 |
| `insulation` | Insulation | Insulation | 1.86 | 55.8 |
| `gypsum` | Gypsum Board | Interior Finishes | 0.39 | 312.0 |

All generic EPDs cover lifecycle stages A1--A3 and use `"generic-ice"` as their source.

### Looking Up EPDs

`lookup` searches the local cache using exact match, then fuzzy keyword matching, then category-based generic fallback:

```python
# Exact match
epd = epd_db.lookup("concrete")
print(epd.material_name)  # "Concrete"
print(epd.gwp_per_kg)     # 0.13

# Fuzzy match (substring matching against cache keys)
epd = epd_db.lookup("reinforced concrete")  # Matches "concrete"

# Category fallback
epd = epd_db.lookup("unknown material", category="Metals")  # Matches steel/aluminum

# No match
epd = epd_db.lookup("exotic material")  # Returns None
```

### Generic EPD Lookup

`get_generic_epd` searches generic EPDs by category name:

```python
epd = epd_db.get_generic_epd("Concrete")
epd = epd_db.get_generic_epd("Metals")    # Matches Steel
epd = epd_db.get_generic_epd("Wood")      # Matches Timber
```

### Async Lookups (EC3 API)

When an API token is configured, `lookup_async` queries the EC3 API if local lookup returns nothing:

```python
import asyncio

async def main():
    epd_db = EpdDatabase(api_token="your-token")

    # Tries local cache first, then queries EC3 API
    epd = await epd_db.lookup_async("low-carbon concrete", category="Concrete")
    if epd:
        print(f"{epd.material_name}: {epd.gwp_per_kg} kgCO2e/kg (source: {epd.source})")

asyncio.run(main())
```

`search_async` performs a broader search across local cache and the EC3 API:

```python
async def main():
    results = await epd_db.search_async("concrete", limit=10)
    for epd in results:
        print(f"{epd.material_name} ({epd.source}): {epd.gwp_per_kg} kgCO2e/kg")

asyncio.run(main())
```

### Cache Management

```python
# Save current cache to disk
epd_db.save_cache("/path/to/epd_cache.json")

# Load cache from disk (also done automatically at init if cache_path is set)
epd_db.load_cache("/path/to/epd_cache.json")
```

## ComplianceChecker

`ComplianceChecker` verifies building performance data against major emissions and energy standards. Each check returns a `ComplianceResult` with pass/fail status, threshold comparison, and improvement recommendations.

### Creating a Checker

```python
from revitpy.sustainability import ComplianceChecker

checker = ComplianceChecker()
```

### Generic Check Interface

The `check` method dispatches to the correct standard-specific checker:

```python
from revitpy.sustainability import ComplianceStandard

result = checker.check(
    ComplianceStandard.LL97,
    {"area_sqft": 50000, "annual_emissions_tco2e": 300, "occupancy_type": "office"},
)

print(result.passed)           # True or False
print(result.actual_value)     # Actual intensity
print(result.threshold)        # Limit for the standard
print(result.unit)             # e.g. "tCO2e/sqft/year"
print(result.recommendations)  # List of improvement suggestions
print(result.details)          # Standard-specific details dict
```

### NYC Local Law 97 (LL97)

Checks carbon intensity against LL97 2024--2029 limits by occupancy type:

```python
result = checker.check_ll97({
    "area_sqft": 50000,
    "annual_emissions_tco2e": 300,
    "occupancy_type": "office",  # optional, defaults to "default"
})
```

Required keys: `area_sqft`, `annual_emissions_tco2e`. Optional: `occupancy_type`.

LL97 limits (tCO2e/sqft/year, 2024--2029 period):

| Occupancy Type | Limit |
|---|---|
| `office` | 0.00846 |
| `residential` | 0.00675 |
| `retail` | 0.01074 |
| `hotel` | 0.00987 |
| `healthcare` | 0.02381 |
| `education` | 0.00758 |
| `warehouse` | 0.00574 |

### Boston BERDO

Checks emissions intensity against Boston BERDO standards:

```python
result = checker.check_berdo({
    "area_sqft": 50000,
    "annual_emissions_kgco2e": 200000,
    "building_type": "office",  # optional
})
```

Required keys: `area_sqft`, `annual_emissions_kgco2e`. Optional: `building_type`.

BERDO limits (kgCO2e/sqft/year):

| Building Type | Limit |
|---|---|
| `office` | 5.4 |
| `residential` | 3.6 |
| `retail` | 6.1 |
| `education` | 4.8 |

### EU EPBD

Checks primary energy demand against the Energy Performance of Buildings Directive:

```python
result = checker.check_epbd({
    "area_m2": 5000,
    "primary_energy_kwh": 550000,
    "building_type": "office",  # optional
})
```

Required keys: `area_m2`, `primary_energy_kwh`. Optional: `building_type`.

EPBD limits (kWh/m2/year):

| Building Type | Limit |
|---|---|
| `residential` | 100.0 |
| `office` | 120.0 |
| `retail` | 130.0 |
| `education` | 110.0 |

### ASHRAE 90.1 Envelope

Checks building envelope thermal performance against ASHRAE 90.1-2019 requirements for climate zone 4A. This method accepts an `EnergyEnvelopeData` dataclass directly:

```python
from revitpy.sustainability import EnergyEnvelopeData

envelope = EnergyEnvelopeData(
    wall_r_value=15.0,
    roof_r_value=30.0,
    window_u_value=0.32,
    glazing_ratio=0.35,
    air_tightness=3.0,  # optional
)

result = checker.check_ashrae(envelope)
```

The method can also be called through the generic `check` interface using a dictionary:

```python
result = checker.check(
    ComplianceStandard.ASHRAE_90_1,
    {
        "wall_r_value": 15.0,
        "roof_r_value": 30.0,
        "window_u_value": 0.32,
        "glazing_ratio": 0.35,
    },
)
```

ASHRAE 90.1-2019 envelope requirements (climate zone 4A):

| Criterion | Requirement |
|---|---|
| Wall R-value | Minimum 13.0 |
| Roof R-value | Minimum 25.0 |
| Window U-value | Maximum 0.38 |
| Glazing ratio | Maximum 0.40 |

The result's `actual_value` is a compliance ratio (0.0 to 1.0) representing the fraction of criteria passed.

### Getting Recommendations

`get_recommendations` provides improvement suggestions based on a compliance result:

```python
recs = checker.get_recommendations(result)
for rec in recs:
    print(f"  - {rec}")
```

When the check passes, the single recommendation is `"Compliance achieved. Consider exceeding targets."`. When it fails, standard-specific recommendations are provided (e.g., HVAC upgrades for LL97, envelope insulation for BERDO, renewable energy for EPBD).

## SustainabilityReporter

`SustainabilityReporter` generates formatted reports from a `BuildingCarbonSummary` and produces certification documentation for green building rating systems.

### Creating a Reporter

```python
from revitpy.sustainability import SustainabilityReporter

reporter = SustainabilityReporter()
```

### Generating Reports

The `generate` method dispatches to the appropriate format handler. When `output_path` is provided the report is written to disk and the `Path` is returned; otherwise the content is returned as a string.

```python
from revitpy.sustainability import ReportFormat

# JSON report (returned as string)
json_content = reporter.generate(summary, format=ReportFormat.JSON)

# CSV report written to disk
path = reporter.generate(summary, format=ReportFormat.CSV, output_path="report.csv")

# HTML report written to disk
path = reporter.generate(summary, format=ReportFormat.HTML, output_path="report.html")
```

### Format-Specific Methods

Each format also has a dedicated method:

```python
# JSON
json_str = reporter.to_json(summary)
path = reporter.to_json(summary, path="output/report.json")

# CSV (rows sorted by carbon contribution, descending)
csv_str = reporter.to_csv(summary)
path = reporter.to_csv(summary, path="output/report.csv")

# HTML (uses Jinja2 if available, falls back to string formatting)
html_str = reporter.to_html(summary)
path = reporter.to_html(summary, path="output/report.html")
```

### Certification Documentation

`generate_certification_docs` produces a dictionary of documentation content for green building certification applications:

```python
from revitpy.sustainability import CertificationSystem

docs = reporter.generate_certification_docs(summary, CertificationSystem.LEED)
print(docs["certification_system"])              # "LEED"
print(docs["total_embodied_carbon_kgco2e"])      # 25100.0
print(docs["credits"]["MRc1"]["name"])           # "Building Life-Cycle Impact Reduction"
print(docs["credits"]["MRc1"]["potential_points"])  # 3

docs = reporter.generate_certification_docs(summary, CertificationSystem.BREEAM)
print(docs["credits"]["Mat01"]["name"])             # "Life Cycle Impacts"
print(docs["credits"]["Mat01"]["potential_credits"])  # 6
```

Supported certification systems and their credit mappings:

| System | Credit Code | Credit Name |
|---|---|---|
| `CertificationSystem.LEED` | `MRc1` | Building Life-Cycle Impact Reduction |
| `CertificationSystem.BREEAM` | `Mat01` | Life Cycle Impacts |
| `CertificationSystem.DGNB` | `ENV1.1` | Life Cycle Assessment |
| `CertificationSystem.GREENSTAR` | `Materials` | Life Cycle Impacts |

## Convenience Functions

For quick one-off operations without manually creating class instances:

```python
from revitpy.sustainability import (
    calculate_carbon,
    check_compliance,
    generate_report,
    MaterialData,
    ComplianceStandard,
    ReportFormat,
)

# Calculate carbon (creates CarbonCalculator internally)
materials = [
    MaterialData(name="Concrete", category="Concrete", mass_kg=50000.0),
]
results = calculate_carbon(materials)

# Check compliance (creates ComplianceChecker internally)
result = check_compliance(
    ComplianceStandard.LL97,
    {"area_sqft": 50000, "annual_emissions_tco2e": 300},
)

# Generate report (creates SustainabilityReporter internally)
content = generate_report(summary, format=ReportFormat.JSON, output_path="report.json")
```

## Enum Reference

### LifecycleStage

EN 15978 lifecycle stages for whole-life carbon assessment:

| Member | Value | Description |
|---|---|---|
| `A1_RAW_MATERIALS` | `"A1"` | Raw material extraction and processing |
| `A2_TRANSPORT` | `"A2"` | Transport to manufacturer |
| `A3_MANUFACTURING` | `"A3"` | Manufacturing |
| `A4_TRANSPORT_SITE` | `"A4"` | Transport to construction site |
| `A5_CONSTRUCTION` | `"A5"` | Construction and installation |
| `B1_USE` | `"B1"` | Use stage |
| `B2_MAINTENANCE` | `"B2"` | Maintenance |
| `B3_REPAIR` | `"B3"` | Repair |
| `B4_REPLACEMENT` | `"B4"` | Replacement |
| `B5_REFURBISHMENT` | `"B5"` | Refurbishment |
| `B6_ENERGY` | `"B6"` | Operational energy use |
| `B7_WATER` | `"B7"` | Operational water use |
| `C1_DEMOLITION` | `"C1"` | Demolition |
| `C2_TRANSPORT` | `"C2"` | Transport to disposal |
| `C3_WASTE` | `"C3"` | Waste processing |
| `C4_DISPOSAL` | `"C4"` | Disposal |
| `D_REUSE` | `"D"` | Reuse, recovery, and recycling potential |

### CertificationSystem

| Member | Value | Description |
|---|---|---|
| `LEED` | `"LEED"` | USGBC LEED rating system |
| `BREEAM` | `"BREEAM"` | BRE Environmental Assessment Method |
| `WELL` | `"WELL"` | WELL Building Standard |
| `GREENSTAR` | `"Green Star"` | Green Building Council of Australia |
| `DGNB` | `"DGNB"` | German Sustainable Building Council |

### ComplianceStandard

| Member | Value | Description |
|---|---|---|
| `LL97` | `"LL97"` | NYC Local Law 97 carbon intensity limits |
| `BERDO` | `"BERDO"` | Boston Building Emissions Reduction and Disclosure Ordinance |
| `EPBD` | `"EPBD"` | EU Energy Performance of Buildings Directive |
| `ASHRAE_90_1` | `"ASHRAE 90.1"` | ASHRAE 90.1 envelope thermal requirements |

### ReportFormat

| Member | Value | Description |
|---|---|---|
| `JSON` | `"json"` | Structured JSON output |
| `CSV` | `"csv"` | Comma-separated values |
| `HTML` | `"html"` | Formatted HTML document |

## Dataclass Reference

### MaterialData

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | -- | Material name |
| `category` | `str` | -- | Material category |
| `volume_m3` | `float` | `0.0` | Volume in cubic meters |
| `area_m2` | `float` | `0.0` | Area in square meters |
| `mass_kg` | `float` | `0.0` | Mass in kilograms |
| `density_kg_m3` | `float` or `None` | `None` | Density in kg/m3 |
| `element_id` | `str` or `None` | `None` | Source Revit element ID |
| `level` | `str` or `None` | `None` | Building level |
| `system` | `str` or `None` | `None` | Building system |

### EpdRecord

| Field | Type | Default | Description |
|---|---|---|---|
| `material_name` | `str` | -- | Material name |
| `category` | `str` | -- | Material category |
| `gwp_per_kg` | `float` | -- | GWP per kilogram (kgCO2e/kg) |
| `gwp_per_m3` | `float` or `None` | `None` | GWP per cubic meter (kgCO2e/m3) |
| `source` | `str` | `"generic"` | Data source identifier |
| `lifecycle_stages` | `list[LifecycleStage]` | `[]` | Applicable lifecycle stages |
| `valid_until` | `str` or `None` | `None` | EPD expiration date |
| `manufacturer` | `str` or `None` | `None` | Product manufacturer |

### CarbonResult

| Field | Type | Default | Description |
|---|---|---|---|
| `material` | `MaterialData` | -- | Source material data |
| `epd` | `EpdRecord` | -- | EPD record used for calculation |
| `embodied_carbon_kgco2e` | `float` | -- | Calculated embodied carbon |
| `lifecycle_stages` | `list[LifecycleStage]` | `[]` | Included lifecycle stages |
| `calculation_method` | `str` | `"mass_based"` | Method used (`"mass_based"`, `"volume_based"`, or `"no_data"`) |

### BuildingCarbonSummary

| Field | Type | Default | Description |
|---|---|---|---|
| `total_embodied_carbon_kgco2e` | `float` | -- | Total embodied carbon |
| `by_material` | `dict[str, float]` | `{}` | Carbon totals by material name |
| `by_system` | `dict[str, float]` | `{}` | Carbon totals by building system |
| `by_level` | `dict[str, float]` | `{}` | Carbon totals by building level |
| `by_lifecycle_stage` | `dict[str, float]` | `{}` | Carbon totals by lifecycle stage |
| `material_count` | `int` | `0` | Number of materials in the summary |
| `calculation_date` | `str` | `""` | ISO timestamp of the calculation |

### ComplianceResult

| Field | Type | Default | Description |
|---|---|---|---|
| `standard` | `ComplianceStandard` | -- | The standard checked |
| `passed` | `bool` | -- | Whether the check passed |
| `threshold` | `float` | -- | Limit value for the standard |
| `actual_value` | `float` | -- | Actual measured/calculated value |
| `unit` | `str` | -- | Unit of measurement |
| `recommendations` | `list[str]` | `[]` | Improvement recommendations |
| `details` | `dict[str, Any]` | `{}` | Standard-specific detail data |

### EnergyEnvelopeData

| Field | Type | Default | Description |
|---|---|---|---|
| `wall_r_value` | `float` | -- | Wall thermal resistance |
| `roof_r_value` | `float` | -- | Roof thermal resistance |
| `window_u_value` | `float` | -- | Window thermal transmittance |
| `glazing_ratio` | `float` | -- | Window-to-wall ratio (0.0 to 1.0) |
| `air_tightness` | `float` or `None` | `None` | Air tightness value |

### CarbonBenchmark

| Field | Type | Default | Description |
|---|---|---|---|
| `actual_kgco2e_per_m2` | `float` | -- | Actual carbon intensity |
| `target_kgco2e_per_m2` | `float` | -- | Target carbon intensity |
| `benchmark_source` | `str` | -- | Source of the benchmark (e.g., `"RIBA 2030 Climate Challenge"`) |
| `rating` | `str` | -- | Performance rating |
| `percentile` | `float` or `None` | `None` | Estimated percentile ranking |

## Full Example

A complete workflow from material data through carbon calculation, compliance checking, and report generation:

```python
from revitpy.sustainability import (
    CarbonCalculator,
    EpdDatabase,
    ComplianceChecker,
    SustainabilityReporter,
    MaterialData,
    LifecycleStage,
    ComplianceStandard,
    EnergyEnvelopeData,
    CertificationSystem,
    ReportFormat,
)

# 1. Set up the EPD database
epd_db = EpdDatabase(cache_path="epd_cache.json")

# 2. Define materials
materials = [
    MaterialData(name="Concrete", category="Concrete", mass_kg=120000.0, volume_m3=50.0, level="Level 1", system="Structure"),
    MaterialData(name="Steel", category="Metals", mass_kg=25000.0, volume_m3=3.2, level="Level 1", system="Structure"),
    MaterialData(name="Timber", category="Wood", mass_kg=8000.0, volume_m3=16.0, level="Level 2", system="Framing"),
    MaterialData(name="Glass", category="Glass", mass_kg=4000.0, volume_m3=1.6, level="Level 1", system="Facade"),
    MaterialData(name="Insulation", category="Insulation", mass_kg=1500.0, volume_m3=50.0, level="Level 1", system="Envelope"),
]

# 3. Calculate embodied carbon
calculator = CarbonCalculator(epd_database=epd_db)
results = calculator.calculate(materials)
summary = calculator.summarize(results)

# 4. Benchmark against RIBA 2030
bench = calculator.benchmark(summary, building_area_m2=3000.0, building_type="office")
print(f"Rating: {bench.rating} ({bench.actual_kgco2e_per_m2:.1f} vs {bench.target_kgco2e_per_m2:.1f} kgCO2e/m2)")

# 5. Check compliance
checker = ComplianceChecker()

ll97 = checker.check_ll97({
    "area_sqft": 32000,
    "annual_emissions_tco2e": 200,
    "occupancy_type": "office",
})
print(f"LL97: {'PASS' if ll97.passed else 'FAIL'}")

ashrae = checker.check_ashrae(EnergyEnvelopeData(
    wall_r_value=15.0,
    roof_r_value=30.0,
    window_u_value=0.32,
    glazing_ratio=0.35,
))
print(f"ASHRAE 90.1: {'PASS' if ashrae.passed else 'FAIL'}")

# 6. Generate reports
reporter = SustainabilityReporter()
reporter.generate(summary, format=ReportFormat.HTML, output_path="sustainability_report.html")
reporter.generate(summary, format=ReportFormat.JSON, output_path="sustainability_report.json")

# 7. Generate certification docs
leed_docs = reporter.generate_certification_docs(summary, CertificationSystem.LEED)
print(f"LEED MRc1 potential points: {leed_docs['credits']['MRc1']['potential_points']}")

# 8. Save EPD cache for next run
epd_db.save_cache("epd_cache.json")
```
