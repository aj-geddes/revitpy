---
layout: page
title: Events
description: Guide to the RevitPy event system with EventManager, decorator-based handlers, priority levels, event filters, throttling, retry, and async dispatch.
doc_tier: user
---

# Events

RevitPy includes an event system for reacting to changes in the Revit model. The system supports event handlers with priorities, filters, async dispatch, throttling, retry logic, and auto-discovery of handlers.

## EventManager

`EventManager` is the central coordinator for the event system. It is a singleton -- calling `EventManager()` always returns the same instance.

```python
from revitpy import EventManager

manager = EventManager()
manager.start()

# Or use as a context manager
with EventManager() as manager:
    # register handlers and dispatch events
    pass
# manager.stop() is called automatically
```

### Starting and Stopping

```python
manager.start(auto_discover=True)  # Start and auto-discover handlers
manager.stop(timeout=5.0)          # Stop with a timeout
```

### Key Properties

- `manager.is_running` -- `True` if the manager has been started.
- `manager.stats` -- Dictionary with dispatcher statistics, handler stats, registered modules, and listener counts.

## Event Types

The `EventType` enum defines all standard Revit event types:

### Document Events
- `DOCUMENT_OPENED`
- `DOCUMENT_CLOSED`
- `DOCUMENT_SAVED`
- `DOCUMENT_SYNCHRONIZED`

### Element Events
- `ELEMENT_CREATED`
- `ELEMENT_MODIFIED`
- `ELEMENT_DELETED`
- `ELEMENT_TYPE_CHANGED`

### Transaction Events
- `TRANSACTION_STARTED`
- `TRANSACTION_COMMITTED`
- `TRANSACTION_ROLLED_BACK`

### Parameter Events
- `PARAMETER_CHANGED`
- `PARAMETER_ADDED`
- `PARAMETER_REMOVED`

### View Events
- `VIEW_ACTIVATED`
- `VIEW_DEACTIVATED`
- `VIEW_CREATED`

### Selection Events
- `SELECTION_CHANGED`

### Application Events
- `APPLICATION_INITIALIZED`
- `APPLICATION_CLOSING`

### Custom Events
- `CUSTOM`

## Event Priorities

The `EventPriority` enum controls the order in which handlers run:

| Priority | Value |
|---|---|
| `LOWEST` | 0 |
| `LOW` | 25 |
| `NORMAL` | 50 |
| `HIGH` | 75 |
| `HIGHEST` | 100 |

Handlers with higher priority values run first.

## The @event_handler Decorator

The `@event_handler` decorator registers a function as an event handler.

```python
from revitpy.events.decorators import event_handler
from revitpy.events.types import EventData, EventResult, EventType, EventPriority

@event_handler(
    event_types=[EventType.ELEMENT_CREATED],
    priority=EventPriority.NORMAL,
    max_errors=10,
    enabled=True,
)
def on_element_created(event_data: EventData) -> EventResult:
    print(f"Element created: {event_data.get_data('element_id')}")
    return EventResult.CONTINUE
```

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `event_types` | `list[EventType]` or `None` | `None` | Event types to handle |
| `priority` | `EventPriority` | `NORMAL` | Handler priority |
| `event_filter` | `EventFilter` or `None` | `None` | Optional filter |
| `max_errors` | `int` | `10` | Maximum errors before the handler is disabled |
| `enabled` | `bool` | `True` | Whether the handler starts enabled |

The `@event_handler` decorator works with both sync and async functions. If the decorated function is a coroutine, it is automatically wrapped as an async handler.

## The @async_event_handler Decorator

Explicitly registers an async function as an event handler:

```python
from revitpy.events.decorators import async_event_handler

@async_event_handler(
    event_types=[EventType.ELEMENT_MODIFIED],
    priority=EventPriority.HIGH,
)
async def on_element_modified(event_data: EventData) -> EventResult:
    await some_async_operation()
    return EventResult.CONTINUE
```

The parameters are the same as `@event_handler`.

## EventResult

Handlers return an `EventResult` to control processing flow:

| Result | Description |
|---|---|
| `CONTINUE` | Continue processing other handlers |
| `STOP` | Stop processing further handlers for this event |
| `CANCEL` | Cancel the event (only if the event is cancellable) |

## Convenience Decorators

RevitPy provides shortcut decorators for common event patterns:

```python
from revitpy.events.decorators import (
    on_element_created,
    on_element_modified,
    on_element_deleted,
    on_parameter_changed,
    on_document_opened,
    on_document_saved,
)

@on_element_created(element_type="Wall")
def handle_wall_created(event_data):
    return EventResult.CONTINUE

@on_element_modified(element_type="Wall", parameter_name="Height")
def handle_wall_height_changed(event_data):
    return EventResult.CONTINUE

@on_parameter_changed("Comments", element_type="Wall")
def handle_comments_changed(event_data):
    return EventResult.CONTINUE

@on_document_opened()
def handle_doc_opened(event_data):
    return EventResult.CONTINUE

@on_document_saved(priority=EventPriority.HIGH)
def handle_doc_saved(event_data):
    return EventResult.CONTINUE
```

## Dispatching Events

### Synchronous Dispatch

```python
from revitpy.events.types import EventType

result = manager.dispatch_event(
    EventType.ELEMENT_CREATED,
    element_id=12345,
    element_type="Wall",
    immediate=False,
)

# Or use the simpler emit method
result = manager.emit(
    EventType.ELEMENT_CREATED,
    data={"element_id": 12345},
    source=some_object,
    cancellable=False,
    immediate=False,
)
```

### Asynchronous Dispatch

```python
result = await manager.dispatch_event_async(
    EventType.ELEMENT_MODIFIED,
    element_id=12345,
)

result = await manager.emit_async(
    EventType.ELEMENT_MODIFIED,
    data={"element_id": 12345},
)
```

### Global Convenience Functions

```python
from revitpy.events.manager import emit_event, emit_event_async, add_event_listener

# Emit an event
emit_event(EventType.ELEMENT_CREATED, data={"element_id": 12345})

# Emit an event asynchronously
await emit_event_async(EventType.ELEMENT_CREATED, data={"element_id": 12345})

# Add a simple listener
add_event_listener(EventType.ELEMENT_CREATED, my_callback, EventPriority.NORMAL)
```

## Event Filters

Filters allow handlers to selectively process events. The base class is `EventFilter`, which supports combining with `&` (AND), `|` (OR), and `~` (NOT).

### Built-in Filter Classes

- `EventTypeFilter(*event_types)` -- Match by event type.
- `ElementTypeFilter(*element_types)` -- Match element events by element type string.
- `CategoryFilter(*categories)` -- Match element events by category string.
- `ParameterChangeFilter(parameter_name)` -- Match parameter change events by parameter name.

### Using Filters with Decorators

```python
from revitpy.events.decorators import event_handler, event_filter
from revitpy.events.filters import ElementTypeFilter

@event_handler([EventType.ELEMENT_MODIFIED])
@event_filter(ElementTypeFilter("Wall"))
def on_wall_modified(event_data):
    return EventResult.CONTINUE
```

Filters can be combined:

```python
wall_or_floor = ElementTypeFilter("Wall") | ElementTypeFilter("Floor")
not_generic = ~CategoryFilter("Generic")
combined = wall_or_floor & not_generic
```

## Event Data Classes

Each event type has a corresponding data class with event-specific fields:

| Class | Used For | Extra Fields |
|---|---|---|
| `EventData` | Base / custom events | `event_type`, `event_id`, `timestamp`, `source`, `data`, `cancellable`, `cancelled` |
| `DocumentEventData` | Document events | `document_path`, `document_title`, `is_family_document` |
| `ElementEventData` | Element events | `element_id`, `element_type`, `category`, `parameters_changed`, `old_values`, `new_values` |
| `TransactionEventData` | Transaction events | `transaction_name`, `transaction_id`, `elements_affected`, `operation_count` |
| `ParameterEventData` | Parameter events | `element_id`, `parameter_name`, `old_value`, `new_value`, `parameter_type`, `storage_type` |
| `ViewEventData` | View events | `view_id`, `view_name`, `view_type`, `is_3d_view`, `previous_view_id` |
| `SelectionEventData` | Selection events | `selected_elements`, `previously_selected`, `added_to_selection`, `removed_from_selection` |

All data classes have `cancel()`, `get_data(key, default)`, and `set_data(key, value)` methods.

## Additional Decorators

### @throttled_handler

Limits how frequently a handler executes:

```python
from revitpy.events.decorators import throttled_handler

@event_handler([EventType.SELECTION_CHANGED])
@throttled_handler(interval_seconds=0.5)
def on_selection_changed(event_data):
    return EventResult.CONTINUE
```

### @conditional_handler

Adds a condition that must be met before the handler runs:

```python
from revitpy.events.decorators import conditional_handler

@event_handler([EventType.ELEMENT_MODIFIED])
@conditional_handler(lambda event: event.get_data("user_initiated", False))
def on_user_modified(event_data):
    return EventResult.CONTINUE
```

### @retry_on_error

Retries the handler on failure:

```python
from revitpy.events.decorators import retry_on_error

@event_handler([EventType.ELEMENT_CREATED])
@retry_on_error(max_retries=3, delay_seconds=1.0)
def on_element_created(event_data):
    return EventResult.CONTINUE
```

### @log_events

Adds logging around handler execution:

```python
from revitpy.events.decorators import log_events

@event_handler([EventType.ELEMENT_DELETED])
@log_events("INFO")
def on_element_deleted(event_data):
    return EventResult.CONTINUE
```

## Registering Class-Based Handlers

If you have a class with decorated handler methods, register all handlers at once:

```python
class MyHandlers:
    @event_handler([EventType.ELEMENT_CREATED])
    def on_created(self, event_data):
        return EventResult.CONTINUE

    @event_handler([EventType.ELEMENT_DELETED])
    def on_deleted(self, event_data):
        return EventResult.CONTINUE

handlers = MyHandlers()
registered = manager.register_class_handlers(handlers)
```

## Handler Auto-Discovery

The `EventManager` can auto-discover handlers from Python files in specified directories:

```python
from pathlib import Path

manager.add_discovery_path(Path("./my_handlers"))
count = manager.discover_handlers()
```

This scans all non-private `.py` files in the directory for functions decorated with `@event_handler` and registers them automatically.
