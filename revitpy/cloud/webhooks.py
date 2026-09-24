"""
Webhook handling for APS events.

This module provides signature verification and an event-routing system
that dispatches incoming webhook payloads to registered callback
functions.

Signatures follow the APS Webhooks scheme
(https://aps.autodesk.com/en/docs/webhooks/v1/tutorials/how-to-verify-payload-signature):
the ``x-adsk-signature`` header carries ``sha1hash=`` followed by the
hex HMAC-SHA1 digest of the raw request body, keyed with the secret
token configured for the hook.

By default ``handle_event`` refuses payloads that are not accompanied by
a valid signature (``verify=True``). Pass ``verify=False`` explicitly to
accept unsigned payloads -- e.g. Design Automation ``onComplete``
callbacks, which APS does not sign.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any

from loguru import logger

from .exceptions import WebhookError
from .types import JobStatus, WebhookConfig, WebhookEvent

SIGNATURE_HEADER = "x-adsk-signature"
SIGNATURE_PREFIX = "sha1hash="


def compute_signature(secret: str, payload: bytes) -> str:
    """Compute the APS webhook signature for a payload.

    Args:
        secret: The webhook secret token.
        payload: Raw request body bytes.

    Returns:
        Signature string in the form ``sha1hash=<hexdigest>``.
    """
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha1).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


class WebhookHandler:
    """Receives, verifies, and routes APS webhook events."""

    def __init__(
        self,
        config: WebhookConfig | None = None,
    ) -> None:
        self._config = config
        self._callbacks: dict[str, list[Callable[[WebhookEvent], Any]]] = defaultdict(
            list
        )

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def verify_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify the HMAC-SHA1 signature of an incoming payload.

        Args:
            payload: Raw request body bytes.
            signature: Value of the ``x-adsk-signature`` header
                (``sha1hash=<hex>``; a bare hex digest is also accepted).

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

        candidate = signature.strip()
        if candidate.lower().startswith(SIGNATURE_PREFIX):
            candidate = candidate[len(SIGNATURE_PREFIX) :]
        if not candidate:
            return False

        expected = compute_signature(self._config.secret, payload)
        provided = f"{SIGNATURE_PREFIX}{candidate.lower()}"
        return hmac.compare_digest(expected.encode("ascii"), provided.encode("utf-8"))

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(
        self,
        event_data: dict[str, Any] | None = None,
        *,
        raw_body: bytes | None = None,
        signature: str | None = None,
        verify: bool = True,
    ) -> WebhookEvent:
        """Verify, parse, and dispatch an incoming webhook payload.

        With ``verify=True`` (the default) a secret must be configured and
        both ``raw_body`` and ``signature`` must be supplied; the event is
        parsed from ``raw_body`` (the signed bytes) and ``event_data`` is
        ignored. With ``verify=False`` the payload is accepted unsigned
        from ``event_data`` (or parsed from ``raw_body``).

        Args:
            event_data: Parsed JSON body (only used when ``verify=False``).
            raw_body: Raw request body bytes.
            signature: Value of the ``x-adsk-signature`` header.
            verify: Require a valid signature (default ``True``).

        Returns:
            ``WebhookEvent`` representing the parsed event.

        Raises:
            WebhookError: If verification fails, the body is not a JSON
                object, or required fields are missing.
        """
        if verify:
            if self._config is None or not self._config.secret:
                raise WebhookError(
                    "Webhook signature verification is enabled but no secret "
                    "is configured; pass verify=False to accept unsigned "
                    "payloads",
                    event_type="signature_verification",
                )
            if raw_body is None or not signature:
                raise WebhookError(
                    "Missing raw body or signature for webhook verification",
                    event_type="signature_verification",
                )
            if not self.verify_signature(raw_body, signature):
                raise WebhookError(
                    "Invalid webhook signature",
                    event_type="signature_verification",
                )
            data = self._parse_body(raw_body)
        else:
            logger.warning("Accepting webhook payload without signature verification")
            if event_data is not None:
                data = event_data
            elif raw_body is not None:
                data = self._parse_body(raw_body)
            else:
                raise WebhookError("No event data supplied", event_type="unknown")

        try:
            event_type = data["eventType"]
        except KeyError as exc:
            raise WebhookError(
                f"Missing required field in webhook payload: {exc}",
                event_type="unknown",
                cause=exc,
            ) from exc

        event = WebhookEvent(
            event_type=event_type,
            job_id=data.get("jobId", ""),
            status=_parse_status(data.get("status", "pending")),
            timestamp=data.get("timestamp", ""),
            payload=data,
        )

        self._dispatch(event)
        return event

    def handle_request(
        self,
        raw_body: bytes,
        headers: Mapping[str, str],
    ) -> WebhookEvent:
        """Verify and handle a raw HTTP webhook request.

        Args:
            raw_body: Raw request body bytes.
            headers: Request headers (looked up case-insensitively).

        Returns:
            ``WebhookEvent`` representing the parsed event.

        Raises:
            WebhookError: If the signature is missing or invalid.
        """
        signature = ""
        for key, value in headers.items():
            if key.lower() == SIGNATURE_HEADER:
                signature = value
                break
        return self.handle_event(raw_body=raw_body, signature=signature, verify=True)

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def register_callback(
        self,
        event_type: str,
        callback: Callable[[WebhookEvent], Any],
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

    @staticmethod
    def _parse_body(raw_body: bytes) -> dict[str, Any]:
        """Parse a raw request body into a JSON object."""
        try:
            parsed = json.loads(raw_body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise WebhookError(
                "Webhook body is not valid JSON",
                event_type="unknown",
                cause=exc,
            ) from exc
        if not isinstance(parsed, dict):
            raise WebhookError(
                "Webhook body must be a JSON object",
                event_type="unknown",
            )
        return parsed

    def _dispatch(self, event: WebhookEvent) -> None:
        """Invoke all registered callbacks for the event's type."""
        callbacks = [
            *self._callbacks.get(event.event_type, []),
            # Also invoke wildcard ("*") listeners
            *self._callbacks.get("*", []),
        ]

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


def _parse_status(raw: Any) -> JobStatus:
    """Map a raw status string to a ``JobStatus`` enum member."""
    return _STATUS_MAP.get(str(raw).lower(), JobStatus.PENDING)
