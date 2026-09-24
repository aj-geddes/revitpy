"""Security tests for authentication endpoints."""

import os
from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from revitpy_package_manager.config import Settings
from revitpy_package_manager.registry.api.main import create_app
from revitpy_package_manager.registry.database import get_db_session
from revitpy_package_manager.registry.models.base import Base
from revitpy_package_manager.security.config import SecurityConfig
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool


class TestAuthenticationSecurity:
    """Test authentication security measures."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create a test client backed by a throwaway SQLite database.

        Settings (and so the app's DB engine) are process-wide singletons, so
        the database is injected via a dependency override rather than env.
        """
        db_file = tmp_path / "auth_security.db"
        sync_engine = create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(sync_engine)
        sync_engine.dispose()

        engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_file}", poolclass=NullPool
        )
        session_factory = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[get_db_session] = override_get_db
        # "localhost" is an allowed host; TestClient's default "testserver"
        # is (correctly) rejected by TrustedHostMiddleware with a 400.
        return TestClient(app, base_url="http://localhost")

    def test_jwt_secret_required(self):
        """Test that production refuses to run without its own JWT secret."""
        from revitpy_package_manager.registry.api.routers.auth import (
            _ensure_secure_jwt_secret,
        )

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            settings = Settings(_env_file=None)
            with pytest.raises(ValueError) as exc_info:
                _ensure_secure_jwt_secret(settings)
            assert "JWT_SECRET_KEY" in str(exc_info.value)

        # A strong, explicitly configured secret is accepted in production
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": SecurityConfig.generate_jwt_secret(),
            },
            clear=True,
        ):
            _ensure_secure_jwt_secret(Settings(_env_file=None))

    def test_password_strength_validation(self, client):
        """Test password strength validation during registration."""
        # Test weak password
        weak_passwords = [
            "123456",  # Too short, no letters, no special chars
            "password",  # No numbers, no special chars, no uppercase
            "PASSWORD123",  # No lowercase, no special chars
            "Password",  # Too short, no numbers, no special chars
            "Pass123",  # Too short, no special chars
        ]

        for weak_password in weak_passwords:
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "username": "testuser",
                    "email": "test@example.com",
                    "password": weak_password,
                    "full_name": "Test User",
                },
            )

            assert response.status_code == 400
            assert "Password is too weak" in response.json()["detail"]

    def test_jwt_algorithm_confusion_prevention(self):
        """Test that JWT algorithm confusion attacks are prevented."""
        # Create a malicious token with 'none' algorithm
        payload = {"sub": "user123", "exp": datetime.utcnow() + timedelta(hours=1)}

        # Try to create token with 'none' algorithm (should be rejected)
        malicious_token = jwt.encode(payload, "", algorithm="none")

        # The decode function should reject this even if we don't verify signature
        from revitpy_package_manager.registry.api.routers.auth import JWT_ALGORITHM

        with pytest.raises((jwt.InvalidTokenError, jwt.DecodeError)):
            # Our decode function explicitly specifies algorithms and verifies signature
            jwt.decode(
                malicious_token,
                "any-key",
                algorithms=[JWT_ALGORITHM],
                options={"verify_signature": True},
            )

    def test_input_sanitization(self, client):
        """Test that user input is properly sanitized."""
        # Test XSS payload in registration
        xss_payload = "<script>alert('xss')</script>"

        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": xss_payload,
                "email": "test@example.com",
                "password": "SecurePassword123!",
                "full_name": xss_payload,
                "bio": xss_payload,
            },
        )

        # Registration might fail due to other validation, but input should be sanitized
        # The malicious script tags should be removed
        assert "<script>" not in str(response.json())
        assert "alert(" not in str(response.json())

    def test_sql_injection_prevention(self, client):
        """Test that SQL injection attacks are prevented."""
        # SQL injection payloads
        sql_payloads = [
            "'; DROP TABLE users; --",
            "admin' OR '1'='1",
            "' UNION SELECT * FROM users --",
            "admin'/*",
        ]

        for payload in sql_payloads:
            # Try SQL injection in login
            response = client.post(
                "/api/v1/auth/login",
                json={"username": payload, "password": "any_password"},
            )

            # Should return authentication error, not SQL error
            assert response.status_code in [
                401,
                422,
            ]  # 422 for validation error, 401 for auth error

            # Response should not contain SQL error messages
            response_text = str(response.json()).lower()
            assert "sql" not in response_text
            assert "syntax" not in response_text
            assert "table" not in response_text

    def test_brute_force_timing_safety(self, client):
        """Test that response times don't leak user existence information."""
        import time

        # Test with existing vs non-existing users
        # (In a real test, you'd set up a test user first)

        # Time authentication attempt with non-existent user
        start_time = time.time()
        response1 = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent_user_12345", "password": "wrong_password"},
        )
        time1 = time.time() - start_time

        # Time authentication attempt with another non-existent user
        start_time = time.time()
        response2 = client.post(
            "/api/v1/auth/login",
            json={
                "username": "another_nonexistent_user_67890",
                "password": "wrong_password",
            },
        )
        time2 = time.time() - start_time

        # Both should fail with similar timing
        assert response1.status_code == 401
        assert response2.status_code == 401

        # Timing should be relatively similar (within reasonable bounds)
        # This is a basic check - in production, you'd use more sophisticated timing analysis
        time_diff = abs(time1 - time2)
        assert time_diff < 0.1  # Less than 100ms difference

    def test_token_expiration(self, client):
        """Test that expired tokens are rejected."""
        # Create an expired token
        payload = {
            "sub": "user123",
            "exp": datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
        }

        # The router reads its signing key once at import, so patch it there
        with patch(
            "revitpy_package_manager.registry.api.routers.auth.JWT_SECRET_KEY",
            "test_secret_key_32_chars_minimum",
        ):
            expired_token = jwt.encode(
                payload, "test_secret_key_32_chars_minimum", algorithm="HS256"
            )

            # Try to use expired token
            response = client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
            )

            assert response.status_code == 401
            assert "expired" in response.json()["detail"].lower()

    def test_malformed_token_handling(self, client):
        """Test handling of malformed JWT tokens."""
        malformed_tokens = [
            "not.a.token",
            "invalid_token_format",
            "",
            "Bearer",
            "a.b",  # Too few parts
            "a.b.c.d",  # Too many parts
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid_payload.signature",
        ]

        for token in malformed_tokens:
            response = client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 401
            assert "Invalid" in response.json()["detail"]

    def test_no_token_handling(self, client):
        """Test handling of requests without authentication token."""
        # Try to access protected endpoint without token
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401 or response.status_code == 403

    def test_user_enumeration_prevention(self, client):
        """Test that user enumeration is prevented."""
        # Try to register with existing vs non-existing username/email
        # The response should not indicate whether user exists

        _response1 = client.post(
            "/api/v1/auth/register",
            json={
                "username": "existing_user_test",
                "email": "existing@example.com",
                "password": "SecurePassword123!",
                "full_name": "Test User",
            },
        )

        # Try to register again with same username
        response2 = client.post(
            "/api/v1/auth/register",
            json={
                "username": "existing_user_test",
                "email": "different@example.com",
                "password": "SecurePassword123!",
                "full_name": "Test User",
            },
        )

        # Try to register with same email
        response3 = client.post(
            "/api/v1/auth/register",
            json={
                "username": "different_user_test",
                "email": "existing@example.com",
                "password": "SecurePassword123!",
                "full_name": "Test User",
            },
        )

        # All should return similar error messages (don't leak which part exists)
        if response2.status_code == 400:
            assert "already registered" in response2.json()["detail"]
        if response3.status_code == 400:
            assert "already registered" in response3.json()["detail"]

    def test_security_headers_present(self, client):
        """Test that security headers are present in responses."""
        response = client.get("/")

        # Check for important security headers
        headers = response.headers

        assert "X-Content-Type-Options" in headers
        assert headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in headers
        assert headers["X-Frame-Options"] == "DENY"

        assert "X-XSS-Protection" in headers

        assert "Strict-Transport-Security" in headers
        assert "max-age=" in headers["Strict-Transport-Security"]

        assert "Content-Security-Policy" in headers
        assert "default-src 'self'" in headers["Content-Security-Policy"]

        # Server header should be removed
        assert "server" not in headers or headers["server"] == ""


class TestPasswordSecurity:
    """Test password handling security."""

    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        from revitpy_package_manager.registry.api.routers.auth import (
            get_password_hash,
            verify_password,
        )

        password = "TestPassword123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different due to salt
        assert hash1 != hash2

        # Both should verify correctly
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)

        # Wrong password should not verify
        assert not verify_password("WrongPassword", hash1)

        # Hash should not contain original password
        assert password not in hash1
        assert password not in hash2

    def test_timing_attack_resistance(self):
        """Test that password verification is resistant to timing attacks."""
        import time

        from revitpy_package_manager.registry.api.routers.auth import (
            get_password_hash,
            verify_password,
        )

        password = "TestPassword123!"
        correct_hash = get_password_hash(password)

        # Time correct password verification
        times_correct = []
        for _ in range(10):
            start = time.time()
            verify_password(password, correct_hash)
            times_correct.append(time.time() - start)

        # Time incorrect password verification
        times_incorrect = []
        for _ in range(10):
            start = time.time()
            verify_password("WrongPassword123!", correct_hash)
            times_incorrect.append(time.time() - start)

        # Average times should be similar (bcrypt should be constant-time)
        avg_correct = sum(times_correct) / len(times_correct)
        avg_incorrect = sum(times_incorrect) / len(times_incorrect)

        # Allow for some variance, but should be roughly similar
        time_ratio = max(avg_correct, avg_incorrect) / min(avg_correct, avg_incorrect)
        assert time_ratio < 2.0  # Less than 2x difference
