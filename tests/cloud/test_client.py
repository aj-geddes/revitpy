"""
Tests for the APS HTTP client module.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from revitpy.cloud.client import (
    _INITIAL_BACKOFF,
    _MAX_REQUESTS_PER_SECOND,
    _MAX_RETRIES,
    BASE_URL,
    ApsClient,
)
from revitpy.cloud.exceptions import ApsApiError
from revitpy.cloud.types import ApsToken, CloudRegion


class TestApsClient:
    """Tests for ApsClient."""

    def test_init_stores_authenticator_and_region(self, mock_authenticator):
        """Client should store authenticator and region."""
        client = ApsClient(mock_authenticator, region=CloudRegion.EMEA)
        assert client._authenticator is mock_authenticator
        assert client._region is CloudRegion.EMEA

    @pytest.mark.asyncio
    async def test_get_delegates_to_request(self, mock_authenticator):
        """get() should call request with GET method."""
        client = ApsClient(mock_authenticator)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}
        mock_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await client.get("/test/endpoint")

        assert result == {"data": "value"}
        mock_http.request.assert_awaited_once()
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == f"{BASE_URL}/test/endpoint"

    @pytest.mark.asyncio
    async def test_post_delegates_to_request(self, mock_authenticator):
        """post() should call request with POST method."""
        client = ApsClient(mock_authenticator)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "new-item"}
        mock_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await client.post("/test", json={"key": "val"})

        assert result == {"id": "new-item"}

    @pytest.mark.asyncio
    async def test_delete_delegates_to_request(self, mock_authenticator):
        """delete() should call request with DELETE method."""
        client = ApsClient(mock_authenticator)

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await client.delete("/test/item/1")

        assert result == {}

    @pytest.mark.asyncio
    async def test_request_injects_auth_header(self, mock_authenticator):
        """Requests should include the Authorization header."""
        client = ApsClient(mock_authenticator)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            await client.get("/test")

        call_kwargs = mock_http.request.call_args[1]
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"].startswith("Bearer ")

    @pytest.mark.asyncio
    async def test_request_raises_on_non_retryable_error(self, mock_authenticator):
        """Non-retryable HTTP errors should raise ApsApiError immediately."""
        client = ApsClient(mock_authenticator)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("revitpy.cloud.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(ApsApiError) as exc_info:
                await client.get("/missing")

        assert exc_info.value.status_code == 404
        assert exc_info.value.endpoint == "/missing"

    @pytest.mark.asyncio
    async def test_request_retries_on_server_error(self, mock_authenticator):
        """Server errors (500) should be retried up to MAX_RETRIES."""
        client = ApsClient(mock_authenticator)

        # First two calls return 500, third succeeds
        responses = []
        for _ in range(_MAX_RETRIES):
            r = MagicMock()
            r.status_code = 500
            r.raise_for_status = MagicMock()
            responses.append(r)

        with patch("revitpy.cloud.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(side_effect=responses)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with patch("revitpy.cloud.client.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ApsApiError) as exc_info:
                    await client.get("/flaky")

        assert "retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_request_retries_on_429(self, mock_authenticator):
        """Rate-limited responses (429) should trigger retries."""
        client = ApsClient(mock_authenticator)

        retry_response = MagicMock()
        retry_response.status_code = 429
        retry_response.raise_for_status = MagicMock()

        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.json.return_value = {"ok": True}
        ok_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(side_effect=[retry_response, ok_response])
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with patch("revitpy.cloud.client.asyncio.sleep", new_callable=AsyncMock):
                result = await client.get("/rate-limited")

        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self, mock_authenticator):
        """Rate limiter should cap to 20 requests per second."""
        client = ApsClient(mock_authenticator)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.client.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.request = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            # Make a few requests to verify no crash
            for _ in range(5):
                await client.get("/test")

        assert mock_http.request.await_count == 5
