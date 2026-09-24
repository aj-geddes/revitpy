---
layout: page
title: Sustainability & Carbon Analytics
description: Estimate embodied carbon with sourced ICE factors, match EPDs with confidence scores, screen LL97/BERDO/EPBD/ASHRAE 90.1-2019 compliance, and generate sustainability reports with RevitPy.
doc_tier: user
---

RevitPy provides a sustainability analysis module for embodied carbon estimation, Environmental Product Declaration (EPD) management, building emissions compliance screening, and report generation for green building certification workflows.

> **Screening-level estimates, not a compliance determination.** Built-in carbon factors are generic database averages, not product EPDs, and built-in regulatory limits are transcriptions that can be out of date or simplified. Every built-in number records its source and year, every one can be overridden, and every result exposes how confident the material-name match was. Verify results against the governing code text and product-specific EPDs, with a qualified professional, before relying on them.

## Overview

The `revitpy.sustainability` module provides five core components:

- **`CarbonCalculator`** -- Calculates embodied carbon for building materials using EPD data, aggregates results into building-level summaries, and benchmarks against RIBA 2030 Climate Challenge targets.
- **`EpdDatabase`** -- Manages EPD records with a local cache of sourced generic values, deterministic scored name matching, and optional async lookup against the EC3 (Embodied Carbon in Construction Calculator) API.
- **`ComplianceChecker`** -- Screens building performance against LL97, BERDO, caller-supplied EPBD national limits, and ASHRAE 90.1-2019 envelope values, with pass/fail results, sources, caveats, and improvement recommendations.
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

Materials without a matching EPD record are skipped with a logged warning. If the calculation itself fails, a `CarbonCalculationError` is raised.

Each `CarbonResult.epd` records how the material name was matched (`match_type`, `match_confidence`, `matched_key`) and where the factor came from (`source`, `source_year`, `notes`). Review low-confidence results before reporting totals:

```python
for r in results:
    if (r.epd.match_confidence or 0) < 0.5:
        print(f"Review {r.material.name!r}: matched {r.epd.matched_key!r} "
              f"({r.epd.match_type}, {r.epd.match_confidence})")
```

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

Built-in RIBA 2030 targets (kgCO2e/m2). **Caveat:** these values have not been re-verified against the current RIBA 2030 Climate Challenge publication, whose embodied-carbon targets are defined over a specific life-cycle scope; treat the rating as indicative only:

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

`EpdDatabase` manages Environmental Product Declaration records with a local cache of sourced generic values, deterministic scored name matching, and optional async queries against the EC3 API.

### Creating a Database

```python
from revitpy.sustainability import EpdDatabase, EpdRecord

# Default: built-in generic values only
epd_db = EpdDatabase()

# With EC3 API token for remote lookups
epd_db = EpdDatabase(api_token="your-ec3-api-token")

# With a local cache file
epd_db = EpdDatabase(cache_path="/path/to/epd_cache.json")

# Override or extend the built-ins with product EPDs
epd_db = EpdDatabase(
    overrides={
        "concrete": EpdRecord(
            material_name="Supplier 30 MPa mix",
            category="Concrete",
            gwp_per_kg=0.098,
            source="Supplier EPD S-P-01234",
            valid_until="2029-06-30",
        )
    }
)
epd_db.register("clt", EpdRecord(material_name="CLT panel", category="Wood",
                                 gwp_per_kg=0.44, source="Manufacturer EPD 2024"))
```

### Built-in Generic Factors

The built-in factors are cradle-to-gate (A1--A3) values from the **ICE database v2.0** (Hammond & Jones, *Inventory of Carbon & Energy*, University of Bath, January 2011), transcribed from its summary tables. ICE v3.0 (Circular Ecology, 2019) values could not be verified against the primary publication, so they are not used. ICE is a generic inventory rather than a product EPD, so `valid_until` is `None`; `source_year` (2011) records the data vintage instead. Each record's `notes` names the exact ICE row.

| Key(s) | Material | kgCO2e/kg | ICE v2.0 row / caveat |
|---|---|---|---|
| `concrete` | Concrete | 0.107 | Concrete, General. ICE recommends a specific mix (e.g. 25/30 MPa = 0.113) |
| `steel` | Steel | 1.46 | Steel, General, UK (EU) average recycled content (59%) |
| `timber` | Timber | 0.31 | Timber, General, fossil carbon only (biogenic 0.41 and storage excluded) |
| `glass` | Glass | 0.91 | Glass, Primary Glass |
| `aluminum` | Aluminum | 9.16 | Aluminium, General (worldwide average recycled content) |
| `brick` | Brick | 0.24 | Bricks, General (Common Brick) |
| `gypsum` | Gypsum Board | 0.39 | Plaster, Plasterboard |
| `mineral wool` | Mineral wool insulation | 1.28 | Insulation, Mineral wool |
| `rock wool`, `rockwool`, `stone wool` | Rock/stone wool | 1.12 | Insulation, Rockwool (ICE notes "cradle to grave") |
| `glass wool`, `fiberglass`, `fibreglass` | Glass wool | 1.35 | Insulation, Fibreglass (Glasswool): **kgCO2 only**, ICE flags poor data |
| `eps`, `expanded polystyrene` | EPS | 3.29 | Plastics, Expanded Polystyrene |
| `polystyrene`, `xps`, `extruded polystyrene` | Polystyrene (generic) | 3.43 | Plastics, General Purpose Polystyrene. **Generic fallback:** ICE v2.0 has no XPS row and XPS blowing agents can raise GWP a lot, so use a product EPD |
| `polyurethane`, `pir`, `pur`, `polyisocyanurate` | PUR/PIR rigid foam | 4.26 | Plastics, Polyurethane Rigid Foam |
| `insulation` | Insulation (generic) | 1.86 | Insulation, General Insulation (**kgCO2 only**, market-share blend). **Generic fallback** |

Volumetric factors (`gwp_per_m3`) are **not** from ICE. They are derived from an assumed density that is recorded in `assumed_density_kg_m3`: concrete 2400, steel 7850, timber 500, glass 2500, aluminum 2700, brick 1800, and gypsum board 800 kg/m3. Insulation records have no volumetric factor because product densities vary too widely. Provide `mass_kg` for insulation.

Earlier releases shipped a single generic `insulation` factor of 1.86 for everything. That hid a roughly threefold difference between mineral wool (about 1.1--1.3) and foam plastics (about 3.3--4.3 kgCO2e/kg). The generic record is still there as a last resort, but matches that land on it are capped at a confidence of 0.3 and logged as warnings.

### Looking Up EPDs

`lookup` uses deterministic scored matching (`revitpy.sustainability.matching`):

1. **exact**: the name equals a key, ignoring case and punctuation (confidence 1.0);
2. **token**: a key's whole words appear in the name (confidence 0.5--0.9);
3. **substring**: a key appears inside a word (confidence 0.15--0.45);
4. **category**: when nothing matches and `category` is given, a fixed representative record for that category is used, e.g. `Metals` goes to steel (confidence 0.2).

Specific records are tried before generic fallback records, and the catch-all `insulation` record is tried last. If several keys match in the same tier, the key whose match ends latest in the name wins, because English compound names put the head noun last. Ties then go to the longest key, then to alphabetical order. The result never depends on dictionary order. If competing keys would give a *different* record, the match is flagged as ambiguous, its confidence is multiplied by 0.6, and a warning is logged.

The returned record is a copy annotated with `match_type`, `match_confidence` and `matched_key`:

```python
epd = epd_db.lookup("concrete")
print(epd.gwp_per_kg, epd.match_type, epd.match_confidence)   # 0.107 exact 1.0

epd = epd_db.lookup("Glass Wool Insulation")
print(epd.matched_key)                                        # "glass wool"

epd = epd_db.lookup("Aluminum-Clad Timber Window")
print(epd.matched_key, epd.match_confidence)                  # "timber" 0.36 (ambiguous with "aluminum")

epd = epd_db.lookup("portland cement", category="Concrete")
print(epd.match_type)                                         # "category"

epd = epd_db.lookup("exotic material")                        # None
```

Heuristics like this can still pick the wrong record. For example, "Timber Frame with Steel Connectors" resolves to steel, flagged as ambiguous. Treat any `match_confidence` below 0.5 as needing human review, or register an exact key for the name.

### Generic EPD Lookup

`get_generic_epd` resolves a category name to a built-in generic record deterministically:

```python
epd_db.get_generic_epd("Concrete")  # Concrete
epd_db.get_generic_epd("Metals")    # Steel (fixed representative, not dict order)
epd_db.get_generic_epd("Wood")      # Timber
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

`search_async` performs a broader search across local cache and the EC3 API. Local results are ranked by match tier, then confidence:

```python
async def main():
    results = await epd_db.search_async("concrete", limit=10)
    for epd in results:
        print(f"{epd.material_name} ({epd.source}): {epd.gwp_per_kg} kgCO2e/kg")

asyncio.run(main())
```

### Cache Management

```python
# Save current cache to disk (provenance fields are preserved)
epd_db.save_cache("/path/to/epd_cache.json")

# Load cache from disk (also done automatically at init if cache_path is set)
epd_db.load_cache("/path/to/epd_cache.json")
```

## ComplianceChecker

`ComplianceChecker` screens building performance data against emissions and energy standards. Each check returns a `ComplianceResult` with pass/fail status, the threshold used, a `source` citation, `notes` with caveats, and improvement recommendations.

> These checks are **screening-level estimates, not compliance determinations**. Each result's `notes` starts with this disclaimer. No check silently falls back to a default building category, and every built-in limit can be overridden.

### Creating a Checker

```python
from revitpy.sustainability import ComplianceChecker

checker = ComplianceChecker()
```

### Generic Check Interface

The `check` method dispatches to the correct standard-specific checker. You can put overrides in the data dictionary as `ll97_limits`, `berdo_limits`, `epbd_limits` (plus `epbd_limit_source`), or, for ASHRAE, `overrides`:

```python
from revitpy.sustainability import ComplianceStandard

result = checker.check(
    ComplianceStandard.LL97,
    {"area_sqft": 50000, "annual_emissions_tco2e": 300,
     "property_type": "Office", "compliance_year": 2026},
)

print(result.passed)           # True or False
print(result.actual_value)     # Actual intensity
print(result.threshold)        # Limit used
print(result.unit)             # e.g. "tCO2e/sqft/year"
print(result.source)           # Citation for the limit (or "caller-supplied")
print(result.notes)            # Disclaimer and caveats
print(result.recommendations)  # Improvement suggestions
print(result.details)          # Standard-specific details dict
```

### NYC Local Law 97 (LL97)

This check compares carbon intensity with the LL97 limit for the chosen **compliance period**. The period is picked from `year`, then `building_data["compliance_year"]`, and falls back to the current calendar year:

| Period | Years |
|---|---|
| `2024-2029` | 2024--2029 |
| `2030-2034` | 2030--2034 |

For a year before 2024, the check applies the 2024--2029 limits and adds a warning. For a year after 2034, it applies the 2030--2034 limits and warns that the result is likely optimistic, because limits from 2035 onward are stricter and are not modeled.

Classify the building in one of two ways:

- `property_type`: an ENERGY STAR Portfolio Manager (ESPM) property type, such as `"Office"`, `"Multifamily Housing"` or `"K-12 School"`. Factors are transcribed from **1 RCNY §103-14(c)(3)** for both periods (60 property types). The rule requires ESPM property types for calendar year 2026 reporting onward.
- `occupancy_type`: an LL97 occupancy group (`A`, `B`, `B-healthcare`, `E`, `F`, `H`, `I-1`...`I-4`, `M`, `R-1`, `R-2`, `S`, `U`) or a convenience alias (`office` = B, `residential`/`multifamily` = R-2, `hotel` = R-1, `retail` = M, `healthcare`/`hospital` = I-2, `education`/`school` = E, `warehouse`/`storage` = S, `assembly` = A, `factory`/`industrial` = F). Aliases are recorded in `notes`. Using occupancy groups for 2026 or later adds a warning.

If neither is given, or the value is unknown, the check raises `ComplianceError`. There is no default occupancy.

```python
result = checker.check_ll97(
    {"area_sqft": 50000, "annual_emissions_tco2e": 300, "property_type": "Office"},
    year=2031,                    # selects the 2030-2034 period
    limits={"Office": 0.0027},    # optional override (or "*" for any)
)
```

Occupancy-group limits (tCO2e/sf/yr) come from **NYC Admin. Code §28-320.3.1** (2024--2029) and **§28-320.3.2** (2030--2034), Local Law 97 of 2019 as amended:

| Group | 2024--2029 | 2030--2034 |
|---|---|---|
| A | 0.01074 | 0.00420 |
| B | 0.00846 | 0.00453 |
| B-healthcare (item 6: B emergency-response, non-production lab, ambulatory health care), H, I-2, I-3 | 0.02381 | 0.01330 |
| E, I-4 | 0.00758 | 0.00344 |
| F | 0.00574 | 0.00167 |
| I-1 | 0.01138 | 0.00598 |
| M | 0.01181 | 0.00403 |
| R-1 | 0.00987 | 0.00526 |
| R-2 | 0.00675 | 0.00407 |
| S, U | 0.00426 | 0.00110 |

A few ESPM examples from 1 RCNY §103-14(c)(3), in tCO2e/sf/yr: Office 0.00758 for 2024--2029 and 0.002690852 for 2030--2034; Multifamily Housing 0.00675 and 0.003346640; Hotel 0.00987 and 0.003850668.

Earlier releases got two limits wrong: `retail` was 0.01074 (the group A value) and `warehouse` was 0.00574 (the group F value). Both now map to the correct groups, M and S.

The check does not model mixed-use buildings, which LL97 handles by area-weighting limits across spaces, and it does not model deductions or the 2035+ periods.

### Boston BERDO

```python
result = checker.check_berdo(
    {"area_sqft": 50000, "annual_emissions_kgco2e": 200000, "building_type": "office"},
    limits={"office": 5.3},   # strongly recommended: current BERDO 2.0 value
)
```

Required keys: `area_sqft`, `annual_emissions_kgco2e`, `building_type`.

**The built-in BERDO values (office 5.4, residential 3.6, retail 6.1, education 4.8 kgCO2e/sf/yr) are unverified legacy placeholders.** They have not been checked against the BERDO 2.0 emissions standards. When they are used, the result's `source` says so and a warning is logged. Pass `limits` taken from the current BERDO 2.0 tables.

### EU EPBD

The Energy Performance of Buildings Directive (Directive (EU) 2024/1275) does **not** set a pan-EU numeric kWh/m2/yr cap. Member States set minimum energy performance and NZEB/ZEB requirements in national or regional law. RevitPy therefore ships **no EPBD limits**, and you must supply the national or local limit:

```python
result = checker.check_epbd(
    {"area_m2": 5000, "primary_energy_kwh": 550000, "building_type": "office"},
    limits={"office": 120.0},                # kWh/m2/yr, keyed by type or "*"
    limit_source="<national regulation, edition>",
)
print(result.notes[1])
# Checked against caller-supplied limit of 120.0 kWh/m2/yr (<national regulation, edition>);
# the EPBD itself sets no pan-EU numeric cap.
```

Required keys: `area_m2`, `primary_energy_kwh`, `building_type`. If you supply no applicable limit, the check raises `ComplianceError` with `requirement="limits"`.

### ASHRAE 90.1 Envelope

This check screens envelope values against **ANSI/ASHRAE/IES Standard 90.1-2019** prescriptive values for nonresidential buildings. `climate_zone` is **required** and must be 0--8 with an optional A/B/C, such as `"4A"`, `"5B"` or `"7"`. Any other value raises `ComplianceError`; there is no silent fallback to 4A.

```python
from revitpy.sustainability import EnergyEnvelopeData

envelope = EnergyEnvelopeData(
    wall_r_value=15.0,
    roof_r_value=30.0,
    window_u_value=0.32,
    glazing_ratio=0.35,
)

result = checker.check_ashrae(envelope, "4A", overrides={"wall_r_min": 13.0})
```

Or through `check` (all envelope keys and `climate_zone` are required, with no assumed values):

```python
result = checker.check(
    ComplianceStandard.ASHRAE_90_1,
    {"climate_zone": "5A", "wall_r_value": 15.0, "roof_r_value": 30.0,
     "window_u_value": 0.32, "glazing_ratio": 0.35,
     "overrides": {"wall_r_min": 13.0}},
)
```

Built-in limits by climate zone:

| Zone | Roof min. R c.i. (insulation entirely above deck) | Fixed fenestration max. U | Max. window-to-wall ratio |
|---|---|---|---|
| 0 | 25 | 0.50 | 0.40 |
| 1 | 20 | 0.50 | 0.40 |
| 2 | 25 | 0.45 | 0.40 |
| 3 | 25 | 0.42 | 0.40 |
| 4 | 30 | 0.36 | 0.40 |
| 5 | 30 | 0.34 | 0.40 |
| 6 | 30 | 0.34 | 0.40 |
| 7 | 35 | 0.29 | 0.40 |
| 8 | 35 | 0.26 | 0.40 |

Sources and caveats:

- **Roof:** Tables 5.5-0 to 5.5-8 as reproduced in the US DOE Building Energy Codes Program training "ANSI/ASHRAE/IES Standard 90.1-2019: Envelope". Only the "insulation entirely above deck" roof class is modeled; metal-building and attic roofs have different requirements.
- **Fenestration:** fixed vertical fenestration U-factors from a **secondary source**, National Glass Association Glass Technical Paper FB74-22 (2022), Table 1. Operable fenestration (U-0.45 in zones 4--5), entrance doors and SHGC are not checked. Verify against the standard, for zone 5 in particular.
- **Window-to-wall ratio:** 40% in all climate zones (§5.5.4.2.1, prescriptive path).
- **Walls are not evaluated by default.** 90.1-2019 wall minimums depend on wall type (mass, metal building, steel-framed or wood-framed), and a single `wall_r_value` cannot represent that. Pass `overrides={"wall_r_min": ...}` for your wall type. Until you do, `details["not_evaluated"]` lists `"wall"`.

`actual_value` is the fraction of *evaluated* criteria that passed.

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
    {"area_sqft": 50000, "annual_emissions_tco2e": 300,
     "property_type": "Office", "compliance_year": 2026},
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
| `classification_code` | `str` or `None` | `None` | Code assigned by `MaterialExtractor.classify` |
| `classification_match` | `str` or `None` | `None` | Match tier used for classification |
| `classification_confidence` | `float` or `None` | `None` | Heuristic match confidence (0--1) |

### EpdRecord

| Field | Type | Default | Description |
|---|---|---|---|
| `material_name` | `str` | -- | Material name |
| `category` | `str` | -- | Material category |
| `gwp_per_kg` | `float` | -- | GWP per kilogram (kgCO2e/kg) |
| `gwp_per_m3` | `float` or `None` | `None` | GWP per cubic meter (kgCO2e/m3) |
| `source` | `str` | `"generic"` | Data source identifier |
| `lifecycle_stages` | `list[LifecycleStage]` | `[]` | Applicable lifecycle stages |
| `valid_until` | `str` or `None` | `None` | EPD expiration date (None for generic database values) |
| `manufacturer` | `str` or `None` | `None` | Product manufacturer |
| `source_year` | `int` or `None` | `None` | Year of the source data |
| `assumed_density_kg_m3` | `float` or `None` | `None` | Density used to derive `gwp_per_m3` |
| `notes` | `str` | `""` | Source row and caveats |
| `is_generic_fallback` | `bool` | `False` | Catch-all record; match confidence is capped at 0.3 |
| `match_type` | `str` or `None` | `None` | Set by `lookup`: `exact`, `token`, `substring` or `category` |
| `match_confidence` | `float` or `None` | `None` | Set by `lookup`: heuristic match quality (0--1), not a probability |
| `matched_key` | `str` or `None` | `None` | Set by `lookup`: the database key that matched |

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
| `source` | `str` | `""` | Citation for the limit used, or `"caller-supplied"` |
| `notes` | `list[str]` | `[]` | Screening disclaimer, aliases applied, warnings |

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
    MaterialData(name="Mineral Wool Insulation", category="Insulation", mass_kg=1500.0, volume_m3=50.0, level="Level 1", system="Envelope"),
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

ll97 = checker.check_ll97(
    {"area_sqft": 32000, "annual_emissions_tco2e": 200, "property_type": "Office"},
    year=2026,
)
print(f"LL97 screening: {'PASS' if ll97.passed else 'FAIL'} ({ll97.source})")

ashrae = checker.check_ashrae(
    EnergyEnvelopeData(
        wall_r_value=15.0,
        roof_r_value=30.0,
        window_u_value=0.32,
        glazing_ratio=0.35,
    ),
    "4A",
    overrides={"wall_r_min": 13.0},  # your wall type's 90.1-2019 minimum
)
print(f"ASHRAE 90.1-2019 screening: {'PASS' if ashrae.passed else 'FAIL'}")
for note in ashrae.notes:
    print(f"  note: {note}")

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
