"""Tests for authentication router endpoints."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import jwt
import pytest
from fastapi import HTTPException, status
from revitpy_package_manager.registry.api.routers.auth import (
    create_access_token,
    get_current_active_user,
    get_current_superuser,
    get_current_user,
    get_password_hash,
    login,
    refresh_token,
    register,
    verify_password,
)
from revitpy_package_manager.registry.api.schemas import (
    LoginRequest,
    UserCreate,
)
from revitpy_package_manager.registry.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

# ============================================================================
# Test Password Hashing
# ============================================================================


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "test_password_123"
        hashed = get_password_hash(password)

        # Hash should be different from plain password
        assert hashed != password
        # Hash should be a string
        assert isinstance(hashed, str)
        # Hash should start with bcrypt prefix
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "test_password_123"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "test_password_123"
        hashed = get_password_hash(password)

        assert verify_password("wrong_password", hashed) is False

    def test_hash_different_for_same_password(self):
        """Test that hashing same password produces different hashes (due to salt)."""
        password = "test_password_123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different (random salt)
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


# ============================================================================
# Test JWT Token Creation
# ============================================================================


class TestJWTToken:
    """Tests for JWT token creation and validation."""

    def test_create_access_token(self):
        """Test creating an access token."""
        data = {"sub": "user123"}
        token = create_access_token(data)

        # Token should be a string
        assert isinstance(token, str)
        # Token should have 3 parts (header.payload.signature)
        assert len(token.split(".")) == 3

    def test_create_access_token_with_expiration(self):
        """Test creating token with custom expiration."""
        data = {"sub": "user123"}
        expires_delta = timedelta(minutes=30)
        token = create_access_token(data, expires_delta)

        # Decode without verification to check expiration
        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
            "test_secret",
        ):
            with patch(
                "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM",
                "HS256",
            ):
                decoded = jwt.decode(token, "test_secret", algorithms=["HS256"])
                exp = datetime.utcfromtimestamp(decoded["exp"])
                now = datetime.utcnow()

                # Expiration should be approximately 30 minutes from now
                delta = (exp - now).total_seconds()
                assert 1790 < delta < 1810  # ~30 minutes (allowing 10s variance)

    def test_token_contains_data(self):
        """Test that token contains the provided data."""
        data = {"sub": "user123", "username": "testuser"}

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
            "test_secret",
        ):
            with patch(
                "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM",
                "HS256",
            ):
                token = create_access_token(data)
                decoded = jwt.decode(token, "test_secret", algorithms=["HS256"])

                assert decoded["sub"] == "user123"
                assert decoded["username"] == "testuser"
                assert "exp" in decoded


# ============================================================================
# Test get_current_user
# ============================================================================


class TestGetCurrentUser:
    """Tests for get_current_user function."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self):
        """Test getting current user with valid token."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1, is_active=True, last_login_at=None)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_credentials = Mock()

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
            "test_secret",
        ):
            with patch(
                "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM",
                "HS256",
            ):
                # Create a valid token
                token = jwt.encode(
                    {"sub": "1", "exp": datetime.utcnow() + timedelta(hours=1)},
                    "test_secret",
                    algorithm="HS256",
                )
                mock_credentials.credentials = token

                user = await get_current_user(credentials=mock_credentials, db=mock_db)

                assert user == mock_user
                mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """Test getting current user with expired token."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_credentials = Mock()

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
            "test_secret",
        ):
            with patch(
                "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM",
                "HS256",
            ):
                # Create an expired token
                token = jwt.encode(
                    {"sub": "1", "exp": datetime.utcnow() - timedelta(hours=1)},
                    "test_secret",
                    algorithm="HS256",
                )
                mock_credentials.credentials = token

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(credentials=mock_credentials, db=mock_db)

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_credentials = Mock()
        mock_credentials.credentials = "invalid.token.string"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=mock_credentials, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_user_no_sub(self):
        """Test getting current user with token missing 'sub' claim."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_credentials = Mock()

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
            "test_secret",
        ):
            with patch(
                "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM",
                "HS256",
            ):
                # Create token without sub
                token = jwt.encode(
                    {"exp": datetime.utcnow() + timedelta(hours=1)},
                    "test_secret",
                    algorithm="HS256",
                )
                mock_credentials.credentials = token

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(credentials=mock_credentials, db=mock_db)

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_current_user_not_found(self):
        """Test getting current user when user not in database."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_credentials = Mock()

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
            "test_secret",
        ):
            with patch(
                "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM",
                "HS256",
            ):
                token = jwt.encode(
                    {"sub": "999", "exp": datetime.utcnow() + timedelta(hours=1)},
                    "test_secret",
                    algorithm="HS256",
                )
                mock_credentials.credentials = token

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(credentials=mock_credentials, db=mock_db)

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_current_user_inactive(self):
        """Test getting current user when user is inactive."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_user = Mock(spec=User, id=1, is_active=False)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_credentials = Mock()

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
            "test_secret",
        ):
            with patch(
                "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM",
                "HS256",
            ):
                token = jwt.encode(
                    {"sub": "1", "exp": datetime.utcnow() + timedelta(hours=1)},
                    "test_secret",
                    algorithm="HS256",
                )
                mock_credentials.credentials = token

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(credentials=mock_credentials, db=mock_db)

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert "inactive" in exc_info.value.detail.lower()


# ============================================================================
# Test get_current_active_user
# ============================================================================


class TestGetCurrentActiveUser:
    """Tests for get_current_active_user function."""

    @pytest.mark.asyncio
    async def test_get_current_active_user_success(self):
        """Test getting active user."""
        mock_user = Mock(spec=User, id=1, is_active=True)

        user = await get_current_active_user(current_user=mock_user)

        assert user == mock_user

    @pytest.mark.asyncio
    async def test_get_current_active_user_inactive(self):
        """Test getting inactive user raises exception."""
        mock_user = Mock(spec=User, id=1, is_active=False)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(current_user=mock_user)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "inactive" in exc_info.value.detail.lower()


# ============================================================================
# Test get_current_superuser
# ============================================================================


class TestGetCurrentSuperuser:
    """Tests for get_current_superuser function."""

    @pytest.mark.asyncio
    async def test_get_current_superuser_success(self):
        """Test getting superuser."""
        mock_user = Mock(spec=User, id=1, is_superuser=True)

        user = await get_current_superuser(current_user=mock_user)

        assert user == mock_user

    @pytest.mark.asyncio
    async def test_get_current_superuser_not_superuser(self):
        """Test getting non-superuser raises exception."""
        mock_user = Mock(spec=User, id=1, is_superuser=False)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_superuser(current_user=mock_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "permission" in exc_info.value.detail.lower()


# ============================================================================
# Test register endpoint
# ============================================================================


class TestRegisterEndpoint:
    """Tests for user registration endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(self):
        """Test successful user registration."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock that username and email don't exist
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!",
            full_name="Test User",
        )

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.SecurityConfig"
        ) as mock_security:
            mock_security.validate_password_strength.return_value = {"valid": True}
            mock_security.sanitize_user_input = lambda x, _: x

            await register(user_data=user_data, db=mock_db)

            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_register_weak_password(self):
        """Test registration with weak password."""
        mock_db = AsyncMock(spec=AsyncSession)

        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="weak",
        )

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.SecurityConfig"
        ) as mock_security:
            mock_security.validate_password_strength.return_value = {
                "valid": False,
                "issues": ["Too short", "No special characters"],
            }

            with pytest.raises(HTTPException) as exc_info:
                await register(user_data=user_data, db=mock_db)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "weak" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_register_username_exists(self):
        """Test registration with existing username."""
        mock_db = AsyncMock(spec=AsyncSession)

        existing_user = Mock(spec=User, username="testuser")
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!",
        )

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.SecurityConfig"
        ) as mock_security:
            mock_security.validate_password_strength.return_value = {"valid": True}
            mock_security.sanitize_user_input = lambda x, _: x

            with pytest.raises(HTTPException) as exc_info:
                await register(user_data=user_data, db=mock_db)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "username" in exc_info.value.detail.lower()
            assert "registered" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_register_email_exists(self):
        """Test registration with existing email."""
        mock_db = AsyncMock(spec=AsyncSession)

        # First query (username) returns None, second (email) returns existing user
        mock_result_username = AsyncMock()
        mock_result_username.scalar_one_or_none.return_value = None

        existing_user = Mock(spec=User, email="test@example.com")
        mock_result_email = AsyncMock()
        mock_result_email.scalar_one_or_none.return_value = existing_user

        mock_db.execute = AsyncMock(
            side_effect=[mock_result_username, mock_result_email]
        )

        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="StrongPassword123!",
        )

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.SecurityConfig"
        ) as mock_security:
            mock_security.validate_password_strength.return_value = {"valid": True}
            mock_security.sanitize_user_input = lambda x, _: x

            with pytest.raises(HTTPException) as exc_info:
                await register(user_data=user_data, db=mock_db)

            assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
            assert "email" in exc_info.value.detail.lower()
            assert "registered" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_register_sanitizes_inputs(self):
        """Test that registration sanitizes user inputs."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        user_data = UserCreate(
            username="test<script>",
            email="test@example.com",
            password="StrongPassword123!",
            full_name="<b>Test</b>",
        )

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.SecurityConfig"
        ) as mock_security:
            mock_security.validate_password_strength.return_value = {"valid": True}
            sanitized_values = {}

            def sanitize_mock(value, max_len):
                sanitized = value.replace("<", "").replace(">", "")
                sanitized_values[value] = sanitized
                return sanitized

            mock_security.sanitize_user_input = sanitize_mock

            await register(user_data=user_data, db=mock_db)

            # Verify sanitization was called
            assert "test<script>" in sanitized_values
            assert sanitized_values["test<script>"] == "testscript"


# ============================================================================
# Test login endpoint
# ============================================================================


class TestLoginEndpoint:
    """Tests for user login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success_with_username(self):
        """Test successful login with username."""
        mock_db = AsyncMock(spec=AsyncSession)

        password = "test_password"
        hashed = get_password_hash(password)

        mock_user = Mock(
            spec=User,
            id=1,
            username="testuser",
            password_hash=hashed,
            is_active=True,
            last_login_at=None,
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        login_data = LoginRequest(username="testuser", password=password)

        response = await login(login_data=login_data, db=mock_db)

        assert response.access_token is not None
        assert response.token_type == "bearer"
        assert response.user == mock_user
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_login_success_with_email(self):
        """Test successful login with email."""
        mock_db = AsyncMock(spec=AsyncSession)

        password = "test_password"
        hashed = get_password_hash(password)

        mock_user = Mock(
            spec=User,
            id=1,
            email="test@example.com",
            password_hash=hashed,
            is_active=True,
            last_login_at=None,
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        login_data = LoginRequest(username="test@example.com", password=password)

        response = await login(login_data=login_data, db=mock_db)

        assert response.access_token is not None
        assert response.token_type == "bearer"

    @pytest.mark.asyncio
    async def test_login_user_not_found(self):
        """Test login with non-existent user."""
        mock_db = AsyncMock(spec=AsyncSession)

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        login_data = LoginRequest(username="nonexistent", password="password")

        with pytest.raises(HTTPException) as exc_info:
            await login(login_data=login_data, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "incorrect" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self):
        """Test login with wrong password."""
        mock_db = AsyncMock(spec=AsyncSession)

        password = "correct_password"
        hashed = get_password_hash(password)

        mock_user = Mock(
            spec=User,
            id=1,
            username="testuser",
            password_hash=hashed,
            is_active=True,
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        login_data = LoginRequest(username="testuser", password="wrong_password")

        with pytest.raises(HTTPException) as exc_info:
            await login(login_data=login_data, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "incorrect" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_login_inactive_user(self):
        """Test login with inactive user."""
        mock_db = AsyncMock(spec=AsyncSession)

        password = "test_password"
        hashed = get_password_hash(password)

        mock_user = Mock(
            spec=User,
            id=1,
            username="testuser",
            password_hash=hashed,
            is_active=False,
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        login_data = LoginRequest(username="testuser", password=password)

        with pytest.raises(HTTPException) as exc_info:
            await login(login_data=login_data, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "inactive" in exc_info.value.detail.lower()


# ============================================================================
# Test refresh token endpoint
# ============================================================================


class TestRefreshTokenEndpoint:
    """Tests for token refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Test successful token refresh."""
        mock_user = Mock(spec=User, id=1, is_active=True)

        response = await refresh_token(current_user=mock_user)

        assert "access_token" in response
        assert response["token_type"] == "bearer"
        assert isinstance(response["access_token"], str)

    @pytest.mark.asyncio
    async def test_refresh_token_contains_user_id(self):
        """Test that refreshed token contains user ID."""
        mock_user = Mock(spec=User, id=123, is_active=True)

        response = await refresh_token(current_user=mock_user)

        # Decode token to verify it contains user ID
        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
            "test_secret",
        ):
            with patch(
                "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM",
                "HS256",
            ):
                decoded = jwt.decode(
                    response["access_token"],
                    "test_secret",
                    algorithms=["HS256"],
                )
                assert decoded["sub"] == "123"


# ============================================================================
# Integration Tests
# ============================================================================


class TestAuthIntegration:
    """Integration tests for authentication flow."""

    @pytest.mark.asyncio
    async def test_full_registration_and_login_flow(self):
        """Test complete registration and login flow."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Registration
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        user_data = UserCreate(
            username="newuser",
            email="new@example.com",
            password="SecurePass123!",
        )

        with patch(
            "revitpy_package_manager.registry.api.routers.auth.SecurityConfig"
        ) as mock_security:
            mock_security.validate_password_strength.return_value = {"valid": True}
            mock_security.sanitize_user_input = lambda x, _: x

            await register(user_data=user_data, db=mock_db)
            mock_db.add.assert_called_once()

        # Login
        password = "SecurePass123!"
        hashed = get_password_hash(password)

        mock_user = Mock(
            spec=User,
            id=1,
            username="newuser",
            password_hash=hashed,
            is_active=True,
            last_login_at=None,
        )

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)

        login_data = LoginRequest(username="newuser", password=password)
        login_response = await login(login_data=login_data, db=mock_db)

        assert login_response.access_token is not None
        assert login_response.token_type == "bearer"

    def test_password_hashing_security(self):
        """Test that password hashing is secure."""
        passwords = ["password1", "password2", "password3"]
        hashes = [get_password_hash(pwd) for pwd in passwords]

        # All hashes should be different
        assert len(set(hashes)) == len(passwords)

        # Verify each password with its hash
        for pwd, hashed in zip(passwords, hashes, strict=False):
            assert verify_password(pwd, hashed) is True

        # Cross-verify should fail
        assert verify_password(passwords[0], hashes[1]) is False

    @pytest.mark.asyncio
    async def test_token_security(self):
        """Test JWT token security features."""
        # Test that tokens with different secrets fail validation
        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
            "secret1",
        ):
            with patch(
                "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM",
                "HS256",
            ):
                token = create_access_token({"sub": "user123"})

        # Try to decode with different secret
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode(token, "wrong_secret", algorithms=["HS256"])

        # Try to decode with different algorithm
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode(token, "secret1", algorithms=["HS512"])
