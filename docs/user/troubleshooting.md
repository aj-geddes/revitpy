---
layout: page
title: Troubleshooting
description: Troubleshooting guide for RevitPy covering API and ORM exception hierarchies, common error messages, connection issues, and step-by-step fix solutions.
doc_tier: user
---

This guide covers the exception classes in RevitPy and common issues you may encounter.

## API Exceptions

These exceptions are defined in `revitpy.api.exceptions`.

### RevitAPIError

The base exception for all RevitPy API errors.

```python
from revitpy.api.exceptions import RevitAPIError

try:
    api.open_document("nonexistent.rvt")
except RevitAPIError as e:
    print(e)           # Error message
    print(e.cause)     # Original exception, if any
```

**Attributes:**
- `cause` -- The underlying exception, or `None`.

### ConnectionError

Raised when RevitPy cannot connect to the Revit application or when an operation is attempted without a connection.

```python
from revitpy.api.exceptions import ConnectionError
```

**Common causes:**
- Calling `api.query()`, `api.elements` or `api.transaction()` before `api.connect()`. These raise `ConnectionError: No active document`.
- Calling `api.connect()` without an application object.
- Passing an object that is neither a Revit `UIApplication`/`Application` nor a RevitPy-compatible application such as `MockApplication`.
- Running outside Revit, where the Revit API cannot be loaded. The subclass `revitpy.revit.RevitApiUnavailableError` is raised when a live adapter is used outside Revit.

**Solutions:**
- Inside Revit, call `api.connect(__revit__)`. In tests, call `api.connect(MockRevit().application)`.
- Use `api.is_connected` to check the connection status before operations.

### ElementNotFoundError

Raised when an element cannot be found by ID or when a parameter does not exist on an element.

```python
from revitpy.api.exceptions import ElementNotFoundError
```

**Attributes:**
- `element_id` -- The ID that was searched for.
- `element_type` -- The type name, if applicable.
- `cause` -- The underlying exception.

**Common causes:**
- Looking up an element by an ID that does not exist in the document.
- Accessing a parameter name that does not exist on the element.
- The element was deleted between the time its ID was obtained and the lookup.

**Solutions:**
- Use `api.get_element_by_id()` which returns `None` for missing elements instead of raising.
- Use `first_or_default()` instead of `first()` when the query may return no results.
- Verify parameter names match exactly (they are case-sensitive).

### TransactionError

Raised during transaction operations (start, commit, rollback).

```python
from revitpy.api.exceptions import TransactionError
```

**Attributes:**
- `transaction_name` -- Name of the transaction.
- `cause` -- The underlying exception.

**Common causes:**
- The document cannot open transactions. `RevitDocumentProvider.start_transaction()` raises `TransactionError` when the document has no `StartTransaction` method (for example a custom provider). It no longer pretends to succeed.
- Revit refused to start the transaction, for example on a read-only document or while another command is running.
- Attempting to start a transaction that has already been started.
- Committing a transaction that is not in the `STARTED` state.
- An operation failing inside a transaction, triggering a rollback.

**Solutions:**
- Use transactions as context managers (`with api.transaction(...)`) to ensure proper start/commit/rollback handling.
- Check `transaction.status` before calling `commit()` or `rollback()` manually.
- Use `retry_transaction()` for operations that may fail transiently.

### ValidationError

Raised when a parameter value fails validation.

```python
from revitpy.api.exceptions import ValidationError
```

**Attributes:**
- `field` -- The field/parameter name.
- `value` -- The invalid value.
- `cause` -- The underlying exception.

**Common causes:**
- Setting a parameter to a value that cannot be converted to the expected type (e.g., setting a numeric parameter to a non-numeric string).
- Setting a parameter that fails Revit-side validation.

**Solutions:**
- Verify the expected type before setting parameter values. Use `ParameterValue.storage_type` to check.
- Ensure values match the parameter's storage type (`String`, `Double`, `Integer`, `ElementId`). On a live model, doubles are in Revit internal units (feet), so pass `3.0 / 0.3048` for 3 m.
- On a live model, parameter writes must happen inside `api.transaction()`.

### PermissionError

Raised when attempting a disallowed operation, such as writing to a read-only parameter.

```python
from revitpy.api.exceptions import PermissionError
```

**Attributes:**
- `operation` -- The operation that was denied.

**Solutions:**
- Check `ParameterValue.is_read_only` before attempting to write.
- Use `ElementProperty.read_only` when defining custom property descriptors.

### ModelError

Raised when the model is in an invalid state, such as failing to create or open a document.

```python
from revitpy.api.exceptions import ModelError
```

**Common causes:**
- `open_document()` returns `None` from Revit.
- `create_document()` returns `None`.

**Solutions:**
- Verify the file path exists and is accessible.
- Ensure the template path is valid for `create_document()`.

## ORM Exceptions

These exceptions are defined in `revitpy.orm.exceptions`. They all inherit from `ORMException`.

### ORMException

Base exception for all ORM errors.

**Attributes:**
- `operation` -- The ORM operation that failed (e.g., `"save_changes"`, `"query"`, `"get_by_id"`).
- `entity_type` -- The entity type name, if applicable.
- `entity_id` -- The entity ID, if applicable.
- `cause` -- The underlying exception.

### QueryError

Raised when a query operation fails.

**Attributes:**
- `query_expression` -- String representation of the query.
- `query_operation` -- The operation that failed (e.g., `"first"`, `"single"`).
- `element_count` -- Number of elements found (useful for `single()` errors).

**Common causes:**
- Calling `first()` on an empty result set.
- Calling `single()` when zero or more than one element matches.
- An error in a predicate function.

**Solutions:**
- Use `first_or_default()` or `single_or_default()` when results may be empty.
- Verify predicates do not raise exceptions by testing them independently.

### RelationshipError

Raised when relationship loading or configuration fails.

**Attributes:**
- `relationship_name` -- The relationship that failed.
- `source_entity` -- The source entity.
- `target_entity` -- The target entity.

**Common causes:**
- Calling `load_relationship()` without a configured relationship manager.

**Solutions:**
- Call `context.configure_relationship()` before loading relationships.

### CacheError

Raised when cache operations fail.

**Attributes:**
- `cache_key` -- The cache key involved.
- `cache_operation` -- The cache operation that failed.

### ChangeTrackingError

Raised when change tracking operations fail.

**Attributes:**
- `entity` -- The entity involved.
- `property_name` -- The property name, if applicable.
- `tracking_operation` -- The operation that failed.

### LazyLoadingError

Raised when lazy loading of a property or relationship fails.

**Attributes:**
- `property_name` -- The property being loaded.
- `entity` -- The entity being loaded.

### AsyncOperationError

Raised when an async ORM operation fails.

**Attributes:**
- `async_operation` -- The async operation name.
- `task_id` -- The task ID, if applicable.

### BatchOperationError

Raised when a batch operation partially or fully fails.

**Attributes:**
- `batch_size` -- Total batch size.
- `failed_operations` -- List of failed operation details.
- `successful_operations` -- Number of operations that succeeded.

### ValidationError (ORM)

Raised when entity validation fails in the ORM layer, including by the factory functions `create_wall`, `create_room`, `create_door` and `create_window`. Constructing a model directly (for example `WallElement(...)`) raises pydantic's own `ValidationError` instead.

**Attributes:**
- `validation_errors` -- Dictionary of field names (dotted paths) to lists of error messages.
- `entity` -- The entity that failed validation, if any.
- `cause` -- The original pydantic `ValidationError` (from the factory functions).

```python
from revitpy.orm import create_wall
from revitpy.orm.exceptions import ValidationError

try:
    create_wall(id=1, height=-1.0, length=10.0, width=0.5)
except ValidationError as e:
    print(e.validation_errors)   # {'height': ['...']}
```

### ConcurrencyError

Raised when concurrent modifications conflict.

**Attributes:**
- `entity` -- The entity with conflicts.
- `conflicting_changes` -- Dictionary of conflicting property changes.

### TransactionError (ORM)

Raised when ORM transaction operations fail.

**Attributes:**
- `transaction_id` -- The transaction ID.
- `transaction_state` -- The transaction state at the time of failure.
- `nested_level` -- The nesting level.

## Common Issues and Solutions

### "No active document" error

**Problem:** You see `ConnectionError: No active document` when calling `api.elements`, `api.query()`, or `api.transaction()`.

**Solution:** Connect first. If Revit has no document open, open or create one:
```python
api.connect(__revit__)          # or api.connect(mock.application) in tests
if api.active_document is None:
    api.open_document("path/to/project.rvt")
```

### "RevitContext has been disposed" error

**Problem:** You see `ORMException: RevitContext has been disposed` when calling context methods.

**Solution:** The context was used after exiting a `with` block or after calling `dispose()`. Create a new context:
```python
# Wrong
with RevitContext(provider) as ctx:
    pass
ctx.query()  # Error: context is disposed

# Right
with RevitContext(provider) as ctx:
    ctx.query()  # Use inside the block
```

### Circular dependency in DI container

**Problem:** `RuntimeError: Circular dependency detected: A -> B -> A`

**Solution:** Refactor to break the cycle. Options include:
- Use a factory function that resolves one dependency lazily.
- Use `register_singleton` with a pre-created instance for one of the services.
- Restructure the dependency graph.

### "Service X is not registered" error

**Problem:** `ValueError: Service MyService is not registered` when calling `container.get_service()`.

**Solution:** Register the service before resolving it:
```python
container.register_singleton(MyService, instance=my_instance)
service = container.get_service(MyService)
```

### Event handler disabled after errors

**Problem:** An event handler stops executing after repeated failures.

**Solution:** The `@event_handler` decorator disables a handler after `max_errors` failures (default 10). Fix the underlying error, then either:
- Increase `max_errors` in the decorator.
- Re-register the handler.
- Use `@retry_on_error` to add retry logic.

### Slow queries

**Problem:** Queries take a long time to execute.

**Solution:**
- Add more specific filters to reduce the result set.
- Use `take()` to limit the number of results.
- Enable caching in the ORM context (`CachePolicy.MEMORY` or `CachePolicy.AGGRESSIVE`).
- For large datasets, use the ORM `as_streaming()` method for batch processing.
- Check `context.cache_statistics` to verify cache hit rates.

### Long-running transactions

**Problem:** A large edit keeps Revit busy for a long time.

**Solution:**
- `TransactionOptions.timeout_seconds` is stored but not enforced, so changing it has no effect.
- Split the work into several `api.transaction()` blocks so that each commit is smaller.
- Narrow queries (typed `api.query(Wall)`, filters, `take()`) before editing.

## Running Inside Revit

### "No Python 3.11-3.14 (x64) installation was found"

**Problem:** The RevitPy add-in cannot find a Python DLL. You see this message when you click **Run Script** or **MCP Server**.

**Solution:** The add-in looks for `python3XX.dll` (3.11–3.14, 64-bit) in this order:

1. `python_dll` in `%APPDATA%\RevitPy\settings.ini`, or the `REVITPY_PYTHON_DLL` environment variable.
2. `python_home`, or `REVITPY_PYTHON_HOME`.
3. Directories on `PATH`.
4. Per-user installs under `%LOCALAPPDATA%\Programs\Python\Python3*`.

Set the full path explicitly:

```ini
python_dll = C:\Python312\python312.dll
```

Use a 64-bit CPython from python.org. The Microsoft Store Python and 32-bit builds won't load. **RevitPy > About** shows the settings file path and whether Python initialized. Settings are read when Revit starts, so restart Revit after editing them.

### `ModuleNotFoundError: No module named 'revitpy'` inside Revit

The embedded interpreter only sees its own `site-packages` plus any `python_path` entries. Add the environment where `revitpy` is installed:

```ini
python_path = C:\dev\my-venv\Lib\site-packages
```

The venv must be created from the same Python version as the DLL. Compiled dependencies such as `pydantic-core` must match that interpreter.

### Revit API errors from background threads, or `TimeoutError`

**Problem:** You get errors such as "Cannot access Revit API outside of a valid API context", or Revit freezes, when you call RevitPy from a `threading.Thread`, an asyncio loop in another thread, or a server.

**Solution:** The Revit API may only be used on Revit's main thread. Inside the RevitPy add-in, dispatch the work:

```python
from revitpy.revit.host import call_on_revit_thread

count = call_on_revit_thread(lambda uiapp: len(list(uiapp.ActiveUIDocument.Selection.GetElementIds())))
```

`call_on_revit_thread` raises:

- `TimeoutError` if Revit did not run the request within `timeout` seconds (default 60). Usually a modal dialog is open or Revit is busy. Close the dialog or pass a larger `timeout`.
- `RevitHostUnavailableError` outside the add-in. pyRevit does not provide the dispatcher.
- `RevitThreadError` if the function raised. The message contains the traceback.

Don't run live Revit calls through `AsyncRevit`, `TaskQueue` or the async decorators, because they use thread-pool executors.

### Values look 3.28 times too large or too small

Revit returns and accepts lengths in feet (areas in ft², volumes in ft³), regardless of project units. Convert explicitly: `metres = feet * 0.3048`.

### MCP client can't connect to the in-Revit server

- Start the server with **RevitPy > MCP Server**. The dialog shows the URL (default `ws://127.0.0.1:8765`) and the bearer token.
- Send `Authorization: Bearer <token>`. Set a fixed token with the `REVITPY_MCP_TOKEN` environment variable, and a different host or port with `REVITPY_MCP_HOST` / `REVITPY_MCP_PORT`.
- Tools that change the model show a Yes/No dialog in Revit. If nobody answers or the dialog fails, the call is denied.

## Optional Integrations

### `pip` resolves `websockets` to 11.x after installing `revitpy[interop]`

`specklepy` requires `gql[websockets]`, which pins `websockets<12`. This is expected, and RevitPy works with it. If another tool in the same environment needs `websockets>=12`, keep Speckle support in a separate virtual environment.

### `ImportError` mentioning ifcopenshell or specklepy

IFC and Speckle support are optional. Install them with `pip install "revitpy[ifc]"` (`ifcopenshell>=0.8`, `ifctester`, `defusedxml`) or `pip install "revitpy[interop]"` (`specklepy>=3`). Run `revitpy doctor` to see which integrations are available.
