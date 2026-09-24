# RevitPy examples

Each example is a single script that runs in two places:

- **On your machine, without Revit.** The script builds a small in-memory demo
  model with `revitpy.testing.mock_revit.MockApplication` and runs against it.
- **Inside Revit.** When the RevitPy host add-in (or pyRevit's CPython engine)
  runs the script, `__revit__` is defined and the script works on the active
  model instead.

The switch is a few lines at the top of every script:

```python
try:
    revit_app = __revit__  # provided inside Revit
except NameError:
    revit_app = build_demo_model()  # MockApplication with sample data
```

The scripts don't import each other, so you can copy any one of them on its own.

## Running locally

From the repository root, with `revitpy` installed (`pip install -e .`):

```bash
python examples/query_elements.py
python examples/bulk_update_parameters.py
python examples/room_schedule_export.py --output ./out
python examples/orm_usage.py
python examples/mcp_server_in_revit.py
```

`tests/test_examples.py` runs every script this way and checks that it exits
with status 0:

```bash
pytest tests/test_examples.py -q
```

## Running inside Revit

1. Install the RevitPy add-in (see the main [README](../README.md)).
2. Open a model.
3. **RevitPy** ribbon tab, then **Run Script**, then pick the example's `.py` file.
   Output is shown in a dialog when the script finishes. **Rerun** runs the last
   script again.

`bulk_update_parameters.py` and `orm_usage.py` change `Mark` / `Comments` on
walls in the open model. Each change is a normal Revit transaction, so
**Undo** reverts it.

## The examples

| Script | What it shows |
| --- | --- |
| [`query_elements.py`](query_elements.py) | `api.query(Wall)` and the other typed classes; `contains` / `equals` filters, `order_by_ascending`, paging with `skip` / `take`, `count`, `first_or_default`, `get_element_by_id`, `get_all_parameters`, and printing an aligned table. |
| [`bulk_update_parameters.py`](bulk_update_parameters.py) | Setting `Mark` and `Comments` on every wall in one `api.transaction(...)`, then an update that fails partway and is rolled back. Values are read back with `use_cache=False` to show what the model actually holds. |
| [`room_schedule_export.py`](room_schedule_export.py) | Turning `Room` elements into rows, then using `revitpy.extract.ScheduleBuilder` for sorting, column selection, totals and per-level subtotals, and `DataExporter` to write CSV and JSON. Files go to `--output` (default: `<temp>/revitpy_room_schedule`). |
| [`orm_usage.py`](orm_usage.py) | The ORM layer: validated pydantic models (`create_wall`, `create_room`) and their `ValidationError.validation_errors`; `RevitContext` queries and `ElementSet` aggregates; change tracking; `save_changes_async()` through an `IUnitOfWork` that writes to Revit in a transaction; and `ctx.transaction()` discarding changes when something fails. |
| [`mcp_server_in_revit.py`](mcp_server_in_revit.py) | Starting and stopping the in-Revit MCP server (`revitpy.revit.host.toggle_mcp_server`) so AI agents can work with the open model. This one needs the RevitPy host add-in: anywhere else it prints what's needed and exits with status 0. |

## Notes

- Numbers read from the mock model come back as strings, while in Revit they
  are floats in internal units (feet, square feet). That's why the examples
  convert values with a small `as_float()` helper.
- Outside Revit, the scripts lower RevitPy's log level so the output is easy
  to read. Inside Revit, logging is left as the host configured it.
