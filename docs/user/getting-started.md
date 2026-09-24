---
layout: page
title: Getting Started
description: "Install RevitPy and learn the basics: connect to Revit, query elements with the fluent QueryBuilder, and run your first transaction with auto-rollback."
doc_tier: user
---

This page covers installation, connecting to Revit, running your first query, and executing your first transaction.

## Installation

Install RevitPy from PyPI:

```bash
pip install revitpy
```

RevitPy supports CPython 3.11–3.13. Optional extras: `revitpy[ifc]` (IfcOpenShell), `revitpy[interop]` (Speckle), `revitpy[all]`. Run `revitpy doctor` to check your environment.

## Connect to Revit

The primary entry point is the `RevitAPI` class. Create an instance and **connect it before doing anything else**. `query()`, `elements` and `transaction()` raise `ConnectionError("No active document")` on an unconnected API.

`connect()` accepts Revit's own `UIApplication` (or `Application`) object and wraps it in RevitPy's pythonnet adapters (`revitpy.revit.adapt_application`) automatically. There are two ways to get that object.

### Option 1: RevitPy add-in

The `src/RevitPy.Addin` add-in embeds CPython in Revit and adds a **RevitPy** ribbon tab (**Run Script**, **Rerun**, **MCP Server**, **About**). Build and install it on the Windows machine that runs Revit (2024–2027):

```powershell
# Requires the .NET SDK (10.x builds every Revit target)
./scripts/install-addin.ps1 -RevitVersion 2025
```

The script builds `src/RevitPy.Addin` and copies it and the `RevitPy.addin` manifest into `%APPDATA%\Autodesk\Revit\Addins\<version>\`. It can also write `%APPDATA%\RevitPy\settings.ini`. See the script for its options.

The add-in needs a 64-bit CPython 3.11–3.14 with `revitpy` installed. Point it at your interpreter and packages in `%APPDATA%\RevitPy\settings.ini`:

```ini
python_dll = C:\Python312\python312.dll
python_path = C:\dev\my-venv\Lib\site-packages
```

Other keys are `python_home`, `startup_script` (repeatable), `python_path` (repeatable) and `initialize_on_startup`. The environment variables `REVITPY_PYTHON_DLL`, `REVITPY_PYTHON_HOME` and `REVITPY_PYTHON_PATH` override the file. See [Configuration]({{ '/user/configuration/' | relative_url }}) for details.

Then write a script and run it with **RevitPy > Run Script**. The script runs on Revit's main thread with `__revit__` bound to the `UIApplication`. Anything it prints is shown in a dialog when it finishes.

```python
from revitpy import RevitAPI
from revitpy.api import Wall

api = RevitAPI()
api.connect(__revit__)

print(api.get_document_info().title)
print(api.query(Wall).count(), "walls")
```

### Option 2: pyRevit (CPython engine)

In a pyRevit script that runs on a CPython 3.11+ engine, with `revitpy` and its dependencies importable (for example by adding a venv's `site-packages` to `sys.path`):

```python
#! python3
from revitpy import RevitAPI

api = RevitAPI()
api.connect(__revit__)
```

### Rules for live models

- **Main thread only.** Revit API calls must run on Revit's main thread: in a ribbon or pyRevit script, a Revit event handler, or an `ExternalEvent`. Code on other threads, such as a web server or an asyncio loop in a background thread, must use `revitpy.revit.host.call_on_revit_thread(lambda uiapp: ...)`.
- **Units are feet.** Lengths, areas and volumes come back in Revit internal units (feet, ft², ft³). Convert them yourself if you need metric.
- **Transactions are real.** `api.transaction()` opens an `Autodesk.Revit.DB.Transaction`. A nested block opens a `SubTransaction`.

### Testing without Revit: MockRevit

`MockRevit` provides a mock application you can connect to exactly like the real one. Use it in unit tests and on machines without Revit:

```python
from revitpy import RevitAPI
from revitpy.api import Wall
from revitpy.testing import MockRevit

mock = MockRevit()
mock.create_document("Test.rvt")
mock.create_element(name="Wall-1", category="OST_Walls")

api = RevitAPI()
api.connect(mock.application)
assert api.query(Wall).count() == 1
```

`RevitAPI` can also be used as a context manager. When the `with` block exits, the API disconnects automatically:

```python
with RevitAPI() as api:
    api.connect(mock.application)
    ...
# api.disconnect() is called automatically
```

### Key Properties and Methods

Once connected, `RevitAPI` provides:

- `api.is_connected` -- Returns `True` if connected to Revit.
- `api.active_document` -- Returns the active `RevitDocumentProvider`, or `None`.
- `api.elements` -- Returns a `QueryBuilder` for all elements in the active document.
- `api.query(element_type)` -- Returns a typed `QueryBuilder`.
- `api.transaction(name)` -- Returns a `Transaction` context manager.
- `api.transaction_group(name)` -- Returns a `TransactionGroup` context manager.
- `api.get_element_by_id(element_id)` -- Returns an `Element` or `None`.
- `api.open_document(file_path)` -- Opens a Revit document and returns a `RevitDocumentProvider`.
- `api.create_document(template_path)` -- Creates a new document.
- `api.save_document()` -- Saves the active document.
- `api.close_document(save_changes=True)` -- Closes the active document.
- `api.get_document_info()` -- Returns a `DocumentInfo` dataclass with `title`, `path`, `is_modified`, `is_read_only`, and `version` fields.

## Your First Query

Use `api.query()` (or `api.elements`) to get a `QueryBuilder`, then chain filter and sort methods. Pass an element class to get a typed query:

```python
from revitpy import FilterOperator
from revitpy.api import Wall

# Typed: elements in the Walls category, wrapped as Wall
walls = api.query(Wall).contains("Name", "Exterior").execute()

# Untyped: every non-type element, filtered by parameter
named = api.elements.equals("Name", "Wall-1").execute()

for wall in walls:
    print(wall.name, wall.id, wall.category)
```

The typed classes are `Wall`, `Floor`, `Door`, `Window`, `Room` and `Level` (in `revitpy.api`). Any element whose category matches one of their `revit_categories` (for example `"OST_Walls"` or `"Walls"`) is wrapped in that class. Other elements are plain `Element`s.

`where()` and the convenience filters read parameters by name. On a live model you can use any Revit parameter name (for example `"Unconnected Height"`), plus the pseudo-parameters `Name`, `Category`, `Type`, `Family` and `Level`. `Category` is the built-in name (`"OST_Walls"`) when Revit has one.

The `QueryBuilder` supports methods like `equals`, `contains`, `starts_with`, `where(name, FilterOperator.X, value)`, `order_by`, `skip` and `take`. Terminal operations include `execute()`, `first()`, `count()` and `to_list()`. See the [Query Builder guide]({{ '/user/features/query-builder/' | relative_url }}) for the full API.

## Your First Transaction

All modifications to a Revit model must occur inside a transaction. `api.transaction()` returns a context manager that opens a real Revit transaction. It commits when the block exits cleanly and rolls back if the block raises:

```python
with api.transaction("Update Comments"):
    element = api.get_element_by_id(12345)
    if element:
        element.set_parameter_value("Comments", "Updated by RevitPy")
```

Parameter writes are applied to the Revit element immediately, inside the open transaction. They become permanent on commit, and Revit reverts them on rollback. Writing outside a transaction fails in Revit.

Transactions can be nested. In a live document the inner block opens a `SubTransaction`, which can roll back on its own without affecting the outer transaction.

### Transaction Options

`api.transaction(name, **options)` accepts the fields of the `TransactionOptions` dataclass:

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` or `None` | Auto-generated | Transaction name (shown in Revit's undo list) |
| `description` | `str` or `None` | `None` | Description |
| `auto_commit` | `bool` | `True` | Commit when the block exits without error. If `False`, the block rolls back unless you call `commit()`. |
| `timeout_seconds` | `float` or `None` | `None` | Stored only; not enforced |
| `retry_count` | `int` | `0` | Stored only; use `retry_transaction()` for retries |
| `retry_delay` | `float` | `1.0` | Stored only |
| `suppress_warnings` | `bool` | `False` | Stored only |

For automatic retries use `revitpy.api.transaction.retry_transaction(api.active_document, operation, max_retries=3, delay=1.0)`.

### Transaction Groups

`api.transaction_group(name)` starts a set of transactions together and then commits them in order, or rolls them all back:

```python
with api.transaction_group("Batch Update") as group:
    ...
```

`TransactionGroup` is RevitPy's own construct, not Revit's `TransactionGroup`. Transactions are added with `group.add_transaction()` before the group starts. In a live document the second and later transactions become `SubTransaction`s of the first, so the group commits and rolls back innermost first. If any commit fails, the rest are rolled back, and rolling back the outer transaction also discards inner ones that already committed. For live-model edits, a single `api.transaction()` with nested blocks is usually simpler.

## Working with Elements

The `Element` class wraps Revit elements with Pythonic property access, caching, and change tracking.

```python
element = api.get_element_by_id(12345)

# Read parameters (plain Python values; lengths in feet)
name = element.name
comments = element.get_parameter_value("Comments")

with api.transaction("Edit element"):
    element.set_parameter_value("Comments", "New value")

    # The change log records old/new values
    if element.is_dirty:
        print("Changes:", element.changes)

    # Write the previous values back (still inside the transaction)
    element.discard_changes()

# Drop cached values and re-read from Revit on next access
element.refresh()
```

`element.save_changes()` only clears the local change log, because writes have already been applied. Elements have built-in property mappings for common parameters: `name`, `family_name`, `type_name`, `level`, `comments` and `mark`.

## Next Steps

- [Query Builder]({{ '/user/features/query-builder/' | relative_url }}) -- Learn the full query API with filters, sorting, and pagination.
- [ORM]({{ '/user/features/orm/' | relative_url }}) -- Use the ORM layer for change tracking and relationship management.
- [Events]({{ '/user/features/events/' | relative_url }}) -- React to Revit events with the event system.
- [Async Support]({{ '/user/features/async/' | relative_url }}) -- Run operations asynchronously for better responsiveness.
- [Testing]({{ '/user/features/testing/' | relative_url }}) -- Test your code without a Revit installation.
