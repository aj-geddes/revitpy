"""
Tests for ApsClient region routing, retry, Retry-After, and timeouts.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from revitpy.cloud.client import (
    _MAX_RETRIES,
    BASE_URL,
    DEFAULT_DA_BASE_PATH,
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_TIMEOUT,
    ApsClient,
)
from revitpy.cloud.exceptions import ApsApiError
from revitpy.cloud.jobs import JobManager
from revitpy.cloud.types import CloudRegion, JobConfig

_REAL_ASYNC_CLIENT = httpx.AsyncClient
_CLIENT_TARGET = "revitpy.cloud.client.httpx.AsyncClient"
_SLEEP_TARGET = "revitpy.cloud.client.asyncio.sleep"

Handler = Callable[[httpx.Request], httpx.Response]


def _fake_http(module_path: str, handler: Handler, calls: list[dict[str, Any]]):
    """Patch ``httpx.AsyncClient`` with a real client on a MockTransport."""

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        calls.append(kwargs)
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    return patch(module_path, side_effect=factory)


def _sequence(*responses: httpx.Response) -> tuple[Handler, list[httpx.Request]]:
    """Handler returning ``responses`` in order (last one repeats)."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return responses[min(len(seen), len(responses)) - 1]

    return handler, seen


_JOB = JobConfig(activity_id="A.B+prod", input_file="https://x/in.rvt")


class TestRegionRouting:
    """The client's region drives the Design Automation base path."""

    def test_us_region_uses_us_east(self, mock_authenticator):
        client = ApsClient(mock_authenticator, region=CloudRegion.US)
        assert client.da_base_path == DEFAULT_DA_BASE_PATH == "/da/us-east/v3"

    def test_emea_without_override_falls_back_to_us_east(self, mock_authenticator):
        client = ApsClient(mock_authenticator, region=CloudRegion.EMEA)
        assert client.region is CloudRegion.EMEA
        assert client.da_base_path == "/da/us-east/v3"

    def test_override_trailing_slash_stripped(self, mock_authenticator):
        client = ApsClient(mock_authenticator, da_base_path="/da/custom/v3/")
        assert client.da_base_path == "/da/custom/v3"

    @pytest.mark.asyncio
    async def test_emea_override_changes_request_url(self, mock_authenticator):
        us_handler, us_seen = _sequence(httpx.Response(200, json={"id": "wi-1"}))
        eu_handler, eu_seen = _sequence(httpx.Response(200, json={"id": "wi-2"}))

        with _fake_http(_CLIENT_TARGET, us_handler, []):
            us_client = ApsClient(mock_authenticator, region=CloudRegion.US)
            assert await JobManager(us_client).submit(_JOB) == "wi-1"

        with _fake_http(_CLIENT_TARGET, eu_handler, []):
            eu_client = ApsClient(
                mock_authenticator,
                region=CloudRegion.EMEA,
                da_base_path="/da/eu-test/v3",
            )
            assert await JobManager(eu_client).submit(_JOB) == "wi-2"

        assert us_seen[0].method == eu_seen[0].method == "POST"
        assert str(us_seen[0].url) == f"{BASE_URL}/da/us-east/v3/workitems"
        assert str(eu_seen[0].url) == f"{BASE_URL}/da/eu-test/v3/workitems"


class TestRetryBehavior:
    """Retry exhaustion keeps status info; Retry-After is honored."""

    @pytest.mark.asyncio
    async def test_exhausted_503_keeps_status_and_body(self, mock_authenticator):
        handler, seen = _sequence(httpx.Response(503, text="Service Unavailable"))
        client = ApsClient(mock_authenticator)

        with (
            _fake_http(_CLIENT_TARGET, handler, []),
            patch(_SLEEP_TARGET, new_callable=AsyncMock) as sleep,
        ):
            with pytest.raises(ApsApiError) as exc_info:
                await client.get("/flaky")

        exc = exc_info.value
        assert exc.status_code == 503
        assert exc.response_body == "Service Unavailable"
        assert "last status 503" in str(exc)
        assert len(seen) == _MAX_RETRIES
        # No pointless sleep after the final attempt
        assert sleep.await_count == _MAX_RETRIES - 1

    @pytest.mark.asyncio
    async def test_exhausted_body_is_truncated(self, mock_authenticator):
        handler, _ = _sequence(httpx.Response(500, text="x" * 2000))
        client = ApsClient(mock_authenticator)

        with (
            _fake_http(_CLIENT_TARGET, handler, []),
            patch(_SLEEP_TARGET, new_callable=AsyncMock),
        ):
            with pytest.raises(ApsApiError) as exc_info:
                await client.get("/flaky")

        assert exc_info.value.status_code == 500
        assert exc_info.value.response_body == "x" * 500

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status", "retry_after", "expected_delay"),
        [
            (429, "7", 7.0),
            (503, "2.5", 2.5),
            (503, "3600", 60.0),  # capped
            (429, "Wed, 21 Oct 2015 07:28:00 GMT", 1.0),  # date form -> backoff
            (500, "9", 1.0),  # only honored for 429/503
        ],
    )
    async def test_retry_after_handling(
        self, mock_authenticator, status, retry_after, expected_delay
    ):
        handler, seen = _sequence(
            httpx.Response(status, headers={"Retry-After": retry_after}),
            httpx.Response(200, json={"ok": True}),
        )
        client = ApsClient(mock_authenticator)

        with (
            _fake_http(_CLIENT_TARGET, handler, []),
            patch(_SLEEP_TARGET, new_callable=AsyncMock) as sleep,
        ):
            result = await client.get("/limited")

        assert result == {"ok": True}
        assert len(seen) == 2
        sleep.assert_awaited_once_with(expected_delay)

    @pytest.mark.asyncio
    async def test_transport_error_exhaustion(self, mock_authenticator):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        client = ApsClient(mock_authenticator)

        with (
            _fake_http(_CLIENT_TARGET, handler, []),
            patch(_SLEEP_TARGET, new_callable=AsyncMock),
        ):
            with pytest.raises(ApsApiError) as exc_info:
                await client.get("/down")

        assert exc_info.value.status_code is None
        assert isinstance(exc_info.value.cause, httpx.ConnectError)


class TestClientTimeouts:
    """Explicit timeouts replace httpx's 5s default."""

    def test_defaults(self, mock_authenticator):
        client = ApsClient(mock_authenticator)
        assert client.timeout == DEFAULT_TIMEOUT
        assert client.download_timeout == DEFAULT_DOWNLOAD_TIMEOUT
        assert DEFAULT_TIMEOUT.connect == 10.0
        assert DEFAULT_DOWNLOAD_TIMEOUT.read == 300.0

    def test_numeric_overrides(self, mock_authenticator):
        client = ApsClient(mock_authenticator, timeout=5, download_timeout=900)
        assert client.timeout.read == 5.0
        assert client.timeout.connect == 5.0
        assert client.download_timeout.read == 900.0
        assert client.download_timeout.connect == 10.0

    def test_timeout_object_passthrough(self, mock_authenticator):
        custom = httpx.Timeout(12.0, connect=3.0)
        client = ApsClient(mock_authenticator, timeout=custom)
        assert client.timeout is custom

    @pytest.mark.asyncio
    async def test_request_passes_timeout(self, mock_authenticator):
        handler, _ = _sequence(httpx.Response(200, json={}))
        calls: list[dict[str, Any]] = []
        client = ApsClient(mock_authenticator)

        with _fake_http(_CLIENT_TARGET, handler, calls):
            await client.get("/test")

        assert calls[0]["timeout"] is client.timeout
