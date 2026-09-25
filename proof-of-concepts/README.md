# RevitPy proofs of concept

Five small demos of data-science work on Revit model data with RevitPy. Each one
reads elements through the RevitPy API, analyses them with the scientific Python
stack (NumPy, pandas, SciPy, scikit-learn), and writes a result back to the model
inside a transaction.

They are demos, not products. The analyses are deliberately simple, most input
data (weather, meter readings, occupancy counts, sensor feeds, site photos) is
synthetic, and the engineering checks are not code checks. What they do show is
the plumbing a real tool needs, and that plumbing runs the same way against a live
Revit session and against RevitPy's mock model.

| Directory | Package | What it does |
|---|---|---|
| [`energy-analytics/`](energy-analytics/README.md) | `energy_analytics` | Envelope heat loss (U x A) from walls and windows, a change-point regression and a random-forest model on meter data, embodied carbon of walls and floors. Flags poor elements. |
| [`ml-space-planning/`](ml-space-planning/README.md) | `space_planning` | Room utilization features from occupancy counts, k-means clustering, an occupancy forecast against a naive baseline, and team-to-room assignment (Hungarian algorithm). |
| [`iot-sensor-integration/`](iot-sensor-integration/README.md) | `iot_monitor` | Replays a sensor feed through an asyncio pipeline, applies comfort-limit and step-change alarm rules per sensor, and writes each room's latest status. |
| [`structural-analysis/`](structural-analysis/README.md) | `structural_analysis` | Simplified steel beam and column checks, a 2D frame solved with the direct stiffness method, modal periods of a shear-building model, steel tonnage and carbon. |
| [`computer-vision-progress/`](computer-vision-progress/README.md) | `progress_vision` | Detects installed precast panels in a rectified facade photo (Otsu threshold, per-cell fill ratio) and records progress on the model's panel grid. |

`common/poc_common` holds what they share: connecting to Revit or the demo model,
parameter helpers and unit conversion, the demo building, and the synthetic data
generators.

## Running them

From a RevitPy checkout (Python 3.11+):

```bash
pip install -e . -e "./proof-of-concepts[test]"
python -m energy_analytics        # or space_planning, iot_monitor,
                                  #    structural_analysis, progress_vision
cd proof-of-concepts && pytest    # 76 tests, about 10 seconds
```

Each `python -m` entry point builds the demo building, runs the analysis, writes
its results into the mock model and prints a short report. `--help` lists the
options, and `--no-write` skips the write-back. The same commands are installed as
`poc-energy`, `poc-space-planning`, `poc-iot`, `poc-structural` and `poc-progress`.

## Running inside Revit

Every package exposes `run(app=None, ...)`. Pass Revit's `UIApplication` to work on
the open model:

```python
from energy_analytics import run

print(run(__revit__).to_text())
```

Run that with **RevitPy > Run Script**, or send it from a terminal with
`revitpy live run script.py` while the Live Server is on. The interpreter RevitPy
embeds must be able to import the packages, so install this project into the
environment its `python_path` setting points at. Each PoC directory has an
`examples/run_in_revit.py` like the one above.

On a real model the demos read the parameters described in each PoC's README.
Some are built-in Revit parameters (`Area`, `Volume`, `Length`, `Level`, `Mark`,
`Comments`). Others are project parameters you would add, such as
`U-Value (W/m2K)` or `Sensor ID`. Elements without them are skipped. Results are
written to `Comments` because every element has it.

## What RevitPy adds here

pyRevit also runs CPython 3 now, so "impossible in pyRevit" is not the argument.
These demos lean on what RevitPy adds on top of running Python in Revit:

- **A typed, queryable API.** `api.query(Room).execute()` returns `Room` wrappers.
  Parameters are read with `get_parameter_value()`. New categories are one class
  away (`StructuralColumn` in `poc_common` is three lines).
- **Transactions as context managers.** `with api.transaction("..."):` commits on
  success and rolls back on any exception. `test_write_back_is_atomic` checks
  this.
- **Testing without Revit.** `revitpy.testing.mock_revit.MockApplication` stands
  in for Revit, so the same `run()` is exercised in CI on Linux.
- **Model data helpers.** `revitpy.extract.QuantityExtractor` converts Revit's
  internal feet, ft² and ft³ to metric. `revitpy.sustainability` provides
  embodied-carbon factors and RIBA 2030 benchmarks.
- **Normal packaging.** The demos are ordinary Python packages with a
  `pyproject.toml`, installed into a normal virtual environment with the
  scientific stack. Revit imports them through RevitPy's `python_path`.

See [MASTER_DOCUMENTATION.md](MASTER_DOCUMENTATION.md) for how the pieces fit
together and what each demo leaves out.
