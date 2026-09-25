---
layout: api
title: API Reference
description: Complete API reference for all RevitPy public classes and methods, covering RevitAPI, ORM, events, extensions, extract, IFC, AI, cloud, and more.
doc_tier: developer
module: revitpy
---

## Core API (`revitpy.api`)

### RevitAPI

The primary interface for interacting with Autodesk Revit.

**Module:** `revitpy.api.wrapper`

```python
class RevitAPI:
    def __init__(self, revit_application: IRevitApplication | None = None) -> None
```

A `RevitAPI` must be connected before use: `elements`, `query()`, `transaction()`, `transaction_group()`, `get_element_by_id()` and `delete_elements()` raise `ConnectionError("No active document")` when there is no connection or no active document.

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_connected` | `bool` | Whether the API is connected to Revit |
| `active_document` | `RevitDocumentProvider \| None` | The active document provider; `None` when not connected |
| `elements` | `QueryBuilder[Element]` | Query builder over all elements of the active document |

**Methods:**

```python
def connect(self, revit_application: IRevitApplication | None = None) -> None
```
Connect to a Revit application. Objects that do not already implement `IRevitApplication` (for example the `UIApplication` / `Application` exposed as `__revit__` by the RevitPy host add-in or pyRevit) are wrapped automatically with `revitpy.revit.adapt_application`. `revitpy.testing.MockApplication` is accepted as-is. Raises `ConnectionError` if no application is given or it cannot be reached.

```python
def disconnect(self) -> None
```
Disconnect from the Revit application and clear cached documents.

```python
def open_document(self, file_path: str) -> RevitDocumentProvider
```
Open a Revit document from a file path and make it the active document.

```python
def create_document(self, template_path: str | None = None) -> RevitDocumentProvider
```
Create a new Revit document, optionally from a template.

```python
def get_document_info(self, provider: RevitDocumentProvider | None = None) -> DocumentInfo
```
Get a `DocumentInfo(title, path, is_modified, is_read_only, version)` for a document. Uses the active document if `provider` is not specified.

```python
def save_document(self, provider: RevitDocumentProvider | None = None) -> bool
```
Save a document. Uses the active document if `provider` is not specified.

```python
def close_document(self, provider: RevitDocumentProvider | None = None, save_changes: bool = True) -> bool
```
Close a document. Uses the active document if `provider` is not specified.

```python
def query(self, element_type: type[T] | None = None) -> QueryBuilder[T]
```
Create a query builder. With an `Element` subclass such as `Wall`, only elements of that type are returned (collected by category when the document supports `GetElementsByCategory`).

```python
def transaction(self, name: str | None = None, **kwargs) -> Transaction
```
Create a transaction (keyword arguments become `TransactionOptions` fields). Use it as a context manager.

```python
def transaction_group(self, name: str | None = None) -> TransactionGroup
```
Create a transaction group.

```python
def get_element_by_id(self, element_id: Any) -> Element | None
```
Get an element by its ID (an `int` or a Revit/RevitPy element id). Returns `None` if it does not exist.

```python
def delete_elements(self, elements: Element | list[Element] | ElementSet) -> None
```
Delete elements from the document. Must run inside a transaction on a live model.

```python
def refresh_cache(self) -> None
```
Refresh the internal element cache.

`RevitAPI` is also a context manager; leaving the `with` block calls `disconnect()`.

```python
from revitpy import RevitAPI
from revitpy.api import Wall

api = RevitAPI()
api.connect(__revit__)  # inside Revit (host add-in or pyRevit CPython)

walls = api.query(Wall).execute()
with api.transaction("Mark walls"):
    for wall in walls:
        wall.set_parameter_value("Comments", "checked")
```

---

### RevitDocumentProvider

Bridges RevitPy to a document object implementing `IRevitDocument` (a `revitpy.revit.RevitDocumentAdapter` or a `MockDocument`). Returned by `RevitAPI.active_document`, `open_document()` and `create_document()`; it implements both `IElementProvider` and `ITransactionProvider`.

**Module:** `revitpy.api.wrapper`

| Member | Description |
|--------|-------------|
| `document` | The underlying document object |
| `supports_transactions` | `True` if the document has a `StartTransaction` method |
| `get_all_elements() -> list[Element]` | All elements, wrapped with `Element.wrap` |
| `get_elements_of_type(element_type) -> list[Element]` | Elements of a type; uses `GetElementsByCategory` for types declaring `revit_categories` |
| `get_element_by_id(element_id) -> Element \| None` | Cached lookup; raises `ElementNotFoundError` on API failure |
| `delete_elements(element_ids) -> None` | Delete by ID |
| `start_transaction(name)` / `commit_transaction(t)` / `rollback_transaction(t)` / `is_in_transaction()` | Transaction provider methods |

`start_transaction()` raises `TransactionError` when the document has no `StartTransaction` method; changes are never applied non-atomically. With a live document, a transaction opened while another is open becomes a Revit `SubTransaction`.

---

### Element

Represents a Revit element with parameter access and change tracking.

**Module:** `revitpy.api.element`

```python
class Element:
    revit_categories: ClassVar[tuple[str, ...]] = ()

    def __init__(self, revit_element: IRevitElement) -> None

    @classmethod
    def wrap(cls, revit_element: IRevitElement) -> Element
```

`Element.wrap()` returns an instance of the most specific registered subclass for the element's category (see typed elements below), falling back to `cls`.

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `id` | `ElementId` | The element's unique identifier |
| `category` | `str \| None` | Category name (e.g. `"OST_Walls"` for live elements) |
| `name` | `str` | The element's name (settable) |
| `is_dirty` | `bool` | Whether tracked changes exist |
| `changes` | `dict[str, Any]` | Tracked changes as `{param: {"old": ..., "new": ...}}` |

Property accessors are also defined for common parameters: `family_name` (`Family`), `type_name` (`Type`), `level` (`Level`), `comments` (`Comments`), `mark` (`Mark`).

**Methods:**

```python
def get_parameter_value(self, parameter_name: str, use_cache: bool = True) -> Any
```
Get the value of a parameter by name. Raises `ElementNotFoundError` if the parameter does not exist.

```python
def set_parameter_value(self, parameter_name: str, value: Any, track_changes: bool = True) -> None
```
Set a parameter. The write is applied to the Revit element **immediately**, so on a live model it must run inside an open transaction; it becomes permanent when that transaction commits and is reverted if it rolls back. Raises `PermissionError` for read-only parameters and `ValidationError` for rejected values.

```python
def get_all_parameters(self, refresh_cache: bool = False) -> dict[str, ParameterValue]
```
Get all parameters as a dictionary.

```python
def save_changes(self) -> None
```
Accept tracked changes. Values were already written by `set_parameter_value`; this only clears the local change log.

```python
def discard_changes(self) -> None
```
Revert tracked changes by writing the previous values back (must be called inside a transaction, like any write).

```python
def refresh(self) -> None
```
Clear cached parameter values and the change log.

Lengths, areas and volumes read from a live model are in Revit internal units (feet, square feet, cubic feet).

---

### Typed Elements

**Module:** `revitpy.api.element` (exported from `revitpy.api`)

| Class | `revit_categories` |
|-------|--------------------|
| `Wall` | `("OST_Walls", "Walls")` |
| `Floor` | `("OST_Floors", "Floors")` |
| `Door` | `("OST_Doors", "Doors")` |
| `Window` | `("OST_Windows", "Windows")` |
| `Room` | `("OST_Rooms", "Rooms")` |
| `Level` | `("OST_Levels", "Levels")` |

Declaring `revit_categories` on your own `Element` subclass registers it for those categories, so `Element.wrap()` and `api.query(MyType)` use it.

---

### ElementSet[T]

A LINQ-style collection of elements supporting fluent query operations.

**Module:** `revitpy.api.element`

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `count` | `int` | Number of elements in the set |

**Methods:**

```python
def where(self, predicate: Callable[[T], bool]) -> "ElementSet[T]"
```
Filter elements by a predicate function.

```python
def select(self, selector: Callable[[T], Any]) -> "ElementSet[Any]"
```
Project elements using a selector function.

```python
def first(self, predicate: Callable[[T], bool] | None = None) -> T
```
Return the first element, optionally matching a predicate. Raises `ElementNotFoundError` if empty.

```python
def first_or_default(self, predicate: Callable[[T], bool] | None = None, default: T | None = None) -> T | None
```
Return the first element or a default value.

```python
def single(self, predicate: Callable[[T], bool] | None = None) -> T
```
Return the single matching element. Raises if zero or more than one match.

```python
def to_list(self) -> list[T]
```
Convert the element set to a list.

```python
def any(self, predicate: Callable[[T], bool] | None = None) -> bool
```
Check if any elements match the predicate.

```python
def all(self, predicate: Callable[[T], bool]) -> bool
```
Check if all elements match the predicate.

```python
def order_by(self, key_selector: Callable[[T], Any]) -> "ElementSet[T]"
```
Sort elements by a key selector.

```python
def group_by(self, key_selector: Callable[[T], Any]) -> dict[Any, list[T]]
```
Group elements by a key selector.

---

### ElementId

**Module:** `revitpy.api.element`

```python
@dataclass(frozen=True)
class ElementId:
    value: int
```

Supports `str()` and `int()`.

---

### ParameterValue

**Module:** `revitpy.api.element`

```python
class ParameterValue(BaseModel):
    name: str
    value: Any
    type_name: str
    is_read_only: bool = False
    storage_type: str = "String"
```

`value` is coerced to `float` / `int` when `storage_type` is `"Double"` / `"Integer"`.

---

### Transaction

Wraps a Revit transaction with context manager support. On a live model, `start()` opens a real `Autodesk.Revit.DB.Transaction` (or a `SubTransaction` when one is already open) through the document's `StartTransaction`; an exception inside the `with` block rolls it back.

**Module:** `revitpy.api.transaction`

```python
class Transaction:
    def __init__(self, provider: ITransactionProvider, options: TransactionOptions | None = None) -> None
```

Usually created with `RevitAPI.transaction(name, **options)`. Supports `with` and `async with`.

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Transaction name |
| `status` | `TransactionStatus` | Current status |
| `is_active` | `bool` | Whether the transaction is currently active |
| `duration` | `float \| None` | Duration in seconds |

**Methods:**

```python
def start(self) -> None
```
Start the transaction. Raises `TransactionError` if it was already started or the provider cannot open one.

```python
def commit(self) -> None
```
Run queued operations, then commit. Rolls back and raises `TransactionError` if an operation or the commit fails.

```python
def rollback(self) -> None
```
Roll back the transaction.

```python
def add_operation(self, operation: Callable) -> None
```
Queue an operation to run at commit time (transaction must be active).

```python
def add_rollback_handler(self, handler: Callable) -> None
```
Add a handler called on rollback.

```python
def add_commit_handler(self, handler: Callable) -> None
```
Add a handler called after a successful commit.

**Helper functions** (same module):

```python
def transaction(provider, name: str | None = None, auto_commit: bool = True, retry_count: int = 0, retry_delay: float = 1.0) -> Transaction
def transaction_scope(provider, name: str | None = None, **kwargs)        # context manager
async def async_transaction_scope(provider, name: str | None = None, **kwargs)  # async context manager
def retry_transaction(provider, operation: Callable[[], Any], max_retries: int = 3, delay: float = 1.0, name: str | None = None) -> Any
```

`retry_transaction()` runs `operation` in a new transaction and retries on failure.

---

### TransactionGroup

Groups multiple RevitPy transactions that are started, committed or rolled back together. This is not a Revit `TransactionGroup`: its transactions are started in order, so on a live model the second and later ones become `SubTransaction`s of the first.

**Module:** `revitpy.api.transaction`

```python
class TransactionGroup:
    def __init__(self, provider: ITransactionProvider, name: str | None = None) -> None
```

**Methods:**

```python
def add_transaction(self, options: TransactionOptions | None = None) -> Transaction
```
Add a transaction to the group (defaults to `auto_commit=False`). Only allowed before the group starts.

```python
def start_all(self) -> None
```
Start all transactions in the group.

```python
def commit_all(self) -> None
```
Commit all transactions in the group.

```python
def rollback_all(self) -> None
```
Roll back all transactions in the group.

---

### TransactionStatus

**Module:** `revitpy.api.transaction`

```python
class TransactionStatus(Enum):
    NOT_STARTED = "not_started"
    STARTED = "started"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
```

---

### TransactionOptions

**Module:** `revitpy.api.transaction`

```python
@dataclass
class TransactionOptions:
    name: str | None = None          # defaults to "Transaction_<8 hex chars>"
    description: str | None = None
    auto_commit: bool = True
    timeout_seconds: float | None = None
    retry_count: int = 0
    retry_delay: float = 1.0
    suppress_warnings: bool = False
```

`Transaction` itself only uses `name` and `auto_commit`. `timeout_seconds`, `retry_count`, `retry_delay` and `suppress_warnings` are stored but not enforced; use `retry_transaction()` for retries.

---

### QueryBuilder[T] (Core API)

Fluent query builder for filtering, sorting, and paginating Revit elements. Property names are parameter names (or pseudo-parameters such as `Name`, `Category`, `Type`, `Family`, `Level` on live elements).

**Module:** `revitpy.api.query`

```python
class QueryBuilder(Generic[T]):
    def __init__(self, provider: IElementProvider, element_type: type[T] | None = None) -> None
```

Created with `api.elements`, `api.query(...)`, or the `Query` factory (`Query.from_provider(provider)`, `Query.from_elements(elements)`, `Query.of_type(provider, element_type)`).

**Filter Methods:**

```python
def where(self, property_name: str, operator: FilterOperator, value: Any = None, case_sensitive: bool = True) -> "QueryBuilder[T]"
```
Add a filter condition.

```python
def equals(self, property_name: str, value: Any, case_sensitive: bool = True) -> "QueryBuilder[T]"
def not_equals(self, property_name: str, value: Any, case_sensitive: bool = True) -> "QueryBuilder[T]"
def contains(self, property_name: str, value: str, case_sensitive: bool = True) -> "QueryBuilder[T]"
def starts_with(self, property_name: str, value: str, case_sensitive: bool = True) -> "QueryBuilder[T]"
def ends_with(self, property_name: str, value: str, case_sensitive: bool = True) -> "QueryBuilder[T]"
def in_values(self, property_name: str, values: list[Any]) -> "QueryBuilder[T]"
def is_null(self, property_name: str) -> "QueryBuilder[T]"
def is_not_null(self, property_name: str) -> "QueryBuilder[T]"
def regex(self, property_name: str, pattern: str, case_sensitive: bool = True) -> "QueryBuilder[T]"
```
Convenience filter methods for common operations.

**Sort Methods:**

```python
def order_by(self, property_name: str, direction: SortDirection = SortDirection.ASCENDING) -> "QueryBuilder[T]"
def order_by_ascending(self, property_name: str) -> "QueryBuilder[T]"
def order_by_descending(self, property_name: str) -> "QueryBuilder[T]"
```

**Pagination Methods:**

```python
def skip(self, count: int) -> "QueryBuilder[T]"
def take(self, count: int) -> "QueryBuilder[T]"
def distinct(self, property_name: str | None = None) -> "QueryBuilder[T]"
```

**Terminal Methods:**

```python
def execute(self) -> ElementSet[T]
def count(self) -> int
def any(self) -> bool
def first(self) -> T
def first_or_default(self, default: T | None = None) -> T | None
def single(self) -> T
def to_list(self) -> list[T]
```

---

### FilterOperator

**Module:** `revitpy.api.query` (also exported from `revitpy`)

```python
class FilterOperator(Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    REGEX = "regex"
```

---

### SortDirection

**Module:** `revitpy.api.query`

```python
class SortDirection(Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"
```

---

### Exceptions

**Module:** `revitpy.api.exceptions`

```python
class RevitAPIError(Exception):
    def __init__(self, message: str, cause: Exception | None = None) -> None

class TransactionError(RevitAPIError):
    def __init__(self, message: str, transaction_name: str | None = None, cause: Exception | None = None) -> None

class ElementNotFoundError(RevitAPIError):
    def __init__(self, element_id: int | None = None, element_type: str | None = None, cause: Exception | None = None) -> None

class ValidationError(RevitAPIError):
    def __init__(self, message: str, field: str | None = None, value: Any = None, cause: Exception | None = None) -> None

class PermissionError(RevitAPIError):
    def __init__(self, message: str, operation: str | None = None, cause: Exception | None = None) -> None

class ModelError(RevitAPIError):
    def __init__(self, message: str, cause: Exception | None = None) -> None

class ConnectionError(RevitAPIError):
    def __init__(self, message: str, cause: Exception | None = None) -> None
```

---

## Live Revit (`revitpy.revit`)

Connects RevitPy to a running Revit session through pythonnet. `RevitAPI.connect(__revit__)` uses these adapters automatically; you rarely need them directly.

All adapters must be used on Revit's main API thread (a ribbon script, an external command, a Revit event handler, or an `ExternalEvent` callback). Lengths, areas and volumes are Revit internal units (feet). `Autodesk.Revit.DB` is loaded lazily, so the module imports on any platform.

### revitpy.revit.adapters

**Module:** `revitpy.revit.adapters` (all names re-exported from `revitpy.revit`)

```python
class RevitApiUnavailableError(ConnectionError): ...

def load_revit_api() -> Any
```
Load and cache the `Autodesk.Revit.DB` namespace (`clr.AddReference("RevitAPI")`). Raises `RevitApiUnavailableError` outside Revit.

```python
def adapt_application(app: Any, db: Any | None = None) -> RevitApplicationAdapter
```
Wrap a Revit `UIApplication` or `Application`. Returns `app` unchanged if it is already an adapter; raises `ConnectionError` if the object does not look like a Revit application. `db` injects a stand-in for `Autodesk.Revit.DB` (used by tests).

#### RevitApplicationAdapter

```python
class RevitApplicationAdapter:
    def __init__(self, app: Any, db: Any | None = None) -> None
```

| Member | Description |
|--------|-------------|
| `ui_application` / `application` | The wrapped `UIApplication` (or `None`) and `Application` |
| `ActiveDocument` | `RevitDocumentAdapter` for the active UI document, or `None` (always `None` when wrapping a bare `Application`) |
| `OpenDocumentFile(file_path)` | Open a document |
| `CreateDocument(template_path=None)` | New project document (default project template when omitted) |
| `GetOpenDocuments()` | Adapters for all open documents |

#### RevitDocumentAdapter

```python
class RevitDocumentAdapter:
    def __init__(self, document: Any, db: Any | None = None) -> None
```

| Member | Description |
|--------|-------------|
| `Title`, `PathName`, `IsModified`, `IsReadOnly` | Document properties |
| `Version` | Revit version number (e.g. `"2025"`), or `None` |
| `GetElements(filter_criteria=None)` | All non-type elements, optionally filtered by a predicate |
| `GetElement(element_id)` | Element by `int`, RevitPy `ElementId` or `DB.ElementId`; `None` if absent |
| `GetElementsByCategory(category)` | Non-type elements of a built-in category (`"OST_Walls"`) or display name (`"Walls"`, locale dependent); `[]` for unknown categories |
| `Delete(element_ids)` | Delete elements (inside a transaction) |
| `Save()` / `Close(save_changes=True)` | Save / close the document |
| `StartTransaction(name)` | Start a `DB.Transaction`, or a `DB.SubTransaction` if the document is already modifiable. Returns a started handle with `Commit()` / `RollBack()`. Raises `TransactionError` if Revit refuses to start it |

#### RevitElementAdapter

```python
class RevitElementAdapter:
    def __init__(self, element: Any, db: Any | None = None) -> None
```

| Member | Description |
|--------|-------------|
| `Id` | Raw `DB.ElementId` |
| `Name` | Element name (`""` if Revit refuses) |
| `Category` | Built-in category name (`"OST_Walls"`), else the display name, else `None` |
| `GetParameterValue(name)` | Parameter as a plain Python value by storage type: `String` → `str`, `Double` → `float` (internal units), `Integer` → `int`, `ElementId` → `int`. Also supports pseudo-parameters `Name`, `Category`, `Type`, `Family`, `Level`. Raises `KeyError` if missing |
| `SetParameterValue(name, value)` | Convert `value` to the parameter's storage type and set it (inside a transaction). Setting `Name` without a `Name` parameter sets `element.Name`. Raises `KeyError` (missing), `PermissionError` (read-only), `ValueError` (Revit rejected the value) |
| `GetAllParameters()` | `{name: value}` for all parameters |

### revitpy.revit.host

Helpers for Python running inside the RevitPy host add-in (`src/RevitPy.Addin`). The add-in initializes CPython on Revit's main thread, so `threading.main_thread()` is Revit's API thread; ribbon scripts run there and may call the Revit API directly. Other threads must go through `call_on_revit_thread`, which uses an `ExternalEvent` dispatcher that the add-in exposes as `builtins.__revitpy_dispatcher__`.

**Module:** `revitpy.revit.host`

```python
class RevitHostUnavailableError(RuntimeError): ...
class RevitThreadError(RuntimeError): ...

def get_dispatcher() -> Any | None
def in_revit_host() -> bool
def set_ui_application(ui_application: Any) -> None
```
`get_dispatcher()` returns the add-in's dispatcher or `None`; `in_revit_host()` is `True` inside the add-in. `set_ui_application()` records the `UIApplication` used when `call_on_revit_thread` is called on the main thread.

```python
def call_on_revit_thread(func: Callable[[Any], T], *, timeout: float | None = 60.0, poll_interval: float = 0.005) -> T
```
Run `func(uiapp)` on Revit's main thread and return its result. On the main thread it runs immediately. Raises `RevitHostUnavailableError` outside the host (or on the main thread before `set_ui_application`), `TimeoutError` if Revit did not run the request in time (for example while a modal dialog is open), and `RevitThreadError` (carrying the traceback) if `func` raised.

```python
import threading
from revitpy.revit.host import call_on_revit_thread

def worker():
    title = call_on_revit_thread(lambda uiapp: uiapp.ActiveUIDocument.Document.Title)
    print(title)

threading.Thread(target=worker).start()
```

```python
class MainThreadRevitTools(RevitTools): ...
```
`RevitTools` whose `execute_tool()` always runs on Revit's main thread (original exception types are re-raised).

```python
def revit_confirmation(tool: ToolDefinition, arguments: dict[str, Any]) -> bool
```
A `SafetyGuard` confirmation callback that shows a Yes/No Revit `TaskDialog` (default No, 300 s timeout). Any failure denies the call.

```python
def start_mcp_server(ui_application: Any, *, host: str | None = None, port: int | None = None, token: str | None = None, startup_timeout: float = 10.0) -> str
def stop_mcp_server(timeout: float = 10.0) -> str
def toggle_mcp_server(ui_application: Any) -> str
def mcp_server_status() -> str
def is_mcp_server_running() -> bool
```
Run an `McpServer` for this Revit session on a background thread. `start_mcp_server` must be called on the main thread; it connects a `RevitAPI` to `ui_application`, wraps it in `MainThreadRevitTools`, requires a bearer token and uses a `SafetyGuard` with `revit_confirmation`, so model-changing tools need approval in Revit. Defaults come from `REVITPY_MCP_HOST` (`127.0.0.1`), `REVITPY_MCP_PORT` (`8765`) and `REVITPY_MCP_TOKEN` (a random token when unset). The functions return a status message containing the `ws://` URL and token. The add-in's **MCP Server** ribbon button calls `toggle_mcp_server(__revit__)`.

---

### revitpy.revit.live

**Module:** `revitpy.revit.live` (runs inside Revit). Protocol details: [Live Server Protocol]({{ '/developer/live-server/' | relative_url }}).

```python
def start_live_server(ui_application, *, host=None, port=None, token=None, startup_timeout=10.0) -> str
def stop_live_server(timeout: float = 10.0) -> str
def toggle_live_server(ui_application) -> str
def live_server_status() -> str
def is_live_server_running() -> bool
def register_analysis(name: str, *, replace: bool = False, main_thread: bool = True)  # decorator: func(elements, options, uiapp)
def unregister_analysis(name: str) -> None
def registered_analyses() -> list[str]
def load_analysis_plugins() -> list[str]   # imports "revitpy.analyses" entry points
def discovery_path() -> Path               # ~/.revitpy/live.json or REVITPY_LIVE_DISCOVERY
```

`LiveServer(host="127.0.0.1", port=8766, auth_token=..., revit_version=None, execute_timeout=300.0)` requires a non-empty token. Defaults for `start_live_server` come from `REVITPY_LIVE_HOST`, `REVITPY_LIVE_PORT` and `REVITPY_LIVE_TOKEN` (random when unset).

### revitpy.live_client

```python
class LiveConnectionInfo:        # url, token, protocol, revit_version, pid
    @classmethod
    def from_discovery(cls, path=None) -> LiveConnectionInfo

class LiveClient:                # async with LiveClient() as client: ...
    async def call(self, method, params=None) -> Any
    async def status(self) -> dict
    async def execute(self, code, filename="<live>", cwd=None) -> dict
    async def run_file(self, path) -> dict
    async def reload(self, modules=None, paths=None) -> dict
    async def start_debugger(self, port=5678) -> dict
    async def list_analyses(self) -> list[str]
    async def analyze(self, analysis, elements, options=None) -> dict

def call_live(method, params=None, *, info=None, timeout=330.0) -> Any   # synchronous one-off
```

`LiveServerNotFoundError` means no server could be reached; `LiveServerError` (`.code`, `.message`) wraps JSON-RPC errors and rejected handshakes.

### revitpy.rpc

`JsonRpcWebSocketServer(host, port, auth_token, allowed_origins=())` is the base class of `McpServer` and `LiveServer`: lifecycle (`start`, `stop`, `port`), bearer-token and Origin checks on the handshake, and JSON-RPC 2.0 frame validation with id-correlated errors. Subclasses implement `async _handle_message(request)`.

---

## Command-line interface (`revitpy.cli`)

Installed as the `revitpy` console script.

| Command | Description |
|---------|-------------|
| `revitpy --version` / `revitpy version` | Print the installed RevitPy version |
| `revitpy doctor [--json]` | Check the Python version, platform, core and optional dependencies (pythonnet, ifcopenshell, specklepy, defusedxml) and whether the Revit API can be loaded. Exits with status 1 if a core dependency is missing |
| `revitpy mcp-serve [--host 127.0.0.1] [--port 8765] [--token TOKEN]` | Run the MCP server without a live Revit connection (`--token` falls back to `REVITPY_MCP_TOKEN`). Tools that need a document report that RevitPy is not connected; use the add-in's MCP Server button (or `start_mcp_server`) to work on a live model |

| `revitpy live status [--json]` | Show the Revit session behind the running Live Server |
| `revitpy live run SCRIPT` | Run a script in Revit (`live/runFile`); exits 1 if it fails |
| `revitpy live exec CODE` | Execute code in Revit (`live/execute`) |
| `revitpy live reload MODULE...` | Reload modules by name or `.py` path (`live/reload`) |
| `revitpy live debug [--port 5678]` | Start `debugpy` in Revit (`debug/start`) |

`revitpy.cli.collect_checks()` returns the `doctor` checks as a list of `{"name", "status", "detail"}` dicts (`status` is `"ok"`, `"warn"` or `"missing"`).

---

## ORM Layer (`revitpy.orm`)

### RevitContext

The primary ORM context for querying and managing Revit elements with change tracking, caching, and relationship support.

**Module:** `revitpy.orm.context` (also `from revitpy.orm import RevitContext, create_context`)

```python
class RevitContext:
    def __init__(
        self,
        provider: IElementProvider,
        *,
        config: ContextConfiguration | None = None,
        cache_manager: CacheManager | None = None,
        change_tracker: ChangeTracker | None = None,
        relationship_manager: RelationshipManager | None = None,
        unit_of_work: IUnitOfWork | None = None,
    ) -> None
```

`provider` is any `IElementProvider`, typically `api.active_document` of a connected `RevitAPI`. Can be used as a context manager (`with RevitContext(provider) as ctx:`); the context is disposed on exit.

**Properties:** `is_disposed`, `has_changes`, `change_count`, `cache_statistics`.

**Query Methods:**

```python
def query(self, element_type: type[T] | None = None) -> QueryBuilder[T]
def all(self, element_type: type[T]) -> ElementSet[T]
def where(self, element_type: type[T], predicate: Callable[[T], bool]) -> ElementSet[T]
def first(self, element_type: type[T], predicate: Callable[[T], bool] | None = None) -> T
def first_or_default(self, element_type: type[T], predicate: Callable[[T], bool] | None = None, default: T | None = None) -> T | None
def single(self, element_type: type[T], predicate: Callable[[T], bool] | None = None) -> T
def count(self, element_type: type[T], predicate: Callable[[T], bool] | None = None) -> int
def any(self, element_type: type[T], predicate: Callable[[T], bool] | None = None) -> bool
def get_by_id(self, element_type: type[T], element_id: ElementId) -> T | None
```

**Change Tracking Methods:**

```python
def attach(self, entity: T, entity_id: ElementId | None = None) -> None
def detach(self, entity: T) -> None
def add(self, entity: T) -> None
def remove(self, entity: T) -> None
def update(self, entity: T, **changes: Any) -> None  # set + track as modified
def get_entity_state(self, entity: T) -> ElementState
def accept_changes(self, entity: T | None = None) -> None
def reject_changes(self, entity: T | None = None) -> None
def save_changes(self) -> int
```

`save_changes()` registers every tracked change with the configured `IUnitOfWork` (`register_new` / `register_dirty` / `register_removed`), calls `commit()`, then accepts the changes and returns their count. On failure it calls the unit of work's `rollback()` and raises `ORMException`. **Without a unit of work, changes are only accepted in the tracker; nothing is written to Revit.** (Writes made through `Element.set_parameter_value` already go to Revit directly inside a `RevitAPI.transaction`.)

**Relationship Methods:**

```python
def load_relationship(self, entity: T, relationship_name: str, strategy: LoadStrategy = LoadStrategy.LAZY) -> Any
def configure_relationship(self, source_type: type[T], relationship_name: str, target_type: type, **kwargs) -> None
```

**Cache Methods:**

```python
def clear_cache(self) -> None
def invalidate_cache(self, entity_type: type | None = None, entity_id: ElementId | None = None) -> None
```

**Other Methods:**

```python
@contextmanager
def transaction(self, auto_commit: bool = True) -> Iterator[RevitContext]
def as_async(self) -> AsyncRevitContext
def dispose(self) -> None
```

`transaction()` is an ORM-level unit of work, not a Revit transaction: on success it calls `save_changes()` (when `auto_commit`), on error it rejects changes and rolls back the unit of work. Wrap it in `RevitAPI.transaction()` when the unit of work writes to a Revit document.

---

### AsyncRevitContext

**Module:** `revitpy.orm.async_support` (exported from `revitpy.orm`)

```python
class AsyncRevitContext:
    def __init__(
        self,
        provider: IElementProvider,
        *,
        cache_manager: CacheManager | None = None,
        change_tracker: ChangeTracker | None = None,
        relationship_manager: RelationshipManager | None = None,
        unit_of_work: IUnitOfWork | None = None,
        auto_track_changes: bool = True,
        default_cache_policy: CachePolicy = CachePolicy.MEMORY,
        transaction_timeout: float | None = None,
        ...
    ) -> None
```

```python
async def get_all_async(self, element_type: type[T] | None = None) -> list[T]
async def get_by_id_async(self, element_id: Any) -> T | None
async def save_changes_async(self) -> int
async def transaction(self, auto_commit: bool = True, timeout_seconds: float | None = None)  # async context manager
async def load_relationship_async(...)
async def dispose_async(self) -> None
```

`save_changes_async()` registers each change with the `IUnitOfWork` and then awaits `commit_async()` (falling back to `commit()`). If any change fails to register, or the commit fails, it rolls back (`rollback_async()` / `rollback()`) and raises `AsyncOperationError`; nothing is reported as saved. Without a unit of work, changes are only accepted in the tracker.

---

### IUnitOfWork

**Module:** `revitpy.orm.types`

```python
class IUnitOfWork(Protocol):
    def register_new(self, entity: Any) -> None: ...
    def register_dirty(self, entity: Any) -> None: ...
    def register_removed(self, entity: Any) -> None: ...
    def register_clean(self, entity: Any) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    async def commit_async(self) -> None: ...
    async def rollback_async(self) -> None: ...
```

The persistence boundary for `RevitContext.save_changes()` and `AsyncRevitContext.save_changes_async()`.

---

### ContextConfiguration

**Module:** `revitpy.orm.context`

```python
@dataclass
class ContextConfiguration:
    auto_track_changes: bool = True
    cache_policy: CachePolicy = CachePolicy.MEMORY
    cache_max_size: int = 10000
    cache_max_memory_mb: int = 500
    lazy_loading_enabled: bool = True
    batch_size: int = 100
    thread_safe: bool = True
    validation_enabled: bool = True
    performance_monitoring: bool = True
```

---

### create_context

**Module:** `revitpy.orm.context` (exported from `revitpy.orm`)

```python
def create_context(provider: IElementProvider, **kwargs) -> RevitContext
def create_async_context(provider: IElementProvider, **kwargs) -> AsyncRevitContext
```

```python
from revitpy import RevitAPI
from revitpy.api import Wall
from revitpy.orm import create_context

api = RevitAPI()
api.connect(__revit__)
ctx = create_context(api.active_document)
walls = ctx.all(Wall)
```

---

### QueryBuilder[T] (ORM)

ORM query builder with lazy evaluation and async support. Distinct from the Core API QueryBuilder. Builders are immutable: every fluent method returns a clone and never mutates the parent.

**Module:** `revitpy.orm.query_builder`

```python
class QueryBuilder(Generic[T]):
    def __init__(
        self,
        provider: IElementProvider,
        element_type: type[T] | None = None,
        cache_manager: CacheManager | None = None,
        query_mode: QueryMode = QueryMode.LAZY,
    ) -> None
```

Usually obtained from `RevitContext.query(element_type)`.

**Fluent Methods:**

```python
def where(self, predicate: Callable[[T], bool]) -> "QueryBuilder[T]"
def select(self, selector: Callable[[T], R]) -> "QueryBuilder[R]"
def order_by(self, key_selector: Callable[[T], Any]) -> "QueryBuilder[T]"
def order_by_descending(self, key_selector: Callable[[T], Any]) -> "QueryBuilder[T]"
def skip(self, count: int) -> "QueryBuilder[T]"
def take(self, count: int) -> "QueryBuilder[T]"
def distinct(self, key_selector: Callable[[T], Any] | None = None) -> "QueryBuilder[T]"
```

`select()` keeps the source element type (it still determines which elements are fetched before the projection runs).

**Synchronous Terminal Methods:**

```python
def first(self, predicate: Callable[[T], bool] | None = None) -> T
def first_or_default(self, predicate: Callable[[T], bool] | None = None, default: T | None = None) -> T | None
def single(self, predicate: Callable[[T], bool] | None = None) -> T
def single_or_default(self, predicate: Callable[[T], bool] | None = None, default: T | None = None) -> T | None
def any(self, predicate: Callable[[T], bool] | None = None) -> bool
def all(self, predicate: Callable[[T], bool]) -> bool
def count(self, predicate: Callable[[T], bool] | None = None) -> int
def to_list(self) -> list[T]
def to_dict(self, key_selector: Callable[[T], Any]) -> dict[Any, T]
def group_by(self, key_selector: Callable[[T], Any]) -> dict[Any, list[T]]
```

**Asynchronous Terminal Methods:**

```python
async def first_async(self, predicate: Callable[[T], bool] | None = None) -> T
async def first_or_default_async(self, predicate: Callable[[T], bool] | None = None, default: T | None = None) -> T | None
async def single_async(self, predicate: Callable[[T], bool] | None = None) -> T
async def any_async(self, predicate: Callable[[T], bool] | None = None) -> bool
async def count_async(self, predicate: Callable[[T], bool] | None = None) -> int
async def to_list_async(self) -> list[T]
async def to_dict_async(self, key_selector: Callable[[T], Any]) -> dict[Any, T]
```

The builder is also iterable (`for x in qb`) and async-iterable (`async for x in qb`).

**Streaming:**

```python
def as_streaming(self, batch_size: int = 100) -> "StreamingQuery[T]"
```

**Caching:**

```python
@property
def is_cacheable(self) -> bool

def plan_is_cacheable(plan: QueryPlan) -> bool   # module-level function
```

Query results are cached (keyed by an MD5 hash of the plan) only when the plan contains no callables -- i.e. no `where` / `select` / `order_by` lambdas -- and caching is not disabled (`CachePolicy.NONE`). Plans made only of `skip` / `take` / `distinct` and similar are cacheable.

**Plan optimisation:** `QueryPlan.optimize()` never changes results. Its only reordering moves a filter ahead of an immediately preceding `order_by` / `then_by`; filters are never moved across `select`, `skip` / `take` or `distinct`.

---

### StreamingQuery[T]

Streaming query executor for processing large result sets in batches. It is an async iterator that consumes the source lazily and yields lists of at most `batch_size` elements.

**Module:** `revitpy.orm.query_builder`

```python
class StreamingQuery(Generic[T]):
    def __init__(self, query_builder: QueryBuilder[T], batch_size: int = 100) -> None

    async def __aiter__(self) -> AsyncIterator[list[T]]
    async def foreach_async(self, action: Callable[[T], Awaitable[None]]) -> None
    async def to_list_async(self) -> list[T]
```

```python
async for batch in ctx.query(Wall).as_streaming(100):
    process(batch)
```

---

### CacheManager

Manages caching of elements and query results with multiple eviction policies.

**Module:** `revitpy.orm.cache`

```python
class CacheManager:
    def __init__(self, config: CacheConfiguration | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `statistics` | `CacheStatistics` | Cache hit/miss statistics |
| `size` | `int` | Number of items in the cache |

**Methods:**

```python
def get(self, key: str) -> Any | None
def set(self, key: str, value: Any, *, ttl_seconds: float | None = None, dependencies: list[str] | None = None) -> None
def delete(self, key: str) -> None
def invalidate(self, key: str) -> None
def invalidate_by_dependency(self, dependency: str) -> None
def invalidate_by_pattern(self, pattern: str) -> None
def clear(self) -> None
def contains(self, key: str) -> bool
def keys(self) -> list[str]
def add_invalidation_callback(self, callback: Callable) -> None
def remove_invalidation_callback(self, callback: Callable) -> None
def get_memory_usage_estimate(self) -> int
```

---

### CacheConfiguration

**Module:** `revitpy.orm.cache`

```python
@dataclass
class CacheConfiguration:
    max_size: int = 1000
    max_memory_mb: float = 100.0
    default_ttl_seconds: float = 300.0
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    enable_statistics: bool = True
    cleanup_interval_seconds: float = 60.0
    compression_enabled: bool = False
    thread_safe: bool = True
```

---

### CacheStatistics

**Module:** `revitpy.orm.cache`

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `hits` | `int` | Number of cache hits |
| `misses` | `int` | Number of cache misses |
| `hit_rate` | `float` | Cache hit rate (0.0 to 1.0) |
| `evictions` | `int` | Number of evictions |
| `invalidations` | `int` | Number of invalidations |
| `memory_usage` | `int` | Estimated memory usage in bytes |
| `uptime` | `float` | Cache uptime in seconds |

---

### EvictionPolicy

**Module:** `revitpy.orm.cache`

```python
class EvictionPolicy(Enum):
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"
    SIZE_BASED = "size_based"
```

---

### ChangeTracker

Tracks changes to entities for the unit of work pattern.

**Module:** `revitpy.orm.change_tracker`

```python
class ChangeTracker:
    def __init__(self, thread_safe: bool = True) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `auto_track` | `bool` | Whether to automatically track property changes (settable) |
| `has_changes` | `bool` | Whether any tracked entities have changes |
| `changed_entities` | `list[ElementId]` | IDs of entities with changes |
| `change_count` | `int` | Total number of changes |

**Methods:**

```python
def attach(self, entity: Any, entity_id: ElementId | None = None) -> None
def detach(self, entity_id: ElementId) -> None
def track_property_change(self, entity: Any, property_name: str, old_value: Any, new_value: Any) -> None   # ValueError if entity is None
def track_relationship_change(self, entity: Any, relationship_name: str, change_type: ChangeType, related_entity: Any | None = None) -> None
def mark_as_added(self, entity: Any) -> None
def mark_as_deleted(self, entity: Any) -> None
def get_entity_state(self, entity_id: ElementId) -> ElementState
def get_changes(self, entity_id: ElementId) -> ChangeSet | None
def get_all_changes(self) -> list[ChangeSet]
def accept_changes(self, entity_id: ElementId | None = None) -> None
def reject_changes(self, entity_id: ElementId | None = None) -> None
def clear(self) -> None
def create_batch_operation(self, operation_type: BatchOperationType, entity: Any, properties: dict[str, Any] | None = None) -> BatchOperation
def add_batch_operation(self, operation: BatchOperation) -> None
def get_batch_operations(self) -> list[BatchOperation]
def clear_batch_operations(self) -> None
def add_change_callback(self, callback: Callable[[PropertyChange], None]) -> None
def remove_change_callback(self, callback: Callable[[PropertyChange], None]) -> None
def is_tracked(self, entity_id: ElementId) -> bool
def get_tracked_count(self) -> int
```

---

### ChangeType

**Module:** `revitpy.orm.change_tracker`

```python
class ChangeType(Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"
```

---

### PropertyChange

**Module:** `revitpy.orm.change_tracker`

```python
@dataclass
class PropertyChange:
    property_name: str
    old_value: Any
    new_value: Any
```

---

### RelationshipManager

Manages relationships between Revit elements (one-to-one, one-to-many, many-to-many).

**Module:** `revitpy.orm.relationships`

```python
class RelationshipManager:
    def __init__(self) -> None
```

**Methods:**

```python
def register_one_to_one(self, source_type: type, target_type: type, foreign_key: str, **kwargs) -> None
def register_one_to_many(self, source_type: type, target_type: type, foreign_key: str, **kwargs) -> None
def register_many_to_many(self, source_type: type, target_type: type, junction_type: type | None = None, **kwargs) -> None
def get_relationship(self, source_type: type, relationship_name: str) -> Relationship | None
def load_relationship(self, entity: Any, relationship_name: str, context=None) -> Any
async def load_relationship_async(self, entity: Any, relationship_name: str, context=None) -> Any
def invalidate_relationship(self, entity: Any, relationship_name: str) -> None
def invalidate_entity(self, entity: Any) -> None
def get_registered_relationships(self) -> list[Relationship]
```

---

### Validation Models

Pydantic-based validation models for common Revit element types.

**Module:** `revitpy.orm.validation`

#### BaseElement

```python
class BaseElement(BaseModel):
    id: int | None = None
    name: str
    category: str = ""
    level_id: int | None = None
    family_name: str = ""
    type_name: str = ""
    created_at: datetime | None = None
    modified_at: datetime | None = None
    version: int = 1
    is_valid: bool = True
    state: str = "unchanged"
```

**Methods:**

```python
def is_dirty(self) -> bool
def mark_dirty(self) -> None
def mark_clean(self) -> None
```

#### WallElement

```python
class WallElement(BaseElement):
    height: float = 0.0
    length: float = 0.0
    width: float = 0.0
    area: float = 0.0
    volume: float = 0.0
    # Additional wall-specific fields
```

#### RoomElement

```python
class RoomElement(BaseElement):
    number: str = ""
    area: float = 0.0
    perimeter: float = 0.0
    volume: float = 0.0
    department: str = ""
    occupancy: int = 0
    # Additional room-specific fields
```

#### DoorElement

```python
class DoorElement(BaseElement):
    width: float = 0.0
    height: float = 0.0
    material: str = ""
    fire_rating: str = ""
    # Additional door-specific fields
```

#### WindowElement

```python
class WindowElement(BaseElement):
    width: float = 0.0
    height: float = 0.0
    glass_type: str = ""
    # Additional window-specific fields
```

#### Factory Functions

```python
def create_wall(**kwargs) -> WallElement
def create_room(**kwargs) -> RoomElement
def create_door(**kwargs) -> DoorElement
def create_window(**kwargs) -> WindowElement
```

---

### ElementValidator

**Module:** `revitpy.orm.validation`

```python
class ElementValidator:
    # Validates elements against Pydantic models and custom constraints
```

### ValidationLevel

**Module:** `revitpy.orm.validation`

```python
class ValidationLevel(Enum):
    # Defines validation strictness levels
```

### ConstraintType

**Module:** `revitpy.orm.validation`

```python
class ConstraintType(Enum):
    # Defines types of validation constraints
```

---

## Events (`revitpy.events`)

### EventManager

Singleton event manager for registering and dispatching events. `EventManager()` and `EventManager.get_instance()` return the same instance; `get_event_manager()` is a module-level shortcut.

**Module:** `revitpy.events.manager` (exported from `revitpy`)

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `dispatcher` | `EventDispatcher` | The internal event dispatcher |
| `is_running` | `bool` | Whether the event manager is running |
| `stats` | `dict` | Event processing statistics |

**Lifecycle Methods:**

```python
def start(self, auto_discover: bool = True) -> None
def stop(self, timeout: float = 5.0) -> None
```

**Handler Registration:**

```python
def register_handler(self, handler: BaseEventHandler, event_types: list[EventType] | None = None) -> None
def register_function(self, func: Callable[[EventData], Any], event_types: list[EventType], priority: EventPriority = EventPriority.NORMAL, event_filter: EventFilter | None = None, name: str | None = None) -> BaseEventHandler
def unregister_handler(self, handler: BaseEventHandler, event_types: list[EventType] | None = None) -> None
def register_class_handlers(self, instance: Any) -> list[BaseEventHandler]
```

`register_function()` is the simplest way to register a plain (or `async`) function. A module-level function decorated with `@event_handler` can be registered with `manager.register_handler(func._event_handler, func._event_types)` or picked up by discovery.

> **Known limitation:** `register_class_handlers()` registers `@event_handler`-decorated methods without binding `self`, so the handler fails at dispatch time with a missing-argument error. Use `register_function()` with bound methods (e.g. `manager.register_function(obj.on_modified, [EventType.ELEMENT_MODIFIED])`) instead.

**Event Dispatch:**

```python
def dispatch_event(self, event_type: EventType, immediate: bool = False, **event_data) -> EventDispatchResult
async def dispatch_event_async(self, event_type: EventType, **event_data) -> EventDispatchResult
def emit(self, event_type: EventType, data: dict | None = None, source: Any | None = None, cancellable: bool = False, immediate: bool = False) -> EventDispatchResult
async def emit_async(self, event_type: EventType, data: dict | None = None, source: Any | None = None, cancellable: bool = False) -> EventDispatchResult
```

`**event_data` becomes fields of the event-type-specific data class (e.g. `element_id=` for element events). Without `immediate=True`, events are queued for the background processor started by `start()`.

```python
from revitpy import EventManager, EventPriority, EventType

def on_element_modified(event):
    print(f"Element {event.element_id} was modified")

manager = EventManager.get_instance()
manager.register_function(on_element_modified, [EventType.ELEMENT_MODIFIED], priority=EventPriority.HIGH)
manager.dispatch_event(EventType.ELEMENT_MODIFIED, element_id=12345, immediate=True)
```

**Discovery:**

```python
def add_discovery_path(self, path: Path) -> None
def discover_handlers(self, paths: list[Path] | None = None) -> int
```

**Listener Management:**

```python
def add_listener(self, event_type: EventType, callback: Callable[[EventData], Any], priority: EventPriority = EventPriority.NORMAL) -> None
def remove_listener(self, event_type: EventType, callback: Callable[[EventData], Any]) -> bool
```

**Revit Integration:**

```python
def connect_to_revit(self, revit_application: Any) -> None
def disconnect_from_revit(self) -> None
```

`connect_to_revit()` looks for a `revitpy.events.revit_bridge` module that is not shipped, so it currently only logs "Revit event bridge not available". Native Revit events are not bridged automatically; subscribe to them with the Revit API and call `dispatch_event()` yourself.

**Debugging:**

```python
def enable_debug(self) -> None
def disable_debug(self) -> None
def clear_event_queue(self) -> int
def reset_statistics(self) -> None
def get_registered_handlers(self) -> dict[EventType, list[str]]
```

---

### EventType

**Module:** `revitpy.events.types` (exported from `revitpy`)

```python
class EventType(Enum):
    # Document events
    DOCUMENT_OPENED = "document_opened"
    DOCUMENT_CLOSED = "document_closed"
    DOCUMENT_SAVED = "document_saved"
    DOCUMENT_SYNCHRONIZED = "document_synchronized"

    # Element events
    ELEMENT_CREATED = "element_created"
    ELEMENT_MODIFIED = "element_modified"
    ELEMENT_DELETED = "element_deleted"
    ELEMENT_TYPE_CHANGED = "element_type_changed"

    # Transaction events
    TRANSACTION_STARTED = "transaction_started"
    TRANSACTION_COMMITTED = "transaction_committed"
    TRANSACTION_ROLLED_BACK = "transaction_rolled_back"

    # Parameter events
    PARAMETER_CHANGED = "parameter_changed"
    PARAMETER_ADDED = "parameter_added"
    PARAMETER_REMOVED = "parameter_removed"

    # View events
    VIEW_ACTIVATED = "view_activated"
    VIEW_DEACTIVATED = "view_deactivated"
    VIEW_CREATED = "view_created"

    # Selection events
    SELECTION_CHANGED = "selection_changed"

    # Application events
    APPLICATION_INITIALIZED = "application_initialized"
    APPLICATION_CLOSING = "application_closing"

    # Custom events
    CUSTOM = "custom"
```

---

### EventPriority

**Module:** `revitpy.events.types` (exported from `revitpy`)

```python
class EventPriority(Enum):
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100
```

---

### EventResult

**Module:** `revitpy.events.types`

```python
class EventResult(Enum):
    CONTINUE = "continue"
    STOP = "stop"
    CANCEL = "cancel"
```

---

### EventData

**Module:** `revitpy.events.types`

```python
@dataclass
class EventData:
    event_type: EventType
    event_id: str                 # uuid4 string
    timestamp: datetime           # datetime.now()
    source: Any | None = None
    data: dict[str, Any] = field(default_factory=dict)
    cancellable: bool = False
    cancelled: bool = False
```

**Methods:**

```python
def cancel(self) -> None
def get_data(self, key: str, default: Any = None) -> Any
def set_data(self, key: str, value: Any) -> None
```

**Specialized Event Data Classes** (created by `create_event_data()` according to the event type):

- `DocumentEventData(EventData)` -- document-specific event data
- `ElementEventData(EventData)` -- element events; has `element_id`
- `TransactionEventData(EventData)` -- transaction-specific event data
- `ParameterEventData(EventData)` -- parameter changes; has `element_id`
- `ViewEventData(EventData)` -- view-specific event data
- `SelectionEventData(EventData)` -- selection change event data

---

### Event Decorators

**Module:** `revitpy.events.decorators`

```python
def event_handler(
    event_types: list[EventType] | None = None,
    priority: EventPriority = EventPriority.NORMAL,
    event_filter: EventFilter | None = None,
    max_errors: int = 10,
    enabled: bool = True,
) -> Callable
```
Mark a function as an event handler. `event_types` is a **list** (e.g. `[EventType.ELEMENT_MODIFIED]`). The handler object is stored on the function as `_event_handler` and the types as `_event_types`; the decorator does not register it with the manager by itself.

```python
def async_event_handler(
    event_types: list[EventType] | None = None,
    priority: EventPriority = EventPriority.NORMAL,
    event_filter: EventFilter | None = None,
    max_errors: int = 10,
    enabled: bool = True,
) -> Callable
```
Same as `event_handler` for async functions.

```python
def event_filter(filter_instance: EventFilter) -> Callable
```
Attach a filter to an event handler.

```python
def throttled_handler(interval_seconds: float = 0.1) -> Callable
```
Throttle handler execution to a minimum interval.

```python
def conditional_handler(condition: Callable[[EventData], bool]) -> Callable
```
Execute the handler only when `condition` returns true.

```python
def retry_on_error(max_retries: int = 3, delay_seconds: float = 1.0) -> Callable
```
Retry a handler on error.

```python
def log_events(log_level: str = "DEBUG") -> Callable
```
Log handler invocations.

**Convenience Decorators:**

```python
def on_element_created(element_type: str | None = None, priority: EventPriority = EventPriority.NORMAL) -> Callable
def on_element_modified(element_type: str | None = None, parameter_name: str | None = None, priority: EventPriority = EventPriority.NORMAL) -> Callable
def on_element_deleted(element_type: str | None = None, priority: EventPriority = EventPriority.NORMAL) -> Callable
def on_parameter_changed(parameter_name: str, element_type: str | None = None, priority: EventPriority = EventPriority.NORMAL) -> Callable
def on_document_opened(priority: EventPriority = EventPriority.NORMAL) -> Callable
def on_document_saved(priority: EventPriority = EventPriority.NORMAL) -> Callable
```

---

## Extensions (`revitpy.extensions`)

### Extension

Abstract base class for RevitPy extensions with lifecycle management.

**Module:** `revitpy.extensions.extension` (exported from `revitpy` and `revitpy.extensions`)

```python
class Extension(ABC):
    def __init__(
        self,
        metadata: ExtensionMetadata,
        container: DIContainer | None = None,
        config: Config | None = None,
    ) -> None
```

`metadata` is required.

**Lifecycle Methods (override in subclasses):**

```python
async def load(self) -> None          # abstract
async def activate(self) -> None      # abstract
async def deactivate(self) -> None    # abstract
async def dispose(self) -> None       # optional override
```

**Lifecycle drivers (called by ExtensionManager, or directly):**

```python
async def load_extension(self) -> bool
async def activate_extension(self) -> bool
async def deactivate_extension(self) -> bool
async def dispose_extension(self) -> None
```

**Properties:** `name`, `version`, `extension_id`, `status`, `is_loaded`, `is_active`, `has_error`, `last_error`.

**Component Access:**

```python
def get_command(self, name: str) -> Any | None
def get_service(self, name: str) -> Any | None
def get_tool(self, name: str) -> Any | None
def get_analyzer(self, name: str) -> Any | None
def get_commands(self) -> dict[str, Any]
def get_services(self) -> dict[str, Any]
def get_tools(self) -> dict[str, Any]
def get_analyzers(self) -> dict[str, Any]
```

**Lifecycle Callbacks:**

```python
def on_load(self, callback: Callable) -> None
def on_activation(self, callback: Callable) -> None
def on_deactivation(self, callback: Callable) -> None
def on_disposal(self, callback: Callable) -> None
```

**Logging helpers:** `log_info()`, `log_warning()`, `log_error()`, `log_debug()`.

```python
from revitpy.extensions import Extension, ExtensionMetadata

class MyExtension(Extension):
    async def load(self):
        self.log_info("loading")

    async def activate(self):
        self.log_info("active")

    async def deactivate(self):
        pass

ext = MyExtension(ExtensionMetadata(name="my-extension", version="1.0.0"))
await ext.load_extension()
await ext.activate_extension()
```

---

### ExtensionMetadata

**Module:** `revitpy.extensions.extension`

```python
@dataclass
class ExtensionMetadata:
    name: str
    version: str
    description: str = ""
    author: str = ""
    website: str = ""
    license: str = ""
    dependencies: list[str] = field(default_factory=list)
    revit_versions: list[str] = field(default_factory=list)
    python_version: str = ">=3.11"
    provides_commands: list[str] = field(default_factory=list)
    provides_services: list[str] = field(default_factory=list)
    provides_tools: list[str] = field(default_factory=list)
    provides_analyzers: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] | None = None
    default_config: dict[str, Any] | None = None
    extension_id: str = field(default_factory=lambda: str(uuid4()))
    load_time: datetime | None = None
    activation_time: datetime | None = None
```

---

### ExtensionStatus

**Module:** `revitpy.extensions.extension`

```python
class ExtensionStatus(Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    DEACTIVATED = "deactivated"
    ERROR = "error"
    DISPOSED = "disposed"
```

---

### ExtensionManager

Singleton manager for discovering, loading, and managing extensions.

**Module:** `revitpy.extensions.manager`

```python
class ExtensionManager:
    # Singleton -- use ExtensionManager() to get the instance
```

**Methods:**

```python
def initialize(self) -> None
def shutdown(self) -> None
def discover_extensions(self, path: str | None = None) -> list[Extension]
def load_extension(self, extension: Extension | str) -> None
def unload_extension(self, extension_name: str) -> None
def activate_extension(self, extension_name: str) -> None
def deactivate_extension(self, extension_name: str) -> None
def get_extension(self, extension_name: str) -> Extension | None
def get_extensions(self) -> list[Extension]
def get_active_extensions(self) -> list[Extension]
def get_extensions_by_status(self, status: ExtensionStatus) -> list[Extension]
def has_extension(self, extension_name: str) -> bool
def is_extension_active(self, extension_name: str) -> bool
def get_statistics(self) -> dict[str, Any]
def get_extension_info(self, extension_name: str) -> dict[str, Any]
```

---

### Extension Decorators

**Module:** `revitpy.extensions.decorators`

```python
def extension(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    author: str = "",
    dependencies: list[str] | None = None,
) -> Callable
```
Class decorator to register a class as an extension.

```python
def command(
    name: str,
    description: str = "",
    icon: str = "",
    tooltip: str = "",
    shortcut: str = "",
    category: str = "",
    enabled: bool = True,
    visible: bool = True,
) -> Callable
```
Decorator to register a method as a command.

```python
def service(
    name: str,
    description: str = "",
    auto_start: bool = False,
    singleton: bool = True,
    dependencies: list[str] | None = None,
) -> Callable
```
Decorator to register a method as a service.

```python
def tool(
    name: str,
    description: str = "",
    icon: str = "",
    tooltip: str = "",
    category: str = "",
    interactive: bool = False,
    preview: bool = False,
) -> Callable
```
Decorator to register a method as a tool.

```python
def analyzer(
    name: str,
    description: str = "",
    element_types: list[str] | None = None,
    categories: list[str] | None = None,
    real_time: bool = False,
    on_demand: bool = True,
) -> Callable
```
Decorator to register a method as an analyzer.

```python
def panel(
    name: str,
    title: str = "",
    width: int = 300,
    height: int = 400,
    resizable: bool = True,
    dockable: bool = True,
    floating: bool = False,
) -> Callable
```
Decorator to register a method as a panel.

```python
def startup(priority: int = 0) -> Callable
```
Decorator to mark a method to run on extension startup.

```python
def shutdown(priority: int = 0) -> Callable
```
Decorator to mark a method to run on extension shutdown.

```python
def config(
    key: str,
    default_value: Any = None,
    description: str = "",
    required: bool = False,
    validator: Callable | None = None,
) -> Callable
```
Decorator to register a configuration option.

```python
def permission(
    name: str,
    description: str = "",
    required: bool = True,
    category: str = "",
) -> Callable
```
Decorator to declare a required permission.

```python
def cache(
    ttl: float = 300.0,
    max_size: int = 100,
    key_func: Callable | None = None,
) -> Callable
```
Decorator to cache method results.

---

## Async Support (`revitpy.async_support`)

### AsyncRevit

Asynchronous interface for Revit operations.

**Module:** `revitpy.async_support.async_revit`

```python
class AsyncRevit:
    def __init__(self, revit_application: IRevitApplication | None = None) -> None
```

Async operations still execute Revit API calls on the calling thread; inside Revit they must run on Revit's main thread (see `revitpy.revit.host.call_on_revit_thread`).

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `api` | `RevitAPI` | The underlying RevitAPI instance |
| `is_connected` | `bool` | Whether connected to Revit |
| `task_queue` | `TaskQueue` | The internal task queue |

**Initialization:**

```python
async def initialize(self, max_concurrent_tasks: int = 4, revit_application=None) -> None
async def shutdown(self, timeout: float | None = None) -> None
```

**Document Operations:**

```python
async def open_document_async(self, file_path: str) -> Any
async def create_document_async(self, template_path: str | None = None) -> Any
async def save_document_async(self, provider=None) -> None
async def close_document_async(self, provider=None, save_changes: bool = True) -> None
```

**Element Operations:**

```python
async def get_elements_async(self, element_type: str | None = None) -> list
async def query_elements_async(self, element_type: str, **filters) -> list
async def update_elements_async(self, elements: list, **updates) -> None
```

**Transaction:**

```python
def async_transaction(self, name: str = "Transaction") -> Any
async def execute_in_transaction_async(self, func: Callable, name: str = "Transaction") -> Any
```

**Background Tasks:**

```python
async def run_background_task(self, func: Callable, *args, **kwargs) -> Any
async def wait_for_background_task(self, task_id: str, timeout: float | None = None) -> Any
async def start_background_task(self, func: Callable, *args, **kwargs) -> str
async def cancel_background_task(self, task_id: str) -> None
```

**Context Managers:**

```python
def element_scope(self, elements: list, auto_save: bool = True) -> Any
def progress_scope(self, total: int, message: str = "") -> Any
```

**Batch Processing:**

```python
async def batch_process(self, items: list, processor: Callable, batch_size: int = 100) -> list
```

---

### Async Decorators

**Module:** `revitpy.async_support.decorators`

```python
def async_revit_operation(
    timeout: float | None = None,
    retry_count: int = 0,
    retry_delay: float = 1.0,
    cancellation_token: CancellationToken | None = None,
    progress_reporter: ProgressReporter | None = None,
) -> Callable
```
Decorator for async Revit operations with timeout, retry, and progress support.

```python
def background_task(
    priority: TaskPriority = TaskPriority.NORMAL,
    timeout: float | None = None,
    retry_count: int = 0,
    retry_delay: float = 1.0,
    progress: bool = False,
    task_queue: TaskQueue | None = None,
) -> Callable
```
Decorator to run a function as a background task.

```python
def revit_transaction(
    name: str = "Transaction",
    auto_commit: bool = True,
    timeout: float | None = None,
) -> Callable
```
Decorator to wrap a function in a Revit transaction.

```python
def rate_limited(max_calls: int, time_window: float) -> Callable
```
Decorator to rate-limit function calls.

```python
def cache_result(ttl: float = 300.0, max_size: int = 100) -> Callable
```
Decorator to cache function results.

---

### Async Context Managers

**Module:** `revitpy.async_support.context_managers`

```python
async def async_transaction(
    provider,
    name: str = "Transaction",
    auto_commit: bool = True,
    timeout: float | None = None,
    retry_count: int = 0,
    retry_delay: float = 1.0,
    cancellation_token: CancellationToken | None = None,
) -> AsyncContextManager
```

```python
async def async_element_scope(
    elements: list,
    auto_save: bool = True,
    rollback_on_error: bool = True,
) -> AsyncContextManager
```

```python
async def async_progress_scope(
    total: int,
    message: str = "",
    console_output: bool = True,
) -> AsyncContextManager
```

```python
async def async_cancellation_scope(
    timeout: float | None = None,
    reason: str = "",
) -> AsyncContextManager
```

```python
async def async_batch_operations(
    batch_size: int = 100,
    delay_between_batches: float = 0.0,
) -> AsyncContextManager
```

```python
async def async_resource_scope(*resources) -> AsyncContextManager
```

---

### TaskQueue

Manages a queue of asynchronous tasks with priority ordering.

**Module:** `revitpy.async_support.task_queue`

```python
class TaskQueue:
    def __init__(self, max_concurrent: int = 4) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_running` | `bool` | Whether the queue is processing |
| `pending_count` | `int` | Number of pending tasks |
| `running_count` | `int` | Number of running tasks |
| `completed_count` | `int` | Number of completed tasks |
| `stats` | `dict` | Queue statistics |

**Methods:**

```python
async def enqueue(self, task: Task) -> str
def enqueue_sync(self, task: Task) -> str
async def submit(self, func: Callable, *args, **kwargs) -> str
async def wait_for_task(self, task_id: str, timeout: float | None = None) -> TaskResult
def get_task_status(self, task_id: str) -> TaskStatus
def get_task_result(self, task_id: str) -> TaskResult | None
async def start(self) -> None
async def stop(self, timeout: float | None = None) -> None
def clear_completed(self, older_than: float | None = None) -> int
```

---

### TaskStatus

**Module:** `revitpy.async_support.task_queue`

```python
class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

---

### TaskPriority

**Module:** `revitpy.async_support.task_queue`

```python
class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3
```

---

### TaskResult

**Module:** `revitpy.async_support.task_queue`

```python
@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Exception | None = None
    duration: float = 0.0
```

---

### ProgressReporter

Reports progress for long-running operations.

**Module:** `revitpy.async_support.progress`

```python
class ProgressReporter:
    def __init__(self, total: int = 100) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `current` | `int` | Current progress value |
| `total` | `int` | Total progress value |
| `percentage` | `float` | Progress as a percentage (0.0-100.0) |
| `state` | `ProgressState` | Current progress state |
| `last_report` | `ProgressReport \| None` | Most recent progress report |
| `elapsed_time` | `float` | Elapsed time in seconds |
| `estimated_remaining` | `float \| None` | Estimated remaining time |

**Methods:**

```python
def add_callback(self, callback: Callable) -> None
def remove_callback(self, callback: Callable) -> None
def set_total(self, total: int) -> None
def start(self) -> None
def increment(self, amount: int = 1) -> None
def set_progress(self, current: int) -> None
def report_progress(self, current: int, message: str = "") -> None
def report(self, message: str = "") -> None
def complete(self) -> None
def fail(self, error: str = "") -> None
def cancel(self) -> None
```

---

### ProgressState

**Module:** `revitpy.async_support.progress`

```python
class ProgressState(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

---

### ProgressReport

**Module:** `revitpy.async_support.progress`

```python
@dataclass
class ProgressReport:
    current: int
    total: int
    percentage: float
    message: str
    state: ProgressState
    elapsed_time: float
    estimated_remaining: float | None
```

---

### CancellationToken

Token for cooperative cancellation of async operations.

**Module:** `revitpy.async_support.cancellation`

```python
class CancellationToken:
    # Created via CancellationTokenSource
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_cancelled` | `bool` | Whether cancellation has been requested |
| `cancelled_at` | `float \| None` | Timestamp when cancelled |
| `reason` | `str` | Reason for cancellation |

**Methods:**

```python
def throw_if_cancellation_requested(self) -> None
```
Raises `OperationCancelledError` if cancellation has been requested.

```python
def register_callback(self, callback: Callable) -> None
```
Register a callback to be called when cancellation is requested.

---

### CancellationTokenSource

Creates and controls `CancellationToken` instances.

**Module:** `revitpy.async_support.cancellation`

```python
class CancellationTokenSource:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `token` | `CancellationToken` | The cancellation token |
| `is_cancelled` | `bool` | Whether cancellation has been requested |

**Methods:**

```python
def cancel(self, reason: str = "") -> None
```
Request cancellation.

```python
def cancel_after(self, timeout: float, reason: str = "") -> None
```
Request cancellation after a timeout.

```python
def dispose(self) -> None
```
Dispose of resources.

---

### OperationCancelledError

**Module:** `revitpy.async_support.cancellation`

```python
class OperationCancelledError(Exception):
    pass
```

---

### Utility Functions

**Module:** `revitpy.async_support.cancellation`

```python
def combine_tokens(*tokens: CancellationToken) -> CancellationToken
```
Combine multiple tokens into one that cancels when any source cancels.

```python
def with_cancellation(token: CancellationToken) -> Callable
```
Decorator to add cancellation support to an async function.

---

## Testing (`revitpy.testing`)

### MockRevit

Mock Revit environment for testing without an actual Revit installation. Connect a `RevitAPI` to it with `api.connect(mock.application)`; `MockDocument.StartTransaction` provides snapshot/rollback semantics, so transactions behave like a live model. Note that `MockParameter` values are converted with `AsString()`, so numeric parameters read back through `Element.get_parameter_value` as strings.

**Module:** `revitpy.testing.mock_revit`

```python
class MockRevit:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `application` | `MockApplication` | The mock application instance |
| `active_document` | `MockDocument \| None` | The currently active document |

**Methods:**

```python
def create_document(self, title: str = "TestDocument.rvt") -> MockDocument
```
Create a test document.

```python
def create_element(
    self,
    name: str = "TestElement",
    category: str = "Generic",
    element_type: str = "Element",
    parameters: dict[str, Any] | None = None,
) -> MockElement
```
Create a test element. If an active document exists, the element is added to it.

```python
def create_elements(
    self,
    count: int,
    name_prefix: str = "Element",
    category: str = "Generic",
    element_type: str = "Element",
) -> list[MockElement]
```
Create multiple test elements with sequential names.

```python
def load_fixture(self, fixture_name: str, fixture_data: Any) -> None
def get_fixture(self, fixture_name: str) -> Any
```
Load and retrieve test fixtures.

```python
def save_state(self, file_path: str) -> None
def load_state(self, file_path: str) -> None
```
Save/load mock Revit state to/from JSON files.

```python
def reset(self) -> None
```
Reset mock environment to initial state.

```python
def add_event_handler(self, handler: Callable) -> None
def trigger_event(self, event_type: str, event_data: Any) -> None
```
Add and trigger event handlers for testing.

```python
def get_statistics(self) -> dict[str, Any]
```
Returns dict with keys: `documents`, `total_elements`, `fixtures`, `event_handlers`, `has_active_document`.

---

### MockDocument

**Module:** `revitpy.testing.mock_revit`

```python
class MockDocument:
    def __init__(
        self,
        title: str = "MockDocument.rvt",
        path: str = "",
        is_family_document: bool = False,
    ) -> None
```

**Attributes:** `Title`, `PathName`, `IsFamilyDocument`

**Methods:**

```python
def GetElements(self, filter_criteria=None) -> list[MockElement]
def GetElement(self, element_id: int | MockElementId) -> MockElement | None
def AddElement(self, element: MockElement) -> MockElement
def CreateElement(self, name: str = "NewElement", category: str = "Generic", element_type: str = "Element") -> MockElement
def Delete(self, element_ids: list[int | MockElementId]) -> None
def Save(self) -> bool
def Close(self, save_changes: bool = True) -> bool
def StartTransaction(self, name: str = "Transaction") -> MockTransaction
def IsModified(self) -> bool
def GetElementCount(self) -> int
def GetElementsByCategory(self, category: str) -> list[MockElement]
def GetElementsByType(self, element_type: str) -> list[MockElement]
def to_dict(self) -> dict[str, Any]
@classmethod
def from_dict(cls, data: dict[str, Any]) -> "MockDocument"
```

---

### MockElement

**Module:** `revitpy.testing.mock_revit`

```python
class MockElement:
    def __init__(
        self,
        element_id: int = None,
        name: str = "MockElement",
        category: str = "Generic",
        element_type: str = "Element",
    ) -> None
```

**Attributes:** `Id` (MockElementId), `Name`, `Category`, `ElementType`

**Methods:**

```python
def GetParameterValue(self, parameter_name: str) -> Any
def SetParameterValue(self, parameter_name: str, value: Any) -> None
def GetParameter(self, parameter_name: str) -> MockParameter | None
def SetParameter(self, parameter_name: str, parameter: MockParameter) -> None
def GetAllParameters(self) -> dict[str, MockParameter]
def HasParameter(self, parameter_name: str) -> bool
def GetProperty(self, property_name: str) -> Any
def SetProperty(self, property_name: str, value: Any) -> None
def to_dict(self) -> dict[str, Any]
@classmethod
def from_dict(cls, data: dict[str, Any]) -> "MockElement"
```

---

### MockApplication

**Module:** `revitpy.testing.mock_revit`

```python
class MockApplication:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `ActiveDocument` | `MockDocument \| None` | The active document |

**Methods:**

```python
def OpenDocumentFile(self, file_path: str) -> MockDocument
def CreateDocument(self, template_path: str | None = None) -> MockDocument
def GetOpenDocuments(self) -> list[MockDocument]
def CloseDocument(self, document: MockDocument) -> bool
```

---

### MockTransaction

**Module:** `revitpy.testing.mock_revit`

```python
class MockTransaction:
    def __init__(self, name: str = "MockTransaction") -> None
```

**Attributes:** `name`, `is_started`, `is_committed`, `is_rolled_back`

**Methods:**

```python
def Start(self) -> bool
def Commit(self) -> bool
def RollBack(self) -> bool
```

---

### MockParameter

**Module:** `revitpy.testing.mock_revit`

```python
@dataclass
class MockParameter:
    name: str
    value: Any = None
    type_name: str = "String"
    storage_type: str = "String"
    is_read_only: bool = False
```

**Methods:**

```python
def AsString(self) -> str
def AsDouble(self) -> float
def AsInteger(self) -> int
def AsValueString(self) -> str
```

---

### MockElementId

**Module:** `revitpy.testing.mock_revit`

```python
class MockElementId:
    def __init__(self, value: int) -> None
```

**Attributes:** `IntegerValue`

---

## Performance (`revitpy.performance`)

**Module:** `revitpy.performance`

The performance module exports exactly these classes (`revitpy.performance.__all__`):

| Class | Source module | Description |
|-------|---------------|-------------|
| `PerformanceOptimizer` | `optimizer` | Optimization engine with caching and object pooling |
| `OptimizationConfig` | `optimizer` | Configuration for the optimizer |
| `AdaptiveCache` | `optimizer` | Adaptive cache used by the optimizer |
| `ObjectPool` | `optimizer` | Reusable object pool |
| `BenchmarkSuite` | `benchmarks` | Suite of performance benchmarks |
| `BenchmarkRunner` | `benchmarks` | Runs benchmark suites |
| `BenchmarkConfiguration` | `benchmarks` | Benchmark settings |
| `MemoryManager` | `memory` | Memory management utilities |
| `MemoryLeakDetector` | `memory` | Detects memory leaks |
| `MetricsCollector` | `monitoring` | Collects performance metrics |
| `PerformanceMonitor` | `monitoring` | Real-time performance monitoring |
| `AlertingSystem` | `monitoring` | Performance alerting |

Module-level helpers: `get_global_optimizer()`, `initialize_performance_framework()`, `cleanup_performance_framework()`.

> `revitpy.performance` imports `psutil` unconditionally, but `psutil` is only included in the `dev` extra. Install it (`pip install psutil`) before importing this package. `numpy` is optional.

---

## Configuration (`revitpy.config`)

**Exports:** `Config`, `ConfigManager`

These classes are exported from `revitpy.__init__` and handle framework configuration. See the [Developer Setup Guide]({{ '/developer/setup/' | relative_url }}) for configuration details.

---

## Quantity Extraction (`revitpy.extract`)

### QuantityExtractor

Extract measured quantities (area, volume, length, count, weight) from Revit elements using duck-typed attribute access.

**Module:** `revitpy.extract.quantities`

```python
class QuantityExtractor:
    def __init__(self, context: Any | None = None) -> None
```

**Methods:**

```python
def extract(self, elements: list[Any], quantity_types: list[QuantityType] | None = None) -> list[QuantityItem]
```
Extract quantities from elements. Defaults to all quantity types when `quantity_types` is `None`.

```python
def extract_grouped(self, elements: list[Any], group_by: AggregationLevel = AggregationLevel.CATEGORY, quantity_types: list[QuantityType] | None = None) -> dict[str, list[QuantityItem]]
```
Extract and group quantities by aggregation level (category, level, system, element, or building).

```python
def summarize(self, items: list[QuantityItem]) -> dict[str, float]
```
Summarize quantities by type, summing values. Returns a dict mapping quantity type names to summed values.

```python
async def extract_async(self, elements: list[Any], quantity_types: list[QuantityType] | None = None, progress: Callable[[int, int], None] | None = None) -> list[QuantityItem]
```
Async version of extract with optional progress reporting callback `(current, total)`.

---

### MaterialTakeoff

Extract and process material quantities from Revit elements, with aggregation and industry-standard classification.

**Module:** `revitpy.extract.materials`

```python
class MaterialTakeoff:
    def __init__(self, context: Any | None = None) -> None
```

**Methods:**

```python
def extract(self, elements: list[Any]) -> list[MaterialQuantity]
```
Extract material data from elements. Elements are duck-typed with optional `material_name`, `material_volume`, `material_area`, `material_mass`, and `category` attributes.

```python
def aggregate(self, materials: list[MaterialQuantity]) -> list[MaterialQuantity]
```
Aggregate material quantities by material name, summing volume, area, and mass.

```python
def classify(self, materials: list[MaterialQuantity], system: str = "UniFormat") -> list[MaterialQuantity]
```
Classify materials against a standard system (`"UniFormat"` or `"MasterFormat"`). Returns new list with `classification_code` and `classification_system` set.

---

### CostEstimator

Map extracted quantities to cost data, producing itemized cost breakdowns and aggregated summaries.

**Module:** `revitpy.extract.costs`

```python
class CostEstimator:
    def __init__(self, cost_database: dict[str, float] | Path | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `database` | `dict[str, float]` | Copy of the current cost database |

**Methods:**

```python
def load_database(self, path: Path) -> None
```
Load cost data from a file. Supports CSV, JSON, and YAML formats (auto-detected from extension).

```python
def estimate(self, quantities: list[QuantityItem], aggregation: AggregationLevel = AggregationLevel.CATEGORY) -> CostSummary
```
Map quantities to costs and produce a summary with itemized costs and aggregated totals by category, system, and level.

---

### DataExporter

Export tabular data to CSV, JSON, Excel, Parquet, or plain dicts.

**Module:** `revitpy.extract.exporters`

```python
class DataExporter:
    # No constructor arguments required
```

**Methods:**

```python
def export(self, data: list[dict[str, Any]], config: ExportConfig) -> Path | list[dict[str, Any]]
```
Export data according to the given configuration. Returns a `Path` for file formats, or `list[dict]` for `DICT` format.

```python
def to_csv(self, data: list[dict[str, Any]], path: Path | None, *, include_headers: bool = True, decimal_places: int = 2) -> Path
```
Export data to CSV.

```python
def to_json(self, data: list[dict[str, Any]], path: Path | None, *, decimal_places: int = 2) -> Path
```
Export data to JSON.

```python
def to_excel(self, data: list[dict[str, Any]], path: Path | None, *, sheet_name: str = "Sheet1", include_headers: bool = True) -> Path
```
Export data to Excel (xlsx). Requires the optional `openpyxl` dependency.

```python
def to_parquet(self, data: list[dict[str, Any]], path: Path | None) -> Path
```
Export data to Parquet. Requires the optional `pyarrow` dependency.

```python
def to_dicts(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]
```
Return data as a list of dicts (shallow copy passthrough).

---

## IFC Interoperability (`revitpy.ifc`)

Requires the `ifc` extra (`pip install revitpy[ifc]`: `ifcopenshell>=0.8`, `defusedxml`, `ifctester`). `revitpy.ifc.ifc_available()` returns `True` when ifcopenshell is importable.

### IfcElementMapper

Bidirectional mapping between RevitPy element types and IFC entity types, with custom property map support and type registration.

**Module:** `revitpy.ifc.mapper`

```python
class IfcElementMapper:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `registered_types` | `list[str]` | All registered RevitPy type names |
| `registered_ifc_types` | `list[str]` | All registered IFC entity type names |

**Methods:**

```python
def register_mapping(self, revitpy_type: str, ifc_entity_type: str, property_map: dict[str, str] | None = None, *, bidirectional: bool = True) -> None
```
Register a custom mapping between a RevitPy type and IFC entity type.

```python
def get_mapping(self, revitpy_type: str) -> IfcMapping | None
```
Get the IFC mapping for a RevitPy type.

```python
def get_ifc_type(self, revitpy_type: str) -> str | None
```
Get the IFC entity type name for a RevitPy type.

```python
def get_revitpy_type(self, ifc_entity_type: str) -> str | None
```
Get the RevitPy type name for an IFC entity type.

```python
def to_ifc(self, element: Any, ifc_file: Any, config: IfcExportConfig | None = None) -> Any
```
Convert a RevitPy element to an IFC entity (mapping resolved by class name, then `category`). Requires `ifcopenshell`. Raises `IfcExportError` when no mapping exists.

```python
def from_ifc(self, ifc_entity: Any, target_type: str | None = None) -> dict[str, Any]
```
Convert an IFC entity to a dict representation. Consults the reverse registry when `target_type` is not provided.

---

### IfcExporter

Export RevitPy elements to IFC files using ifcopenshell.

**Module:** `revitpy.ifc.exporter`

```python
class IfcExporter:
    def __init__(self, mapper: IfcElementMapper | None = None, config: IfcExportConfig | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `mapper` | `IfcElementMapper` | The element mapper used by this exporter |
| `config` | `IfcExportConfig` | The export configuration |

**Methods:**

```python
def export(self, elements: list[Any], output_path: str | Path, version: IfcVersion = IfcVersion.IFC4) -> Path
```
Export elements to an IFC file. Creates the spatial hierarchy (IfcProject, IfcSite, IfcBuilding, and an IfcBuildingStorey per element `level`) and converts each element via the mapper. The mapping is looked up by the element's class name first (e.g. `WallElement`), then by its `category` attribute; unmapped elements are skipped with a warning. Requires `ifcopenshell>=0.8` (`pip install revitpy[ifc]`).

```python
async def export_async(self, elements: list[Any], output_path: str | Path, version: IfcVersion = IfcVersion.IFC4, progress: Callable[[int, int], None] | None = None) -> Path
```
Export elements to an IFC file asynchronously with optional progress reporting.

---

### IfcImporter

Import elements from IFC files and convert them to RevitPy element dictionaries.

**Module:** `revitpy.ifc.importer`

```python
class IfcImporter:
    def __init__(self, mapper: IfcElementMapper | None = None, config: IfcImportConfig | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `mapper` | `IfcElementMapper` | The element mapper used by this importer |
| `config` | `IfcImportConfig` | The import configuration |

**Methods:**

```python
def import_file(self, path: str | Path) -> list[dict[str, Any]]
```
Import elements from an IFC file. Parses the file with ifcopenshell and converts entities via the mapper.

```python
async def import_file_async(self, path: str | Path) -> list[dict[str, Any]]
```
Import elements from an IFC file asynchronously.

---

### IdsValidator

Validate elements or IFC files against IDS (Information Delivery Specification) requirements. Three levels of support:

1. `validate()` / JSON rule files -- a RevitPy rule set inspired by IDS, checked against in-memory elements.
2. `load_ids_xml()` (used by `validate_from_file()` for `.ids` / `.xml`) -- reads buildingSMART IDS 1.0 XML and maps a subset (entity applicability; attribute and property facets with `simpleValue` / `xs:enumeration`; cardinality) onto that rule set. Other facets and restrictions are ignored with a warning.
3. `validate_ifc_file()` -- full IDS 1.0 validation of an IFC file via `ifctester`.

**Module:** `revitpy.ifc.validator`

```python
class IdsValidator:
    def __init__(self, mapper: IfcElementMapper | None = None) -> None
```

**Methods:**

```python
def validate(self, elements: list[Any], requirements: list[IdsRequirement]) -> list[IdsValidationResult]
```
Validate elements against a list of requirements. A requirement applies when its `entity_type` is `None`, matches the element's RevitPy type/category, or is an IFC entity name the element's type maps to.

```python
def validate_from_file(self, elements: list[Any], ids_path: str | Path) -> list[IdsValidationResult]
```
Validate elements against requirements from a file: `.ids` / `.xml` are read as IDS 1.0 XML, anything else as a RevitPy JSON rule list. Raises `IdsValidationError` if the file is missing or cannot be parsed.

```python
def load_ids_xml(self, ids_path: str | Path) -> list[IdsRequirement]
```
Parse a buildingSMART IDS 1.0 XML file (with `defusedxml` when installed) into requirements.

```python
def validate_ifc_file(self, ifc_path: str | Path, ids_path: str | Path) -> list[IdsValidationResult]
```
Full IDS 1.0 validation of an IFC file using `ifctester` (part of the `ifc` extra). Raises `ImportError` if ifcopenshell/ifctester are missing and `IdsValidationError` if a file is missing or validation fails.

---

### BcfManager

Create, read, and write BCF (BIM Collaboration Format) issues as buildingSMART BCF-XML 2.1 archives.

**Module:** `revitpy.ifc.bcf`

```python
class BcfManager:
    BCF_VERSION = "2.1"

    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `issues` | `list[BcfIssue]` | All managed issues (a copy) |

**Methods:**

```python
def create_issue(self, title: str, description: str = "", *, author: str = "", status: str = "Open", assigned_to: str = "", element_ids: list[str] | None = None) -> BcfIssue
```
Create a new BCF issue and add it to the managed list.

```python
def read_bcf(self, path: str | Path) -> list[BcfIssue]
```
Read BCF issues. `.bcf` / `.bcfzip` / `.zip` archives may be BCF 2.1, BCF 3.0 or legacy RevitPy `markup.xml` archives; `.json` files are accepted as a simplified alternative. XML is parsed with `defusedxml` when installed. Raises `BcfError`.

```python
def write_bcf(self, issues: list[BcfIssue] | None = None, path: str | Path = "issues.bcf") -> Path
```
Write a BCF-XML 2.1 archive: `bcf.version`, and per topic `markup.bcf`, `viewpoint.bcfv` (when the issue has elements or a snapshot) and `snapshot.png`. Element ids are written as viewpoint components: 22-character IFC GlobalIds as `IfcGuid`, other ids (e.g. Revit element ids) as `AuthoringToolId` with `OriginatingSystem="RevitPy"`. No camera is written. Defaults to all managed issues; raises `BcfError` if there are none.

---

### IfcDiff

Compare two IFC model states and produce a structured diff identifying added, modified, and removed entities.

**Module:** `revitpy.ifc.diff`

```python
class IfcDiff:
    def __init__(self) -> None
```

**Methods:**

```python
def compare(self, old_elements: list[Any], new_elements: list[Any]) -> IfcDiffResult
```
Compare two element lists and return differences. Elements are matched by `id` or `global_id`.

```python
def compare_files(self, old_path: str | Path, new_path: str | Path) -> IfcDiffResult
```
Compare two IFC files and return differences. Both files are imported and compared at the property level.

---

## AI & MCP Server (`revitpy.ai`)

### RevitTools

Registry of tools that can be invoked through the MCP server. Manages tool definitions, validates arguments, dispatches execution, and converts tools to MCP-compatible JSON Schema format.

**Module:** `revitpy.ai.tools`

```python
class RevitTools:
    def __init__(self, context: RevitContext | Any = None) -> None
```

`context` is any object shaped like `revitpy.ai.tools.RevitContext` (an `active_document`, `get_element_by_id(id)`, and `transaction(name)` returning a commit-on-success / rollback-on-error context manager); a connected `revitpy.api.RevitAPI` satisfies it. Built-in tools: `query_elements`, `get_element`, `modify_parameter` (category `MODIFY`), `get_quantities`, `validate_model`, `export_data`. Without a context, built-in tools raise `ToolExecutionError("Not connected to a Revit document")` rather than returning placeholder data.

**Methods:**

```python
def register_tool(self, definition: ToolDefinition, handler: Callable) -> None
```
Register a tool with its handler callable.

```python
def get_tool(self, name: str) -> ToolDefinition | None
```
Return the definition of a registered tool, or `None`.

```python
def list_tools(self) -> list[ToolDefinition]
```
Return all registered tool definitions.

```python
def execute_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult
```
Execute a tool by name. Validates required parameters, invokes the handler, and wraps the outcome in a `ToolResult`.

```python
def to_mcp_tool_list(self) -> list[dict[str, Any]]
```
Convert all tools to MCP-format JSON Schema definitions.

---

### SafetyGuard

Validates tool calls against a safety policy (`SafetyMode.READ_ONLY`, `CAUTIOUS` (default) or `FULL_ACCESS`) and provides an undo stack.

**Module:** `revitpy.ai.safety`

```python
ConfirmationCallback = Callable[[ToolDefinition, dict[str, Any]], bool | Awaitable[bool]]

class SafetyGuard:
    def __init__(self, config: SafetyConfig | None = None, *, confirmation_callback: ConfirmationCallback | None = None) -> None
```

Policy:

- Tools listed in `SafetyConfig.blocked_tools` are always denied.
- `READ_ONLY` denies `MODIFY` tools.
- `CAUTIOUS` (the default) requires confirmation for categories in `SafetyConfig.require_confirmation_for` (default `[ToolCategory.MODIFY]`). The `confirmation_callback` must return literally `True` to approve; any other value, an exception, or **no callback at all** denies the call.
- `FULL_ACCESS` allows everything not blocked.

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `config` | `SafetyConfig` | The active safety configuration |
| `confirmation_callback` | `ConfirmationCallback \| None` | Settable confirmation callback |

**Methods:**

```python
def validate_tool_call(self, tool: ToolDefinition, arguments: dict[str, Any]) -> bool
async def avalidate_tool_call(self, tool: ToolDefinition, arguments: dict[str, Any]) -> bool
```
Check whether a tool call is allowed. Raise `SafetyViolationError` when blocked or not confirmed. The sync variant denies when the callback is async; use `avalidate_tool_call()` (as `McpServer` does) for async callbacks.

```python
def preview_changes(self, tool: ToolDefinition, arguments: dict[str, Any]) -> dict[str, Any]
```
Return a dry-run preview of the changes a tool call would make.

```python
def push_undo(self, operation: dict[str, Any]) -> None
```
Push an operation onto the undo stack (bounded by `SafetyConfig.max_undo_stack`).

```python
def undo_last(self) -> dict[str, Any] | None
```
Pop and return the most recent undo entry, or `None`.

```python
def get_undo_stack(self) -> list[dict[str, Any]]
```
Return a copy of the current undo stack.

### SafetyConfig

**Module:** `revitpy.ai.types`

```python
@dataclass
class SafetyConfig:
    mode: SafetyMode = SafetyMode.CAUTIOUS
    max_undo_stack: int = 50
    require_confirmation_for: list[ToolCategory] = field(default_factory=lambda: [ToolCategory.MODIFY])
    blocked_tools: list[str] = field(default_factory=list)
```

---

### PromptLibrary

Manages and renders Jinja2 prompt templates for LLM interactions within the MCP server. Built-in templates are registered at construction time.

**Module:** `revitpy.ai.prompts`

```python
class PromptLibrary:
    def __init__(self) -> None
```

**Methods:**

```python
def render(self, template_name: str, /, **kwargs: Any) -> str
```
Render a template by name. Raises `PromptError` if the template does not exist or rendering fails.

```python
def register_template(self, name: str, template: str) -> None
```
Register or overwrite a Jinja2 template.

```python
def get_template(self, name: str) -> str | None
```
Return the raw source of a template, or `None`.

```python
def list_templates(self) -> list[str]
```
Return sorted list of all template names.

```python
def to_mcp_prompts_list(self) -> list[dict[str, Any]]
```
Convert templates to MCP-format prompt definitions.

---

### McpServer

Asynchronous WebSocket server implementing a subset of the Model Context Protocol, exposing tools, prompts, and safety controls.

**Module:** `revitpy.ai.server`

```python
class McpServer:
    def __init__(self, tools: RevitTools, *, config: McpServerConfig | None = None, safety_guard: SafetyGuard | None = None, prompt_library: PromptLibrary | None = None) -> None
```

Security: binds to `localhost` by default. When `config.auth_token` is set, the WebSocket handshake must carry `Authorization: Bearer <token>` (HTTP 401 otherwise); binding to a non-loopback host without a token logs a warning. Handshakes with an `Origin` header not in `config.allowed_origins` are rejected with HTTP 403. Tool calls are checked with `SafetyGuard.avalidate_tool_call()`; tool failures are returned as `tools/call` results with `isError: true`. Works with `websockets` 11/12 (legacy server API) and >= 13 (asyncio API).

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `config` | `McpServerConfig` | The active server configuration |
| `connections` | `set[Any]` | Set of active WebSocket connections |
| `port` | `int \| None` | Bound port while running (useful with `port=0`) |

**Methods:**

```python
async def start(self) -> None
```
Start the WebSocket server on the configured host and port.

```python
async def stop(self, timeout: float = 5.0) -> None
```
Gracefully stop the server. Waits up to `timeout` seconds for connections to close.

Supports the async context manager protocol: `async with McpServer(...) as server:` starts the server on entry and stops it on exit (do not call `start()` again inside the block).

To serve a live Revit model, use the host add-in's **MCP Server** button or `revitpy.revit.host.start_mcp_server()`; `revitpy mcp-serve` runs without a Revit connection.

### McpServerConfig

**Module:** `revitpy.ai.types`

```python
@dataclass
class McpServerConfig:
    host: str = "localhost"
    port: int = 8765
    name: str = "revitpy-mcp"
    version: str = "1.0.0"
    auth_token: str | None = None          # excluded from repr
    allowed_origins: list[str] = field(default_factory=list)
```

---

## Sustainability (`revitpy.sustainability`)

### CarbonCalculator

Calculate embodied carbon for building materials using EPD database lookups. Supports mass-based and volume-based calculation methods.

**Module:** `revitpy.sustainability.carbon`

```python
class CarbonCalculator:
    def __init__(self, epd_database: EpdDatabase | None = None) -> None
```

**Methods:**

```python
def calculate(self, materials: list[MaterialData], lifecycle_stages: list[LifecycleStage] | None = None) -> list[CarbonResult]
```
Calculate embodied carbon for a list of materials. Defaults to A1-A3 lifecycle stages. Looks up EPD records and computes carbon as `mass * gwp_per_kg` or `volume * gwp_per_m3`.

```python
def summarize(self, results: list[CarbonResult]) -> BuildingCarbonSummary
```
Aggregate carbon results into a building-level summary with totals by material, system, level, and lifecycle stage.

```python
def benchmark(self, summary: BuildingCarbonSummary, building_area_m2: float, building_type: str = "default") -> CarbonBenchmark
```
Benchmark building carbon against RIBA 2030 Climate Challenge targets. Returns rating (Excellent, Good, Acceptable, Below Average, Poor).

```python
async def calculate_async(self, materials: list[MaterialData], lifecycle_stages: list[LifecycleStage] | None = None, progress: Callable[[int, int], None] | None = None) -> list[CarbonResult]
```
Asynchronously calculate embodied carbon with optional progress callback `(completed, total)`.

---

### EpdDatabase

Environmental Product Declaration database with local cache, generic fallback values, and optional EC3 API integration. The built-in factors are screening-level generic cradle-to-gate (A1-A3) averages from the ICE v2.0 summary tables (`ICE_V2_SOURCE`), each carrying its source, data year and any density assumption; they are not product EPDs.

**Module:** `revitpy.sustainability.epd`

```python
class EpdDatabase:
    def __init__(self, *, api_token: str | None = None, cache_path: Path | str | None = None, overrides: dict[str, EpdRecord] | None = None) -> None
```

**Methods:**

```python
def register(self, key: str, epd: EpdRecord) -> None
```
Add or replace a record (e.g. a project-specific product EPD) under a case-insensitive key. `overrides` in the constructor calls this for each entry.

```python
def lookup(self, material_name: str, category: str | None = None) -> EpdRecord | None
```
Look up an EPD record. Matching is deterministic and scored (`revitpy.sustainability.matching`): specific records before generic fallbacks; exact name, then whole-token, then substring; finally a category-level generic record when `category` is given. Returns an annotated copy (`match_type`, `match_confidence`, `matched_key`) or `None`. Generic-fallback matches are capped at `GENERIC_FALLBACK_MAX_CONFIDENCE` (0.3); low-confidence or ambiguous matches are logged as warnings.

```python
async def lookup_async(self, material_name: str, category: str | None = None) -> EpdRecord | None
```
Asynchronously look up an EPD record, querying the EC3 API when a token is configured; falls back to `lookup()` otherwise.

```python
async def search_async(self, query: str, limit: int = 10) -> list[EpdRecord]
```
Search for EPD records matching a query. Searches the local cache and, with a token, the EC3 API.

```python
def get_generic_epd(self, material_category: str) -> EpdRecord | None
```
Get the representative generic EPD record for a material category (e.g. `"Concrete"`, `"Metals"` -> steel).

```python
def load_cache(self, path: Path | str) -> None
def save_cache(self, path: Path | str) -> None
```
Load / save cached EPD records as JSON.

`EpdRecord` fields: `material_name`, `category`, `gwp_per_kg`, `gwp_per_m3`, `source`, `lifecycle_stages`, `valid_until`, `manufacturer`, `source_year`, `assumed_density_kg_m3`, `notes`, `is_generic_fallback`, `match_type`, `match_confidence`, `matched_key`.

---

### ComplianceChecker

Screen building data against NYC LL97, Boston BERDO, EU EPBD national/local limits and ASHRAE 90.1-2019 prescriptive envelope values. Results are **screening-level estimates, not compliance determinations**: every built-in limit records its source, every limit can be overridden, and no check silently falls back to a default building category. Missing or unknown inputs raise `ComplianceError`.

**Module:** `revitpy.sustainability.compliance`

```python
class ComplianceChecker:
    def __init__(self) -> None
```

**Methods:**

```python
def check(self, standard: ComplianceStandard, building_data: dict[str, Any]) -> ComplianceResult
```
Dispatch to the standard-specific check. Limit overrides may be passed in `building_data` as `"ll97_limits"`, `"berdo_limits"`, `"epbd_limits"` (plus `"epbd_limit_source"`), and for ASHRAE 90.1 as `"overrides"`. For `ASHRAE_90_1`, `building_data` must contain `climate_zone`, `wall_r_value`, `roof_r_value`, `window_u_value` and `glazing_ratio` (optional `air_tightness`).

```python
def check_ll97(self, building_data: dict[str, Any], *, year: int | None = None, limits: dict[str, float] | None = None) -> ComplianceResult
```
NYC Local Law 97. Keys: `area_sqft` (required), `annual_emissions_tco2e`, and **either** `property_type` (ENERGY STAR Portfolio Manager type such as `"Office"`) **or** `occupancy_type` (LL97 occupancy group such as `"B"`, `"R-2"`, `"B-healthcare"`, or an alias like `"office"`); optional `compliance_year`. Occupancy-group limits are only permitted for 2024-2025 reporting; for later years a warning recommends `property_type`. `year` (default `compliance_year` or the current year) selects the 2024-2029 or 2030-2034 period; years outside those are clamped with a warning note. `limits` overrides are keyed by the resolved group/property type or `"*"`.

```python
def check_berdo(self, building_data: dict[str, Any], *, limits: dict[str, float] | None = None) -> ComplianceResult
```
Boston BERDO. Keys: `area_sqft`, `annual_emissions_kgco2e`, `building_type` (all required). The built-in values are unverified placeholders; pass `limits` (kgCO2e/sf/yr keyed by building type or `"*"`) from the current BERDO 2.0 standards for a meaningful result.

```python
def check_epbd(self, building_data: dict[str, Any], *, limits: dict[str, float] | None = None, limit_source: str | None = None) -> ComplianceResult
```
EU EPBD. The directive sets no pan-EU numeric cap, so there are **no built-in limits**: supply `limits` (primary energy kWh/m2/yr keyed by building type or `"*"`) and ideally a `limit_source` citation, otherwise `ComplianceError` is raised. Keys: `area_m2`, `primary_energy_kwh`, `building_type` (all required).

```python
def check_ashrae(self, envelope_data: EnergyEnvelopeData, climate_zone: str | int, *, overrides: dict[str, float] | None = None) -> ComplianceResult
```
ASHRAE 90.1-2019 prescriptive envelope screening (nonresidential). `climate_zone` is **required** (`"4A"`, `"5B"`, `7`, ...; parsed by `parse_climate_zone()`). Built-in limits cover roof R (insulation above deck), fixed-fenestration U and a 40% glazing ratio; walls are evaluated only when `overrides["wall_r_min"]` is given. Allowed override keys: `wall_r_min`, `roof_r_min`, `window_u_max`, `glazing_ratio_max`.

```python
def get_recommendations(self, result: ComplianceResult) -> list[str]
```
Get improvement recommendations based on a compliance result.

```python
def parse_climate_zone(zone: str | int) -> tuple[int, str]   # module-level
```

`ComplianceResult` fields: `standard`, `passed`, `threshold`, `actual_value`, `unit`, `recommendations`, `details`, `source`, `notes`.

```python
from revitpy.sustainability import ComplianceChecker, EnergyEnvelopeData

checker = ComplianceChecker()
ll97 = checker.check_ll97(
    {"area_sqft": 50_000, "annual_emissions_tco2e": 300, "property_type": "Office"},
    year=2030,
)
ashrae = checker.check_ashrae(
    EnergyEnvelopeData(wall_r_value=13, roof_r_value=30, window_u_value=0.38, glazing_ratio=0.35),
    climate_zone="4A",
)
```

---

### SustainabilityReporter

Generate sustainability assessment reports in JSON, CSV, and HTML formats, and produce certification documentation for LEED, BREEAM, DGNB, and Green Star.

**Module:** `revitpy.sustainability.reports`

```python
class SustainabilityReporter:
    def __init__(self) -> None
```

**Methods:**

```python
def generate(self, summary: BuildingCarbonSummary, format: ReportFormat = ReportFormat.JSON, output_path: str | Path | None = None) -> str | Path
```
Generate a sustainability report. Returns content as a string when `output_path` is `None`, or the output `Path` when written to disk.

```python
def to_json(self, summary: BuildingCarbonSummary, path: str | Path | None = None) -> str | Path
```
Generate a JSON sustainability report.

```python
def to_csv(self, summary: BuildingCarbonSummary, path: str | Path | None = None) -> str | Path
```
Generate a CSV sustainability report with material rows, carbon values, and percentages.

```python
def to_html(self, summary: BuildingCarbonSummary, path: str | Path | None = None) -> str | Path
```
Generate an HTML sustainability report. Uses Jinja2 if available, otherwise falls back to string formatting.

```python
def generate_certification_docs(self, summary: BuildingCarbonSummary, system: CertificationSystem) -> dict
```
Generate certification documentation helpers for a given rating system (LEED, BREEAM, DGNB, Green Star). Returns a dict with certification-specific credit sections.

---

## Speckle Interop (`revitpy.interop`)

### SpeckleTypeMapper

Bidirectional mapping between RevitPy element types and Speckle object types, with custom property maps and type registration.

**Module:** `revitpy.interop.mapper`

```python
class SpeckleTypeMapper:
    def __init__(self) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `registered_types` | `list[str]` | All registered RevitPy type names |
| `registered_speckle_types` | `list[str]` | All registered Speckle type identifiers |

**Methods:**

```python
def register_mapping(self, revitpy_type: str, speckle_type: str, property_map: dict[str, str] | None = None) -> None
```
Register a custom mapping between a RevitPy type and Speckle type.

```python
def get_mapping(self, revitpy_type: str) -> TypeMapping | None
```
Get the Speckle mapping for a RevitPy type.

```python
def to_speckle(self, element: Any) -> dict[str, Any]
```
Convert a RevitPy element to a Speckle-compatible dict. Raises `TypeMappingError` if the element type is not mapped.

```python
def from_speckle(self, speckle_obj: dict[str, Any], target_type: str | None = None) -> dict[str, Any]
```
Convert a Speckle object dict back to a RevitPy-compatible dict. Consults the reverse registry when `target_type` is not provided.

```python
def get_unmapped_status(self, revitpy_type: str) -> TypeMapping
```
Return a `TypeMapping` with `MappingStatus.UNMAPPED` for an unregistered type.

---

### SpeckleClient

Async client for a Speckle server, backed by `specklepy>=3` (`pip install revitpy[interop]`). The underlying `specklepy` client is created lazily and authenticated with `config.token`; blocking SDK calls run in a worker thread. Uses Speckle's current **project / model / version** terminology.

**Module:** `revitpy.interop.client`

```python
class SpeckleClient:
    def __init__(self, config: SpeckleConfig | None = None) -> None
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_connected` | `bool` | Whether the client has successfully connected |
| `config` | `SpeckleConfig` | The current server configuration |
| `sdk_client` | `Any \| None` | The underlying `specklepy` client, once created |

**Methods:**

```python
async def connect(self) -> None
```
Validate the connection (server info query). Raises `ImportError` without specklepy and `SpeckleConnectionError` if the server is unreachable or authentication fails.

```python
async def get_projects(self, limit: int = 25) -> list[dict[str, Any]]
async def get_project(self, project_id: str) -> dict[str, Any]
async def get_models(self, project_id: str, limit: int = 25) -> list[dict[str, Any]]
async def resolve_model_id(self, project_id: str, model: str, *, create: bool = False) -> str
async def get_versions(self, project_id: str, model: str = "main", limit: int = 10) -> list[SpeckleCommit]
```
List projects, models and versions. `model` accepts a model name (e.g. `"main"`) or id.

```python
async def send_objects(self, project_id: str, objects: list[dict[str, Any]], model: str = "main", message: str = "", *, branch: str | None = None) -> SpeckleCommit
```
Upload objects (wrapped in a `Collection`) and create a new version on `model`, creating the model if needed. Returns a `SpeckleCommit` whose `id` is the version id and `referenced_object` the root object hash. Requires a token; raises `SpeckleSyncError` on failure.

```python
async def receive_objects(self, project_id: str, version_id: str | None = None, model: str = "main", *, commit_id: str | None = None, branch: str | None = None) -> list[dict[str, Any]]
```
Download the objects of a version (the latest version of `model` when `version_id` is `None`).

```python
async def close(self) -> None
```
Release the client.

**Deprecated aliases** (emit `DeprecationWarning`): `get_streams()` -> `get_projects()`, `get_stream(stream_id)` -> `get_project()`, `get_branches(stream_id)` -> `get_models()`, `get_commits(stream_id, branch, limit)` -> `get_versions()`. The keyword arguments `branch=` and `commit_id=` are deprecated aliases of `model=` and `version_id=`; passing both the old and new name raises `TypeError`.

Module helpers: `dict_to_base()`, `base_to_dict()`, `flatten_received()`.

---

### SpeckleSync

High-level synchronisation between RevitPy and Speckle, with push, pull, and bidirectional sync operations. `project_id` defaults to `config.default_project` (or the deprecated `default_stream`).

**Module:** `revitpy.interop.sync`

```python
class SpeckleSync:
    def __init__(self, client: SpeckleClient, mapper: SpeckleTypeMapper | None = None, change_tracker: Any | None = None) -> None
```

**Methods:**

```python
async def push(self, elements: list[Any], project_id: str | None = None, model: str = "main", message: str = "", *, stream_id: str | None = None, branch: str | None = None) -> SyncResult
```
Map each element with the mapper and send them as a new version of `model`.

```python
async def pull(self, project_id: str | None = None, model: str = "main", version_id: str | None = None, *, stream_id: str | None = None, branch: str | None = None, commit_id: str | None = None) -> list[dict[str, Any]]
```
Pull a version (latest when `version_id` is `None`) and map the objects back to RevitPy-compatible dicts.

```python
async def sync(self, elements: list[Any], project_id: str | None = None, mode: SyncMode = SyncMode.INCREMENTAL, direction: SyncDirection = SyncDirection.BIDIRECTIONAL, *, model: str = "main", stream_id: str | None = None) -> SyncResult
```
Run a sync. Direction controls whether elements are pushed, pulled, or both; mode controls whether all or only changed elements are synced.

`stream_id`, `branch` and `commit_id` are deprecated aliases of `project_id`, `model` and `version_id`.

`SyncResult` fields: `direction`, `objects_sent`, `objects_received`, `errors`, `commit_id`, `duration_ms`, `object_id`, plus the `version_id` property (alias of `commit_id`).

---

### Convenience functions

**Module:** `revitpy.interop`

```python
def speckle_available() -> bool
async def push_to_speckle(elements: list, project_id: str | None = None, model: str = "main", message: str = "", config: SpeckleConfig | None = None, *, stream_id: str | None = None, branch: str | None = None) -> SyncResult
async def pull_from_speckle(project_id: str | None = None, model: str = "main", version_id: str | None = None, config: SpeckleConfig | None = None, *, stream_id: str | None = None, branch: str | None = None, commit_id: str | None = None) -> list[dict]
async def sync(elements: list, project_id: str | None = None, mode: SyncMode = SyncMode.INCREMENTAL, direction: SyncDirection = SyncDirection.BIDIRECTIONAL, config: SpeckleConfig | None = None, *, model: str = "main", stream_id: str | None = None) -> SyncResult
```

```python
@dataclass
class SpeckleConfig:
    server_url: str = "https://app.speckle.systems"
    token: str | None = None
    default_stream: str | None = None     # deprecated alias of default_project
    default_project: str | None = None
```

---

### SpeckleSubscriptions

WebSocket subscriptions to new versions on a project model. Each subscription runs as an asyncio task; events are passed to the callback and, when an `event_manager` is given, to `event_manager.dispatch("speckle.version_created", payload)`.

**Module:** `revitpy.interop.subscriptions`

```python
class SpeckleSubscriptions:
    def __init__(self, client: SpeckleClient, event_manager: Any | None = None) -> None

    async def subscribe(self, project_id: str | None = None, model: str = "main", callback: Callable[..., Any] | None = None, *, stream_id: str | None = None, branch: str | None = None) -> None
    async def unsubscribe(self, project_id: str) -> None   # all models of the project
    @property
    def active_subscriptions(self) -> list[str]            # "project/model" keys
    async def close(self) -> None
```

> `specklepy` pulls in `gql[websockets]`, which requires `websockets<12`, so installing the `interop` extra constrains `websockets` to 11.x. `revitpy.ai` supports both the legacy (<13) and the asyncio (>=13) websockets server APIs.

---

### SpeckleDiff

Compare local and remote element sets to produce diff entries describing additions, modifications, and removals at the property level.

**Module:** `revitpy.interop.diff`

```python
class SpeckleDiff:
    def __init__(self) -> None
```

**Methods:**

```python
def compare(self, local_elements: list[dict[str, Any]], remote_elements: list[dict[str, Any]]) -> list[DiffEntry]
```
Compare local and remote element dicts and return diffs. Elements are matched by their `id` key.

```python
def has_changes(self, local_elements: list[dict[str, Any]], remote_elements: list[dict[str, Any]]) -> bool
```
Return whether any differences exist between the two sets.

---

### SpeckleMerge

Merge local and remote element sets according to a configurable conflict resolution strategy (`LOCAL_WINS`, `REMOTE_WINS`, or `MANUAL`).

**Module:** `revitpy.interop.merge`

```python
class SpeckleMerge:
    def __init__(self, resolution: ConflictResolution = ConflictResolution.LOCAL_WINS) -> None
```

**Methods:**

```python
def merge(self, local_elements: list[dict[str, Any]], remote_elements: list[dict[str, Any]], diff_entries: list[DiffEntry] | None = None) -> MergeResult
```
Merge local and remote elements. Computes the diff automatically when `diff_entries` is `None`. Raises `MergeConflictError` when using `MANUAL` resolution with unresolved conflicts.

```python
def resolve_conflicts(self, conflicts: list[DiffEntry], strategy: ConflictResolution) -> list[dict[str, Any]]
```
Resolve a list of conflict entries using the given strategy. Returns list of resolved property dicts.

---

## Cloud & Design Automation (`revitpy.cloud`)

### ApsAuthenticator

OAuth2 client-credentials authentication for Autodesk Platform Services, with token caching and automatic refresh.

**Module:** `revitpy.cloud.auth`

```python
class ApsAuthenticator:
    def __init__(self, credentials: ApsCredentials) -> None
```

**Methods:**

```python
async def authenticate(self) -> ApsToken
```
Perform a fresh OAuth2 client-credentials authentication against the APS token endpoint.

```python
async def get_token(self) -> ApsToken
```
Return a cached token, refreshing it if expired or not yet obtained.

```python
def is_token_valid(self) -> bool
```
Check whether the cached token is still valid (uses a 60-second buffer before expiry).

---

### ApsClient

Authenticated HTTP client for the APS API (`https://developer.api.autodesk.com`) with sliding-window rate limiting (20 req/s), retry on 429 / 5xx with exponential backoff (honoring `Retry-After` in seconds on 429/503, capped at 60 s), and explicit timeouts.

**Module:** `revitpy.cloud.client`

```python
class ApsClient:
    def __init__(
        self,
        authenticator: ApsAuthenticator,
        *,
        region: CloudRegion = CloudRegion.US,
        timeout: httpx.Timeout | float | None = None,           # default 30 s (connect 10 s)
        download_timeout: httpx.Timeout | float | None = None,  # default 300 s (connect 10 s)
        da_base_path: str | None = None,
    ) -> None
```

A float timeout becomes `httpx.Timeout(seconds, connect=min(10, seconds))`.

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `region` | `CloudRegion` | Target APS region |
| `timeout` | `httpx.Timeout` | Timeout for API requests |
| `download_timeout` | `httpx.Timeout` | Timeout for result/report downloads |
| `da_base_path` | `str` | Design Automation v3 base path. `CloudRegion.US` maps to `/da/us-east/v3`; regions without a documented endpoint (e.g. `EMEA`) fall back to it with a warning. Pass `da_base_path` to override |

**Methods:**

```python
async def request(self, method: str, endpoint: str, **kwargs: Any) -> dict
```
Make an authenticated HTTP request with retry and rate limiting. Automatically injects Bearer token.

```python
async def get(self, endpoint: str, **kwargs: Any) -> dict
```
Perform an authenticated GET request.

```python
async def post(self, endpoint: str, **kwargs: Any) -> dict
```
Perform an authenticated POST request.

```python
async def delete(self, endpoint: str, **kwargs: Any) -> dict
```
Perform an authenticated DELETE request.

---

### JobManager

Manages Design Automation work items through the APS API: submit, poll, download results, cancel, and retrieve logs.

**Module:** `revitpy.cloud.jobs`

```python
class JobManager:
    def __init__(self, client: ApsClient) -> None

    @property
    def workitems_path(self) -> str   # f"{client.da_base_path}/workitems"
```

All work-item requests go to `workitems_path`.

**Methods:**

```python
async def submit(self, config: JobConfig) -> str
```
Submit a new Design Automation work item. Returns the `job_id`.

```python
async def get_status(self, job_id: str) -> JobStatus
```
Get the current status of a work item.

```python
async def wait_for_completion(self, job_id: str, timeout: float = 600.0, poll_interval: float = 5.0) -> JobResult
```
Poll a work item until it reaches a terminal state. Raises `JobExecutionError` on failure or timeout.

```python
async def download_results(self, job_id: str, output_dir: Path) -> list[Path]
```
Download output files for a completed work item. Files are streamed to disk in chunks using the client's `download_timeout`, written to a `.part` temp file and renamed on success.

```python
async def cancel(self, job_id: str) -> bool
```
Cancel a running work item. Returns `True` if cancellation succeeded.

```python
async def get_logs(self, job_id: str) -> str
```
Retrieve execution logs for a work item.

---

### BatchProcessor

Process multiple Design Automation jobs concurrently with bounded parallelism, automatic retry, and optional progress/cancellation callbacks.

**Module:** `revitpy.cloud.batch`

```python
class BatchProcessor:
    def __init__(self, job_manager: JobManager, *, config: BatchConfig | None = None) -> None
```

**Methods:**

```python
async def process(self, jobs: list[JobConfig], progress: Callable[[int, int], Any] | None = None, cancel: asyncio.Event | None = None) -> BatchResult
```
Process a list of jobs with bounded concurrency. Reports progress via callback `(completed, total)`. Stops submitting new jobs when the `cancel` event is set.

```python
async def process_directory(self, input_dir: Path, script_path: Path, *, activity_id: str = "RevitPy.Validate+prod", **kwargs: Any) -> BatchResult
```
Create and process jobs for every `.rvt` file in a directory.

---

### CIHelper

Generate CI/CD pipeline configurations for GitHub Actions and GitLab CI.

**Module:** `revitpy.cloud.ci`

```python
class CIHelper:
    def __init__(self) -> None
```

**Methods:**

```python
def generate_github_workflow(self, name: str = "revitpy-validation", script_path: str = "validate.py", revit_version: str = "2024", *, branches: str = "main", runner: str = "ubuntu-latest", python_version: str = "3.11") -> str
```
Generate a GitHub Actions workflow YAML string.

```python
def generate_gitlab_ci(self, name: str = "revitpy-validation", script_path: str = "validate.py", revit_version: str = "2024", *, python_version: str = "3.11") -> str
```
Generate a GitLab CI pipeline YAML string.

```python
def save_workflow(self, content: str, output_path: str | Path) -> Path
```
Write a workflow/pipeline configuration to disk.

---

### WebhookHandler

Receive, verify, and route APS webhook events to registered callbacks. Signatures follow the APS Webhooks scheme: the `x-adsk-signature` header carries `sha1hash=` followed by the hex HMAC-SHA1 of the raw request body, keyed with the hook's secret.

**Module:** `revitpy.cloud.webhooks`

```python
SIGNATURE_HEADER = "x-adsk-signature"

def compute_signature(secret: str, payload: bytes) -> str   # "sha1hash=<hexdigest>"

class WebhookHandler:
    def __init__(self, config: WebhookConfig | None = None) -> None
```

`WebhookConfig(url: str, secret: str, events: list[str] = [])`; `WebhookEvent(event_type, job_id, status, timestamp, payload)`.

**Methods:**

```python
def verify_signature(self, payload: bytes, signature: str) -> bool
```
Constant-time check of an `x-adsk-signature` value (`sha1hash=<hex>` or a bare hex digest). Raises `WebhookError` if no secret is configured.

```python
def handle_event(self, event_data: dict[str, Any] | None = None, *, raw_body: bytes | None = None, signature: str | None = None, verify: bool = True) -> WebhookEvent
```
Verify, parse and dispatch a webhook payload. **Verification is on by default**: a secret must be configured and both `raw_body` and `signature` supplied; the event is parsed from the signed `raw_body` and `event_data` is ignored. Pass `verify=False` explicitly to accept unsigned payloads (e.g. Design Automation `onComplete` callbacks, which APS does not sign). Raises `WebhookError` on a missing/invalid signature, a non-object body, or a missing `eventType`.

```python
def handle_request(self, raw_body: bytes, headers: Mapping[str, str]) -> WebhookEvent
```
Look up `x-adsk-signature` case-insensitively in `headers` and call `handle_event(raw_body=..., signature=..., verify=True)`.

```python
def register_callback(self, event_type: str, callback: Callable[[WebhookEvent], Any]) -> None
```
Register a callback for a specific event type. Use `"*"` to listen for all event types.
