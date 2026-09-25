# pyRevit bridge

Call Python 3 analyses running in **RevitPy** from **pyRevit** scripts.

RevitPy runs inside Revit (the RevitPy add-in embeds CPython) and exposes the
[RevitPy Live Server](../docs/developer/live-server.md), an authenticated JSON-RPC
WebSocket endpoint. The bridge has two parts, one on each side of that connection:

| Part | Runs in | What it is |
|---|---|---|
| [`RevitPyBridge.extension/lib/revitpy_bridge.py`](RevitPyBridge.extension/lib/revitpy_bridge.py) | pyRevit (IronPython 2.7 or CPython 3) | One self-contained module: finds the Live Server, serializes Revit elements to JSON and calls `bridge/analyze` |
| [`RevitPyBridge.extension/`](RevitPyBridge.extension/) | pyRevit | Sample extension: a **RevitPy Bridge** tab with **Run Analysis** and **Live Server Status** buttons |
| [`analyses/`](analyses/) (`revitpy-bridge-analyses`) | RevitPy's Python (3.11+) | Installable package of analyses, loaded automatically by the Live Server |

```
pyRevit button ──► revitpy_bridge.py ──JSON-RPC over ws://127.0.0.1:8766──► Live Server ──► registered analysis
   (selection)      serialize elements        Bearer token from ~/.revitpy/live.json          (revitpy-bridge-analyses)
```

## Setup

### 1. Install the analyses into RevitPy's Python

Use the Python that the RevitPy add-in embeds (the interpreter configured in
`%APPDATA%\RevitPy\settings.ini`), from a clone of this repository:

```bat
python -m pip install -e path\to\revitpy\pyrevit-bridge\analyses
```

The package declares a `revitpy.analyses` entry point, so the Live Server imports it
when it starts. Nothing else to configure.

### 2. Start the Live Server

In Revit, click **Live Server** on the **RevitPy** ribbon tab, or set
`start_live_server = true` in `%APPDATA%\RevitPy\settings.ini`. The server writes
`~/.revitpy/live.json` (URL and token), which `revitpy_bridge.py` reads.

### 3. Add the pyRevit side

Either:

- **use the sample extension**: in pyRevit, *Settings → Custom Extension Directories*,
  add this `pyrevit-bridge` folder (the parent of `RevitPyBridge.extension`) and reload
  pyRevit. A **RevitPy Bridge** tab appears; or
- **use the module in your own extension**: copy
  `RevitPyBridge.extension/lib/revitpy_bridge.py` into your extension's `lib/` folder.

### 4. Run it

Select some elements, click **RevitPy Bridge → Run Analysis**, pick an analysis. The
result appears in the pyRevit output window, with element ids linked back to the model.
**Live Server Status** shows the connection and the registered analyses.

## Using `revitpy_bridge.py` in your scripts

```python
from pyrevit import revit
from revitpy_bridge import RevitPyBridge, AnalysisFailed, BridgeError, serialize_elements

bridge = RevitPyBridge(timeout=120)
print(bridge.list_analyses())

elements = serialize_elements(revit.get_selection().elements)
try:
    takeoff = bridge.analyze("quantity_takeoff", elements, {"group_by": "level"})
except AnalysisFailed as exc:   # the analysis raised; exc.details is the traceback
    print(exc.details)
except BridgeError as exc:      # not running, auth failed, unknown analysis, timeout
    print(exc)
```

Exceptions (all subclass `BridgeError`):

| Exception | When |
|---|---|
| `LiveServerNotRunning` | No discovery file, or nothing listening at its URL |
| `AuthenticationFailed` | Handshake rejected (HTTP 401/403), usually a stale discovery file |
| `UnknownAnalysis` | No analysis registered under that name (JSON-RPC `-32602`) |
| `RpcError` | Any other JSON-RPC error (`.code`, `.message`) |
| `AnalysisFailed` | The analysis raised; `.details` holds the server-side traceback |

The module is written for both IronPython 2.7 and CPython 3. Under IronPython (and
under pythonnet when `websockets` is missing) it uses .NET's `ClientWebSocket`; under
CPython it uses the `websockets` package (11 or later).

### Serialized element format

`serialize_element(element)` returns plain JSON data. **All geometry and measured
values are in Revit internal units: feet, square feet, cubic feet, radians.**

```json
{
  "id": 316104, "unique_id": "…", "name": "Generic - 200mm", "category": "Walls",
  "type_name": "Generic - 200mm", "level": "Level 1", "units": "ft",
  "parameters": {
    "Area": {"storage_type": "Double", "value": 215.3, "display": "20.00 m²",
             "builtin": "HOST_AREA_COMPUTED", "data_type": "autodesk.spec.aec:area-2.0.0",
             "read_only": true}
  },
  "location": {"type": "curve", "start": [0, 0, 0], "end": [32.8, 0, 0], "length": 32.8},
  "bounding_box": {"min": [-0.3, -0.3, 0], "max": [33.1, 0.3, 9.8]},
  "materials": [{"id": 1234, "name": "Concrete, Cast-in-Place", "material_class": "Concrete",
                 "volume": 142.1, "area": 430.6}]
}
```

`id` is `ElementId.Value` (Revit 2024+) or `ElementId.IntegerValue` (earlier).
`display` is Revit's own formatted string in the project's display units.
`serialize_element(e, include_parameters=..., include_materials=..., include_geometry=...)`
can leave parts out to keep large selections small.

## Analyses (`revitpy-bridge-analyses`)

Every analysis takes the serialized elements plus an `options` object. Parameters are
looked up by built-in parameter first (`HOST_AREA_COMPUTED`, `ROOM_AREA`, …) so
non-English Revit works, then by English name.

| Name | Result | Options |
|---|---|---|
| `element_summary` | Counts by category, level and type | `categories` |
| `parameter_statistics` | Per parameter: min/max/mean/sum (numeric, Revit internal units) or distinct and most common values (text) | `categories`, `parameters`, `top` (10), `include_empty` |
| `quantity_takeoff` | Area, volume, length and count grouped by category, level, element or building, in m², m³, m and ft², ft³, ft. Built on `revitpy.extract.QuantityExtractor` | `categories`, `group_by` (`category`) |
| `embodied_carbon` | Screening A1–A3 embodied carbon from Revit material volumes and the generic ICE v2.0 factors in `revitpy.sustainability`, with match confidence per material and an optional RIBA 2030 benchmark | `categories`, `gross_floor_area_m2`, `building_type` |
| `bounding_box_clashes` | Pairs of elements whose axis-aligned bounding boxes overlap (a shortlist for review, not solid intersection) | `categories`, `tolerance_ft` (0), `ignore_same_category`, `max_results` (500) |

The embodied-carbon figures are screening-level. They use generic factors, not
product EPDs, and materials without a volume (paints, surface finishes) are listed
as unquantified.

### Adding your own analysis

```python
from revitpy.revit.live import register_analysis

@register_analysis("door_count", main_thread=False)
def door_count(elements, options, uiapp):
    return {"doors": sum(1 for e in elements if e.get("category") == "Doors")}
```

Ship it in a package with a `revitpy.analyses` entry point, like `analyses/pyproject.toml`.

> **Threading.** A pyRevit button runs on Revit's main thread and holds it while it
> waits for the reply. An analysis that the Live Server has to run on the main thread
> (the default for `register_analysis`) cannot start until then, so the call fails when
> the request times out. Register analyses that only use the element data they are sent
> with `main_thread=False` (they then get `uiapp=None`), as this package does. Only
> analyses that need the Revit API should stay on the main thread; those can only be
> called from outside Revit's main thread, for example from `revitpy live` or an
> external tool.
>
> `main_thread=False` needs a RevitPy whose `register_analysis` has that option. With
> an older RevitPy this package still registers its analyses, but they run on the main
> thread and so cannot be called from a pyRevit button.

## Tests

```bash
pip install -e ".[dev]" -e pyrevit-bridge/analyses vermin
pytest pyrevit-bridge/tests
```

The tests cover the analyses, element serialization against fake Revit objects, a full
round trip (the pyRevit client under CPython → a real Live Server with a fake Revit
dispatcher → the registered analyses), and a check with `vermin` that `revitpy_bridge.py`
and the button scripts are valid Python 2.7. The .NET `ClientWebSocket` transport used
under IronPython can only be exercised inside Revit.

Files under `RevitPyBridge.extension/` must stay Python 2.7 compatible; its
`ruff.toml` turns off the pyupgrade (`UP`) rules there.
