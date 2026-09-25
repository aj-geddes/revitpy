# RevitPy

[![CI](https://github.com/aj-geddes/revitpy/actions/workflows/ci.yml/badge.svg)](https://github.com/aj-geddes/revitpy/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Development Status](https://img.shields.io/badge/status-alpha-orange.svg)]()

A modern CPython framework for Autodesk Revit: LINQ-style queries, typed elements, real Revit transactions, an ORM with change tracking, events, extensions, and a mock Revit for testing. Domain modules cover quantity takeoff, IFC, AI agents (MCP), embodied carbon, Speckle, and APS Design Automation.

> **Status**: Alpha (Development Status 3). The API works but may change before 1.0.

## Installation

```bash
pip install revitpy
pip install "revitpy[ifc]"       # IFC: ifcopenshell>=0.8, ifctester, defusedxml
pip install "revitpy[interop]"   # Speckle: specklepy>=3
pip install "revitpy[all]"       # all optional integrations
```

Python 3.11–3.13 is supported. For development:

```bash
git clone https://github.com/aj-geddes/revitpy.git
cd revitpy
pip install -e ".[dev]"
```

## Quick Start

`RevitAPI` must be connected before you query or open transactions. Inside Revit you connect to the live session; in tests you connect to `MockRevit`:

```python
from revitpy import FilterOperator, RevitAPI
from revitpy.api import Wall

api = RevitAPI()
api.connect(__revit__)  # Revit's UIApplication (RevitPy add-in or pyRevit)

# Typed query: elements of the Walls category are wrapped as Wall
walls = api.query(Wall).contains("Name", "Exterior").execute()

# Generic query with the fluent builder
tall = (
    api.query()
    .where("Category", FilterOperator.EQUALS, "OST_Walls")
    .where("Unconnected Height", FilterOperator.GREATER_THAN, 10.0)  # feet
    .order_by_descending("Unconnected Height")
    .take(50)
    .execute()
)

# Writes run inside a real Revit transaction: commit on success,
# roll back if the block raises. Nested blocks become SubTransactions.
with api.transaction("Mark exterior walls"):
    for wall in walls:
        wall.set_parameter_value("Comments", "Exterior")
```

Things to keep in mind with a live model:

- Lengths, areas and volumes are in Revit internal units (feet, square feet, cubic feet).
- Revit API calls must run on Revit's main thread. Scripts started from the RevitPy ribbon or pyRevit already run there. Background threads in the RevitPy add-in should use `revitpy.revit.host.call_on_revit_thread()`.
- Parameter writes apply straight away inside the open transaction. Revit undoes them if the transaction rolls back.

## Running Inside Revit

### Option 1: The RevitPy add-in

`src/RevitPy.Addin` is a Revit add-in (`RevitPy.Addin.RevitPyApplication`) that embeds CPython through pythonnet. It adds a **RevitPy** ribbon tab with **Run Script**, **Rerun**, **Live Server**, **MCP Server** and **About** buttons. Scripts run on Revit's main thread with `__revit__` bound to the `UIApplication`.

Requirements: Windows, Revit 2024–2027, and a 64-bit CPython 3.11–3.14 with `revitpy` installed (a venv is fine).

```powershell
# Build (the .NET 10 SDK can build every target)
dotnet build src/RevitPy.Addin/RevitPy.Addin.csproj -c Release -p:RevitVersion=2025

# Build + install for the current user (see the script for all options)
./scripts/install-addin.ps1 -RevitVersion 2025
```

| Revit | Target framework |
|---|---|
| 2024 | net48 |
| 2025, 2026 | net8.0-windows |
| 2027 | net10.0-windows |

Settings are read from `%APPDATA%\RevitPy\settings.ini`:

```ini
# Optional. Otherwise the add-in searches PATH and per-user Python installs.
python_dll = C:\Python312\python312.dll
python_home = C:\Python312
# Repeatable. Point it at the site-packages where revitpy is installed.
python_path = C:\dev\my-venv\Lib\site-packages
# Optional, repeatable. Runs once, when Python starts.
startup_script = %USERPROFILE%\revitpy\startup.py
# true = start Python when Revit starts instead of on first use.
initialize_on_startup = false
# true = start the Live Server (for VS Code / dev tools) when Revit starts.
start_live_server = false
```

Comments must be on their own line (`#` or `;`). Values are expanded with `%VAR%` environment variables.

The environment variables `REVITPY_PYTHON_DLL`, `REVITPY_PYTHON_HOME` and `REVITPY_PYTHON_PATH` (`;`-separated) override these settings.

The **MCP Server** button starts an MCP server inside the Revit session (default `ws://127.0.0.1:8765`, override with `REVITPY_MCP_HOST` / `REVITPY_MCP_PORT` / `REVITPY_MCP_TOKEN`). It requires a bearer token (a random one is generated if you don't set it), and Revit asks you to confirm any tool that changes the model.

The **Live Server** button (or `start_live_server = true`) lets development tools run code in the open session: the [VS Code extension](vscode-extension/), the file-watching [dev server](dev-server/), the pyRevit bridge and `revitpy live ...`. It listens on `ws://127.0.0.1:8766`, always requires a bearer token, and publishes its URL and token in `~/.revitpy/live.json` for those clients. See the [Live Server protocol](https://aj-geddes.github.io/revitpy/developer/live-server/).

### Option 2: pyRevit (CPython engine)

In a pyRevit script running on a CPython 3.11+ engine, with `revitpy` and its dependencies importable:

```python
#! python3
from revitpy import RevitAPI
from revitpy.api import Door

api = RevitAPI()
api.connect(__revit__)
print(api.query(Door).count(), "doors")
```

## Testing Without Revit

`MockRevit` stands in for the Revit application, so the same code runs in pytest:

```python
from revitpy import RevitAPI
from revitpy.api import Wall
from revitpy.testing import MockRevit

mock = MockRevit()
doc = mock.create_document("Test.rvt")
mock.create_element(name="Exterior Wall", category="OST_Walls")
mock.create_element(name="Door 1", category="OST_Doors")
assert doc.GetElementCount() == 2

api = RevitAPI()
api.connect(mock.application)

walls = api.query(Wall).execute()
with api.transaction("Rename"):
    walls[0].name = "Wall-A"

assert api.query(Wall).first().name == "Wall-A"
```

## More Features

### ORM with Change Tracking

```python
from revitpy.api import Wall
from revitpy.orm import create_context

context = create_context(api.active_document)  # any IElementProvider
walls = context.all(Wall)
exterior = context.where(Wall, lambda w: "Exterior" in w.name)
```

Without a unit of work, `save_changes()` / `save_changes_async()` only accept tracked changes. Pass `unit_of_work=` to `RevitContext` to persist them. That unit of work's `commit` (or `commit_async`) is called, and a failure raises.

### Events

```python
from revitpy import EventManager, EventPriority, EventType

def on_element_modified(event):
    print(f"Element {event.element_id} was modified")

manager = EventManager.get_instance()
manager.register_function(
    on_element_modified, [EventType.ELEMENT_MODIFIED], priority=EventPriority.HIGH
)
manager.dispatch_event(EventType.ELEMENT_MODIFIED, element_id=12345, immediate=True)
```

### Extensions

```python
import asyncio

from revitpy.extensions import Extension, ExtensionMetadata

class MyExtension(Extension):
    async def load(self):
        self.log_info("loading")

    async def activate(self):
        self.log_info("active")

    async def deactivate(self):
        pass

async def main():
    ext = MyExtension(ExtensionMetadata(name="my-extension", version="1.0.0"))
    await ext.load_extension()
    await ext.activate_extension()

asyncio.run(main())
```

### Domain Modules

```python
from pathlib import Path
from types import SimpleNamespace

# Quantity takeoff: works on any object exposing area/volume/length/... attributes
from revitpy.extract import AggregationLevel, DataExporter, QuantityExtractor

items = [SimpleNamespace(id=1, name="W1", category="Walls", level="Level 1", area=25.5)]
extractor = QuantityExtractor()
quantities = extractor.extract(items)
by_level = extractor.extract_grouped(items, group_by=AggregationLevel.LEVEL)
DataExporter().to_csv([q.__dict__ for q in quantities], Path("takeoff.csv"))

# IFC export (pip install "revitpy[ifc]")
from revitpy.ifc import IfcExporter, IfcVersion
from revitpy.orm import create_wall

wall = create_wall(id=1001, height=10.0, length=20.0, width=0.5, name="W1")
IfcExporter().export([wall], Path("model.ifc"), version=IfcVersion.IFC4)

# Embodied carbon
from revitpy.sustainability import CarbonCalculator, MaterialData

calculator = CarbonCalculator()
results = calculator.calculate([MaterialData(name="Concrete", category="Concrete", mass_kg=50_000)])
benchmark = calculator.benchmark(calculator.summarize(results), building_area_m2=5000.0)

# APS Design Automation (inside an async function)
from revitpy.cloud import ApsAuthenticator, ApsClient, ApsCredentials, JobConfig, JobManager

client = ApsClient(ApsAuthenticator(ApsCredentials(client_id="...", client_secret="...")))
jobs = JobManager(client)
job_id = await jobs.submit(JobConfig(activity_id="RevitPy.Validate+prod", input_file="https://.../model.rvt"))
result = await jobs.wait_for_completion(job_id)
```

The MCP server for AI agents lives in `revitpy.ai`. Speckle (projects/models/versions) is in `revitpy.interop`. See the [feature guides](https://aj-geddes.github.io/revitpy/user/) for both.

## Command Line

```bash
revitpy version                 # installed version
revitpy doctor [--json]         # check Python, dependencies, optional integrations
revitpy mcp-serve --port 8765 --token SECRET   # MCP server without a live Revit (use the add-in for a live model)
revitpy live status             # the Revit session behind the Live Server
revitpy live run script.py      # run a script in Revit
revitpy live reload mymodule    # reload modules (names or .py paths) in Revit
revitpy live debug              # start debugpy in Revit, then attach your editor
```

## Architecture

```
revitpy/
  api/             RevitAPI, Element + typed Wall/Floor/Door/Window/Room/Level, Transaction, QueryBuilder
  revit/           Live Revit: pythonnet adapters, host helpers + MCP (host.py), Live Server (live.py)
  rpc.py           Authenticated JSON-RPC over WebSocket (shared by MCP and the Live Server)
  live_client.py   Client for the Live Server
  cli.py           `revitpy` command (version, doctor, mcp-serve, live)
  orm/             RevitContext, change tracking, caching, relationships, validation models
  events/          EventManager, dispatcher, decorators, filters
  extensions/      Extension, ExtensionManager, dependency injection
  async_support/   AsyncRevit, TaskQueue, progress, cancellation
  performance/     Optimizer, benchmarks, memory and metrics monitoring
  testing/         MockRevit, MockApplication, MockDocument, MockElement
  config.py        Config, ConfigManager
  extract/         Quantity takeoff, materials, costs, schedules, export
  ifc/             IFC export/import, mapping, IDS validation, BCF 2.1, diff
  ai/              MCP server, tools, safety guard, prompts
  sustainability/  Carbon, EPD database, compliance, reports
  interop/         Speckle client, sync, mapping, diff, merge, subscriptions
  cloud/           APS auth/client, Design Automation jobs, batch, CI, webhooks
src/RevitPy.Addin/ C# Revit add-in hosting CPython (the only C# project that is built)
```

## Development

```bash
pytest                 # slow stress tests are excluded by default
pytest -m slow         # run only the slow tests
ruff check revitpy/ tests/ && ruff format --check revitpy/ tests/
mypy revitpy
pre-commit install && pre-commit install --hook-type pre-push
```

## Documentation

Full documentation: [aj-geddes.github.io/revitpy](https://aj-geddes.github.io/revitpy/)

- [Getting Started](https://aj-geddes.github.io/revitpy/user/getting-started/)
- [API Reference](https://aj-geddes.github.io/revitpy/developer/api-reference/)
- [User Guide](https://aj-geddes.github.io/revitpy/user/)
- [Contributing](https://aj-geddes.github.io/revitpy/developer/contributing/)
- [Examples](examples/) (runnable scripts)
- [Changelog](CHANGELOG.md)

## License

MIT License. See [LICENSE](LICENSE) for details.
