# Energy analytics

`python -m energy_analytics` · package `energy_analytics`

## What it does

1. **Reads the envelope.** Queries exterior `Wall`s (`Function = Exterior`) and
   `Window`s through `api.query(...)`. For each it reads `Area` (ft², converted
   to m²) and a `U-Value (W/m2K)` project parameter. Elements without a U-value
   are skipped.
2. **Heat loss.** Sums U x A per level (W/K).
3. **Meter data regression.** Fits an ASHRAE Guideline 14 style three-parameter
   heating change-point model to daily energy vs outdoor temperature: grid
   search plus `scipy.optimize.curve_fit`. It reports base load, balance point,
   slope, R² and CV(RMSE). The slope converts to a heat loss coefficient, which
   is compared with the model's U x A. A large gap points to missing envelope
   data, infiltration or a controls problem.
4. **Hourly model.** Trains a scikit-learn random forest on outdoor temperature,
   hour, weekday and occupancy. The last 20% of the year is held out
   chronologically and used to report R² and MAE.
5. **Embodied carbon.** `revitpy.extract.QuantityExtractor` reads wall and
   floor `Volume` (ft³ to m³). `revitpy.sustainability.CarbonCalculator` applies
   the built-in generic ICE v2.0 factors for each `Material` and benchmarks the
   result per m² of floor area against the RIBA 2030 office target. This is a
   screening-level A1-A3 figure for walls and floors only.
6. **Write-back.** Walls with U > 1.0 and windows with U > 2.0 W/m²K get a note
   in `Comments`. All writes happen in one `api.transaction(...)`, so an error
   part-way through rolls the whole set back.

Pass `html=Path("energy.html")` (or `--html energy.html`) to also write an
interactive Plotly chart.

## Data

With no `metered=` argument, hourly weather and meter data are **synthetic**.
They are generated from the model's own U x A, with a 15 °C balance point, base
and occupied electrical loads, and 5% noise (`poc_common.timeseries`). The
regression recovering the model's heat loss is therefore a consistency check of
the pipeline, not evidence about a real building. To use real data, pass
`metered=`: a DataFrame with an hourly `DatetimeIndex` and `outdoor_temp_c`,
`occupied` and `total_kwh` columns, e.g. from a BMS or utility export.

## Model parameters used

| Parameter | On | Notes |
|---|---|---|
| `Area` | walls, windows, floors | built-in, ft² |
| `Volume` | walls, floors | built-in, ft³ |
| `Level`, `Comments` | all | built-in |
| `Function` | walls | `Exterior` / `Interior` (a type parameter in Revit) |
| `Material` | walls, floors | matched to an EPD record by name |
| `U-Value (W/m2K)` | walls, windows | project parameter. Revit's own thermal properties live on types and materials; map them into this parameter or change `model_data.U_VALUE`. |

## Limitations

- U x A only: no thermal bridges, ground floor or roof losses, infiltration or
  solar gains.
- The random forest mostly learns the synthetic generator's structure. Its
  score says nothing about real-world accuracy.
- Carbon factors are generic cradle-to-gate averages. Use product EPDs for any
  real assessment.
