"""
Unit tests for SpeckleClient.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from revitpy.interop.client import SpeckleClient
from revitpy.interop.exceptions import SpeckleConnectionError, SpeckleSyncError
from revitpy.interop.types import SpeckleCommit, SpeckleConfig


class TestSpeckleClient:
    """Test Speckle GraphQL API client with mocked httpx responses."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return SpeckleConfig(
            server_url="https://test.speckle.dev",
            token="test-token",
        )

    @pytest.fixture
    def client(self, config):
        """Create a client with test configuration."""
        return SpeckleClient(config=config)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_connect_success(self, client):
        """connect should succeed with valid server response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "serverInfo": {
                    "name": "Test Server",
                    "version": "2.0.0",
                }
            }
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.is_closed = False

        client._http = mock_http
        await client.connect()

        assert client.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_failure_raises_error(self, client):
        """connect should raise SpeckleConnectionError on failure."""
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_http.is_closed = False

        client._http = mock_http

        with pytest.raises(SpeckleConnectionError, match="Failed to connect"):
            await client.connect()

    # ------------------------------------------------------------------
    # Streams
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_streams(self, client):
        """get_streams should return a list of stream dicts."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "streams": {
                    "items": [
                        {"id": "s1", "name": "Stream 1"},
                        {"id": "s2", "name": "Stream 2"},
                    ]
                }
            }
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.is_closed = False
        client._http = mock_http

        streams = await client.get_streams()
        assert len(streams) == 2
        assert streams[0]["id"] == "s1"

    @pytest.mark.asyncio
    async def test_get_stream(self, client):
        """get_stream should return a single stream dict."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "stream": {
                    "id": "s1",
                    "name": "Stream 1",
                    "description": "Test",
                }
            }
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.is_closed = False
        client._http = mock_http

        stream = await client.get_stream("s1")
        assert stream["id"] == "s1"
        assert stream["name"] == "Stream 1"

    # ------------------------------------------------------------------
    # Branches
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_branches(self, client):
        """get_branches should return branch list for a stream."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "stream": {
                    "branches": {
                        "items": [
                            {"id": "b1", "name": "main"},
                            {"id": "b2", "name": "dev"},
                        ]
                    }
                }
            }
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.is_closed = False
        client._http = mock_http

        branches = await client.get_branches("s1")
        assert len(branches) == 2
        assert branches[0]["name"] == "main"

    # ------------------------------------------------------------------
    # Commits
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_commits(self, client):
        """get_commits should return SpeckleCommit objects."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "stream": {
                    "branch": {
                        "commits": {
                            "items": [
                                {
                                    "id": "c1",
                                    "message": "test commit",
                                    "authorName": "tester",
                                    "createdAt": "2025-01-01",
                                    "sourceApplication": "revitpy",
                                    "totalChildrenCount": 5,
                                },
                            ]
                        }
                    }
                }
            }
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.is_closed = False
        client._http = mock_http

        commits = await client.get_commits("s1", branch="main", limit=10)
        assert len(commits) == 1
        assert isinstance(commits[0], SpeckleCommit)
        assert commits[0].id == "c1"
        assert commits[0].message == "test commit"
        assert commits[0].total_objects == 5

    # ------------------------------------------------------------------
    # Send objects
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_send_objects(self, client):
        """send_objects should create a commit and return it."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {"commitCreate": "commit-abc"}}

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.is_closed = False
        client._http = mock_http

        objects = [{"id": "1", "name": "Wall"}]
        commit = await client.send_objects("s1", objects, message="test push")

        assert isinstance(commit, SpeckleCommit)
        assert commit.id == "commit-abc"
        assert commit.total_objects == 1

    @pytest.mark.asyncio
    async def test_send_objects_graphql_error(self, client):
        """send_objects should raise SpeckleSyncError on GraphQL errors."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"errors": [{"message": "Permission denied"}]}

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_http.is_closed = False
        client._http = mock_http

        with pytest.raises(SpeckleSyncError, match="GraphQL errors"):
            await client.send_objects("s1", [{"id": "1"}])

    # ------------------------------------------------------------------
    # Receive objects
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_receive_objects(self, client):
        """receive_objects should return object dicts."""
        # First call: get_commits for latest commit
        commits_response = MagicMock()
        commits_response.raise_for_status = MagicMock()
        commits_response.json.return_value = {
            "data": {
                "stream": {
                    "branch": {
                        "commits": {
                            "items": [
                                {
                                    "id": "c1",
                                    "message": "latest",
                                    "authorName": "tester",
                                    "createdAt": "2025-01-01",
                                    "sourceApplication": "revitpy",
                                    "totalChildrenCount": 2,
                                },
                            ]
                        }
                    }
                }
            }
        }

        # Second call: get objects
        objects_response = MagicMock()
        objects_response.raise_for_status = MagicMock()
        objects_response.json.return_value = {
            "data": {
                "stream": {
                    "object": {
                        "id": "c1",
                        "data": {"id": "root", "name": "root"},
                        "totalChildrenCount": 2,
                        "children": {
                            "objects": [
                                {"id": "o1", "data": {"id": "o1", "name": "Wall"}},
                                {"id": "o2", "data": {"id": "o2", "name": "Room"}},
                            ]
                        },
                    }
                }
            }
        }

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=[commits_response, objects_response])
        mock_http.is_closed = False
        client._http = mock_http

        objects = await client.receive_objects("s1")
        assert len(objects) == 2

    # ------------------------------------------------------------------
    # Headers and config
    # ------------------------------------------------------------------

    def test_build_headers_with_token(self, client):
        """Headers should include Authorization when token is set."""
        headers = client._build_headers()
        assert headers["Authorization"] == "Bearer test-token"

    def test_build_headers_without_token(self):
        """Headers should omit Authorization when no token is set."""
        client = SpeckleClient(config=SpeckleConfig())
        headers = client._build_headers()
        assert "Authorization" not in headers

    def test_config_property(self, client, config):
        """config property should return the configuration."""
        assert client.config.server_url == config.server_url
        assert client.config.token == config.token

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_close(self, client):
        """close should shut down the HTTP client."""
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.aclose = AsyncMock()
        client._http = mock_http
        client._connected = True

        await client.close()

        mock_http.aclose.assert_called_once()
        assert client.is_connected is False
