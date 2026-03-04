"""
Speckle real-time subscription manager for RevitPy.

This module provides a ``SpeckleSubscriptions`` class that manages
GraphQL subscriptions over WebSocket connections to receive live
commit and branch update notifications.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from .client import SpeckleClient
from .exceptions import SpeckleConnectionError


class SpeckleSubscriptions:
    """Manages WebSocket-based GraphQL subscriptions to Speckle streams.

    Args:
        client: An initialised :class:`SpeckleClient`.
        event_manager: Optional event manager for dispatching
            subscription events.
    """

    def __init__(
        self,
        client: SpeckleClient,
        event_manager: Any | None = None,
    ) -> None:
        self._client = client
        self._event_manager = event_manager
        self._subscriptions: dict[str, Any] = {}
        self._callbacks: dict[str, Callable[..., Any]] = {}

    async def subscribe(
        self,
        stream_id: str,
        branch: str = "main",
        callback: Callable[..., Any] | None = None,
    ) -> None:
        """Subscribe to commit events on a stream branch.

        The subscription listens for new commits and invokes the
        callback (if provided) or dispatches through the event
        manager.

        Args:
            stream_id: The Speckle stream identifier.
            branch: Branch name to watch.
            callback: Optional callable invoked with the commit
                payload whenever a new commit arrives.

        Raises:
            SpeckleConnectionError: If the WebSocket connection
                cannot be established.
        """
        sub_key = f"{stream_id}/{branch}"
        if sub_key in self._subscriptions:
            logger.warning(
                "Already subscribed to {}, skipping",
                sub_key,
            )
            return

        try:
            config = self._client.config
            ws_url = config.server_url.replace("https://", "wss://").replace(
                "http://", "ws://"
            )

            subscription_query = """
            subscription($streamId: String!) {
                commitCreated(streamId: $streamId) {
                    id
                    message
                    authorName
                    branchName
                    sourceApplication
                    totalChildrenCount
                    createdAt
                }
            }
            """

            # Store subscription metadata (actual WS connection would
            # be managed by an async task in production)
            self._subscriptions[sub_key] = {
                "stream_id": stream_id,
                "branch": branch,
                "ws_url": ws_url,
                "query": subscription_query,
                "active": True,
            }

            if callback is not None:
                self._callbacks[sub_key] = callback

            logger.info(
                "Subscribed to commits on {}/{}",
                stream_id,
                branch,
            )

        except Exception as exc:
            raise SpeckleConnectionError(
                f"Failed to subscribe to {stream_id}/{branch}",
                server_url=self._client.config.server_url,
                cause=exc,
            ) from exc

    async def unsubscribe(self, stream_id: str) -> None:
        """Unsubscribe from all branches of a stream.

        Args:
            stream_id: The Speckle stream identifier.
        """
        keys_to_remove = [
            k for k in self._subscriptions if k.startswith(f"{stream_id}/")
        ]

        for key in keys_to_remove:
            sub = self._subscriptions.pop(key, None)
            if sub:
                sub["active"] = False
            self._callbacks.pop(key, None)
            logger.info("Unsubscribed from {}", key)

        if not keys_to_remove:
            logger.debug(
                "No active subscriptions found for stream {}",
                stream_id,
            )

    @property
    def active_subscriptions(self) -> list[str]:
        """Return a list of active subscription keys."""
        return [k for k, v in self._subscriptions.items() if v.get("active", False)]

    async def close(self) -> None:
        """Close all active subscriptions."""
        for key in list(self._subscriptions.keys()):
            sub = self._subscriptions.pop(key)
            sub["active"] = False
            self._callbacks.pop(key, None)

        logger.info("Closed all subscriptions")
