"""
Unit tests for change tracking functionality.
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch
from datetime import datetime

from revitpy.orm.change_tracker import (
    ChangeTracker, EntityTracker, PropertyChange, RelationshipChange,
    ChangeType, track_changes
)
from revitpy.orm.types import ElementState, ChangeSet, BatchOperation, BatchOperationType
from revitpy.orm.exceptions import ChangeTrackingError


class MockElement:
    """Mock element for testing."""
    
    def __init__(self, id: int, name: str, category: str = "Wall"):
        self.id = id
        self.name = name
        self.category = category
        self._property_mappings = {"name": "Name", "category": "Category"}
        self._change_tracker = None
    
    def __eq__(self, other):
        return isinstance(other, MockElement) and self.id == other.id
    
    def __hash__(self):
        return hash(self.id)


@pytest.fixture
def mock_element():
    """Create mock element for testing."""
    return MockElement(1, "Test Wall", "Wall")


@pytest.fixture
def change_tracker():
    """Create change tracker for testing."""
    return ChangeTracker(thread_safe=True)


class TestPropertyChange:
    """Test PropertyChange functionality."""
    
    def test_property_change_creation(self):
        """Test creating property change."""
        change = PropertyChange(
            entity_id=1,
            entity_type="MockElement",
            property_name="name",
            old_value="Old Name",
            new_value="New Name"
        )
        
        assert change.entity_id == 1
        assert change.entity_type == "MockElement"
        assert change.property_name == "name"
        assert change.old_value == "Old Name"
        assert change.new_value == "New Name"
        assert change.has_change is True
        assert isinstance(change.timestamp, datetime)
    
    def test_no_change(self):
        """Test property change with same values."""
        change = PropertyChange(
            entity_id=1,
            entity_type="MockElement",
            property_name="name",
            old_value="Same Value",
            new_value="Same Value"
        )
        
        assert change.has_change is False
    
    def test_change_id_uniqueness(self):
        """Test that change IDs are unique."""
        change1 = PropertyChange(1, "MockElement", "name", "old", "new1")
        change2 = PropertyChange(1, "MockElement", "name", "old", "new2")
        
        assert change1.change_id != change2.change_id
        assert hash(change1) != hash(change2)


class TestRelationshipChange:
    """Test RelationshipChange functionality."""
    
    def test_relationship_change_creation(self):
        """Test creating relationship change."""
        change = RelationshipChange(
            entity_id=1,
            entity_type="MockElement",
            relationship_name="related_elements",
            change_type=ChangeType.RELATIONSHIP_ADDED,
            related_entity_id=2,
            related_entity_type="RelatedElement"
        )
        
        assert change.entity_id == 1
        assert change.entity_type == "MockElement"
        assert change.relationship_name == "related_elements"
        assert change.change_type == ChangeType.RELATIONSHIP_ADDED
        assert change.related_entity_id == 2
        assert change.related_entity_type == "RelatedElement"
        assert isinstance(change.timestamp, datetime)
    
    def test_relationship_change_without_related(self):
        """Test relationship change without related entity."""
        change = RelationshipChange(
            entity_id=1,
            entity_type="MockElement",
            relationship_name="related_elements",
            change_type=ChangeType.RELATIONSHIP_REMOVED
        )
        
        assert change.related_entity_id is None
        assert change.related_entity_type is None


class TestEntityTracker:
    """Test EntityTracker functionality."""
    
    def test_entity_tracker_creation(self, mock_element):
        """Test creating entity tracker."""
        tracker = EntityTracker(mock_element, mock_element.id)
        
        assert tracker.entity_id == mock_element.id
        assert tracker.entity_type == "MockElement"
        assert tracker.entity_ref == mock_element
        assert tracker.state == ElementState.UNCHANGED
        assert not tracker.is_dirty
    
    def test_snapshot_current_state(self, mock_element):
        """Test taking snapshot of current state."""
        tracker = EntityTracker(mock_element, mock_element.id)
        tracker.snapshot_current_state()
        
        assert "name" in tracker.original_values
        assert "category" in tracker.original_values
        assert tracker.original_values["name"] == "Test Wall"
        assert tracker.original_values["category"] == "Wall"
        assert tracker.version == 1
    
    def test_track_property_change(self, mock_element):
        """Test tracking property changes."""
        tracker = EntityTracker(mock_element, mock_element.id)
        
        tracker.track_property_change("name", "Old Name", "New Name")
        
        assert tracker.is_dirty
        assert tracker.state == ElementState.MODIFIED
        assert "name" in tracker.property_changes
        assert "name" in tracker.changed_properties
        assert tracker.current_values["name"] == "New Name"
        
        # Check the property change
        change = tracker.property_changes["name"]
        assert change.old_value == "Old Name"
        assert change.new_value == "New Name"
    
    def test_track_same_value_change(self, mock_element):
        """Test tracking change with same value."""
        tracker = EntityTracker(mock_element, mock_element.id)
        
        tracker.track_property_change("name", "Same Value", "Same Value")
        
        assert not tracker.is_dirty
        assert "name" not in tracker.property_changes
    
    def test_track_relationship_change(self, mock_element):
        """Test tracking relationship changes."""
        tracker = EntityTracker(mock_element, mock_element.id)
        
        tracker.track_relationship_change(
            "related_elements",
            ChangeType.RELATIONSHIP_ADDED,
            related_entity_id=2
        )
        
        assert tracker.is_dirty
        assert tracker.state == ElementState.MODIFIED
        assert len(tracker.relationship_changes) == 1
        
        change = tracker.relationship_changes[0]
        assert change.relationship_name == "related_elements"
        assert change.change_type == ChangeType.RELATIONSHIP_ADDED
        assert change.related_entity_id == 2
    
    def test_accept_changes(self, mock_element):
        """Test accepting changes."""
        tracker = EntityTracker(mock_element, mock_element.id)
        
        # Make some changes
        tracker.track_property_change("name", "Old", "New")
        tracker.track_relationship_change("rel", ChangeType.RELATIONSHIP_ADDED)
        
        assert tracker.is_dirty
        
        # Accept changes
        tracker.accept_changes()
        
        assert not tracker.is_dirty
        assert tracker.state == ElementState.UNCHANGED
        assert len(tracker.property_changes) == 0
        assert len(tracker.relationship_changes) == 0
        assert tracker.version == 1
    
    def test_reject_changes(self, mock_element):
        """Test rejecting changes."""
        tracker = EntityTracker(mock_element, mock_element.id)
        tracker.snapshot_current_state()
        
        # Make changes
        tracker.track_property_change("name", "Test Wall", "Modified Name")
        assert tracker.is_dirty
        
        # Reject changes
        tracker.reject_changes()
        
        assert not tracker.is_dirty
        assert tracker.state == ElementState.UNCHANGED
        assert len(tracker.property_changes) == 0
        assert len(tracker.relationship_changes) == 0
        # Original value should be restored
        assert mock_element.name == "Test Wall"
    
    def test_get_change_set(self, mock_element):
        """Test getting change set."""
        tracker = EntityTracker(mock_element, mock_element.id)
        tracker.snapshot_current_state()
        tracker.track_property_change("name", "Old", "New")
        
        change_set = tracker.get_change_set()
        
        assert isinstance(change_set, ChangeSet)
        assert change_set.entity_id == mock_element.id
        assert change_set.entity_type == "MockElement"
        assert change_set.state == ElementState.MODIFIED
        assert change_set.has_changes
        assert "name" in change_set.changed_properties


class TestChangeTracker:
    """Test ChangeTracker functionality."""
    
    def test_change_tracker_creation(self):
        """Test creating change tracker."""
        tracker = ChangeTracker(thread_safe=True)
        
        assert tracker.auto_track is True
        assert not tracker.has_changes
        assert tracker.change_count == 0
        assert len(tracker.changed_entities) == 0
    
    def test_attach_entity(self, change_tracker, mock_element):
        """Test attaching entity to tracker."""
        change_tracker.attach(mock_element)
        
        assert change_tracker.is_tracked(mock_element.id)
        assert change_tracker.get_tracked_count() == 1
        assert change_tracker.get_entity_state(mock_element.id) == ElementState.UNCHANGED
    
    def test_detach_entity(self, change_tracker, mock_element):
        """Test detaching entity from tracker."""
        change_tracker.attach(mock_element)
        assert change_tracker.is_tracked(mock_element.id)
        
        change_tracker.detach(mock_element.id)
        assert not change_tracker.is_tracked(mock_element.id)
        assert change_tracker.get_tracked_count() == 0
    
    def test_track_property_change(self, change_tracker, mock_element):
        """Test tracking property changes."""
        change_tracker.track_property_change(mock_element, "name", "Old", "New")
        
        assert change_tracker.has_changes
        assert change_tracker.change_count == 1
        assert mock_element.id in change_tracker.changed_entities
        assert change_tracker.get_entity_state(mock_element.id) == ElementState.MODIFIED
    
    def test_track_relationship_change(self, change_tracker, mock_element):
        """Test tracking relationship changes."""
        related_element = MockElement(2, "Related", "Door")
        
        change_tracker.track_relationship_change(
            mock_element,
            "related_elements",
            ChangeType.RELATIONSHIP_ADDED,
            related_element
        )
        
        assert change_tracker.has_changes
        assert change_tracker.change_count == 1
    
    def test_mark_as_added(self, change_tracker, mock_element):
        """Test marking entity as added."""
        change_tracker.mark_as_added(mock_element)
        
        assert change_tracker.has_changes
        assert change_tracker.get_entity_state(mock_element.id) == ElementState.ADDED
    
    def test_mark_as_deleted(self, change_tracker, mock_element):
        """Test marking entity as deleted."""
        change_tracker.mark_as_deleted(mock_element)
        
        assert change_tracker.has_changes
        assert change_tracker.get_entity_state(mock_element.id) == ElementState.DELETED
    
    def test_get_changes(self, change_tracker, mock_element):
        """Test getting changes for entity."""
        change_tracker.track_property_change(mock_element, "name", "Old", "New")
        
        changes = change_tracker.get_changes(mock_element.id)
        
        assert changes is not None
        assert isinstance(changes, ChangeSet)
        assert changes.entity_id == mock_element.id
        assert changes.has_changes
    
    def test_get_all_changes(self, change_tracker):
        """Test getting all changes."""
        element1 = MockElement(1, "Element 1")
        element2 = MockElement(2, "Element 2")
        
        change_tracker.track_property_change(element1, "name", "Old1", "New1")
        change_tracker.track_property_change(element2, "name", "Old2", "New2")
        
        all_changes = change_tracker.get_all_changes()
        
        assert len(all_changes) == 2
        assert all(isinstance(change, ChangeSet) for change in all_changes)
        assert all(change.has_changes for change in all_changes)
    
    def test_accept_changes(self, change_tracker, mock_element):
        """Test accepting changes."""
        change_tracker.track_property_change(mock_element, "name", "Old", "New")
        assert change_tracker.has_changes
        
        change_tracker.accept_changes(mock_element.id)
        
        assert not change_tracker.has_changes
        assert change_tracker.change_count == 0
        assert change_tracker.get_entity_state(mock_element.id) == ElementState.UNCHANGED
    
    def test_accept_all_changes(self, change_tracker):
        """Test accepting all changes."""
        element1 = MockElement(1, "Element 1")
        element2 = MockElement(2, "Element 2")
        
        change_tracker.track_property_change(element1, "name", "Old1", "New1")
        change_tracker.track_property_change(element2, "name", "Old2", "New2")
        
        assert change_tracker.change_count == 2
        
        change_tracker.accept_changes()  # Accept all
        
        assert not change_tracker.has_changes
        assert change_tracker.change_count == 0
    
    def test_reject_changes(self, change_tracker, mock_element):
        """Test rejecting changes."""
        original_name = mock_element.name
        change_tracker.attach(mock_element)
        change_tracker.track_property_change(mock_element, "name", original_name, "Modified")
        
        assert change_tracker.has_changes
        
        change_tracker.reject_changes(mock_element.id)
        
        assert not change_tracker.has_changes
        assert change_tracker.change_count == 0
    
    def test_clear(self, change_tracker, mock_element):
        """Test clearing all changes."""
        change_tracker.track_property_change(mock_element, "name", "Old", "New")
        assert change_tracker.has_changes
        
        change_tracker.clear()
        
        assert not change_tracker.has_changes
        assert change_tracker.change_count == 0
        assert change_tracker.get_tracked_count() == 0
    
    def test_auto_track_disabled(self, mock_element):
        """Test with auto tracking disabled."""
        tracker = ChangeTracker(thread_safe=True)
        tracker.auto_track = False
        
        tracker.track_property_change(mock_element, "name", "Old", "New")
        
        # Should not track changes when auto_track is False
        assert not tracker.has_changes
        assert tracker.change_count == 0
    
    def test_batch_operations(self, change_tracker, mock_element):
        """Test batch operation management."""
        operation = change_tracker.create_batch_operation(
            BatchOperationType.UPDATE,
            mock_element,
            {"name": "New Name"}
        )
        
        assert operation.operation_type == BatchOperationType.UPDATE
        assert operation.entity == mock_element
        assert operation.properties["name"] == "New Name"
        
        change_tracker.add_batch_operation(operation)
        
        operations = change_tracker.get_batch_operations()
        assert len(operations) == 1
        assert operations[0] == operation
        
        change_tracker.clear_batch_operations()
        assert len(change_tracker.get_batch_operations()) == 0
    
    def test_change_callbacks(self, change_tracker, mock_element):
        """Test change callback functionality."""
        callback_calls = []
        
        def test_callback(change: PropertyChange):
            callback_calls.append(change)
        
        change_tracker.add_change_callback(test_callback)
        change_tracker.track_property_change(mock_element, "name", "Old", "New")
        
        assert len(callback_calls) == 1
        assert callback_calls[0].property_name == "name"
        
        # Remove callback
        change_tracker.remove_change_callback(test_callback)
        change_tracker.track_property_change(mock_element, "category", "Old", "New")
        
        assert len(callback_calls) == 1  # Should not increase
    
    def test_thread_safety(self, change_tracker):
        """Test thread-safe operations."""
        elements = [MockElement(i, f"Element {i}") for i in range(100)]
        
        def worker(start_idx, end_idx):
            for i in range(start_idx, end_idx):
                element = elements[i]
                change_tracker.track_property_change(element, "name", f"Old {i}", f"New {i}")
        
        # Use multiple threads
        threads = []
        for i in range(5):
            start = i * 20
            end = (i + 1) * 20
            thread = threading.Thread(target=worker, args=(start, end))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert change_tracker.change_count == 100
        assert len(change_tracker.changed_entities) == 100
    
    def test_error_handling(self, change_tracker):
        """Test error handling in change tracking."""
        # Test with invalid entity
        with pytest.raises(Exception):  # Should handle gracefully
            change_tracker.track_property_change(None, "name", "old", "new")


class TestTrackChangesDecorator:
    """Test track_changes decorator."""
    
    def test_decorator_functionality(self, change_tracker):
        """Test change tracking decorator."""
        
        class TestClass:
            def __init__(self):
                self._name = "Initial"
                self._change_tracker = change_tracker
            
            @property
            def name(self):
                return self._name
            
            @track_changes
            def set_name(self, value):
                self._name = value
        
        obj = TestClass()
        obj.set_name("Modified")
        
        # Should have tracked the change
        assert change_tracker.has_changes
    
    def test_decorator_without_tracker(self):
        """Test decorator when no change tracker is available."""
        
        class TestClass:
            def __init__(self):
                self._name = "Initial"
            
            @property
            def name(self):
                return self._name
            
            @track_changes
            def set_name(self, value):
                self._name = value
        
        obj = TestClass()
        # Should not raise error even without change tracker
        obj.set_name("Modified")
        assert obj.name == "Modified"


if __name__ == "__main__":
    pytest.main([__file__])