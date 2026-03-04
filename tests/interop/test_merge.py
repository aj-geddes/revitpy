"""
Unit tests for SpeckleMerge.
"""

import pytest

from revitpy.interop.exceptions import MergeConflictError
from revitpy.interop.merge import SpeckleMerge
from revitpy.interop.types import ConflictResolution, DiffEntry


class TestSpeckleMerge:
    """Test merge and conflict resolution strategies."""

    # ------------------------------------------------------------------
    # LOCAL_WINS
    # ------------------------------------------------------------------

    def test_merge_local_wins_resolves_conflicts(self):
        """LOCAL_WINS strategy should auto-resolve all conflicts."""
        merger = SpeckleMerge(resolution=ConflictResolution.LOCAL_WINS)
        local = [
            {"id": "1", "name": "Wall A", "height": 10},
        ]
        remote = [
            {"id": "1", "name": "Wall A", "height": 15},
        ]

        result = merger.merge(local, remote)

        assert result.conflict_count == 1
        assert result.merged_count == 1
        assert result.resolution == ConflictResolution.LOCAL_WINS

    def test_resolve_conflicts_local_wins(self):
        """resolve_conflicts with LOCAL_WINS should keep local values."""
        merger = SpeckleMerge()
        conflicts = [
            DiffEntry(
                element_id="1",
                change_type="modified",
                property_name="height",
                local_value=10,
                remote_value=15,
            ),
        ]

        resolved = merger.resolve_conflicts(conflicts, ConflictResolution.LOCAL_WINS)

        assert len(resolved) == 1
        assert resolved[0]["resolved_value"] == 10

    # ------------------------------------------------------------------
    # REMOTE_WINS
    # ------------------------------------------------------------------

    def test_merge_remote_wins_resolves_conflicts(self):
        """REMOTE_WINS strategy should auto-resolve all conflicts."""
        merger = SpeckleMerge(resolution=ConflictResolution.REMOTE_WINS)
        local = [
            {"id": "1", "name": "Wall A", "height": 10},
        ]
        remote = [
            {"id": "1", "name": "Wall A", "height": 15},
        ]

        result = merger.merge(local, remote)

        assert result.conflict_count == 1
        assert result.merged_count == 1
        assert result.resolution == ConflictResolution.REMOTE_WINS

    def test_resolve_conflicts_remote_wins(self):
        """resolve_conflicts with REMOTE_WINS should keep remote values."""
        merger = SpeckleMerge()
        conflicts = [
            DiffEntry(
                element_id="1",
                change_type="modified",
                property_name="height",
                local_value=10,
                remote_value=15,
            ),
        ]

        resolved = merger.resolve_conflicts(conflicts, ConflictResolution.REMOTE_WINS)

        assert len(resolved) == 1
        assert resolved[0]["resolved_value"] == 15

    # ------------------------------------------------------------------
    # MANUAL
    # ------------------------------------------------------------------

    def test_merge_manual_raises_on_conflicts(self):
        """MANUAL strategy should raise MergeConflictError."""
        merger = SpeckleMerge(resolution=ConflictResolution.MANUAL)
        local = [
            {"id": "1", "name": "Wall A", "height": 10},
        ]
        remote = [
            {"id": "1", "name": "Wall A", "height": 15},
        ]

        with pytest.raises(MergeConflictError, match="Manual resolution required"):
            merger.merge(local, remote)

    def test_resolve_conflicts_manual_raises(self):
        """resolve_conflicts with MANUAL should raise MergeConflictError."""
        merger = SpeckleMerge()
        conflicts = [
            DiffEntry(
                element_id="1",
                change_type="modified",
                property_name="height",
                local_value=10,
                remote_value=15,
            ),
        ]

        with pytest.raises(MergeConflictError, match="Cannot auto-resolve"):
            merger.resolve_conflicts(conflicts, ConflictResolution.MANUAL)

    # ------------------------------------------------------------------
    # No conflicts
    # ------------------------------------------------------------------

    def test_merge_without_conflicts(self):
        """Merge with only additions and removals should report zero conflicts."""
        merger = SpeckleMerge()
        local = [
            {"id": "1", "name": "Wall A"},
            {"id": "2", "name": "Wall B"},
        ]
        remote = [
            {"id": "1", "name": "Wall A"},
            {"id": "3", "name": "Wall C"},
        ]

        result = merger.merge(local, remote)

        assert result.conflict_count == 0
        assert result.merged_count == 2  # 1 added + 1 removed
        assert result.conflicts == []

    # ------------------------------------------------------------------
    # Pre-computed diff entries
    # ------------------------------------------------------------------

    def test_merge_with_precomputed_diff(self):
        """merge should accept pre-computed diff entries."""
        merger = SpeckleMerge()
        diff_entries = [
            DiffEntry(element_id="1", change_type="added"),
            DiffEntry(
                element_id="2",
                change_type="modified",
                property_name="height",
                local_value=10,
                remote_value=15,
            ),
        ]

        result = merger.merge([], [], diff_entries=diff_entries)

        assert result.merged_count == 2  # 1 added + 1 conflict resolved
        assert result.conflict_count == 1

    # ------------------------------------------------------------------
    # Multiple conflicts
    # ------------------------------------------------------------------

    def test_multiple_conflicts_resolved(self):
        """Multiple conflicts should all be counted and resolved."""
        merger = SpeckleMerge(resolution=ConflictResolution.LOCAL_WINS)
        local = [
            {"id": "1", "name": "A", "height": 10, "width": 0.5},
        ]
        remote = [
            {"id": "1", "name": "B", "height": 15, "width": 0.6},
        ]

        result = merger.merge(local, remote)

        # name, height, and width are all different
        assert result.conflict_count == 3
        assert result.merged_count == 3

    def test_merge_conflict_error_contains_details(self):
        """MergeConflictError should include element and conflict info."""
        merger = SpeckleMerge(resolution=ConflictResolution.MANUAL)
        local = [{"id": "1", "name": "A", "height": 10}]
        remote = [{"id": "1", "name": "B", "height": 15}]

        with pytest.raises(MergeConflictError) as exc_info:
            merger.merge(local, remote)

        error = exc_info.value
        assert len(error.conflicts) == 2
