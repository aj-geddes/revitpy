"""
Change tracking system for RevitPy ORM.

This module provides comprehensive change tracking with dirty checking,
batch operations, and transaction support for efficient Revit element updates.
"""

from __future__ import annotations

import threading
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import (
    Any, Dict, List, Optional, Set, Type, TypeVar, Union,
    Callable, Iterator, Tuple
)
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from loguru import logger

from .types import ElementState, ChangeSet, BatchOperation, BatchOperationType, ElementId
from .exceptions import ChangeTrackingError, BatchOperationError


T = TypeVar('T')
E = TypeVar('E', bound='Element')


class ChangeType(Enum):
    """Types of changes that can be tracked."""
    
    PROPERTY_CHANGED = "property_changed"
    RELATIONSHIP_ADDED = "relationship_added"
    RELATIONSHIP_REMOVED = "relationship_removed"
    ENTITY_ADDED = "entity_added"
    ENTITY_DELETED = "entity_deleted"
    ENTITY_ATTACHED = "entity_attached"
    ENTITY_DETACHED = "entity_detached"


@dataclass
class PropertyChange:
    """Represents a change to an entity property."""
    
    entity_id: ElementId
    entity_type: str
    property_name: str
    old_value: Any
    new_value: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    change_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    @property
    def has_change(self) -> bool:
        """Check if there's actually a change."""
        return self.old_value != self.new_value
    
    def __hash__(self) -> int:
        return hash(self.change_id)


@dataclass
class RelationshipChange:
    """Represents a change to an entity relationship."""
    
    entity_id: ElementId
    entity_type: str
    relationship_name: str
    change_type: ChangeType
    related_entity_id: Optional[ElementId] = None
    related_entity_type: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    change_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __hash__(self) -> int:
        return hash(self.change_id)


class EntityTracker:
    """Tracks changes for a single entity."""
    
    def __init__(self, entity: Any, entity_id: ElementId) -> None:
        self.entity_id = entity_id
        self.entity_type = type(entity).__name__
        self.entity_ref = entity  # Direct reference to entity
        self.state = ElementState.UNCHANGED
        self.original_values: Dict[str, Any] = {}
        self.current_values: Dict[str, Any] = {}
        self.property_changes: Dict[str, PropertyChange] = {}
        self.relationship_changes: List[RelationshipChange] = []
        self.created_at = datetime.utcnow()
        self.last_modified = datetime.utcnow()
        self.version = 0
    
    @property
    def is_dirty(self) -> bool:
        """Check if entity has any changes."""
        return (
            self.state != ElementState.UNCHANGED or
            bool(self.property_changes) or
            bool(self.relationship_changes)
        )
    
    @property
    def changed_properties(self) -> Set[str]:
        """Get names of changed properties."""
        return set(self.property_changes.keys())
    
    def snapshot_current_state(self) -> None:
        """Take snapshot of current entity state."""
        if hasattr(self.entity_ref, '__dict__'):
            # For regular Python objects
            for attr_name, attr_value in self.entity_ref.__dict__.items():
                if not attr_name.startswith('_'):
                    self.original_values[attr_name] = self._deep_copy_value(attr_value)
        
        # For custom property getters
        if hasattr(self.entity_ref, '_property_mappings'):
            for prop_name in self.entity_ref._property_mappings:
                try:
                    value = getattr(self.entity_ref, prop_name)
                    self.original_values[prop_name] = self._deep_copy_value(value)
                except Exception as e:
                    logger.warning(f"Failed to snapshot property {prop_name}: {e}")
        
        self.state = ElementState.UNCHANGED
        self.version += 1
        self.last_modified = datetime.utcnow()
    
    def track_property_change(self, property_name: str, old_value: Any, new_value: Any) -> None:
        """Track a property change."""
        if old_value == new_value:
            # Remove change if values are the same
            if property_name in self.property_changes:
                del self.property_changes[property_name]
        else:
            change = PropertyChange(
                entity_id=self.entity_id,
                entity_type=self.entity_type,
                property_name=property_name,
                old_value=old_value,
                new_value=new_value
            )
            self.property_changes[property_name] = change
            
            if self.state == ElementState.UNCHANGED:
                self.state = ElementState.MODIFIED
        
        self.current_values[property_name] = new_value
        self.last_modified = datetime.utcnow()
    
    def track_relationship_change(
        self,
        relationship_name: str,
        change_type: ChangeType,
        related_entity_id: Optional[ElementId] = None,
        related_entity_type: Optional[str] = None
    ) -> None:
        """Track a relationship change."""
        change = RelationshipChange(
            entity_id=self.entity_id,
            entity_type=self.entity_type,
            relationship_name=relationship_name,
            change_type=change_type,
            related_entity_id=related_entity_id,
            related_entity_type=related_entity_type
        )
        
        self.relationship_changes.append(change)
        
        if self.state == ElementState.UNCHANGED:
            self.state = ElementState.MODIFIED
        
        self.last_modified = datetime.utcnow()
    
    def accept_changes(self) -> None:
        """Accept all changes and reset tracking."""
        # Move current values to original values
        self.original_values.update(self.current_values)
        
        # Clear change tracking
        self.property_changes.clear()
        self.relationship_changes.clear()
        self.current_values.clear()
        
        # Reset state
        self.state = ElementState.UNCHANGED
        self.version += 1
        self.last_modified = datetime.utcnow()
    
    def reject_changes(self) -> None:
        """Reject all changes and revert to original state."""
        # Revert properties to original values
        for prop_name, original_value in self.original_values.items():
            try:
                if hasattr(self.entity_ref, prop_name):
                    setattr(self.entity_ref, prop_name, original_value)
            except Exception as e:
                logger.warning(f"Failed to revert property {prop_name}: {e}")
        
        # Clear change tracking
        self.property_changes.clear()
        self.relationship_changes.clear()
        self.current_values.clear()
        
        # Reset state
        self.state = ElementState.UNCHANGED
        self.last_modified = datetime.utcnow()
    
    def get_change_set(self) -> ChangeSet:
        """Get change set for this entity."""
        return ChangeSet(
            entity_id=self.entity_id,
            entity_type=self.entity_type,
            original_values=self.original_values.copy(),
            current_values=self.current_values.copy(),
            state=self.state,
            timestamp=self.last_modified
        )
    
    def _deep_copy_value(self, value: Any) -> Any:
        """Create a deep copy of a value for tracking."""
        # Simplified deep copy - in practice you might want to use copy.deepcopy
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        elif isinstance(value, (list, tuple)):
            return type(value)(self._deep_copy_value(item) for item in value)
        elif isinstance(value, dict):
            return {k: self._deep_copy_value(v) for k, v in value.items()}
        else:
            # For complex objects, store reference
            return value


class ChangeTracker:
    """
    Main change tracking system for the ORM.
    
    Provides comprehensive change tracking with dirty checking, batch operations,
    and transaction support for efficient database updates.
    """
    
    def __init__(self, thread_safe: bool = True) -> None:
        self._tracked_entities: Dict[ElementId, EntityTracker] = {}
        self._entity_states: Dict[ElementId, ElementState] = {}
        self._batch_operations: List[BatchOperation] = []
        self._transaction_stack: List[str] = []
        self._change_callbacks: List[Callable[[PropertyChange], None]] = []
        self._lock = threading.RLock() if thread_safe else None
        self._auto_track = True
        self._change_counter = 0
    
    @property
    def auto_track(self) -> bool:
        """Check if automatic change tracking is enabled."""
        return self._auto_track
    
    @auto_track.setter
    def auto_track(self, value: bool) -> None:
        """Enable or disable automatic change tracking."""
        self._auto_track = value
    
    @property
    def has_changes(self) -> bool:
        """Check if there are any tracked changes."""
        with self._lock if self._lock else self._no_op():
            return any(tracker.is_dirty for tracker in self._tracked_entities.values())
    
    @property
    def changed_entities(self) -> List[ElementId]:
        """Get list of entities with changes."""
        with self._lock if self._lock else self._no_op():
            return [
                entity_id for entity_id, tracker in self._tracked_entities.items()
                if tracker.is_dirty
            ]
    
    @property
    def change_count(self) -> int:
        """Get total number of changes."""
        with self._lock if self._lock else self._no_op():
            return sum(
                len(tracker.property_changes) + len(tracker.relationship_changes)
                for tracker in self._tracked_entities.values()
            )
    
    def attach(self, entity: Any, entity_id: Optional[ElementId] = None) -> None:
        """Start tracking an entity."""
        with self._lock if self._lock else self._no_op():
            if entity_id is None:
                entity_id = self._get_entity_id(entity)
            
            if entity_id in self._tracked_entities:
                logger.debug(f"Entity {entity_id} is already being tracked")
                return
            
            try:
                tracker = EntityTracker(entity, entity_id)
                tracker.snapshot_current_state()
                
                self._tracked_entities[entity_id] = tracker
                self._entity_states[entity_id] = ElementState.UNCHANGED
                
                logger.debug(f"Started tracking entity {entity_id}")
                
            except Exception as e:
                logger.error(f"Failed to attach entity {entity_id}: {e}")
                raise ChangeTrackingError(
                    f"Failed to attach entity for tracking",
                    entity=entity,
                    tracking_operation="attach",
                    cause=e
                )
    
    def detach(self, entity_id: ElementId) -> None:
        """Stop tracking an entity."""
        with self._lock if self._lock else self._no_op():
            if entity_id in self._tracked_entities:
                del self._tracked_entities[entity_id]
                
            if entity_id in self._entity_states:
                del self._entity_states[entity_id]
            
            logger.debug(f"Stopped tracking entity {entity_id}")
    
    def track_property_change(
        self,
        entity: Any,
        property_name: str,
        old_value: Any,
        new_value: Any
    ) -> None:
        """Track a property change on an entity."""
        if not self._auto_track:
            return
        
        with self._lock if self._lock else self._no_op():
            entity_id = self._get_entity_id(entity)
            
            # Auto-attach if not already tracked
            if entity_id not in self._tracked_entities:
                self.attach(entity, entity_id)
            
            tracker = self._tracked_entities[entity_id]
            tracker.track_property_change(property_name, old_value, new_value)
            
            # Update entity state
            if tracker.is_dirty:
                self._entity_states[entity_id] = tracker.state
            
            # Notify callbacks
            if property_name in tracker.property_changes:
                change = tracker.property_changes[property_name]
                for callback in self._change_callbacks:
                    try:
                        callback(change)
                    except Exception as e:
                        logger.warning(f"Change callback error: {e}")
            
            self._change_counter += 1
            logger.debug(f"Tracked property change: {entity_id}.{property_name}")
    
    def track_relationship_change(
        self,
        entity: Any,
        relationship_name: str,
        change_type: ChangeType,
        related_entity: Optional[Any] = None
    ) -> None:
        """Track a relationship change on an entity."""
        if not self._auto_track:
            return
        
        with self._lock if self._lock else self._no_op():
            entity_id = self._get_entity_id(entity)
            
            # Auto-attach if not already tracked
            if entity_id not in self._tracked_entities:
                self.attach(entity, entity_id)
            
            related_entity_id = None
            related_entity_type = None
            
            if related_entity is not None:
                related_entity_id = self._get_entity_id(related_entity)
                related_entity_type = type(related_entity).__name__
            
            tracker = self._tracked_entities[entity_id]
            tracker.track_relationship_change(
                relationship_name,
                change_type,
                related_entity_id,
                related_entity_type
            )
            
            # Update entity state
            if tracker.is_dirty:
                self._entity_states[entity_id] = tracker.state
            
            self._change_counter += 1
            logger.debug(f"Tracked relationship change: {entity_id}.{relationship_name}")
    
    def mark_as_added(self, entity: Any) -> None:
        """Mark entity as newly added."""
        with self._lock if self._lock else self._no_op():
            entity_id = self._get_entity_id(entity)
            
            if entity_id not in self._tracked_entities:
                self.attach(entity, entity_id)
            
            tracker = self._tracked_entities[entity_id]
            tracker.state = ElementState.ADDED
            self._entity_states[entity_id] = ElementState.ADDED
            
            logger.debug(f"Marked entity as added: {entity_id}")
    
    def mark_as_deleted(self, entity: Any) -> None:
        """Mark entity as deleted."""
        with self._lock if self._lock else self._no_op():
            entity_id = self._get_entity_id(entity)
            
            if entity_id not in self._tracked_entities:
                self.attach(entity, entity_id)
            
            tracker = self._tracked_entities[entity_id]
            tracker.state = ElementState.DELETED
            self._entity_states[entity_id] = ElementState.DELETED
            
            logger.debug(f"Marked entity as deleted: {entity_id}")
    
    def get_entity_state(self, entity_id: ElementId) -> ElementState:
        """Get the current state of an entity."""
        with self._lock if self._lock else self._no_op():
            return self._entity_states.get(entity_id, ElementState.DETACHED)
    
    def get_changes(self, entity_id: ElementId) -> Optional[ChangeSet]:
        """Get change set for a specific entity."""
        with self._lock if self._lock else self._no_op():
            tracker = self._tracked_entities.get(entity_id)
            if tracker:
                return tracker.get_change_set()
            return None
    
    def get_all_changes(self) -> List[ChangeSet]:
        """Get change sets for all tracked entities."""
        with self._lock if self._lock else self._no_op():
            changes = []
            for tracker in self._tracked_entities.values():
                if tracker.is_dirty:
                    changes.append(tracker.get_change_set())
            return changes
    
    def accept_changes(self, entity_id: Optional[ElementId] = None) -> None:
        """Accept changes for specific entity or all entities."""
        with self._lock if self._lock else self._no_op():
            if entity_id is not None:
                # Accept changes for specific entity
                if entity_id in self._tracked_entities:
                    tracker = self._tracked_entities[entity_id]
                    tracker.accept_changes()
                    self._entity_states[entity_id] = ElementState.UNCHANGED
            else:
                # Accept changes for all entities
                for entity_id, tracker in self._tracked_entities.items():
                    tracker.accept_changes()
                    self._entity_states[entity_id] = ElementState.UNCHANGED
            
            logger.debug(f"Accepted changes for {'all entities' if entity_id is None else entity_id}")
    
    def reject_changes(self, entity_id: Optional[ElementId] = None) -> None:
        """Reject changes for specific entity or all entities."""
        with self._lock if self._lock else self._no_op():
            if entity_id is not None:
                # Reject changes for specific entity
                if entity_id in self._tracked_entities:
                    tracker = self._tracked_entities[entity_id]
                    tracker.reject_changes()
                    self._entity_states[entity_id] = ElementState.UNCHANGED
            else:
                # Reject changes for all entities
                for entity_id, tracker in self._tracked_entities.items():
                    tracker.reject_changes()
                    self._entity_states[entity_id] = ElementState.UNCHANGED
            
            logger.debug(f"Rejected changes for {'all entities' if entity_id is None else entity_id}")
    
    def clear(self) -> None:
        """Clear all tracked entities and changes."""
        with self._lock if self._lock else self._no_op():
            self._tracked_entities.clear()
            self._entity_states.clear()
            self._batch_operations.clear()
            self._change_counter = 0
            
            logger.debug("Cleared all tracked changes")
    
    def create_batch_operation(
        self,
        operation_type: BatchOperationType,
        entity: Any,
        properties: Optional[Dict[str, Any]] = None
    ) -> BatchOperation:
        """Create a batch operation for an entity."""
        return BatchOperation(
            operation_type=operation_type,
            entity=entity,
            properties=properties or {}
        )
    
    def add_batch_operation(self, operation: BatchOperation) -> None:
        """Add a batch operation to the queue."""
        with self._lock if self._lock else self._no_op():
            self._batch_operations.append(operation)
            logger.debug(f"Added batch operation: {operation.operation_type} for {operation.entity}")
    
    def get_batch_operations(self) -> List[BatchOperation]:
        """Get all queued batch operations."""
        with self._lock if self._lock else self._no_op():
            return self._batch_operations.copy()
    
    def clear_batch_operations(self) -> None:
        """Clear all queued batch operations."""
        with self._lock if self._lock else self._no_op():
            self._batch_operations.clear()
            logger.debug("Cleared batch operations")
    
    def add_change_callback(self, callback: Callable[[PropertyChange], None]) -> None:
        """Add callback for property changes."""
        self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: Callable[[PropertyChange], None]) -> None:
        """Remove property change callback."""
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
    
    def is_tracked(self, entity_id: ElementId) -> bool:
        """Check if entity is being tracked."""
        with self._lock if self._lock else self._no_op():
            return entity_id in self._tracked_entities
    
    def get_tracked_count(self) -> int:
        """Get number of tracked entities."""
        with self._lock if self._lock else self._no_op():
            return len(self._tracked_entities)
    
    def _get_entity_id(self, entity: Any) -> ElementId:
        """Get entity ID from entity object."""
        if hasattr(entity, 'id'):
            return entity.id
        elif hasattr(entity, 'Id'):
            return entity.Id
        elif hasattr(entity, '__hash__') and entity.__hash__ is not None:
            return hash(entity)
        else:
            return id(entity)
    
    def _no_op(self):
        """No-op context manager for non-thread-safe mode."""
        return self
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Decorators for automatic change tracking

def track_changes(func):
    """Decorator to automatically track property changes."""
    def wrapper(self, *args, **kwargs):
        if hasattr(self, '_change_tracker') and self._change_tracker:
            # Get old value
            if hasattr(self, func.__name__.replace('set_', '')):
                old_value = getattr(self, func.__name__.replace('set_', ''))
            else:
                old_value = None
            
            # Call the function
            result = func(self, *args, **kwargs)
            
            # Get new value
            if hasattr(self, func.__name__.replace('set_', '')):
                new_value = getattr(self, func.__name__.replace('set_', ''))
            else:
                new_value = args[0] if args else None
            
            # Track the change
            property_name = func.__name__.replace('set_', '')
            self._change_tracker.track_property_change(
                self, property_name, old_value, new_value
            )
            
            return result
        else:
            return func(self, *args, **kwargs)
    
    return wrapper