"""
Tests for the webhook handling module.
"""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import MagicMock

import pytest

from revitpy.cloud.exceptions import WebhookError
from revitpy.cloud.types import JobStatus, WebhookConfig, WebhookEvent
from revitpy.cloud.webhooks import WebhookHandler


class TestWebhookHandler:
    """Tests for WebhookHandler."""

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def test_verify_signature_valid(self):
        """verify_signature should return True for a valid signature."""
        secret = "webhook-secret-key"
        config = WebhookConfig(
            url="https://example.com/hook",
            secret=secret,
        )
        handler = WebhookHandler(config=config)

        payload = b'{"eventType": "job.completed"}'
        signature = hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        assert handler.verify_signature(payload, signature) is True

    def test_verify_signature_invalid(self):
        """verify_signature should return False for a bad signature."""
        config = WebhookConfig(
            url="https://example.com/hook",
            secret="correct-secret",
        )
        handler = WebhookHandler(config=config)

        payload = b'{"eventType": "job.completed"}'
        bad_signature = "0" * 64

        assert handler.verify_signature(payload, bad_signature) is False

    def test_verify_signature_no_config_raises(self):
        """verify_signature should raise WebhookError without config."""
        handler = WebhookHandler(config=None)

        with pytest.raises(WebhookError) as exc_info:
            handler.verify_signature(b"data", "sig")

        assert "secret" in str(exc_info.value).lower()

    def test_verify_signature_empty_secret_raises(self):
        """verify_signature should raise WebhookError with empty secret."""
        config = WebhookConfig(
            url="https://example.com/hook",
            secret="",
        )
        handler = WebhookHandler(config=config)

        with pytest.raises(WebhookError):
            handler.verify_signature(b"data", "sig")

    def test_verify_signature_tampered_payload(self):
        """verify_signature should reject a tampered payload."""
        secret = "my-secret"
        config = WebhookConfig(
            url="https://example.com/hook",
            secret=secret,
        )
        handler = WebhookHandler(config=config)

        original_payload = b'{"status": "completed"}'
        signature = hmac.new(
            secret.encode("utf-8"),
            original_payload,
            hashlib.sha256,
        ).hexdigest()

        tampered_payload = b'{"status": "failed"}'
        assert handler.verify_signature(tampered_payload, signature) is False

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def test_handle_event_returns_webhook_event(self):
        """handle_event should parse data into a WebhookEvent."""
        handler = WebhookHandler()

        event_data = {
            "eventType": "job.completed",
            "jobId": "job-abc",
            "status": "completed",
            "timestamp": "2024-01-15T10:00:00Z",
            "extra": "data",
        }

        event = handler.handle_event(event_data)

        assert isinstance(event, WebhookEvent)
        assert event.event_type == "job.completed"
        assert event.job_id == "job-abc"
        assert event.status == JobStatus.COMPLETED
        assert event.timestamp == "2024-01-15T10:00:00Z"
        assert event.payload == event_data

    def test_handle_event_missing_event_type_raises(self):
        """handle_event should raise WebhookError for missing eventType."""
        handler = WebhookHandler()

        with pytest.raises(WebhookError) as exc_info:
            handler.handle_event({"jobId": "1", "status": "ok"})

        assert "eventType" in str(exc_info.value)

    def test_handle_event_defaults_for_optional_fields(self):
        """handle_event should use defaults for missing optional fields."""
        handler = WebhookHandler()

        event_data = {"eventType": "job.started"}
        event = handler.handle_event(event_data)

        assert event.job_id == ""
        assert event.status == JobStatus.PENDING
        assert event.timestamp == ""

    def test_handle_event_unknown_status_defaults_to_pending(self):
        """Unknown status strings should map to PENDING."""
        handler = WebhookHandler()

        event_data = {
            "eventType": "job.custom",
            "status": "unknown_xyz",
        }
        event = handler.handle_event(event_data)

        assert event.status == JobStatus.PENDING

    # ------------------------------------------------------------------
    # Callback registration and dispatch
    # ------------------------------------------------------------------

    def test_register_callback(self):
        """register_callback should store the callback."""
        handler = WebhookHandler()
        callback = MagicMock()

        handler.register_callback("job.completed", callback)

        assert callback in handler._callbacks["job.completed"]

    def test_callback_invoked_on_matching_event(self):
        """Registered callbacks should be called on matching events."""
        handler = WebhookHandler()
        callback = MagicMock()
        handler.register_callback("job.completed", callback)

        event_data = {
            "eventType": "job.completed",
            "jobId": "job-1",
            "status": "completed",
            "timestamp": "2024-01-15T10:00:00Z",
        }
        handler.handle_event(event_data)

        callback.assert_called_once()
        event_arg = callback.call_args[0][0]
        assert isinstance(event_arg, WebhookEvent)
        assert event_arg.event_type == "job.completed"

    def test_callback_not_invoked_for_different_event(self):
        """Callbacks should not fire for non-matching event types."""
        handler = WebhookHandler()
        callback = MagicMock()
        handler.register_callback("job.completed", callback)

        event_data = {
            "eventType": "job.failed",
            "status": "failed",
        }
        handler.handle_event(event_data)

        callback.assert_not_called()

    def test_wildcard_callback_invoked_for_all_events(self):
        """Wildcard ('*') callbacks should fire for every event type."""
        handler = WebhookHandler()
        wildcard_cb = MagicMock()
        handler.register_callback("*", wildcard_cb)

        handler.handle_event({"eventType": "job.completed"})
        handler.handle_event({"eventType": "job.failed"})

        assert wildcard_cb.call_count == 2

    def test_multiple_callbacks_for_same_event(self):
        """Multiple callbacks for the same event should all be invoked."""
        handler = WebhookHandler()
        cb1 = MagicMock()
        cb2 = MagicMock()
        handler.register_callback("job.completed", cb1)
        handler.register_callback("job.completed", cb2)

        handler.handle_event(
            {
                "eventType": "job.completed",
                "status": "completed",
            }
        )

        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_callback_exception_does_not_propagate(self):
        """Exceptions in callbacks should not propagate."""
        handler = WebhookHandler()
        bad_cb = MagicMock(side_effect=RuntimeError("boom"))
        good_cb = MagicMock()
        handler.register_callback("job.completed", bad_cb)
        handler.register_callback("job.completed", good_cb)

        # Should not raise
        handler.handle_event(
            {
                "eventType": "job.completed",
                "status": "completed",
            }
        )

        bad_cb.assert_called_once()
        good_cb.assert_called_once()
