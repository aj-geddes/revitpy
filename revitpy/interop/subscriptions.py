"""
Speckle real-time subscription manager for RevitPy.

Listens for new Speckle *versions* (formerly commits) through the current
GraphQL subscription ``projectVersionsUpdated(id: $projectId)`` exposed by
``specklepy`` (``client.subscription.project_versions_updated``).  The
legacy ``commitCreated(streamId: ...)`` stream subscription no longer
exists on current Speckle servers.

Requirements and behaviour:

* ``specklepy`` must be installed (``pip install revitpy[interop]``).
* WebSocket subscriptions require an authenticated client, so
  :class:`SpeckleConfig` must carry a personal access token.
* The server emits events for every model in the project; events are
  filtered client-side to the subscribed model.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from loguru import logger

from ._compat import require_specklepy, resolve_renamed
from .client import SpeckleClient
from .exceptions import SpeckleConnectionError

VERSION_CREATED_EVENT = "speckle.version_created"


class SpeckleSubscriptions:
    """Manages WebSocket subscriptions to Speckle model versions.

    Each subscription runs as an ``asyncio`` task.  Matching events are
    converted to plain dict payloads and passed to the registered
    callback and, when provided, ``event_manager.dispatch(
    "speckle.version_created", payload)``.

    Args:
        client: A :class:`SpeckleClient` (authenticated with a token).
        event_manager: Optional event manager with a ``dispatch``
            method for subscription events.
    """

    def __init__(
        self,
        client: SpeckleClient,
        event_manager: Any | None = None,
    ) -> None:
        self._client = client
        self._event_manager = event_manager
        self._subscriptions: dict[str, dict[str, Any]] = {}
        self._callbacks: dict[str, Callable[..., Any]] = {}
        self._pending: set[asyncio.Future[Any]] = set()

    async def subscribe(
        self,
        project_id: str | None = None,
        model: str = "main",
        callback: Callable[..., Any] | None = None,
        *,
        stream_id: str | None = None,
        branch: str | None = None,
    ) -> None:
        """Subscribe to new versions on a project model.

        Args:
            project_id: The Speckle project identifier.
            model: Model name or id to watch.
            callback: Optional callable (sync or async) invoked with a
                payload dict for every new/updated version on the model.
            stream_id: Deprecated alias of ``project_id``.
            branch: Deprecated alias of ``model``.

        Raises:
            ImportError: If ``specklepy`` is not installed.
            SpeckleConnectionError: If the subscription cannot be set up.
        """
        project_id = resolve_renamed(
            project_id, stream_id, new_name="project_id", old_name="stream_id"
        )
        if branch is not None:
            model = resolve_renamed(
                None if model == "main" else model,
                branch,
                new_name="model",
                old_name="branch",
            )

        sub_key = f"{project_id}/{model}"
        if sub_key in self._subscriptions:
            logger.warning("Already subscribed to {}, skipping", sub_key)
            return

        require_specklepy()

        try:
            sdk = await self._client._get_sdk()
            model_id = await self._client.resolve_model_id(project_id, model)

            def handler(message: Any) -> None:
                if getattr(message, "model_id", None) != model_id:
                    return
                payload = self._message_to_payload(
                    message, project_id=project_id, model=model
                )
                self._dispatch(sub_key, payload)

            task = asyncio.create_task(
                self._run(
                    sub_key,
                    sdk.subscription.project_versions_updated(handler, id=project_id),
                )
            )
        except ImportError:
            raise
        except Exception as exc:
            raise SpeckleConnectionError(
                f"Failed to subscribe to {project_id}/{model}",
                server_url=self._client.config.server_url,
                cause=exc,
            ) from exc

        self._subscriptions[sub_key] = {
            "project_id": project_id,
            "model": model,
            "model_id": model_id,
            "task": task,
            "active": True,
        }
        if callback is not None:
            self._callbacks[sub_key] = callback

        logger.info("Subscribed to versions on {}/{}", project_id, model)

    async def _run(self, sub_key: str, coro: Awaitable[Any]) -> None:
        """Run a subscription coroutine, marking it inactive on failure."""
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Subscription {} failed: {}", sub_key, exc)
            entry = self._subscriptions.get(sub_key)
            if entry is not None:
                entry["active"] = False

    @staticmethod
    def _message_to_payload(
        message: Any,
        *,
        project_id: str,
        model: str,
    ) -> dict[str, Any]:
        """Convert a ``ProjectVersionsUpdatedMessage`` into a plain dict."""
        version = getattr(message, "version", None)
        author_user = getattr(version, "author_user", None)
        created = getattr(version, "created_at", None)
        if created is not None and hasattr(created, "isoformat"):
            created_at: str | None = created.isoformat()
        else:
            created_at = None if created is None else str(created)
        event_type = getattr(message, "type", None)

        return {
            "project_id": project_id,
            "model": model,
            "model_id": getattr(message, "model_id", None),
            "type": str(getattr(event_type, "value", event_type)),
            "version_id": getattr(version, "id", None),
            "referenced_object": getattr(version, "referenced_object", None),
            "message": getattr(version, "message", None),
            "source_application": getattr(version, "source_application", None),
            "created_at": created_at,
            "author": getattr(author_user, "name", None),
        }

    def _dispatch(self, sub_key: str, payload: dict[str, Any]) -> None:
        """Deliver a payload to the callback and event manager."""
        callback = self._callbacks.get(sub_key)
        if callback is not None:
            try:
                result = callback(payload)
                if inspect.isawaitable(result):
                    future = asyncio.ensure_future(result)
                    self._pending.add(future)
                    future.add_done_callback(self._pending.discard)
            except Exception:
                logger.exception("Subscription callback for {} failed", sub_key)

        dispatch = getattr(self._event_manager, "dispatch", None)
        if dispatch is not None:
            try:
                dispatch(VERSION_CREATED_EVENT, payload)
            except Exception:
                logger.exception("Event manager dispatch failed for {}", sub_key)

    @staticmethod
    async def _cancel(entry: dict[str, Any]) -> None:
        """Mark a subscription inactive and cancel its task."""
        entry["active"] = False
        task = entry.get("task")
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task

    async def unsubscribe(self, project_id: str) -> None:
        """Unsubscribe from all models of a project.

        Args:
            project_id: The Speckle project identifier.
        """
        keys = [k for k in self._subscriptions if k.startswith(f"{project_id}/")]
        for key in keys:
            entry = self._subscriptions.pop(key)
            await self._cancel(entry)
            self._callbacks.pop(key, None)
            logger.info("Unsubscribed from {}", key)

        if not keys:
            logger.debug("No active subscriptions found for project {}", project_id)

    @property
    def active_subscriptions(self) -> list[str]:
        """Return a list of active subscription keys (``project/model``)."""
        return [k for k, v in self._subscriptions.items() if v.get("active", False)]

    async def close(self) -> None:
        """Cancel all active subscriptions."""
        for key in list(self._subscriptions):
            await self._cancel(self._subscriptions.pop(key))
            self._callbacks.pop(key, None)

        logger.info("Closed all subscriptions")
