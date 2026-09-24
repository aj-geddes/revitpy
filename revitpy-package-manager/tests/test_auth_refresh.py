"""Tests for the access/refresh token split.

- Access and refresh tokens are distinguished by their ``type`` claim.
- ``POST /auth/refresh`` only accepts refresh tokens, so a stolen access
  token can't be renewed indefinitely.
- Refresh tokens can't authenticate ordinary API calls.
- Sessions have an absolute lifetime anchored at ``auth_time`` (the
  password login), which is preserved across refresh-token rotation.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from revitpy_package_manager.registry.api.routers import auth
from revitpy_package_manager.registry.api.schemas import (
    RefreshTokenRequest,
    TokenRefreshResponse,
)
from revitpy_package_manager.registry.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


def _decode(token: str) -> dict:
    return jwt.decode(token, auth.JWT_SECRET_KEY, algorithms=[auth.JWT_ALGORITHM])


def _login(client) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpassword"},
    )
    assert response.status_code == 200
    return response.json()


def _mock_db(user):
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_result
    return mock_db


def _user(is_active=True):
    return Mock(spec=User, id=uuid.uuid4(), is_active=is_active)


def _encode(claims: dict, key: str | None = None) -> str:
    return jwt.encode(claims, key or auth.JWT_SECRET_KEY, algorithm=auth.JWT_ALGORITHM)


def _in(**delta) -> int:
    return int((datetime.now(UTC) + timedelta(**delta)).timestamp())


class TestTokenCreation:
    def test_access_token_has_type_access_and_timestamps(self):
        now = datetime.now(UTC)
        payload = _decode(auth.create_access_token({"sub": "user123"}))

        assert payload["type"] == auth.ACCESS_TOKEN_TYPE
        assert payload["exp"] - payload["iat"] == auth.JWT_EXPIRE_HOURS * 3600
        assert abs(payload["iat"] - now.timestamp()) < 5

    def test_access_token_overrides_type_claim(self):
        token = auth.create_access_token({"sub": "user123", "type": "refresh"})
        assert _decode(token)["type"] == auth.ACCESS_TOKEN_TYPE

    def test_refresh_token_claims(self):
        now = datetime.now(UTC)
        payload = _decode(auth.create_refresh_token("user123"))

        assert payload["type"] == auth.REFRESH_TOKEN_TYPE
        assert payload["sub"] == "user123"
        assert isinstance(payload["auth_time"], int)
        assert abs(payload["auth_time"] - now.timestamp()) < 5
        assert payload["jti"]
        assert (
            payload["exp"] - payload["auth_time"]
            == auth.JWT_REFRESH_EXPIRE_DAYS * 86400
        )

    def test_refresh_token_with_explicit_auth_time(self):
        auth_time = _in(days=-10)
        payload = _decode(auth.create_refresh_token("user123", auth_time=auth_time))

        assert payload["auth_time"] == auth_time
        assert payload["exp"] == auth_time + auth.JWT_REFRESH_EXPIRE_DAYS * 86400

    def test_refresh_tokens_differ_in_jti(self):
        first = _decode(auth.create_refresh_token("user123"))
        second = _decode(auth.create_refresh_token("user123"))
        assert first["jti"] != second["jti"]


class TestRefreshEndpointUnit:
    @staticmethod
    async def _refresh_401(token: str | None, user) -> HTTPException:
        body = RefreshTokenRequest(refresh_token=token) if token else None
        with pytest.raises(HTTPException) as exc_info:
            await auth.refresh_token(body=body, credentials=None, db=_mock_db(user))
        assert exc_info.value.status_code == 401
        return exc_info.value

    @pytest.mark.asyncio
    async def test_valid_refresh_token_in_body(self):
        user = _user()
        auth_time = _in(hours=-1)
        token = auth.create_refresh_token(str(user.id), auth_time=auth_time)

        response = await auth.refresh_token(
            body=RefreshTokenRequest(refresh_token=token),
            credentials=None,
            db=_mock_db(user),
        )

        assert isinstance(response, TokenRefreshResponse)
        assert response.token_type == "bearer"
        assert response.expires_in == auth.JWT_EXPIRE_HOURS * 3600
        access = _decode(response.access_token)
        assert access["type"] == auth.ACCESS_TOKEN_TYPE
        assert access["sub"] == str(user.id)
        rotated = _decode(response.refresh_token)
        assert rotated["type"] == auth.REFRESH_TOKEN_TYPE
        assert rotated["auth_time"] == auth_time
        assert response.refresh_token != token

    @pytest.mark.asyncio
    async def test_refresh_token_via_credentials(self):
        user = _user()
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=auth.create_refresh_token(str(user.id))
        )

        response = await auth.refresh_token(
            body=None, credentials=credentials, db=_mock_db(user)
        )

        assert _decode(response.access_token)["sub"] == str(user.id)

    @pytest.mark.asyncio
    async def test_access_token_rejected(self):
        user = _user()
        error = await self._refresh_401(
            auth.create_access_token({"sub": str(user.id)}), user
        )
        assert "refresh token is required" in error.detail

    @pytest.mark.asyncio
    async def test_legacy_untyped_token_rejected(self):
        user = _user()
        await self._refresh_401(
            _encode({"sub": str(user.id), "exp": _in(hours=1)}), user
        )

    @pytest.mark.asyncio
    async def test_no_token_provided(self):
        error = await self._refresh_401(None, _user())
        assert "missing refresh token" in error.detail.lower()

    @pytest.mark.asyncio
    async def test_expired_refresh_token(self):
        user = _user()
        auth_time = _in(days=-(auth.JWT_REFRESH_EXPIRE_DAYS + 1))
        error = await self._refresh_401(
            auth.create_refresh_token(str(user.id), auth_time=auth_time), user
        )
        assert "expired" in error.detail.lower()

    @pytest.mark.asyncio
    async def test_absolute_session_cap(self):
        """The cap is enforced from auth_time even while exp is still valid."""
        user = _user()
        token = auth.create_refresh_token(str(user.id), auth_time=_in(days=-2))

        with patch.object(auth, "JWT_REFRESH_EXPIRE_DAYS", 1):
            error = await self._refresh_401(token, user)

        assert "Session has expired" in error.detail

    @pytest.mark.asyncio
    async def test_refresh_token_missing_auth_time(self):
        user = _user()
        token = _encode({"sub": str(user.id), "type": "refresh", "exp": _in(days=1)})
        error = await self._refresh_401(token, user)
        assert "invalid refresh token" in error.detail.lower()

    @pytest.mark.asyncio
    async def test_wrong_secret_signature(self):
        user = _user()
        token = _encode(
            {
                "sub": str(user.id),
                "type": "refresh",
                "auth_time": _in(),
                "exp": _in(days=1),
            },
            key="x" * 40,
        )
        await self._refresh_401(token, user)

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        await self._refresh_401(auth.create_refresh_token(str(uuid.uuid4())), None)

    @pytest.mark.asyncio
    async def test_inactive_user(self):
        user = _user(is_active=False)
        await self._refresh_401(auth.create_refresh_token(str(user.id)), user)


class TestAccessRejectsRefreshToken:
    @pytest.mark.asyncio
    async def test_refresh_token_rejected_by_get_current_user(self):
        user = _user()
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=auth.create_refresh_token(str(user.id))
        )

        with pytest.raises(HTTPException) as exc_info:
            await auth.get_current_user(credentials=credentials, db=_mock_db(user))

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_legacy_untyped_token_accepted_by_get_current_user(self):
        """Tokens issued before the type claim existed stay valid until exp."""
        user = _user()
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=_encode({"sub": str(user.id), "exp": _in(hours=1)}),
        )

        result = await auth.get_current_user(credentials=credentials, db=_mock_db(user))

        assert result is user


class TestRefreshFlowIntegration:
    def test_login_returns_token_pair(self, test_client, test_user):
        tokens = _login(test_client)

        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] == auth.JWT_EXPIRE_HOURS * 3600
        assert tokens["user"]["username"] == "testuser"
        assert _decode(tokens["access_token"])["type"] == auth.ACCESS_TOKEN_TYPE
        assert _decode(tokens["refresh_token"])["type"] == auth.REFRESH_TOKEN_TYPE

    def test_refresh_token_works(self, test_client, test_user):
        tokens = _login(test_client)

        response = test_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert response.status_code == 200
        refreshed = response.json()
        assert refreshed["token_type"] == "bearer"
        assert refreshed["expires_in"] == auth.JWT_EXPIRE_HOURS * 3600

        me = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refreshed['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["username"] == "testuser"

    def test_refresh_rotation_preserves_auth_time(self, test_client, test_user):
        refresh = _login(test_client)["refresh_token"]
        auth_time = _decode(refresh)["auth_time"]

        for _ in range(2):
            response = test_client.post(
                "/api/v1/auth/refresh", json={"refresh_token": refresh}
            )
            assert response.status_code == 200
            refresh = response.json()["refresh_token"]
            assert _decode(refresh)["auth_time"] == auth_time

    def test_refresh_via_authorization_header(self, test_client, test_user):
        refresh = _login(test_client)["refresh_token"]

        response = test_client.post(
            "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh}"}
        )

        assert response.status_code == 200
        assert _decode(response.json()["access_token"])["type"] == "access"

    def test_access_token_cannot_refresh(self, test_client, test_user):
        """A stolen access token can't be exchanged for a fresh one."""
        access = _login(test_client)["access_token"]

        in_body = test_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": access}
        )
        assert in_body.status_code == 401

        as_header = test_client.post(
            "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {access}"}
        )
        assert as_header.status_code == 401

    def test_refresh_token_rejected_on_protected_endpoint(self, test_client, test_user):
        refresh = _login(test_client)["refresh_token"]

        response = test_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh}"}
        )

        assert response.status_code == 401

    def test_refresh_without_token(self, test_client, test_user):
        response = test_client.post("/api/v1/auth/refresh")
        assert response.status_code == 401
