"""
Pytest configuration and fixtures for interop tests.
"""

from unittest.mock import AsyncMock

import pytest

from revitpy.interop.client import SpeckleClient
from revitpy.interop.types import SpeckleCommit, SpeckleConfig

# ---------------------------------------------------------------------------
# Mock element classes (cannot use SimpleNamespace with __class__ reassignment)
# ---------------------------------------------------------------------------


class WallElement:
    """Mock WallElement for testing."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class RoomElement:
    """Mock RoomElement for testing."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_speckle_config():
    """Fixture providing a Speckle server configuration."""
    return SpeckleConfig(
        server_url="https://test.speckle.dev",
        token="test-token-abc123",
        default_stream="stream-001",
    )


@pytest.fixture
def mock_speckle_client(mock_speckle_config):
    """Fixture providing a mocked SpeckleClient."""
    client = SpeckleClient(config=mock_speckle_config)

    client.connect = AsyncMock()
    client.get_streams = AsyncMock(
        return_value=[
            {"id": "stream-001", "name": "Test Stream"},
        ]
    )
    client.get_stream = AsyncMock(
        return_value={"id": "stream-001", "name": "Test Stream"},
    )
    client.get_branches = AsyncMock(
        return_value=[
            {"id": "branch-001", "name": "main"},
        ]
    )
    client.get_commits = AsyncMock(
        return_value=[
            SpeckleCommit(
                id="commit-001",
                message="Initial commit",
                author="tester",
                created_at="2025-01-01T00:00:00Z",
                total_objects=3,
            ),
        ]
    )
    client.send_objects = AsyncMock(
        return_value=SpeckleCommit(
            id="commit-002",
            message="push",
            author="revitpy",
            created_at="2025-01-02T00:00:00Z",
            total_objects=2,
        ),
    )
    client.receive_objects = AsyncMock(
        return_value=[
            {
                "id": "wall-1",
                "name": "Wall A",
                "speckle_type": "Objects.BuiltElements.Wall:Wall",
                "height": 10,
            },
            {
                "id": "room-1",
                "name": "Room 101",
                "speckle_type": "Objects.BuiltElements.Room:Room",
                "area": 200,
            },
        ]
    )
    client.close = AsyncMock()

    return client


@pytest.fixture
def sample_elements():
    """Fixture providing mock RevitPy element objects."""
    wall = WallElement(
        id="wall-1",
        name="Wall A",
        height=10,
        length=20,
        width=0.5,
    )
    room = RoomElement(
        id="room-1",
        name="Room 101",
        number="101",
        area=200,
        perimeter=60,
        volume=2000,
    )
    return [wall, room]


@pytest.fixture
def sample_speckle_objects():
    """Fixture providing sample Speckle object dicts."""
    return [
        {
            "id": "wall-1",
            "name": "Wall A",
            "speckle_type": "Objects.BuiltElements.Wall:Wall",
            "height": 10,
            "length": 20,
        },
        {
            "id": "room-1",
            "name": "Room 101",
            "speckle_type": "Objects.BuiltElements.Room:Room",
            "area": 200,
            "number": "101",
        },
    ]
