"""
Tests for the APS authentication module.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from revitpy.cloud.auth import TOKEN_ENDPOINT, ApsAuthenticator
from revitpy.cloud.exceptions import AuthenticationError
from revitpy.cloud.types import ApsCredentials, ApsToken, CloudRegion


class TestApsAuthenticator:
    """Tests for ApsAuthenticator."""

    def test_init_stores_credentials(self, mock_credentials):
        """Authenticator should store the provided credentials."""
        auth = ApsAuthenticator(mock_credentials)
        assert auth._credentials is mock_credentials
        assert auth._token is None

    @pytest.mark.asyncio
    async def test_authenticate_success(self, mock_credentials):
        """Successful authentication should return a valid token."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "fresh-token-abc",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "code:all data:write data:read",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.auth.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            auth = ApsAuthenticator(mock_credentials)
            token = await auth.authenticate()

        assert isinstance(token, ApsToken)
        assert token.access_token == "fresh-token-abc"
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600
        assert auth._token is token

    @pytest.mark.asyncio
    async def test_authenticate_http_status_error(self, mock_credentials):
        """Authentication should raise AuthenticationError on HTTP errors."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.json.return_value = {"error": "invalid_client"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("revitpy.cloud.auth.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            auth = ApsAuthenticator(mock_credentials)
            with pytest.raises(AuthenticationError) as exc_info:
                await auth.authenticate()

        assert exc_info.value.auth_method == "client_credentials"
        assert exc_info.value.cause is not None

    @pytest.mark.asyncio
    async def test_authenticate_connection_error(self, mock_credentials):
        """Authentication should raise AuthenticationError on connection errors."""
        with patch("revitpy.cloud.auth.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            auth = ApsAuthenticator(mock_credentials)
            with pytest.raises(AuthenticationError) as exc_info:
                await auth.authenticate()

        assert "client_credentials" == exc_info.value.auth_method

    @pytest.mark.asyncio
    async def test_get_token_caches_result(self, mock_credentials):
        """get_token should cache the token and reuse it."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "cached-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.auth.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            auth = ApsAuthenticator(mock_credentials)
            token1 = await auth.get_token()
            token2 = await auth.get_token()

        assert token1 is token2
        # Only one HTTP call should have been made
        assert mock_client.post.await_count == 1

    @pytest.mark.asyncio
    async def test_get_token_refreshes_expired(self, mock_credentials):
        """get_token should refresh the token when it expires."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.auth.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            auth = ApsAuthenticator(mock_credentials)

            # First call
            await auth.get_token()

            # Expire the token artificially
            auth._token.issued_at = time.time() - 7200

            # Second call should refresh
            await auth.get_token()

        assert mock_client.post.await_count == 2

    def test_is_token_valid_no_token(self, mock_credentials):
        """is_token_valid should return False when no token exists."""
        auth = ApsAuthenticator(mock_credentials)
        assert auth.is_token_valid() is False

    def test_is_token_valid_fresh_token(self, mock_credentials, mock_aps_token):
        """is_token_valid should return True for a fresh token."""
        auth = ApsAuthenticator(mock_credentials)
        auth._token = mock_aps_token
        assert auth.is_token_valid() is True

    def test_is_token_valid_expired_token(self, mock_credentials):
        """is_token_valid should return False for an expired token."""
        auth = ApsAuthenticator(mock_credentials)
        auth._token = ApsToken(
            access_token="expired",
            expires_in=3600,
            issued_at=time.time() - 7200,
        )
        assert auth.is_token_valid() is False
