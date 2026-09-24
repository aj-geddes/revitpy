"""
Tests for webhook signature enforcement and token-refresh locking.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from revitpy.cloud.auth import TOKEN_ENDPOINT, ApsAuthenticator
from revitpy.cloud.exceptions import WebhookError
from revitpy.cloud.types import ApsCredentials, ApsToken, JobStatus, WebhookConfig
from revitpy.cloud.webhooks import SIGNATURE_HEADER, WebhookHandler, compute_signature

SECRET_VALUE = "whsec-test-value"
BODY = json.dumps(
    {"eventType": "job.completed", "jobId": "wi-9", "status": "completed"}
).encode()


def _handler() -> WebhookHandler:
    return WebhookHandler(
        WebhookConfig(url="https://example.com/hook", secret=SECRET_VALUE)
    )


class TestWebhookSignatureEnforcement:
    """handle_event must reject unsigned or badly signed payloads."""

    def test_signature_header_name(self):
        assert SIGNATURE_HEADER == "x-adsk-signature"

    def test_compute_signature_format(self):
        sig = compute_signature(SECRET_VALUE, BODY)
        expected = (
            "sha1hash="
            + hmac.new(SECRET_VALUE.encode(), BODY, hashlib.sha1).hexdigest()
        )
        assert sig == expected
        assert sig.startswith("sha1hash=")

    def test_handle_event_valid_signature(self):
        handler = _handler()
        callback = MagicMock()
        handler.register_callback("job.completed", callback)

        sig = compute_signature(SECRET_VALUE, BODY)
        event = handler.handle_event(raw_body=BODY, signature=sig)

        assert event.event_type == "job.completed"
        assert event.job_id == "wi-9"
        assert event.status == JobStatus.COMPLETED
        callback.assert_called_once_with(event)

    def test_handle_event_ignores_event_data_when_verifying(self):
        handler = _handler()
        sig = compute_signature(SECRET_VALUE, BODY)

        event = handler.handle_event(
            event_data={"eventType": "forged"}, raw_body=BODY, signature=sig
        )

        assert event.event_type == "job.completed"

    def test_handle_event_invalid_signature_raises(self):
        handler = _handler()
        callback = MagicMock()
        handler.register_callback("job.completed", callback)

        with pytest.raises(WebhookError):
            handler.handle_event(raw_body=BODY, signature="sha1hash=" + "0" * 40)

        callback.assert_not_called()

    def test_handle_event_missing_signature_or_body(self):
        handler = _handler()
        sig = compute_signature(SECRET_VALUE, BODY)

        with pytest.raises(WebhookError):
            handler.handle_event(raw_body=BODY, signature=None)
        with pytest.raises(WebhookError):
            handler.handle_event(raw_body=BODY, signature="")
        with pytest.raises(WebhookError):
            handler.handle_event(raw_body=None, signature=sig)

    def test_handle_event_default_verify_requires_secret(self):
        handler = WebhookHandler()
        with pytest.raises(WebhookError) as exc_info:
            handler.handle_event(event_data={"eventType": "job.completed"})
        assert "verify=False" in str(exc_info.value)

    def test_handle_event_tampered_body(self):
        handler = _handler()
        callback = MagicMock()
        handler.register_callback("job.completed", callback)

        tampered = json.dumps(
            {"eventType": "job.completed", "jobId": "wi-9", "status": "failed"}
        ).encode()
        sig = compute_signature(SECRET_VALUE, BODY)
        with pytest.raises(WebhookError):
            handler.handle_event(raw_body=tampered, signature=sig)

        callback.assert_not_called()

    def test_verify_signature_bare_and_uppercase_hex(self):
        handler = _handler()
        bare = compute_signature(SECRET_VALUE, BODY).split("=", 1)[1]

        assert handler.verify_signature(BODY, bare) is True
        assert handler.verify_signature(BODY, "sha1hash=" + bare.upper()) is True

    def test_handle_request_reads_header_case_insensitively(self):
        handler = _handler()
        callback = MagicMock()
        handler.register_callback("job.completed", callback)

        sig = compute_signature(SECRET_VALUE, BODY)
        event = handler.handle_request(
            BODY, {"X-Adsk-Signature": sig, "Content-Type": "application/json"}
        )

        assert event.event_type == "job.completed"
        callback.assert_called_once()

    def test_handle_request_without_header_raises(self):
        with pytest.raises(WebhookError):
            _handler().handle_request(BODY, {})

    def test_verify_false_parses_raw_body(self):
        event = WebhookHandler().handle_event(raw_body=BODY, verify=False)
        assert event.job_id == "wi-9"

    def test_verify_false_rejects_bad_bodies(self):
        handler = WebhookHandler()
        with pytest.raises(WebhookError):
            handler.handle_event(raw_body=b"not json", verify=False)
        with pytest.raises(WebhookError):
            handler.handle_event(raw_body=b"[1, 2]", verify=False)
        with pytest.raises(WebhookError):
            handler.handle_event(verify=False)


class TestTokenRefreshLock:
    """Concurrent get_token() calls must share a single refresh."""

    def test_token_endpoint_is_v2(self):
        assert "/authentication/v2/token" in TOKEN_ENDPOINT

    @staticmethod
    def _fake_auth(auth: ApsAuthenticator, counter: dict[str, int]):
        async def fake_authenticate() -> ApsToken:
            await asyncio.sleep(0.01)
            counter["count"] += 1
            token = ApsToken(
                access_token=f"tok-{counter['count']}", issued_at=time.time()
            )
            auth._token = token
            return token

        return fake_authenticate

    @pytest.mark.asyncio
    async def test_concurrent_calls_without_token_authenticate_once(
        self, mock_credentials: ApsCredentials
    ):
        auth = ApsAuthenticator(mock_credentials)
        counter = {"count": 0}

        with patch.object(
            auth, "authenticate", side_effect=self._fake_auth(auth, counter)
        ):
            tokens = await asyncio.gather(*(auth.get_token() for _ in range(10)))

        assert counter["count"] == 1
        assert all(t is tokens[0] for t in tokens)

    @pytest.mark.asyncio
    async def test_concurrent_calls_with_expired_token_authenticate_once(
        self, mock_credentials: ApsCredentials
    ):
        auth = ApsAuthenticator(mock_credentials)
        auth._token = ApsToken(access_token="old", issued_at=time.time() - 7200)
        counter = {"count": 0}

        with patch.object(
            auth, "authenticate", side_effect=self._fake_auth(auth, counter)
        ):
            tokens = await asyncio.gather(*(auth.get_token() for _ in range(5)))

        assert counter["count"] == 1
        assert all(t.access_token == "tok-1" for t in tokens)

    @pytest.mark.asyncio
    async def test_valid_cached_token_skips_authenticate(
        self, mock_credentials: ApsCredentials
    ):
        auth = ApsAuthenticator(mock_credentials)
        auth._token = ApsToken(access_token="valid", issued_at=time.time())
        mock_authenticate = AsyncMock()

        with patch.object(auth, "authenticate", mock_authenticate):
            tokens = await asyncio.gather(*(auth.get_token() for _ in range(5)))

        mock_authenticate.assert_not_awaited()
        assert all(t is auth._token for t in tokens)
