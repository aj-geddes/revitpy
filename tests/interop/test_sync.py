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
            project_id="stream-001",
            message="test push",
        )

        assert result.direction == SyncDirection.PUSH
        assert result.objects_sent == 2
        assert result.commit_id == "commit-002"
        assert result.version_id == "commit-002"
        assert result.object_id == "0123456789abcdef0123456789abcdef"
        assert result.errors == []
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_push_with_no_elements(self, syncer):
        """push with empty list should return zero objects sent."""
        result = await syncer.push([], project_id="stream-001")

        assert result.objects_sent == 0
        assert result.commit_id is None

    @pytest.mark.asyncio
    async def test_push_records_mapping_errors(self, syncer, mock_speckle_client):
        """push should record errors for unmappable elements."""
        bad_element = UnknownWidget(id="x")

        result = await syncer.push([bad_element], project_id="stream-001")

        assert result.objects_sent == 0
        assert len(result.errors) == 1
        assert "UnknownWidget" in result.errors[0]

    # ------------------------------------------------------------------
    # Pull
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_pull_receives_and_maps_objects(self, syncer):
        """pull should receive objects and map them to RevitPy dicts."""
        elements = await syncer.pull(project_id="stream-001")

        assert len(elements) == 2
        assert elements[0]["type"] == "WallElement"
        assert elements[1]["type"] == "RoomElement"

    @pytest.mark.asyncio
    async def test_pull_with_specific_version(self, syncer, mock_speckle_client):
        """pull with a version_id should pass it to the client."""
        await syncer.pull(project_id="stream-001", version_id="commit-001")

        mock_speckle_client.receive_objects.assert_called_once_with(
            "stream-001",
            version_id="commit-001",
            model="main",
        )

    # ------------------------------------------------------------------
    # Legacy stream/branch/commit arguments
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_push_legacy_kwargs_warn(
        self, syncer, mock_speckle_client, sample_elements
    ):
        """Legacy stream_id/branch kwargs still work but are deprecated."""
        with pytest.warns(DeprecationWarning):
            result = await syncer.push(
                sample_elements, stream_id="stream-001", branch="dev"
            )

        assert result.commit_id == "commit-002"
        args, kwargs = mock_speckle_client.send_objects.call_args
        assert args[0] == "stream-001"
        assert kwargs["model"] == "dev"

    @pytest.mark.asyncio
    async def test_pull_legacy_kwargs_warn(self, syncer, mock_speckle_client):
        """Legacy commit_id/branch kwargs map to version_id/model."""
        with pytest.warns(DeprecationWarning):
            await syncer.pull(stream_id="stream-001", branch="dev", commit_id="c1")

        mock_speckle_client.receive_objects.assert_called_once_with(
            "stream-001",
            version_id="c1",
            model="dev",
        )

    @pytest.mark.asyncio
    async def test_push_uses_default_project(
        self, mock_speckle_client, sample_elements
    ):
        """Without a project_id the configured default project is used."""
        syncer = SpeckleSync(client=mock_speckle_client)
        await syncer.push(sample_elements)

        assert mock_speckle_client.send_objects.call_args.args[0] == "stream-001"

    @pytest.mark.asyncio
    async def test_push_without_project_raises(self, sample_elements):
        """Without a project_id or default an informative TypeError is raised."""
        from revitpy.interop.client import SpeckleClient

        syncer = SpeckleSync(client=SpeckleClient())
        with pytest.raises(TypeError, match="project_id"):
            await syncer.push(sample_elements)

    # ------------------------------------------------------------------
    # Bidirectional sync
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_sync_bidirectional(self, syncer, sample_elements):
        """sync with BIDIRECTIONAL direction should push and pull."""
        result = await syncer.sync(
            sample_elements,
            project_id="stream-001",
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
            project_id="stream-001",
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
            project_id="stream-001",
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
            project_id="stream-001",
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
            project_id="stream-001",
            mode=SyncMode.FULL,
            direction=SyncDirection.PUSH,
        )

        assert result.objects_sent == 2
