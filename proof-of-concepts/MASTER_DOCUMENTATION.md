# Proofs of concept: how they are built

This document covers the structure the five demos share, how model data flows
through them, and what they leave out. The top-level [README](README.md) covers
running them. Each PoC's README covers its analysis.

## Layout

```
proof-of-concepts/
├── pyproject.toml            # one non-published project: revitpy-pocs
├── common/poc_common/        # shared: connect, params/units, demo model, synthetic data
├── tests/                    # entry-point smoke tests, in-Revit example tests
└── <poc>/
    ├── README.md
    ├── examples/run_in_revit.py
    ├── src/<package>/
    │   ├── __init__.py       # run(app=None, ...) -> Report with .to_text()
    │   ├── __main__.py       # python -m <package>
    │   ├── model_data.py     # RevitPy queries and write-back
    │   └── analysis.py       # pure NumPy/pandas/SciPy/scikit-learn, no Revit
    └── tests/
        ├── test_analysis.py  # analysis functions against known answers
        └── test_*_model.py   # run() against the demo model
```

Keeping `analysis.py` free of Revit calls is deliberate. The analysis is tested
on plain DataFrames, and `model_data.py` is the only layer that touches the
model.

## Data flow

```
app (__revit__ in Revit, MockApplication elsewhere)
  └─ poc_common.connect(app) ─► RevitAPI
       ├─ api.query(Room | Wall | Window | Floor | Level | StructuralColumn ...)
       │     .execute()  ─► typed Element wrappers
       ├─ element.get_parameter_value("Area") ... internal units (ft, ft², ft³)
       │     └─ converted to metric (poc_common.FT2_TO_M2, QuantityExtractor)
       ├─ model_data.*  ─► pandas DataFrames
       ├─ analysis.*    ─► results
       └─ with api.transaction("..."):
             element.set_parameter_value("Comments", ...)   # all-or-nothing
```

`connect(None)` builds the demo building (`poc_common.demo_model`): three
storeys with 24 rooms, an exterior envelope with walls and windows, slabs, a
5 x 3 steel column grid with beams, and 60 precast facade panels. It is a
`revitpy.testing.mock_revit.MockApplication`, the mock RevitPy's own test suite
uses, so queries, parameter reads, typed wrappers and transaction rollback
behave as they do against Revit through `revitpy.revit`'s adapters.

## Conventions

- **Units.** Revit reports lengths in feet, areas in ft² and volumes in ft³.
  Every conversion to metric happens in `model_data.py` or through
  `QuantityExtractor`, never in the analysis code.
- **Missing data.** `poc_common.param()` and `number()` return a default when
  a parameter is missing, so elements without the needed parameters are
  skipped rather than crashing the run. Each run raises a clear `ValueError`
  if nothing usable is found.
- **Write-back.** Results go to `Comments` in one named transaction per run.
  Every element has `Comments`. A production tool would use dedicated shared
  parameters. Pass `write=False` (CLI `--no-write`) to leave the model
  untouched.
- **Synthetic inputs.** Anything that doesn't come from the model is generated
  by `poc_common.timeseries` from a seed: weather, meter data, occupancy, sensor
  feeds and facade photos. Every `run()` accepts the real equivalent as an
  argument, and the report says when an input was synthetic.

## Dependencies

Declared in `pyproject.toml`, only what the code imports:

| Package | Used for |
|---|---|
| `revitpy` | model access, quantities, carbon factors (installed from this repo) |
| `numpy`, `pandas` | everything |
| `scipy` | change-point fit, assignment, frame solve, eigenproblem, image labelling |
| `scikit-learn` | random forest, k-means, gradient boosting |
| `plotly` | optional HTML chart in `energy_analytics` |
| `loguru` | quieting RevitPy's logging in the CLIs |
| `pytest` (extra `test`) | tests |

The earlier `requirements.txt` files listed TensorFlow, PyTorch, Detectron2,
FEniCS, cloud IoT SDKs and several packages that don't exist on PyPI. The code
never used them, so they were removed. The READMEs say where a lighter method
replaced a heavy framework.

## CI

The `pocs` job in `.github/workflows/ci.yml` installs RevitPy and this project
on Python 3.12, then runs `pytest` from this directory, using the
`[tool.pytest.ini_options]` in this `pyproject.toml` rather than the repository
root's. `ruff check proof-of-concepts` and `ruff format --check
proof-of-concepts` pass under the root ruff configuration.

## What the demos do not do

- They make no claims about savings, ROI or market size. Earlier drafts of this
  directory did, without evidence, and those documents were removed.
- They are not engineering or energy-modelling tools. The structural checks
  are not design-code checks, the energy model is a U x A screening model, and
  the carbon factors are generic cradle-to-gate averages.
- They have not been run against a large production model. The API calls are
  the ones RevitPy's live adapters implement, but nothing here has been tuned
  for performance.
