"""Standalone test runner for authentication router.

This script tests the auth router without requiring pytest or database setup.
Run with: python tests/run_auth_router_tests.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock modules before importing
sys.modules["revitpy_package_manager.registry.database"] = Mock()
sys.modules["revitpy_package_manager.registry.security"] = Mock()
sys.modules["revitpy_package_manager.registry.security.config"] = Mock()

import jwt
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
from revitpy_package_manager.registry.api.schemas import LoginRequest, UserCreate

# ============================================================================
# Test Utilities
# ============================================================================


class TestRunner:
    """Simple test runner for standalone tests."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    async def run_test(self, test_func, test_name):
        """Run a single test function."""
        try:
            if asyncio.iscoroutinefunction(test_func):
                await test_func()
            else:
                test_func()
            self.passed += 1
            print(f"  ✅ {test_name}")
        except AssertionError as e:
            self.failed += 1
            self.errors.append((test_name, str(e)))
            print(f"  ❌ {test_name}: {e}")
        except Exception as e:
            self.failed += 1
            self.errors.append((test_name, f"Error: {e}"))
            print(f"  ❌ {test_name}: Error: {e}")

    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print("\n" + "=" * 70)
        if self.failed == 0:
            print("  ✅ ALL TESTS PASSED! 🎉")
        else:
            print("  ⚠️  SOME TESTS FAILED")
        print("=" * 70)
        print(f"\nTotal: {total} | Passed: {self.passed} | Failed: {self.failed}\n")

        if self.errors:
            print("Failed tests:")
            for test_name, error in self.errors:
                print(f"  - {test_name}: {error}")


runner = TestRunner()


# ============================================================================
# Test Password Hashing
# ============================================================================


def test_hash_password():
    """Test password hashing."""
    password = "test_password_123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")


def test_verify_password_correct():
    """Test verifying correct password."""
    password = "test_password_123"
    hashed = get_password_hash(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Test verifying incorrect password."""
    password = "test_password_123"
    hashed = get_password_hash(password)

    assert verify_password("wrong_password", hashed) is False


def test_hash_different_for_same_password():
    """Test that hashing same password produces different hashes."""
    password = "test_password_123"
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)

    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


# ============================================================================
# Test JWT Token Creation
# ============================================================================


def test_create_access_token():
    """Test creating an access token."""
    data = {"sub": "user123"}
    token = create_access_token(data)

    assert isinstance(token, str)
    assert len(token.split(".")) == 3


def test_create_access_token_with_expiration():
    """Test creating token with custom expiration."""
    data = {"sub": "user123"}
    expires_delta = timedelta(minutes=30)

    # Import the actual secret used by the auth module
    from revitpy_package_manager.registry.api.routers import auth

    token = create_access_token(data, expires_delta)
    decoded = jwt.decode(token, auth.JWT_SECRET_KEY, algorithms=[auth.JWT_ALGORITHM])
    exp = datetime.utcfromtimestamp(decoded["exp"])
    now = datetime.utcnow()

    delta = (exp - now).total_seconds()
    assert 1790 < delta < 1810


def test_token_contains_data():
    """Test that token contains the provided data."""
    data = {"sub": "user123", "username": "testuser"}

    with patch(
        "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
        "test_secret",
    ):
        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM", "HS256"
        ):
            token = create_access_token(data)
            decoded = jwt.decode(token, "test_secret", algorithms=["HS256"])

            assert decoded["sub"] == "user123"
            assert decoded["username"] == "testuser"
            assert "exp" in decoded


# ============================================================================
# Test get_current_user
# ============================================================================


async def test_get_current_user_success():
    """Test getting current user with valid token."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1, is_active=True, last_login_at=None)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_credentials = Mock()

    with patch(
        "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
        "test_secret",
    ):
        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM", "HS256"
        ):
            token = jwt.encode(
                {"sub": "1", "exp": datetime.utcnow() + timedelta(hours=1)},
                "test_secret",
                algorithm="HS256",
            )
            mock_credentials.credentials = token

            user = await get_current_user(credentials=mock_credentials, db=mock_db)

            assert user == mock_user
            mock_db.commit.assert_awaited_once()


async def test_get_current_user_expired_token():
    """Test getting current user with expired token."""
    mock_db = AsyncMock()
    mock_credentials = Mock()

    with patch(
        "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
        "test_secret",
    ):
        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM", "HS256"
        ):
            token = jwt.encode(
                {"sub": "1", "exp": datetime.utcnow() - timedelta(hours=1)},
                "test_secret",
                algorithm="HS256",
            )
            mock_credentials.credentials = token

            try:
                await get_current_user(credentials=mock_credentials, db=mock_db)
                raise AssertionError("Should have raised HTTPException")
            except Exception as e:
                assert hasattr(e, "status_code")
                assert e.status_code == 401


async def test_get_current_user_invalid_token():
    """Test getting current user with invalid token."""
    mock_db = AsyncMock()
    mock_credentials = Mock()
    mock_credentials.credentials = "invalid.token.string"

    try:
        await get_current_user(credentials=mock_credentials, db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")


async def test_get_current_user_not_found():
    """Test getting current user when user not in database."""
    mock_db = AsyncMock()
    mock_credentials = Mock()

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch(
        "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
        "test_secret",
    ):
        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM", "HS256"
        ):
            token = jwt.encode(
                {"sub": "999", "exp": datetime.utcnow() + timedelta(hours=1)},
                "test_secret",
                algorithm="HS256",
            )
            mock_credentials.credentials = token

            try:
                await get_current_user(credentials=mock_credentials, db=mock_db)
                raise AssertionError("Should have raised HTTPException")
            except Exception as e:
                assert hasattr(e, "status_code")
                assert e.status_code == 401


async def test_get_current_user_inactive():
    """Test getting current user when user is inactive."""
    mock_db = AsyncMock()
    mock_user = Mock(id=1, is_active=False)

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_credentials = Mock()

    with patch(
        "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
        "test_secret",
    ):
        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM", "HS256"
        ):
            token = jwt.encode(
                {"sub": "1", "exp": datetime.utcnow() + timedelta(hours=1)},
                "test_secret",
                algorithm="HS256",
            )
            mock_credentials.credentials = token

            try:
                await get_current_user(credentials=mock_credentials, db=mock_db)
                raise AssertionError("Should have raised HTTPException")
            except Exception as e:
                assert hasattr(e, "status_code")


# ============================================================================
# Test get_current_active_user
# ============================================================================


async def test_get_current_active_user_success():
    """Test getting active user."""
    mock_user = Mock(id=1, is_active=True)

    user = await get_current_active_user(current_user=mock_user)

    assert user == mock_user


async def test_get_current_active_user_inactive():
    """Test getting inactive user raises exception."""
    mock_user = Mock(id=1, is_active=False)

    try:
        await get_current_active_user(current_user=mock_user)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 400


# ============================================================================
# Test get_current_superuser
# ============================================================================


async def test_get_current_superuser_success():
    """Test getting superuser."""
    mock_user = Mock(id=1, is_superuser=True)

    user = await get_current_superuser(current_user=mock_user)

    assert user == mock_user


async def test_get_current_superuser_not_superuser():
    """Test getting non-superuser raises exception."""
    mock_user = Mock(id=1, is_superuser=False)

    try:
        await get_current_superuser(current_user=mock_user)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 403


# ============================================================================
# Test register endpoint
# ============================================================================


async def test_register_success():
    """Test successful user registration."""
    mock_db = AsyncMock()

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


async def test_register_weak_password():
    """Test registration with weak password."""
    AsyncMock()

    # Pydantic validation will catch passwords that are too short
    try:
        UserCreate(
            username="testuser",
            email="test@example.com",
            password="weak",  # Too short, will fail Pydantic validation
        )
        raise AssertionError("Should have raised ValidationError")
    except Exception as e:
        # Pydantic ValidationError expected
        assert "validation error" in str(e).lower() or "too short" in str(e).lower()


async def test_register_username_exists():
    """Test registration with existing username."""
    mock_db = AsyncMock()

    existing_user = Mock(username="testuser")
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

        try:
            await register(user_data=user_data, db=mock_db)
            raise AssertionError("Should have raised HTTPException")
        except Exception as e:
            assert hasattr(e, "status_code")
            assert e.status_code == 400


async def test_register_email_exists():
    """Test registration with existing email."""
    mock_db = AsyncMock()

    mock_result_username = AsyncMock()
    mock_result_username.scalar_one_or_none.return_value = None

    existing_user = Mock(email="test@example.com")
    mock_result_email = AsyncMock()
    mock_result_email.scalar_one_or_none.return_value = existing_user

    mock_db.execute = AsyncMock(side_effect=[mock_result_username, mock_result_email])

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

        try:
            await register(user_data=user_data, db=mock_db)
            raise AssertionError("Should have raised HTTPException")
        except Exception as e:
            assert hasattr(e, "status_code")
            assert e.status_code == 400


# ============================================================================
# Test login endpoint
# ============================================================================


async def test_login_success_with_username():
    """Test successful login with username."""
    mock_db = AsyncMock()

    password = "test_password"
    hashed = get_password_hash(password)

    mock_user = Mock(
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


async def test_login_user_not_found():
    """Test login with non-existent user."""
    mock_db = AsyncMock()

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    login_data = LoginRequest(username="nonexistent", password="password")

    try:
        await login(login_data=login_data, db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 401


async def test_login_wrong_password():
    """Test login with wrong password."""
    mock_db = AsyncMock()

    password = "correct_password"
    hashed = get_password_hash(password)

    mock_user = Mock(
        id=1,
        username="testuser",
        password_hash=hashed,
        is_active=True,
    )

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    login_data = LoginRequest(username="testuser", password="wrong_password")

    try:
        await login(login_data=login_data, db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 401


async def test_login_inactive_user():
    """Test login with inactive user."""
    mock_db = AsyncMock()

    password = "test_password"
    hashed = get_password_hash(password)

    mock_user = Mock(
        id=1,
        username="testuser",
        password_hash=hashed,
        is_active=False,
    )

    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    login_data = LoginRequest(username="testuser", password=password)

    try:
        await login(login_data=login_data, db=mock_db)
        raise AssertionError("Should have raised HTTPException")
    except Exception as e:
        assert hasattr(e, "status_code")
        assert e.status_code == 400


# ============================================================================
# Test refresh token endpoint
# ============================================================================


async def test_refresh_token_success():
    """Test successful token refresh."""
    mock_user = Mock(id=1, is_active=True)

    response = await refresh_token(current_user=mock_user)

    assert "access_token" in response
    assert response["token_type"] == "bearer"
    assert isinstance(response["access_token"], str)


async def test_refresh_token_contains_user_id():
    """Test that refreshed token contains user ID."""
    from revitpy_package_manager.registry.api.routers import auth

    mock_user = Mock(id=123, is_active=True)

    response = await refresh_token(current_user=mock_user)

    decoded = jwt.decode(
        response["access_token"],
        auth.JWT_SECRET_KEY,
        algorithms=[auth.JWT_ALGORITHM],
    )
    assert decoded["sub"] == "123"


# ============================================================================
# Integration Tests
# ============================================================================


def test_password_hashing_security():
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


def test_token_security():
    """Test JWT token security features."""
    with patch(
        "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY", "secret1"
    ):
        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_ALGORITHM", "HS256"
        ):
            token = create_access_token({"sub": "user123"})

    # Try to decode with different secret
    try:
        jwt.decode(token, "wrong_secret", algorithms=["HS256"])
        raise AssertionError("Should have raised InvalidTokenError")
    except jwt.InvalidTokenError:
        pass  # Expected

    # Try to decode with different algorithm
    try:
        jwt.decode(token, "secret1", algorithms=["HS512"])
        raise AssertionError("Should have raised InvalidTokenError")
    except jwt.InvalidTokenError:
        pass  # Expected


# ============================================================================
# Main Test Runner
# ============================================================================


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  Testing Authentication Router")
    print("=" * 70 + "\n")

    # Password hashing tests
    print("Testing password hashing:")
    await runner.run_test(test_hash_password, "hash_password")
    await runner.run_test(test_verify_password_correct, "verify_password_correct")
    await runner.run_test(test_verify_password_incorrect, "verify_password_incorrect")
    await runner.run_test(
        test_hash_different_for_same_password, "hash_different_for_same_password"
    )

    # JWT token tests
    print("\nTesting JWT tokens:")
    await runner.run_test(test_create_access_token, "create_access_token")
    await runner.run_test(
        test_create_access_token_with_expiration, "create_access_token_with_expiration"
    )
    await runner.run_test(test_token_contains_data, "token_contains_data")

    # get_current_user tests
    print("\nTesting get_current_user:")
    await runner.run_test(test_get_current_user_success, "get_current_user_success")
    await runner.run_test(
        test_get_current_user_expired_token, "get_current_user_expired_token"
    )
    await runner.run_test(
        test_get_current_user_invalid_token, "get_current_user_invalid_token"
    )
    await runner.run_test(test_get_current_user_not_found, "get_current_user_not_found")
    await runner.run_test(test_get_current_user_inactive, "get_current_user_inactive")

    # get_current_active_user tests
    print("\nTesting get_current_active_user:")
    await runner.run_test(
        test_get_current_active_user_success, "get_current_active_user_success"
    )
    await runner.run_test(
        test_get_current_active_user_inactive, "get_current_active_user_inactive"
    )

    # get_current_superuser tests
    print("\nTesting get_current_superuser:")
    await runner.run_test(
        test_get_current_superuser_success, "get_current_superuser_success"
    )
    await runner.run_test(
        test_get_current_superuser_not_superuser, "get_current_superuser_not_superuser"
    )

    # register endpoint tests
    print("\nTesting register endpoint:")
    await runner.run_test(test_register_success, "register_success")
    await runner.run_test(test_register_weak_password, "register_weak_password")
    await runner.run_test(test_register_username_exists, "register_username_exists")
    await runner.run_test(test_register_email_exists, "register_email_exists")

    # login endpoint tests
    print("\nTesting login endpoint:")
    await runner.run_test(
        test_login_success_with_username, "login_success_with_username"
    )
    await runner.run_test(test_login_user_not_found, "login_user_not_found")
    await runner.run_test(test_login_wrong_password, "login_wrong_password")
    await runner.run_test(test_login_inactive_user, "login_inactive_user")

    # refresh token tests
    print("\nTesting refresh token endpoint:")
    await runner.run_test(test_refresh_token_success, "refresh_token_success")
    await runner.run_test(
        test_refresh_token_contains_user_id, "refresh_token_contains_user_id"
    )

    # Integration tests
    print("\nTesting integration scenarios:")
    await runner.run_test(test_password_hashing_security, "password_hashing_security")
    await runner.run_test(test_token_security, "token_security")

    runner.print_summary()

    return runner.failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
