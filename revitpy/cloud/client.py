"""
Authenticated HTTP client for the Autodesk Platform Services API.

This module provides a thin wrapper around ``httpx.AsyncClient`` that
transparently injects authentication headers, enforces rate limiting
(20 requests/second), and retries transient failures with exponential
backoff.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

import httpx
from loguru import logger

from .auth import ApsAuthenticator
from .exceptions import ApsApiError
from .types import CloudRegion

BASE_URL = "https://developer.api.autodesk.com"

# Rate-limiting defaults
_MAX_REQUESTS_PER_SECOND = 20

# Retry defaults
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503})
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0


class ApsClient:
    """HTTP client for making authenticated APS API requests.

    Features:
        * Automatic Bearer-token injection via ``ApsAuthenticator``.
        * Sliding-window rate limiting (20 req/s by default).
        * Exponential-backoff retry on 429 / 5xx responses.
    """

    def __init__(
        self,
        authenticator: ApsAuthenticator,
        *,
        region: CloudRegion = CloudRegion.US,
    ) -> None:
        self._authenticator = authenticator
        self._region = region
        self._request_times: deque[float] = deque()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def get(self, endpoint: str, **kwargs: Any) -> dict:
        """Perform an authenticated GET request."""
        return await self.request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs: Any) -> dict:
        """Perform an authenticated POST request."""
        return await self.request("POST", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs: Any) -> dict:
        """Perform an authenticated DELETE request."""
        return await self.request("DELETE", endpoint, **kwargs)

    # ------------------------------------------------------------------
    # Core request method
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict:
        """Make an authenticated HTTP request with retry and rate limiting.

        Args:
            method: HTTP method (GET, POST, DELETE, ...).
            endpoint: API path relative to the APS base URL.
            **kwargs: Forwarded to ``httpx.AsyncClient.request``.

        Returns:
            Parsed JSON response body as a dict.

        Raises:
            ApsApiError: On non-retryable HTTP errors.
        """
        url = f"{BASE_URL}{endpoint}"
        token = await self._authenticator.get_token()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"{token.token_type} {token.access_token}"

        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            await self._enforce_rate_limit()

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        **kwargs,
                    )

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    backoff = _INITIAL_BACKOFF * (2**attempt)
                    logger.warning(
                        "Retryable status {} on {} {} (attempt {}/{}), "
                        "backing off {:.1f}s",
                        response.status_code,
                        method,
                        endpoint,
                        attempt + 1,
                        _MAX_RETRIES,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue

                response.raise_for_status()
                # Some DELETE endpoints return 204 No Content
                if response.status_code == 204:
                    return {}
                return response.json()

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                raise ApsApiError(
                    f"APS API error: {exc.response.status_code} on {method} {endpoint}",
                    endpoint=endpoint,
                    status_code=exc.response.status_code,
                    response_body=exc.response.text,
                    cause=exc,
                ) from exc

            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    backoff = _INITIAL_BACKOFF * (2**attempt)
                    logger.warning(
                        "HTTP error on {} {}: {} (attempt {}/{})",
                        method,
                        endpoint,
                        exc,
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(backoff)
                    continue

        # All retries exhausted
        raise ApsApiError(
            f"APS request failed after {_MAX_RETRIES} retries: {method} {endpoint}",
            endpoint=endpoint,
            cause=last_exc,
        )

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    async def _enforce_rate_limit(self) -> None:
        """Sliding-window rate limiter: max 20 requests per second."""
        now = time.monotonic()

        # Remove timestamps older than 1 second
        while self._request_times and (now - self._request_times[0] > 1.0):
            self._request_times.popleft()

        if len(self._request_times) >= _MAX_REQUESTS_PER_SECOND:
            sleep_time = 1.0 - (now - self._request_times[0])
            if sleep_time > 0:
                logger.debug("Rate limit reached, sleeping {:.3f}s", sleep_time)
                await asyncio.sleep(sleep_time)

        self._request_times.append(time.monotonic())
