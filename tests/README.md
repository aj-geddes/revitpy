# RevitPy test suite

All tests run without Revit. Live-Revit code paths are exercised against fakes
(`revitpy.testing.MockRevit`, and a fake `Autodesk.Revit.DB` namespace in
`tests/revit/`).

```
tests/
  api/             Core API: typed queries, transactions, parameters, CLI, exports
  revit/           pythonnet adapters (fake Revit API) and the in-Revit host helpers
  orm/             RevitContext, query builder, change tracking, caching, persistence
  events/          Class-based handlers and the native Revit event bridge
  ai/              MCP server protocol, auth, safety guard, tools
  cloud/           APS client, Design Automation jobs, webhooks, auth
  ifc/             IFC export/import (real ifcopenshell when installed), BCF, IDS
  interop/         Speckle client/sync/subscriptions (mocked at the specklepy boundary)
  sustainability/  Carbon, EPD matching, compliance checks
  extract/         Quantities, materials, costs, export
  performance/     Stress/benchmark suite (marked `slow`, excluded by default)
  test_examples.py Runs every script in examples/
```

## Running

```bash
pip install -e ".[dev]"          # add ",all" to also run the IFC/Speckle integration tests
pytest                           # everything except slow tests
pytest -m slow                   # the stress/benchmark suite
pytest tests/orm -k cache        # a subset
pytest --cov=revitpy             # with coverage
```

Configuration lives in `pyproject.toml` (`[tool.pytest.ini_options]`); async tests
run in pytest-asyncio auto mode. Tests needing optional packages (`ifcopenshell`,
`specklepy`, `defusedxml`) skip when those aren't installed.

The C# add-in (`src/RevitPy.Addin`) is verified by compiling it for every supported
Revit version (`./build.sh`, and the `addin` CI job).
