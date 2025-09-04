"""
Event types and data structures for the RevitPy event system.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, Type
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class EventType(Enum):
    """Standard Revit event types."""
    
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


class EventPriority(Enum):
    """Event handler priority levels."""
    
    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


class EventResult(Enum):
    """Event handling results."""
    
    CONTINUE = "continue"  # Continue processing other handlers
    STOP = "stop"         # Stop processing further handlers
    CANCEL = "cancel"     # Cancel the event (if cancellable)


@dataclass
class EventData:
    """Base event data container."""
    
    event_type: EventType
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[Any] = None
    data: Dict[str, Any] = field(default_factory=dict)
    cancellable: bool = False
    cancelled: bool = False
    
    def cancel(self) -> None:
        """Cancel the event if it's cancellable."""
        if self.cancellable:
            self.cancelled = True
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """Get data value by key."""
        return self.data.get(key, default)
    
    def set_data(self, key: str, value: Any) -> None:
        """Set data value by key."""
        self.data[key] = value


@dataclass
class DocumentEventData(EventData):
    """Event data for document-related events."""
    
    document_path: Optional[str] = None
    document_title: Optional[str] = None
    is_family_document: bool = False


@dataclass
class ElementEventData(EventData):
    """Event data for element-related events."""
    
    element_id: Optional[Any] = None
    element_type: Optional[str] = None
    category: Optional[str] = None
    parameters_changed: List[str] = field(default_factory=list)
    old_values: Dict[str, Any] = field(default_factory=dict)
    new_values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionEventData(EventData):
    """Event data for transaction-related events."""
    
    transaction_name: Optional[str] = None
    transaction_id: Optional[str] = None
    elements_affected: List[Any] = field(default_factory=list)
    operation_count: int = 0


@dataclass
class ParameterEventData(EventData):
    """Event data for parameter-related events."""
    
    element_id: Optional[Any] = None
    parameter_name: str = ""
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    parameter_type: Optional[str] = None
    storage_type: Optional[str] = None


@dataclass
class ViewEventData(EventData):
    """Event data for view-related events."""
    
    view_id: Optional[Any] = None
    view_name: Optional[str] = None
    view_type: Optional[str] = None
    is_3d_view: bool = False
    previous_view_id: Optional[Any] = None


@dataclass
class SelectionEventData(EventData):
    """Event data for selection-related events."""
    
    selected_elements: List[Any] = field(default_factory=list)
    previously_selected: List[Any] = field(default_factory=list)
    added_to_selection: List[Any] = field(default_factory=list)
    removed_from_selection: List[Any] = field(default_factory=list)


# Event data factory
def create_event_data(
    event_type: EventType,
    **kwargs
) -> EventData:
    """
    Factory function to create appropriate event data based on event type.
    
    Args:
        event_type: The type of event
        **kwargs: Event-specific data
        
    Returns:
        Appropriate EventData subclass instance
    """
    base_kwargs = {
        'event_type': event_type,
        'timestamp': kwargs.pop('timestamp', datetime.now()),
        'source': kwargs.pop('source', None),
        'data': kwargs.pop('data', {}),
        'cancellable': kwargs.pop('cancellable', False),
    }
    
    if event_type in (
        EventType.DOCUMENT_OPENED,
        EventType.DOCUMENT_CLOSED,
        EventType.DOCUMENT_SAVED,
        EventType.DOCUMENT_SYNCHRONIZED
    ):
        return DocumentEventData(
            **base_kwargs,
            document_path=kwargs.get('document_path'),
            document_title=kwargs.get('document_title'),
            is_family_document=kwargs.get('is_family_document', False)
        )
    
    elif event_type in (
        EventType.ELEMENT_CREATED,
        EventType.ELEMENT_MODIFIED,
        EventType.ELEMENT_DELETED,
        EventType.ELEMENT_TYPE_CHANGED
    ):
        return ElementEventData(
            **base_kwargs,
            element_id=kwargs.get('element_id'),
            element_type=kwargs.get('element_type'),
            category=kwargs.get('category'),
            parameters_changed=kwargs.get('parameters_changed', []),
            old_values=kwargs.get('old_values', {}),
            new_values=kwargs.get('new_values', {})
        )
    
    elif event_type in (
        EventType.TRANSACTION_STARTED,
        EventType.TRANSACTION_COMMITTED,
        EventType.TRANSACTION_ROLLED_BACK
    ):
        return TransactionEventData(
            **base_kwargs,
            transaction_name=kwargs.get('transaction_name'),
            transaction_id=kwargs.get('transaction_id'),
            elements_affected=kwargs.get('elements_affected', []),
            operation_count=kwargs.get('operation_count', 0)
        )
    
    elif event_type in (
        EventType.PARAMETER_CHANGED,
        EventType.PARAMETER_ADDED,
        EventType.PARAMETER_REMOVED
    ):
        return ParameterEventData(
            **base_kwargs,
            element_id=kwargs.get('element_id'),
            parameter_name=kwargs.get('parameter_name', ''),
            old_value=kwargs.get('old_value'),
            new_value=kwargs.get('new_value'),
            parameter_type=kwargs.get('parameter_type'),
            storage_type=kwargs.get('storage_type')
        )
    
    elif event_type in (
        EventType.VIEW_ACTIVATED,
        EventType.VIEW_DEACTIVATED,
        EventType.VIEW_CREATED
    ):
        return ViewEventData(
            **base_kwargs,
            view_id=kwargs.get('view_id'),
            view_name=kwargs.get('view_name'),
            view_type=kwargs.get('view_type'),
            is_3d_view=kwargs.get('is_3d_view', False),
            previous_view_id=kwargs.get('previous_view_id')
        )
    
    elif event_type == EventType.SELECTION_CHANGED:
        return SelectionEventData(
            **base_kwargs,
            selected_elements=kwargs.get('selected_elements', []),
            previously_selected=kwargs.get('previously_selected', []),
            added_to_selection=kwargs.get('added_to_selection', []),
            removed_from_selection=kwargs.get('removed_from_selection', [])
        )
    
    else:
        # Default to base EventData
        return EventData(**base_kwargs)


# Type aliases
EventHandler = Union['BaseEventHandler', 'AsyncEventHandler', callable]
EventCallback = callable