"""
Unit tests for SpeckleDiff.
"""

import pytest

from revitpy.interop.diff import SpeckleDiff


class TestSpeckleDiff:
    """Test element diff detection between local and remote sets."""

    @pytest.fixture
    def differ(self):
        """Create a fresh diff instance."""
        return SpeckleDiff()

    # ------------------------------------------------------------------
    # Added elements
    # ------------------------------------------------------------------

    def test_detect_added_elements(self, differ):
        """Elements present locally but not remotely are 'added'."""
        local = [
            {"id": "1", "name": "Wall A"},
            {"id": "2", "name": "Wall B"},
        ]
        remote = [
            {"id": "1", "name": "Wall A"},
        ]

        entries = differ.compare(local, remote)
        added = [e for e in entries if e.change_type == "added"]

        assert len(added) == 1
        assert added[0].element_id == "2"

    # ------------------------------------------------------------------
    # Removed elements
    # ------------------------------------------------------------------

    def test_detect_removed_elements(self, differ):
        """Elements present remotely but not locally are 'removed'."""
        local = [
            {"id": "1", "name": "Wall A"},
        ]
        remote = [
            {"id": "1", "name": "Wall A"},
            {"id": "3", "name": "Wall C"},
        ]

        entries = differ.compare(local, remote)
        removed = [e for e in entries if e.change_type == "removed"]

        assert len(removed) == 1
        assert removed[0].element_id == "3"

    # ------------------------------------------------------------------
    # Modified elements
    # ------------------------------------------------------------------

    def test_detect_modified_properties(self, differ):
        """Property changes on shared elements are 'modified'."""
        local = [
            {"id": "1", "name": "Wall A", "height": 10},
        ]
        remote = [
            {"id": "1", "name": "Wall A", "height": 12},
        ]

        entries = differ.compare(local, remote)
        modified = [e for e in entries if e.change_type == "modified"]

        assert len(modified) == 1
        assert modified[0].element_id == "1"
        assert modified[0].property_name == "height"
        assert modified[0].local_value == 10
        assert modified[0].remote_value == 12

    def test_multiple_property_changes(self, differ):
        """Multiple property diffs should produce multiple entries."""
        local = [
            {"id": "1", "name": "Wall A", "height": 10, "length": 20},
        ]
        remote = [
            {"id": "1", "name": "Wall B", "height": 12, "length": 20},
        ]

        entries = differ.compare(local, remote)
        modified = [e for e in entries if e.change_type == "modified"]

        assert len(modified) == 2
        prop_names = {e.property_name for e in modified}
        assert prop_names == {"name", "height"}

    # ------------------------------------------------------------------
    # No changes
    # ------------------------------------------------------------------

    def test_identical_sets_produce_no_entries(self, differ):
        """Identical element sets should produce an empty diff."""
        elements = [
            {"id": "1", "name": "Wall A", "height": 10},
            {"id": "2", "name": "Wall B", "height": 8},
        ]

        entries = differ.compare(elements, elements)
        assert entries == []

    def test_has_changes_false_for_identical(self, differ):
        """has_changes should return False when no differences exist."""
        elements = [{"id": "1", "name": "Wall"}]
        assert differ.has_changes(elements, elements) is False

    def test_has_changes_true_for_different(self, differ):
        """has_changes should return True when differences exist."""
        local = [{"id": "1", "name": "Wall A"}]
        remote = [{"id": "1", "name": "Wall B"}]
        assert differ.has_changes(local, remote) is True

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_sets(self, differ):
        """Comparing two empty sets should produce no entries."""
        assert differ.compare([], []) == []

    def test_ignored_keys_excluded(self, differ):
        """Keys in the ignored set should not generate diff entries."""
        local = [{"id": "1", "speckle_type": "A", "name": "Wall"}]
        remote = [{"id": "1", "speckle_type": "B", "name": "Wall"}]

        entries = differ.compare(local, remote)
        assert entries == []

    def test_element_id_fallback(self, differ):
        """Should fall back to element_id key when id is missing."""
        local = [{"element_id": "1", "name": "Wall A"}]
        remote = [{"element_id": "1", "name": "Wall B"}]

        entries = differ.compare(local, remote)
        modified = [e for e in entries if e.change_type == "modified"]
        assert len(modified) == 1
        assert modified[0].element_id == "1"

    def test_mixed_additions_removals_modifications(self, differ):
        """Should handle a mix of all change types."""
        local = [
            {"id": "1", "name": "Unchanged"},
            {"id": "2", "name": "Modified", "height": 10},
            {"id": "4", "name": "Added"},
        ]
        remote = [
            {"id": "1", "name": "Unchanged"},
            {"id": "2", "name": "Modified", "height": 15},
            {"id": "3", "name": "Removed"},
        ]

        entries = differ.compare(local, remote)

        change_types = {e.change_type for e in entries}
        assert change_types == {"added", "removed", "modified"}

        added = [e for e in entries if e.change_type == "added"]
        removed = [e for e in entries if e.change_type == "removed"]
        modified = [e for e in entries if e.change_type == "modified"]

        assert len(added) == 1
        assert added[0].element_id == "4"
        assert len(removed) == 1
        assert removed[0].element_id == "3"
        assert len(modified) == 1
        assert modified[0].property_name == "height"
