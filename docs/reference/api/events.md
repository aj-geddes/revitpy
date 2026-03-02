---
layout: api
title: Event System API
description: Event system for subscribing to and dispatching Revit events
---

# Event System API

The Event System provides a centralized event manager for subscribing to Revit events, dispatching custom events, and auto-discovering event handlers. It follows a singleton pattern and supports both synchronous and asynchronous handlers.

---

## EventType

Enumeration of standard Revit event types.

**Module:** `revitpy.events.types`

| Event | Value | Description |
|-------|-------|-------------|
| `DOCUMENT_OPENED` | `"document_opened"` | Document was opened. |
| `DOCUMENT_CLOSED` | `"document_closed"` | Document was closed. |
| `DOCUMENT_SAVED` | `"document_saved"` | Document was saved. |
| `DOCUMENT_SYNCHRONIZED` | `"document_synchronized"` | Document was synchronized with central. |
| `ELEMENT_CREATED` | `"element_created"` | Element was created. |
| `ELEMENT_MODIFIED` | `"element_modified"` | Element was modified. |
| `ELEMENT_DELETED` | `"element_deleted"` | Element was deleted. |
| `ELEMENT_TYPE_CHANGED` | `"element_type_changed"` | Element type was changed. |
| `TRANSACTION_STARTED` | `"transaction_started"` | Transaction started. |
| `TRANSACTION_COMMITTED` | `"transaction_committed"` | Transaction committed. |
| `TRANSACTION_ROLLED_BACK` | `"transaction_rolled_back"` | Transaction rolled back. |
| `PARAMETER_CHANGED` | `"parameter_changed"` | Parameter value changed. |
| `PARAMETER_ADDED` | `"parameter_added"` | Parameter was added. |
| `PARAMETER_REMOVED` | `"parameter_removed"` | Parameter was removed. |
| `VIEW_ACTIVATED` | `"view_activated"` | View was activated. |
| `VIEW_DEACTIVATED` | `"view_deactivated"` | View was deactivated. |
| `VIEW_CREATED` | `"view_created"` | View was created. |
| `SELECTION_CHANGED` | `"selection_changed"` | Selection changed. |
| `APPLICATION_INITIALIZED` | `"application_initialized"` | Application initialized. |
| `APPLICATION_CLOSING` | `"application_closing"` | Application closing. |
| `CUSTOM` | `"custom"` | Custom user-defined event. |

---

## EventPriority

Handler execution priority levels.

**Module:** `revitpy.events.types`

| Priority | Value | Description |
|----------|-------|-------------|
| `LOWEST` | `0` | Runs last. |
| `LOW` | `25` | Below normal priority. |
| `NORMAL` | `50` | Default priority. |
| `HIGH` | `75` | Above normal priority. |
| `HIGHEST` | `100` | Runs first. |

---

## EventData

Base event data container. Specialized subclasses exist for different event categories.

**Module:** `revitpy.events.types`

### Constructor

```python
EventData(
    event_type: EventType,
    event_id: str = <auto>,
    timestamp: datetime = <now>,
    source: Any | None = None,
    data: dict[str, Any] = {},
    cancellable: bool = False,
    cancelled: bool = False
)
```

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | `EventType` | The type of event. |
| `event_id` | `str` | Unique ID (auto-generated UUID). |
| `timestamp` | `datetime` | When the event was created. |
| `source` | `Any` or `None` | The object that emitted the event. |
| `data` | `dict[str, Any]` | Arbitrary event payload. |
| `cancellable` | `bool` | Whether the event can be cancelled by handlers. |
| `cancelled` | `bool` | Whether the event has been cancelled. |

### Methods

#### `cancel()`

Cancels the event if `cancellable` is `True`.

#### `get_data(key, default=None)`

Gets a value from the `data` dictionary.

#### `set_data(key, value)`

Sets a value in the `data` dictionary.

### Specialized EventData Subclasses

| Class | Extra Fields | Used For |
|-------|-------------|----------|
| `DocumentEventData` | `document_path`, `document_title`, `is_family_document` | Document events |
| `ElementEventData` | `element_id`, `element_type`, `category`, `parameters_changed`, `old_values`, `new_values` | Element events |
| `TransactionEventData` | `transaction_name`, `transaction_id`, `elements_affected`, `operation_count` | Transaction events |
| `ParameterEventData` | `element_id`, `parameter_name`, `old_value`, `new_value`, `parameter_type`, `storage_type` | Parameter events |
| `ViewEventData` | `view_id`, `view_name`, `view_type`, `is_3d_view`, `previous_view_id` | View events |
| `SelectionEventData` | `selected_elements`, `previously_selected`, `added_to_selection`, `removed_from_selection` | Selection events |

### Factory Function

```python
from revitpy.events.types import create_event_data

event = create_event_data(
    EventType.ELEMENT_MODIFIED,
    element_id=12345,
    category="Walls",
    parameters_changed=["Height"],
)
# Returns ElementEventData with appropriate fields populated
```

---

## EventManager

Singleton manager that coordinates the entire event system: handler registration, event dispatching, auto-discovery, and Revit integration.

**Module:** `revitpy.events.manager`

### Constructor / Singleton

```python
event_mgr = EventManager()          # returns singleton
event_mgr = EventManager.get_instance()  # explicit singleton access
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `dispatcher` | `EventDispatcher` | The underlying event dispatcher. |
| `is_running` | `bool` | Whether the event manager is running. |
| `stats` | `dict[str, Any]` | Event processing statistics. |

### Lifecycle Methods

#### `start(auto_discover=True)`

Starts the event manager. Optionally runs handler auto-discovery.

| Parameter | Type | Description |
|-----------|------|-------------|
| `auto_discover` | `bool` | Whether to auto-discover handlers. Default `True`. |

#### `stop(timeout=5.0)`

Stops the event manager and halts event processing.

| Parameter | Type | Description |
|-----------|------|-------------|
| `timeout` | `float` | Timeout in seconds. Default `5.0`. |

### Handler Registration

#### `register_handler(handler, event_types=None)`

Registers a `BaseEventHandler` instance.

| Parameter | Type | Description |
|-----------|------|-------------|
| `handler` | `BaseEventHandler` | Handler to register. |
| `event_types` | `list[EventType]` or `None` | Event types to handle. `None` for all. |

#### `register_function(func, event_types, priority=EventPriority.NORMAL, event_filter=None, name=None)`

Registers a function (sync or async) as an event handler. Automatically detects async functions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `func` | `Callable[[EventData], Any]` | Handler function. |
| `event_types` | `list[EventType]` | Events to handle. |
| `priority` | `EventPriority` | Handler priority. Default `NORMAL`. |
| `event_filter` | `EventFilter` or `None` | Optional filter. |
| `name` | `str` or `None` | Handler name. Defaults to the function name. |

**Returns:** `BaseEventHandler` -- The created handler instance.

```python
from revitpy.events.manager import EventManager
from revitpy.events.types import EventType, EventPriority

mgr = EventManager()

def on_element_created(event):
    print(f"Created: {event.element_id}")

mgr.register_function(
    on_element_created,
    [EventType.ELEMENT_CREATED],
    priority=EventPriority.HIGH,
)
```

#### `unregister_handler(handler, event_types=None)`

Unregisters a handler. Pass `event_types` to unregister from specific events only.

#### `register_class_handlers(instance)`

Scans a class instance for methods decorated with event handler markers and registers them.

**Returns:** `list[BaseEventHandler]` -- List of registered handlers.

### Event Dispatching

#### `dispatch_event(event_type, immediate=False, **event_data)`

Dispatches an event synchronously.

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_type` | `EventType` | Type of event. |
| `immediate` | `bool` | Whether to process immediately (bypass queue). |
| `**event_data` | | Event-specific data passed to `create_event_data`. |

**Returns:** `EventDispatchResult`

#### `dispatch_event_async(event_type, **event_data)`

Dispatches an event asynchronously.

**Returns:** `EventDispatchResult`

#### `emit(event_type, data=None, source=None, cancellable=False, immediate=False)`

Simplified event emission interface.

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_type` | `EventType` | Event type. |
| `data` | `dict` or `None` | Event payload. |
| `source` | `Any` or `None` | Event source. |
| `cancellable` | `bool` | Whether handlers can cancel. |
| `immediate` | `bool` | Process immediately. |

**Returns:** `EventDispatchResult`

```python
result = mgr.emit(
    EventType.ELEMENT_MODIFIED,
    data={"element_id": 12345, "field": "Height"},
    source=my_extension,
)
```

#### `emit_async(event_type, data=None, source=None, cancellable=False)`

Async version of `emit()`.

**Returns:** `EventDispatchResult`

### Handler Discovery

#### `add_discovery_path(path)`

Adds a directory for auto-discovery of event handlers.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `Path` | Directory to scan. |

#### `discover_handlers(paths=None)`

Scans directories for Python files containing decorated event handlers and registers them.

| Parameter | Type | Description |
|-----------|------|-------------|
| `paths` | `list[Path]` or `None` | Paths to scan. Uses registered discovery paths if `None`. |

**Returns:** `int` -- Number of handlers discovered.

### Event Listeners (Simple Callback Interface)

#### `add_listener(event_type, callback, priority=EventPriority.NORMAL)`

Adds a simple callback listener for an event type.

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_type` | `EventType` | Event to listen for. |
| `callback` | `Callable[[EventData], Any]` | Callback function. |
| `priority` | `EventPriority` | Listener priority. |

#### `remove_listener(event_type, callback)`

Removes a listener.

**Returns:** `bool` -- `True` if the listener was found and removed.

### Revit Integration

#### `connect_to_revit(revit_application)`

Connects to the native Revit event system via `RevitEventBridge`.

#### `disconnect_from_revit()`

Disconnects from the native Revit event system.

### Utility Methods

| Method | Description |
|--------|-------------|
| `enable_debug()` | Enables debug logging for events. |
| `disable_debug()` | Disables debug logging. |
| `clear_event_queue()` | Clears pending events. Returns count cleared. |
| `reset_statistics()` | Resets all event statistics. |
| `get_registered_handlers()` | Returns `dict[EventType, list[str]]` of handler names by event type. |

### Context Manager

```python
with EventManager() as mgr:
    mgr.register_function(handler, [EventType.ELEMENT_CREATED])
    mgr.emit(EventType.ELEMENT_CREATED, data={"element_id": 123})
# stop() called on exit
```

Also supports `async with`.

---

## Global Convenience Functions

**Module:** `revitpy.events.manager`

```python
from revitpy.events.manager import (
    get_event_manager,
    register_handler,
    emit_event,
    emit_event_async,
    add_event_listener,
)

# Get global singleton
mgr = get_event_manager()

# Register a handler globally
register_handler(my_handler, [EventType.ELEMENT_MODIFIED])

# Emit an event globally
result = emit_event(EventType.ELEMENT_CREATED, data={"element_id": 456})

# Emit async
result = await emit_event_async(EventType.DOCUMENT_SAVED)

# Add a simple listener
add_event_listener(EventType.SELECTION_CHANGED, on_selection_changed)
```

---

## Usage Examples

### Registering Function Handlers

```python
from revitpy.events.manager import EventManager
from revitpy.events.types import EventType

mgr = EventManager()
mgr.start()

def on_wall_modified(event):
    if event.category == "Walls":
        print(f"Wall {event.element_id} modified: {event.parameters_changed}")

mgr.register_function(on_wall_modified, [EventType.ELEMENT_MODIFIED])
```

### Async Event Handler

```python
import asyncio
from revitpy.events.manager import EventManager
from revitpy.events.types import EventType

mgr = EventManager()

async def on_doc_saved(event):
    print(f"Document saved: {event.document_title}")
    await notify_team(event.document_title)

mgr.register_function(on_doc_saved, [EventType.DOCUMENT_SAVED])
```

### Cancellable Events

```python
from revitpy.events.manager import EventManager
from revitpy.events.types import EventType

mgr = EventManager()

def validate_before_save(event):
    if not is_valid(event.data):
        event.cancel()
        print("Save cancelled: validation failed")

mgr.register_function(validate_before_save, [EventType.DOCUMENT_SAVED])

# Dispatch a cancellable event
result = mgr.emit(EventType.DOCUMENT_SAVED, cancellable=True)
```

### Auto-Discovery

```python
from pathlib import Path
from revitpy.events.manager import EventManager

mgr = EventManager()
mgr.add_discovery_path(Path("./my_handlers"))
count = mgr.discover_handlers()
print(f"Discovered {count} handlers")
mgr.start(auto_discover=False)  # already discovered
```

---

## Best Practices

1. **Use priorities wisely** -- Validators at `HIGH`, logging at `LOW`.
2. **Unregister handlers when done** -- Prevent memory leaks and stale callbacks.
3. **Keep handlers focused** -- Each handler should do one thing.
4. **Use the singleton** -- `EventManager()` always returns the same instance.
5. **Use `emit()` for simple dispatch** -- It provides a cleaner API than `dispatch_event`.
6. **Handle errors in handlers** -- Unhandled exceptions in handlers are logged but may disrupt event chains.

---

## Next Steps

- **[Extensions Framework]({{ '/reference/api/extensions/' | relative_url }})**: Build extensions with event support
- **[Async Support]({{ '/reference/api/async/' | relative_url }})**: Async event handling
- **[Testing]({{ '/reference/api/testing/' | relative_url }})**: Test event-driven code
