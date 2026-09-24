"""
APS OAuth2 authentication for RevitPy cloud operations.

This module handles the OAuth2 client-credentials flow against the
Autodesk Platform Services (APS) authentication endpoint, including
token caching and automatic refresh when the token nears expiry.
"""

from __future__ import annotations

import asyncio
import time

import httpx
from loguru import logger

from .exceptions import AuthenticationError
from .types import ApsCredentials, ApsToken

TOKEN_ENDPOINT = "https://developer.api.autodesk.com/authentication/v2/token"  # noqa: S105
_AUTH_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ApsAuthenticator:
    """Authenticator for Autodesk Platform Services using OAuth2.

    Manages the client-credentials flow, caches the issued token, and
    transparently refreshes it when it is about to expire.
    """

    def __init__(self, credentials: ApsCredentials) -> None:
        self._credentials = credentials
        self._token: ApsToken | None = None
        # Serializes refreshes so concurrent callers holding an expired
        # token trigger exactly one re-authentication.
        self._refresh_lock = asyncio.Lock()

    async def authenticate(self) -> ApsToken:
        """Perform a fresh OAuth2 client-credentials authentication.

        Returns:
            ApsToken with the newly issued access token.

        Raises:
            AuthenticationError: If the token endpoint returns an error.
        """
        logger.debug("Authenticating with APS token endpoint")

        data = {
            "grant_type": "client_credentials",
            "client_id": self._credentials.client_id,
            "client_secret": self._credentials.client_secret,
            "scope": "code:all data:write data:read bucket:create",
        }

        try:
            async with httpx.AsyncClient(timeout=_AUTH_TIMEOUT) as client:
                response = await client.post(
                    TOKEN_ENDPOINT,
                    data=data,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as exc:
            raise AuthenticationError(
                f"APS authentication failed with status {exc.response.status_code}",
                auth_method="client_credentials",
                cause=exc,
            ) from exc
        except httpx.HTTPError as exc:
            raise AuthenticationError(
                f"APS authentication request failed: {exc}",
                auth_method="client_credentials",
                cause=exc,
            ) from exc

        self._token = ApsToken(
            access_token=body["access_token"],
            token_type=body.get("token_type", "Bearer"),
            expires_in=body.get("expires_in", 3600),
            scope=body.get("scope", ""),
            issued_at=time.time(),
        )
        logger.info("APS authentication successful")
        return self._token

    async def get_token(self) -> ApsToken:
        """Return a cached token, refreshing it if expired.

        Concurrent callers share a single refresh: the first caller to find
        the token expired re-authenticates under a lock, and the others
        reuse the freshly issued token.

        Returns:
            A valid ApsToken.
        """
        token = self._token
        if token is not None and not token.is_expired:
            return token

        async with self._refresh_lock:
            # Re-check: another coroutine may have refreshed while we waited.
            token = self._token
            if token is None or token.is_expired:
                token = await self.authenticate()
            return token

    def is_token_valid(self) -> bool:
        """Check whether the cached token is still valid.

        Uses a 60-second buffer before the actual expiry time.
        """
        if self._token is None:
            return False
        return not self._token.is_expired
