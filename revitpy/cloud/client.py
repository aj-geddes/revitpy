"""
Authenticated HTTP client for the Autodesk Platform Services API.

This module provides a thin wrapper around ``httpx.AsyncClient`` that
transparently injects authentication headers, enforces rate limiting
(20 requests/second), retries transient failures with exponential
backoff (honoring ``Retry-After`` on 429/503), and applies explicit
``httpx`` timeouts to every request.
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
_MAX_RETRY_AFTER = 60.0
_ERROR_BODY_SNIPPET = 500

# Timeout defaults. API calls get a moderate read timeout; downloads of
# work-item outputs/reports get a generous one.
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DEFAULT_DOWNLOAD_TIMEOUT = httpx.Timeout(300.0, connect=10.0)

# Design Automation v3 regional base paths.
#
# Design Automation v3 is documented only at
# https://developer.api.autodesk.com/da/us-east/v3
# (source: https://aps.autodesk.com/en/docs/design-automation/v3/reference/http/workitems-POST).
# Probing the APS gateway on 2026-09-24 returned 401 (route exists, auth
# required) for /da/us-east/v3/engines but 404 (no such route) for
# /da/eu-west/v3/engines, so no EMEA Design Automation endpoint is mapped.
# Unmapped regions fall back to us-east with a warning; callers can pass
# ``da_base_path`` to ``ApsClient`` to override.
DEFAULT_DA_BASE_PATH = "/da/us-east/v3"
DA_BASE_PATHS: dict[CloudRegion, str] = {CloudRegion.US: DEFAULT_DA_BASE_PATH}


def _coerce_timeout(
    value: httpx.Timeout | float | None,
    default: httpx.Timeout,
) -> httpx.Timeout:
    """Normalize a user-supplied timeout into an ``httpx.Timeout``."""
    if value is None:
        return default
    if isinstance(value, httpx.Timeout):
        return value
    seconds = float(value)
    return httpx.Timeout(seconds, connect=min(10.0, seconds))


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """Compute how long to wait before retrying a retryable response.

    Honors the seconds form of ``Retry-After`` on 429/503 (capped at
    ``_MAX_RETRY_AFTER``); otherwise uses exponential backoff.
    """
    if response.status_code in (429, 503):
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                value = float(retry_after)
            except ValueError:
                value = -1.0  # HTTP-date form or garbage: use backoff
            if value >= 0:
                return min(value, _MAX_RETRY_AFTER)
    return _INITIAL_BACKOFF * (2**attempt)


class ApsClient:
    """HTTP client for making authenticated APS API requests.

    Features:
        * Automatic Bearer-token injection via ``ApsAuthenticator``.
        * Sliding-window rate limiting (20 req/s by default).
        * Retry on 429 / 5xx with exponential backoff, honoring
          ``Retry-After`` (seconds form, capped at 60s) on 429/503.
        * Explicit ``httpx`` timeouts (``timeout`` for API calls,
          ``download_timeout`` for result/report downloads).
        * Region-aware Design Automation base path (``da_base_path``).
    """

    def __init__(
        self,
        authenticator: ApsAuthenticator,
        *,
        region: CloudRegion = CloudRegion.US,
        timeout: httpx.Timeout | float | None = None,
        download_timeout: httpx.Timeout | float | None = None,
        da_base_path: str | None = None,
    ) -> None:
        self._authenticator = authenticator
        self._region = region
        self._request_times: deque[float] = deque()
        self._timeout = _coerce_timeout(timeout, DEFAULT_TIMEOUT)
        self._download_timeout = _coerce_timeout(
            download_timeout, DEFAULT_DOWNLOAD_TIMEOUT
        )

        if da_base_path is not None:
            self._da_base_path = da_base_path.rstrip("/")
        else:
            mapped = DA_BASE_PATHS.get(region)
            if mapped is None:
                logger.warning(
                    "Design Automation has no documented endpoint for region "
                    "'{}'; falling back to {}",
                    region.value,
                    DEFAULT_DA_BASE_PATH,
                )
                mapped = DEFAULT_DA_BASE_PATH
            self._da_base_path = mapped

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def region(self) -> CloudRegion:
        """The APS region this client targets."""
        return self._region

    @property
    def timeout(self) -> httpx.Timeout:
        """Timeout applied to API requests."""
        return self._timeout

    @property
    def download_timeout(self) -> httpx.Timeout:
        """Timeout applied to file/report downloads."""
        return self._download_timeout

    @property
    def da_base_path(self) -> str:
        """Design Automation v3 base path (e.g. ``/da/us-east/v3``)."""
        return self._da_base_path

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
            ApsApiError: On non-retryable HTTP errors, or when retries are
                exhausted (``status_code``/``response_body`` carry the last
                retryable response, if any).
        """
        url = f"{BASE_URL}{endpoint}"
        token = await self._authenticator.get_token()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"{token.token_type} {token.access_token}"

        last_exc: Exception | None = None
        last_status: int | None = None
        last_body: str | None = None

        for attempt in range(_MAX_RETRIES):
            await self._enforce_rate_limit()
            is_last_attempt = attempt >= _MAX_RETRIES - 1

            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        **kwargs,
                    )

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    last_status = response.status_code
                    last_body = response.text[:_ERROR_BODY_SNIPPET]
                    last_exc = None
                    if not is_last_attempt:
                        delay = _retry_delay(response, attempt)
                        logger.warning(
                            "Retryable status {} on {} {} (attempt {}/{}), "
                            "retrying in {:.1f}s",
                            response.status_code,
                            method,
                            endpoint,
                            attempt + 1,
                            _MAX_RETRIES,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    continue

                response.raise_for_status()
                # Some DELETE endpoints return 204 No Content
                if response.status_code == 204:
                    return {}
                return response.json()

            except httpx.HTTPStatusError as exc:
                raise ApsApiError(
                    f"APS API error: {exc.response.status_code} on {method} {endpoint}",
                    endpoint=endpoint,
                    status_code=exc.response.status_code,
                    response_body=exc.response.text[:_ERROR_BODY_SNIPPET],
                    cause=exc,
                ) from exc

            except httpx.HTTPError as exc:
                last_exc = exc
                last_status = None
                last_body = None
                if not is_last_attempt:
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

        # All retries exhausted
        message = (
            f"APS request failed after {_MAX_RETRIES} attempts: {method} {endpoint}"
        )
        if last_status is not None:
            message += f" (last status {last_status}: {last_body})"
        elif last_exc is not None:
            message += f" ({last_exc})"
        raise ApsApiError(
            message,
            endpoint=endpoint,
            status_code=last_status,
            response_body=last_body,
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
