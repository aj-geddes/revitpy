"""
Tests for the IFC diff engine.
"""

from types import SimpleNamespace

import pytest

from revitpy.ifc.diff import IfcDiff
from revitpy.ifc.types import IfcChangeType, IfcDiffEntry, IfcDiffResult


class TestIfcDiff:
    """Tests for IfcDiff."""

    def test_no_changes(self, sample_elements):
        """Comparing identical lists should produce no differences."""
        differ = IfcDiff()
        result = differ.compare(sample_elements, list(sample_elements))

        assert len(result.added) == 0
        assert len(result.modified) == 0
        assert len(result.removed) == 0

    def test_added_elements(self):
        """New elements should appear in the added list."""
        differ = IfcDiff()

        old = [SimpleNamespace(id="a", name="Wall A", category="WallElement")]
        new = [
            SimpleNamespace(id="a", name="Wall A", category="WallElement"),
            SimpleNamespace(id="b", name="Wall B", category="WallElement"),
        ]

        result = differ.compare(old, new)

        assert len(result.added) == 1
        assert result.added[0].global_id == "b"
        assert result.added[0].change_type == IfcChangeType.ADDED
        assert result.summary["added"] == 1

    def test_removed_elements(self):
        """Deleted elements should appear in the removed list."""
        differ = IfcDiff()

        old = [
            SimpleNamespace(id="a", name="Wall A", category="WallElement"),
            SimpleNamespace(id="b", name="Wall B", category="WallElement"),
        ]
        new = [SimpleNamespace(id="a", name="Wall A", category="WallElement")]

        result = differ.compare(old, new)

        assert len(result.removed) == 1
        assert result.removed[0].global_id == "b"
        assert result.removed[0].change_type == IfcChangeType.REMOVED
        assert result.summary["removed"] == 1

    def test_modified_elements(self):
        """Changed properties should appear in the modified list."""
        differ = IfcDiff()

        old = [
            SimpleNamespace(id="a", name="Wall A", category="WallElement", height=3.0),
        ]
        new = [
            SimpleNamespace(
                id="a", name="Wall A Modified", category="WallElement", height=3.5
            ),
        ]

        result = differ.compare(old, new)

        assert len(result.modified) == 1
        entry = result.modified[0]
        assert entry.global_id == "a"
        assert entry.change_type == IfcChangeType.MODIFIED
        assert "name" in entry.changed_fields
        assert "height" in entry.changed_fields
        assert result.summary["modified"] == 1

    def test_mixed_changes(self):
        """Combined add/modify/remove should all be detected."""
        differ = IfcDiff()

        old = [
            SimpleNamespace(id="1", name="Keep", category="WallElement"),
            SimpleNamespace(id="2", name="Remove", category="WallElement"),
            SimpleNamespace(
                id="3", name="Modify Me", category="DoorElement", height=2.0
            ),
        ]
        new = [
            SimpleNamespace(id="1", name="Keep", category="WallElement"),
            SimpleNamespace(
                id="3", name="Modified", category="DoorElement", height=2.1
            ),
            SimpleNamespace(id="4", name="Added", category="WindowElement"),
        ]

        result = differ.compare(old, new)

        assert len(result.added) == 1
        assert len(result.modified) == 1
        assert len(result.removed) == 1

        assert result.added[0].global_id == "4"
        assert result.removed[0].global_id == "2"
        assert result.modified[0].global_id == "3"

    def test_result_is_ifc_diff_result(self, sample_elements):
        """compare should return an IfcDiffResult dataclass."""
        differ = IfcDiff()
        result = differ.compare(sample_elements, sample_elements)
        assert isinstance(result, IfcDiffResult)

    def test_diff_entries_are_correct_type(self):
        """Each entry in the result should be an IfcDiffEntry."""
        differ = IfcDiff()

        old = [SimpleNamespace(id="a", name="Old", category="WallElement")]
        new = [SimpleNamespace(id="b", name="New", category="WallElement")]

        result = differ.compare(old, new)

        for entry in result.added + result.removed:
            assert isinstance(entry, IfcDiffEntry)

    def test_summary_counts(self):
        """The summary dict should have correct counts."""
        differ = IfcDiff()

        old = [SimpleNamespace(id=str(i), name=f"E{i}", category="W") for i in range(5)]
        new = [
            SimpleNamespace(id=str(i), name=f"E{i}", category="W") for i in range(3, 8)
        ]

        result = differ.compare(old, new)

        assert result.summary["added"] == len(result.added)
        assert result.summary["modified"] == len(result.modified)
        assert result.summary["removed"] == len(result.removed)

    def test_dict_elements(self):
        """compare should also work with dict-based elements."""
        differ = IfcDiff()

        old = [{"id": "a", "name": "Wall A", "type": "WallElement"}]
        new = [{"id": "a", "name": "Wall A Updated", "type": "WallElement"}]

        result = differ.compare(old, new)

        assert len(result.modified) == 1
        assert "name" in result.modified[0].changed_fields

    def test_global_id_preferred_over_id(self):
        """Elements with global_id should use it over id."""
        differ = IfcDiff()

        old = [SimpleNamespace(global_id="g1", id="1", name="A", category="W")]
        new = [SimpleNamespace(global_id="g1", id="1", name="B", category="W")]

        result = differ.compare(old, new)

        assert len(result.modified) == 1
        assert result.modified[0].global_id == "g1"

    def test_empty_lists(self):
        """Comparing two empty lists should produce no changes."""
        differ = IfcDiff()
        result = differ.compare([], [])

        assert len(result.added) == 0
        assert len(result.modified) == 0
        assert len(result.removed) == 0
