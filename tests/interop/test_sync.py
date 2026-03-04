"""
Unit tests for SpeckleSync.
"""

import pytest

from revitpy.interop.sync import SpeckleSync
from revitpy.interop.types import SyncDirection, SyncMode


# Lightweight mock element for unmapped type testing
class UnknownWidget:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestSpeckleSync:
    """Test push, pull, and bidirectional sync operations."""

    @pytest.fixture
    def syncer(self, mock_speckle_client):
        """Create a SpeckleSync with a mocked client."""
        return SpeckleSync(client=mock_speckle_client)

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_push_maps_and_sends_elements(self, syncer, sample_elements):
        """push should map elements and send them to Speckle."""
        result = await syncer.push(
            sample_elements,
            stream_id="stream-001",
            message="test push",
        )

        assert result.direction == SyncDirection.PUSH
        assert result.objects_sent == 2
        assert result.commit_id == "commit-002"
        assert result.errors == []
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_push_with_no_elements(self, syncer):
        """push with empty list should return zero objects sent."""
        result = await syncer.push([], stream_id="stream-001")

        assert result.objects_sent == 0
        assert result.commit_id is None

    @pytest.mark.asyncio
    async def test_push_records_mapping_errors(self, syncer, mock_speckle_client):
        """push should record errors for unmappable elements."""
        bad_element = UnknownWidget(id="x")

        result = await syncer.push([bad_element], stream_id="stream-001")

        assert result.objects_sent == 0
        assert len(result.errors) == 1
        assert "UnknownWidget" in result.errors[0]

    # ------------------------------------------------------------------
    # Pull
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_pull_receives_and_maps_objects(self, syncer):
        """pull should receive objects and map them to RevitPy dicts."""
        elements = await syncer.pull(stream_id="stream-001")

        assert len(elements) == 2
        assert elements[0]["type"] == "WallElement"
        assert elements[1]["type"] == "RoomElement"

    @pytest.mark.asyncio
    async def test_pull_with_specific_commit(self, syncer, mock_speckle_client):
        """pull with a commit_id should pass it to the client."""
        await syncer.pull(stream_id="stream-001", commit_id="commit-001")

        mock_speckle_client.receive_objects.assert_called_once_with(
            "stream-001",
            commit_id="commit-001",
            branch="main",
        )

    # ------------------------------------------------------------------
    # Bidirectional sync
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sync_bidirectional(self, syncer, sample_elements):
        """sync with BIDIRECTIONAL direction should push and pull."""
        result = await syncer.sync(
            sample_elements,
            stream_id="stream-001",
            direction=SyncDirection.BIDIRECTIONAL,
        )

        assert result.direction == SyncDirection.BIDIRECTIONAL
        assert result.objects_sent == 2
        assert result.objects_received == 2

    @pytest.mark.asyncio
    async def test_sync_push_only(self, syncer, sample_elements):
        """sync with PUSH direction should only send."""
        result = await syncer.sync(
            sample_elements,
            stream_id="stream-001",
            direction=SyncDirection.PUSH,
        )

        assert result.direction == SyncDirection.PUSH
        assert result.objects_sent == 2
        assert result.objects_received == 0

    @pytest.mark.asyncio
    async def test_sync_pull_only(self, syncer, sample_elements):
        """sync with PULL direction should only receive."""
        result = await syncer.sync(
            sample_elements,
            stream_id="stream-001",
            direction=SyncDirection.PULL,
        )

        assert result.direction == SyncDirection.PULL
        assert result.objects_sent == 0
        assert result.objects_received == 2

    @pytest.mark.asyncio
    async def test_sync_incremental_with_change_tracker(
        self, mock_speckle_client, sample_elements
    ):
        """Incremental sync should filter elements via change tracker."""

        class MockTracker:
            def is_changed(self, elem):
                return getattr(elem, "id", None) == "wall-1"

        syncer = SpeckleSync(
            client=mock_speckle_client,
            change_tracker=MockTracker(),
        )
        result = await syncer.sync(
            sample_elements,
            stream_id="stream-001",
            mode=SyncMode.INCREMENTAL,
            direction=SyncDirection.PUSH,
        )

        # Only the wall should be sent (tracker marks only wall-1)
        assert result.objects_sent == 1

    @pytest.mark.asyncio
    async def test_sync_full_mode_sends_all(self, syncer, sample_elements):
        """Full sync should send all elements regardless of changes."""
        result = await syncer.sync(
            sample_elements,
            stream_id="stream-001",
            mode=SyncMode.FULL,
            direction=SyncDirection.PUSH,
        )

        assert result.objects_sent == 2
