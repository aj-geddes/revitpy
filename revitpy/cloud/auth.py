"""
APS OAuth2 authentication for RevitPy cloud operations.

This module handles the OAuth2 client-credentials flow against the
Autodesk Platform Services (APS) authentication endpoint, including
token caching and automatic refresh when the token nears expiry.
"""

from __future__ import annotations

import time

import httpx
from loguru import logger

from .exceptions import AuthenticationError
from .types import ApsCredentials, ApsToken

TOKEN_ENDPOINT = "https://developer.api.autodesk.com/authentication/v2/token"  # noqa: S105


class ApsAuthenticator:
    """Authenticator for Autodesk Platform Services using OAuth2.

    Manages the client-credentials flow, caches the issued token, and
    transparently refreshes it when it is about to expire.
    """

    def __init__(self, credentials: ApsCredentials) -> None:
        self._credentials = credentials
        self._token: ApsToken | None = None

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
            async with httpx.AsyncClient() as client:
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

        Returns:
            A valid ApsToken.
        """
        if self._token is None or not self.is_token_valid():
            await self.authenticate()
        return self._token  # type: ignore[return-value]

    def is_token_valid(self) -> bool:
        """Check whether the cached token is still valid.

        Uses a 60-second buffer before the actual expiry time.
        """
        if self._token is None:
            return False
        return not self._token.is_expired
