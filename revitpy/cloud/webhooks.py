"""
Webhook handling for APS Design Automation events.

This module provides HMAC-SHA256 signature verification and an
event-routing system that dispatches incoming webhook payloads to
registered callback functions.
"""

from __future__ import annotations

import hashlib
import hmac
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from loguru import logger

from .exceptions import WebhookError
from .types import JobStatus, WebhookConfig, WebhookEvent


class WebhookHandler:
    """Receives, verifies, and routes APS webhook events."""

    def __init__(
        self,
        config: WebhookConfig | None = None,
    ) -> None:
        self._config = config
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def verify_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify HMAC-SHA256 signature of an incoming payload.

        Args:
            payload: Raw request body bytes.
            signature: Hex-encoded HMAC signature from the request
                header.

        Returns:
            ``True`` if the signature is valid.

        Raises:
            WebhookError: If no secret is configured.
        """
        if self._config is None or not self._config.secret:
            raise WebhookError(
                "Cannot verify signature without a configured secret",
                event_type="signature_verification",
            )

        expected = hmac.new(
            self._config.secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, event_data: dict[str, Any]) -> WebhookEvent:
        """Parse an incoming webhook payload and dispatch callbacks.

        Args:
            event_data: Parsed JSON body from the webhook request.

        Returns:
            ``WebhookEvent`` representing the parsed event.

        Raises:
            WebhookError: If required fields are missing.
        """
        try:
            event_type = event_data["eventType"]
            job_id = event_data.get("jobId", "")
            raw_status = event_data.get("status", "pending")
            timestamp = event_data.get("timestamp", "")
        except KeyError as exc:
            raise WebhookError(
                f"Missing required field in webhook payload: {exc}",
                event_type="unknown",
                cause=exc,
            ) from exc

        status = _parse_status(raw_status)

        event = WebhookEvent(
            event_type=event_type,
            job_id=job_id,
            status=status,
            timestamp=timestamp,
            payload=event_data,
        )

        self._dispatch(event)
        return event

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def register_callback(
        self,
        event_type: str,
        callback: Callable,
    ) -> None:
        """Register a callback for a specific event type.

        Args:
            event_type: The event type string to listen for.
            callback: A callable that accepts a ``WebhookEvent``.
        """
        self._callbacks[event_type].append(callback)
        logger.debug("Registered callback for event type '{}'", event_type)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _dispatch(self, event: WebhookEvent) -> None:
        """Invoke all registered callbacks for the event's type."""
        callbacks = self._callbacks.get(event.event_type, [])
        # Also invoke wildcard ("*") listeners
        callbacks = [*callbacks, *self._callbacks.get("*", [])]

        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                logger.exception(
                    "Error in webhook callback for event '{}'",
                    event.event_type,
                )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_STATUS_MAP: dict[str, JobStatus] = {s.value: s for s in JobStatus}


def _parse_status(raw: str) -> JobStatus:
    """Map a raw status string to a ``JobStatus`` enum member."""
    return _STATUS_MAP.get(raw.lower(), JobStatus.PENDING)
