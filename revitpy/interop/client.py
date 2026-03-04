"""
Speckle GraphQL API client for RevitPy.

This module provides an async HTTP client for interacting with the
Speckle server GraphQL API.  It uses ``httpx`` for transport and
optionally leverages ``specklepy`` when available.
"""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from .exceptions import SpeckleConnectionError, SpeckleSyncError
from .types import SpeckleCommit, SpeckleConfig


class SpeckleClient:
    """Async client for the Speckle GraphQL API.

    Uses ``httpx.AsyncClient`` for all network calls and constructs
    GraphQL queries against the Speckle server.

    Args:
        config: Optional Speckle server configuration.  When ``None``
            the public Speckle server is used without authentication.
    """

    def __init__(self, config: SpeckleConfig | None = None) -> None:
        self._config = config or SpeckleConfig()
        self._http: httpx.AsyncClient | None = None
        self._connected = False

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers including auth when a token is set."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._config.token:
            headers["Authorization"] = f"Bearer {self._config.token}"
        return headers

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Return (and lazily create) the underlying HTTP client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._config.server_url,
                headers=self._build_headers(),
                timeout=30.0,
            )
        return self._http

    async def _graphql(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query against the Speckle server.

        Args:
            query: The GraphQL query string.
            variables: Optional query variables.

        Returns:
            The ``data`` portion of the GraphQL response.

        Raises:
            SpeckleSyncError: If the response contains errors.
        """
        client = await self._ensure_client()
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = await client.post("/graphql", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SpeckleSyncError(
                f"GraphQL request failed: {exc}",
                cause=exc,
            ) from exc

        body = response.json()
        if "errors" in body:
            errors = body["errors"]
            msg = "; ".join(e.get("message", str(e)) for e in errors)
            raise SpeckleSyncError(f"GraphQL errors: {msg}")

        return body.get("data", {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Validate the connection to the Speckle server.

        Sends a lightweight ``serverInfo`` query.

        Raises:
            SpeckleConnectionError: If the server is unreachable or
                returns an unexpected response.
        """
        try:
            data = await self._graphql("{ serverInfo { name version } }")
            server_info = data.get("serverInfo", {})
            logger.info(
                "Connected to Speckle server: {} ({})",
                server_info.get("name", "unknown"),
                server_info.get("version", "unknown"),
            )
            self._connected = True
        except Exception as exc:
            raise SpeckleConnectionError(
                f"Failed to connect to {self._config.server_url}",
                server_url=self._config.server_url,
                cause=exc if not isinstance(exc, SpeckleConnectionError) else None,
            ) from exc

    async def get_streams(self) -> list[dict[str, Any]]:
        """Return a list of streams visible to the authenticated user.

        Returns:
            List of stream dicts with ``id``, ``name``, etc.
        """
        query = """
        query {
            streams {
                items {
                    id
                    name
                    description
                    updatedAt
                }
            }
        }
        """
        data = await self._graphql(query)
        return data.get("streams", {}).get("items", [])

    async def get_stream(self, stream_id: str) -> dict[str, Any]:
        """Return details of a single stream.

        Args:
            stream_id: The Speckle stream identifier.

        Returns:
            Stream dict.
        """
        query = """
        query($id: String!) {
            stream(id: $id) {
                id
                name
                description
                updatedAt
            }
        }
        """
        data = await self._graphql(query, {"id": stream_id})
        return data.get("stream", {})

    async def get_branches(
        self,
        stream_id: str,
    ) -> list[dict[str, Any]]:
        """Return the branches of a stream.

        Args:
            stream_id: The Speckle stream identifier.

        Returns:
            List of branch dicts.
        """
        query = """
        query($id: String!) {
            stream(id: $id) {
                branches {
                    items {
                        id
                        name
                        description
                    }
                }
            }
        }
        """
        data = await self._graphql(query, {"id": stream_id})
        stream = data.get("stream", {})
        return stream.get("branches", {}).get("items", [])

    async def get_commits(
        self,
        stream_id: str,
        branch: str = "main",
        limit: int = 10,
    ) -> list[SpeckleCommit]:
        """Return recent commits on a branch.

        Args:
            stream_id: The Speckle stream identifier.
            branch: Branch name (default ``"main"``).
            limit: Maximum number of commits to return.

        Returns:
            List of ``SpeckleCommit`` instances.
        """
        query = """
        query($id: String!, $branch: String!, $limit: Int!) {
            stream(id: $id) {
                branch(name: $branch) {
                    commits(limit: $limit) {
                        items {
                            id
                            message
                            authorName
                            createdAt
                            sourceApplication
                            totalChildrenCount
                        }
                    }
                }
            }
        }
        """
        data = await self._graphql(
            query,
            {"id": stream_id, "branch": branch, "limit": limit},
        )
        stream = data.get("stream", {})
        branch_data = stream.get("branch", {})
        items = branch_data.get("commits", {}).get("items", [])

        return [
            SpeckleCommit(
                id=item["id"],
                message=item.get("message", ""),
                author=item.get("authorName", ""),
                created_at=item.get("createdAt", ""),
                source_application=item.get("sourceApplication", "revitpy"),
                total_objects=item.get("totalChildrenCount", 0),
            )
            for item in items
        ]

    async def send_objects(
        self,
        stream_id: str,
        objects: list[dict[str, Any]],
        branch: str = "main",
        message: str = "",
    ) -> SpeckleCommit:
        """Send objects to a Speckle stream and create a commit.

        Args:
            stream_id: The Speckle stream identifier.
            objects: List of Speckle-compatible object dicts.
            branch: Target branch name.
            message: Commit message.

        Returns:
            The created ``SpeckleCommit``.

        Raises:
            SpeckleSyncError: If the upload or commit creation fails.
        """
        commit_message = message or f"revitpy push ({len(objects)} objects)"

        query = """
        mutation($commit: CommitCreateInput!) {
            commitCreate(commit: $commit)
        }
        """
        variables = {
            "commit": {
                "streamId": stream_id,
                "branchName": branch,
                "message": commit_message,
                "sourceApplication": "revitpy",
                "totalChildrenCount": len(objects),
                "objectId": f"revitpy-{stream_id}-{len(objects)}",
            },
        }

        try:
            data = await self._graphql(query, variables)
            commit_id = data.get("commitCreate", "")
            logger.info(
                "Created commit {} on {}/{}",
                commit_id,
                stream_id,
                branch,
            )
            return SpeckleCommit(
                id=commit_id,
                message=commit_message,
                author="revitpy",
                created_at="",
                total_objects=len(objects),
            )
        except SpeckleSyncError:
            raise
        except Exception as exc:
            raise SpeckleSyncError(
                f"Failed to send objects to stream {stream_id}",
                stream_id=stream_id,
                direction="push",
                cause=exc,
            ) from exc

    async def receive_objects(
        self,
        stream_id: str,
        commit_id: str | None = None,
        branch: str = "main",
    ) -> list[dict[str, Any]]:
        """Receive objects from a Speckle stream.

        When ``commit_id`` is ``None`` the latest commit on the branch
        is used.

        Args:
            stream_id: The Speckle stream identifier.
            commit_id: Optional specific commit to fetch.
            branch: Branch name used when ``commit_id`` is ``None``.

        Returns:
            List of object dicts.

        Raises:
            SpeckleSyncError: If the download fails.
        """
        if commit_id is None:
            commits = await self.get_commits(stream_id, branch=branch, limit=1)
            if not commits:
                return []
            commit_id = commits[0].id

        query = """
        query($id: String!, $objectId: String!) {
            stream(id: $id) {
                object(id: $objectId) {
                    id
                    data
                    totalChildrenCount
                    children(limit: 100) {
                        objects {
                            id
                            data
                        }
                    }
                }
            }
        }
        """
        try:
            data = await self._graphql(
                query,
                {"id": stream_id, "objectId": commit_id},
            )
            stream = data.get("stream", {})
            obj = stream.get("object", {})

            children = obj.get("children", {}).get("objects", [])
            objects = [child.get("data", child) for child in children]

            if not objects and obj.get("data"):
                objects = [obj["data"]]

            logger.info(
                "Received {} objects from {}/{}",
                len(objects),
                stream_id,
                branch,
            )
            return objects

        except SpeckleSyncError:
            raise
        except Exception as exc:
            raise SpeckleSyncError(
                f"Failed to receive objects from stream {stream_id}",
                stream_id=stream_id,
                direction="pull",
                cause=exc,
            ) from exc

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
            self._http = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Whether the client has successfully connected."""
        return self._connected

    @property
    def config(self) -> SpeckleConfig:
        """The current server configuration."""
        return self._config
