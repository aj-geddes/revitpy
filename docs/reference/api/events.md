---
layout: api
title: Event System API
description: Event System API reference documentation
---

# Event System API

RevitPy's Event System provides a powerful, flexible framework for event-driven programming in Revit applications.

## Overview

The Event System enables:

- **Event subscription**: Subscribe to Revit events with decorators
- **Custom events**: Define and dispatch custom application events
- **Event filtering**: Filter events based on criteria
- **Async event handlers**: Use async/await in event handlers
- **Event priority**: Control handler execution order
- **Event pipelines**: Chain event handlers

## Core Classes

### EventManager

Central manager for all events in the application.

::: revitpy.events.EventManager
    options:
      members:
        - subscribe
        - unsubscribe
        - dispatch
        - dispatch_async
        - get_subscribers
        - clear_all_subscribers

### EventHandler

Base class for event handlers.

::: revitpy.events.handlers.BaseEventHandler
    options:
      members:
        - handle
        - can_handle
        - get_priority
        - get_name

### EventType

Enumeration of available event types.

::: revitpy.events.types.EventType
    options:
      members:
        - DOCUMENT_OPENED
        - DOCUMENT_CLOSED
        - DOCUMENT_SAVING
        - DOCUMENT_SAVED
        - ELEMENT_ADDED
        - ELEMENT_MODIFIED
        - ELEMENT_DELETED
        - VIEW_ACTIVATED
        - SELECTION_CHANGED

### EventData

Container for event data.

::: revitpy.events.types.EventData
    options:
      members:
        - event_type
        - timestamp
        - source
        - data
        - is_cancellable
        - cancel

### EventFilter

Filter events based on criteria.

::: revitpy.events.filters.EventFilter
    options:
      members:
        - matches
        - add_condition
        - and_filter
        - or_filter

## Basic Usage

### Simple Event Handler

```python
from revitpy.events import EventManager, event_handler, EventType

# Get event manager
event_mgr = EventManager()

# Define event handler
@event_handler(EventType.ELEMENT_ADDED)
def on_element_added(event_data):
    """Handle element added event."""
    element = event_data.data['element']
    print(f"Element added: {element.Name} (ID: {element.Id})")

# Subscribe to events
event_mgr.subscribe(EventType.ELEMENT_ADDED, on_element_added)

# Later: unsubscribe
event_mgr.unsubscribe(EventType.ELEMENT_ADDED, on_element_added)
```

### Class-Based Event Handler

```python
from revitpy.events import BaseEventHandler, EventType, EventPriority

class WallCreationHandler(BaseEventHandler):
    """Handle wall creation events."""

    def __init__(self):
        super().__init__(
            event_type=EventType.ELEMENT_ADDED,
            priority=EventPriority.HIGH
        )

    def can_handle(self, event_data):
        """Check if this handler can process the event."""
        element = event_data.data.get('element')
        return element and element.Category == 'Walls'

    def handle(self, event_data):
        """Process the event."""
        wall = event_data.data['element']
        print(f"New wall created: {wall.Name}")

        # Automatically tag new walls
        wall.set_parameter('Mark', f'W-{wall.Id.value}')

# Register handler
handler = WallCreationHandler()
event_mgr.subscribe(EventType.ELEMENT_ADDED, handler)
```

### Async Event Handler

```python
from revitpy.events import async_event_handler

@async_event_handler(EventType.DOCUMENT_SAVING)
async def on_document_saving_async(event_data):
    """Async handler for document saving."""
    document = event_data.data['document']

    # Perform async validation
    is_valid = await validate_document_async(document)

    if not is_valid:
        # Cancel the save operation
        event_data.cancel()
        print("Document save cancelled due to validation errors")
    else:
        print("Document validated, proceeding with save")

# Subscribe
event_mgr.subscribe(EventType.DOCUMENT_SAVING, on_document_saving_async)
```

## Event Filtering

### Basic Filtering

```python
from revitpy.events import EventFilter, ElementTypeFilter

def setup_filtered_events():
    """Set up events with filtering."""
    event_mgr = EventManager()

    # Filter for wall elements only
    wall_filter = ElementTypeFilter(category='Walls')

    @event_handler(EventType.ELEMENT_MODIFIED, filter=wall_filter)
    def on_wall_modified(event_data):
        wall = event_data.data['element']
        print(f"Wall modified: {wall.Name}")

    event_mgr.subscribe(EventType.ELEMENT_MODIFIED, on_wall_modified)
```

### Custom Filters

```python
from revitpy.events import EventFilter

class ParameterChangeFilter(EventFilter):
    """Filter for specific parameter changes."""

    def __init__(self, parameter_name):
        self.parameter_name = parameter_name

    def matches(self, event_data):
        """Check if event matches filter criteria."""
        changes = event_data.data.get('changes', [])
        return any(
            change.parameter_name == self.parameter_name
            for change in changes
        )

# Use custom filter
height_filter = ParameterChangeFilter('Height')

@event_handler(EventType.ELEMENT_MODIFIED, filter=height_filter)
def on_height_changed(event_data):
    element = event_data.data['element']
    print(f"Element height changed: {element.Name}")

event_mgr.subscribe(EventType.ELEMENT_MODIFIED, on_height_changed)
```

### Composite Filters

```python
from revitpy.events import ElementTypeFilter, ParameterChangeFilter

def setup_composite_filters():
    """Combine multiple filters."""
    # Filter for walls with height changes
    wall_filter = ElementTypeFilter(category='Walls')
    height_filter = ParameterChangeFilter('Height')

    combined_filter = wall_filter.and_filter(height_filter)

    @event_handler(EventType.ELEMENT_MODIFIED, filter=combined_filter)
    def on_wall_height_changed(event_data):
        wall = event_data.data['element']
        new_height = wall.get_parameter('Height').AsDouble()
        print(f"Wall height changed: {wall.Name} -> {new_height:.2f} ft")

    event_mgr.subscribe(EventType.ELEMENT_MODIFIED, on_wall_height_changed)
```

## Event Priority

### Priority-Based Execution

```python
from revitpy.events import EventPriority

# High priority handler (runs first)
@event_handler(EventType.ELEMENT_ADDED, priority=EventPriority.HIGH)
def validate_element(event_data):
    """Validate element before other handlers."""
    element = event_data.data['element']
    if not is_valid_element(element):
        event_data.cancel()
        print("Invalid element, cancelling event")

# Normal priority handler
@event_handler(EventType.ELEMENT_ADDED, priority=EventPriority.NORMAL)
def log_element(event_data):
    """Log element creation."""
    element = event_data.data['element']
    print(f"Element created: {element.Name}")

# Low priority handler (runs last)
@event_handler(EventType.ELEMENT_ADDED, priority=EventPriority.LOW)
def update_statistics(event_data):
    """Update statistics after all other handlers."""
    update_element_count()
```

## Custom Events

### Defining Custom Events

```python
from revitpy.events import EventType, EventData

# Define custom event types
class CustomEventType:
    VALIDATION_COMPLETE = "validation_complete"
    EXPORT_STARTED = "export_started"
    EXPORT_COMPLETE = "export_complete"

# Dispatch custom event
def perform_validation():
    """Perform validation and dispatch event."""
    # ... perform validation ...

    # Create event data
    event_data = EventData(
        event_type=CustomEventType.VALIDATION_COMPLETE,
        source='validation_system',
        data={
            'is_valid': True,
            'error_count': 0,
            'warning_count': 3
        }
    )

    # Dispatch event
    event_mgr.dispatch(CustomEventType.VALIDATION_COMPLETE, event_data)

# Subscribe to custom event
@event_handler(CustomEventType.VALIDATION_COMPLETE)
def on_validation_complete(event_data):
    """Handle validation complete event."""
    is_valid = event_data.data['is_valid']
    print(f"Validation complete: {'PASS' if is_valid else 'FAIL'}")
```

### Event Pipelines

```python
from revitpy.events import EventPipeline

class DocumentExportPipeline:
    """Pipeline for document export events."""

    def __init__(self):
        self.pipeline = EventPipeline()
        self.setup_pipeline()

    def setup_pipeline(self):
        """Set up event pipeline."""
        # Stage 1: Validation
        self.pipeline.add_handler(self.validate_document, priority=1)

        # Stage 2: Preparation
        self.pipeline.add_handler(self.prepare_export, priority=2)

        # Stage 3: Export
        self.pipeline.add_handler(self.perform_export, priority=3)

        # Stage 4: Cleanup
        self.pipeline.add_handler(self.cleanup, priority=4)

    async def validate_document(self, event_data):
        """Validate document before export."""
        print("Stage 1: Validating...")
        # Validation logic
        return True

    async def prepare_export(self, event_data):
        """Prepare for export."""
        print("Stage 2: Preparing...")
        # Preparation logic
        return True

    async def perform_export(self, event_data):
        """Perform the export."""
        print("Stage 3: Exporting...")
        # Export logic
        return True

    async def cleanup(self, event_data):
        """Clean up after export."""
        print("Stage 4: Cleaning up...")
        # Cleanup logic
        return True

    async def execute(self, document):
        """Execute the pipeline."""
        event_data = EventData(
            event_type='document_export',
            data={'document': document}
        )

        await self.pipeline.execute(event_data)
```

## Advanced Patterns

### Event Aggregation

```python
from revitpy.events import EventAggregator

class ChangeAggregator:
    """Aggregate multiple change events."""

    def __init__(self, window_seconds=5):
        self.aggregator = EventAggregator(window_seconds)
        self.changes = []

    @event_handler(EventType.ELEMENT_MODIFIED)
    def on_element_modified(self, event_data):
        """Collect element changes."""
        self.changes.append(event_data)

        # Aggregate changes
        self.aggregator.add_event(event_data)

    def flush_changes(self):
        """Process all aggregated changes."""
        aggregated = self.aggregator.get_aggregated_events()

        print(f"Processing {len(aggregated)} aggregated changes")

        # Process batched changes
        with RevitContext() as context:
            with context.transaction("Batch Update") as txn:
                for event in aggregated:
                    process_change(event)
                txn.commit()

        self.changes.clear()
```

### Event Replay

```python
from revitpy.events import EventRecorder

class EventReplaySystem:
    """Record and replay events."""

    def __init__(self):
        self.recorder = EventRecorder()

    def start_recording(self):
        """Start recording events."""
        self.recorder.start()

        # Subscribe to all event types
        for event_type in EventType:
            event_mgr.subscribe(event_type, self.recorder.record)

    def stop_recording(self):
        """Stop recording events."""
        self.recorder.stop()

    def replay_events(self):
        """Replay recorded events."""
        recorded_events = self.recorder.get_recorded_events()

        print(f"Replaying {len(recorded_events)} events")

        for event_data in recorded_events:
            event_mgr.dispatch(event_data.event_type, event_data)

    def save_recording(self, filename):
        """Save recording to file."""
        self.recorder.save(filename)

    def load_recording(self, filename):
        """Load recording from file."""
        self.recorder.load(filename)
```

### Event Transformation

```python
from revitpy.events import EventTransformer

class ElementChangeTransformer(EventTransformer):
    """Transform element change events."""

    def transform(self, event_data):
        """Transform event data."""
        element = event_data.data['element']

        # Enrich event data
        enriched_data = {
            'element': element,
            'element_type': element.Category,
            'parameters': {
                p.Definition.Name: p.AsValueString()
                for p in element.get_all_parameters()
            },
            'timestamp': event_data.timestamp,
            'user': get_current_user()
        }

        # Create transformed event
        return EventData(
            event_type=event_data.event_type,
            source=event_data.source,
            data=enriched_data
        )

# Use transformer
transformer = ElementChangeTransformer()
event_mgr.add_transformer(EventType.ELEMENT_MODIFIED, transformer)
```

## Error Handling

### Handling Event Errors

```python
from revitpy.events import EventError

@event_handler(EventType.ELEMENT_ADDED)
def error_prone_handler(event_data):
    """Handler that might raise errors."""
    try:
        element = event_data.data['element']

        # Risky operation
        result = process_element(element)

        if not result:
            raise ValueError("Processing failed")

    except Exception as e:
        # Log error but don't crash
        print(f"Error in event handler: {e}")
        # Event system continues with next handler

# Configure error handling
event_mgr.configure(
    stop_on_error=False,  # Continue processing other handlers
    log_errors=True,      # Log errors
    error_handler=custom_error_handler  # Custom error handler
)
```

## Performance Optimization

### Efficient Event Dispatching

```python
# BAD: Dispatch events in loop
for element in elements:
    event_mgr.dispatch(EventType.ELEMENT_ADDED, EventData(data={'element': element}))

# GOOD: Batch event dispatch
event_mgr.dispatch_batch(
    EventType.ELEMENT_ADDED,
    [EventData(data={'element': e}) for e in elements]
)
```

### Async Event Dispatch

```python
# Dispatch events asynchronously
await event_mgr.dispatch_async(
    EventType.DOCUMENT_SAVING,
    EventData(data={'document': doc})
)
```

## Testing Events

### Testing Event Handlers

```python
import pytest
from revitpy.testing import MockEventManager, create_mock_event

def test_event_handler():
    """Test event handler behavior."""
    mock_event_mgr = MockEventManager()
    handler_called = False

    @event_handler(EventType.ELEMENT_ADDED)
    def test_handler(event_data):
        nonlocal handler_called
        handler_called = True

    # Subscribe
    mock_event_mgr.subscribe(EventType.ELEMENT_ADDED, test_handler)

    # Dispatch test event
    test_event = create_mock_event(
        EventType.ELEMENT_ADDED,
        data={'element': mock_element}
    )
    mock_event_mgr.dispatch(EventType.ELEMENT_ADDED, test_event)

    # Verify handler was called
    assert handler_called
```

## Best Practices

1. **Use event filters**: Filter events early to improve performance
2. **Handle errors gracefully**: Don't let handler errors crash the application
3. **Respect priorities**: Use appropriate priorities for handler execution order
4. **Unsubscribe when done**: Clean up event subscriptions to prevent memory leaks
5. **Keep handlers focused**: Each handler should do one thing well
6. **Use async for I/O**: Use async handlers for network or file operations

## Next Steps

- **[Extensions Framework](extensions.md)**: Build extensions with event support
- **[Async Support](async.md)**: Use async/await with events
- **[Testing Events](../../guides/testing-events.md)**: Test event-driven code
