"""Tests for security configuration and validation."""

import os
from unittest.mock import patch

import pytest
from revitpy_package_manager.security.config import (
    SecurityConfig,
    ensure_secure_environment,
)


class TestSecurityConfig:
    """Test security configuration functionality."""

    def test_generate_jwt_secret(self):
        """Test JWT secret generation."""
        secret1 = SecurityConfig.generate_jwt_secret()
        secret2 = SecurityConfig.generate_jwt_secret()

        # Should be different each time
        assert secret1 != secret2

        # Should meet length requirements
        assert len(secret1) == 64
        assert len(secret2) == 64

        # Should be valid
        assert SecurityConfig.validate_jwt_secret(secret1)
        assert SecurityConfig.validate_jwt_secret(secret2)

    def test_validate_jwt_secret(self):
        """Test JWT secret validation."""
        # Valid secrets
        assert SecurityConfig.validate_jwt_secret("a" * 32)
        assert SecurityConfig.validate_jwt_secret("a" * 64)

        # Invalid secrets
        assert not SecurityConfig.validate_jwt_secret(None)
        assert not SecurityConfig.validate_jwt_secret("")
        assert not SecurityConfig.validate_jwt_secret("short")
        assert not SecurityConfig.validate_jwt_secret("a" * 31)

    def test_validate_password_strength(self):
        """Test password strength validation."""
        # Strong password
        result = SecurityConfig.validate_password_strength("MyStrongP@ssw0rd123!")
        assert result["valid"] is True
        assert result["strength"] == 5
        assert len(result["issues"]) == 0

        # Weak password - too short
        result = SecurityConfig.validate_password_strength("weak")
        assert result["valid"] is False
        assert "12 characters" in str(result["issues"])

        # Missing uppercase
        result = SecurityConfig.validate_password_strength("mystrongp@ssw0rd123!")
        assert result["valid"] is False
        assert "uppercase" in str(result["issues"])

        # Missing numbers
        result = SecurityConfig.validate_password_strength("MyStrongP@ssword!")
        assert result["valid"] is False
        assert "numbers" in str(result["issues"])

        # Missing special characters
        result = SecurityConfig.validate_password_strength("MyStrongPassw0rd123")
        assert result["valid"] is False
        assert "special" in str(result["issues"])

    def test_validate_filename(self):
        """Test filename validation for security."""
        # Valid filenames
        assert SecurityConfig.validate_filename("package.py")
        assert SecurityConfig.validate_filename("module.pyi")
        assert SecurityConfig.validate_filename("data.json")
        assert SecurityConfig.validate_filename("config.yaml")
        assert SecurityConfig.validate_filename("README.md")
        assert SecurityConfig.validate_filename("setup.cfg")
        assert SecurityConfig.validate_filename("package.zip")
        assert SecurityConfig.validate_filename("package.whl")

        # Invalid filenames - path traversal
        assert not SecurityConfig.validate_filename("../../../etc/passwd")
        assert not SecurityConfig.validate_filename("..\\windows\\system32")
        assert not SecurityConfig.validate_filename("~/secret.txt")

        # Invalid filenames - system directories
        assert not SecurityConfig.validate_filename("/etc/passwd")
        assert not SecurityConfig.validate_filename("system32/config")
        assert not SecurityConfig.validate_filename("program files/app")

        # Invalid filenames - version control
        assert not SecurityConfig.validate_filename(".git/config")
        assert not SecurityConfig.validate_filename("__pycache__/module.pyc")

        # Invalid extensions
        assert not SecurityConfig.validate_filename("malware.exe")
        assert not SecurityConfig.validate_filename("script.sh")
        assert not SecurityConfig.validate_filename("dangerous.bat")

        # No extension
        assert not SecurityConfig.validate_filename("noextension")

    def test_sanitize_user_input(self):
        """Test user input sanitization."""
        # Normal input
        assert SecurityConfig.sanitize_user_input("normal text") == "normal text"

        # With whitespace
        assert (
            SecurityConfig.sanitize_user_input("  text with spaces  ")
            == "text with spaces"
        )

        # With control characters
        input_with_nulls = "text\x00with\x01nulls\x02"
        assert SecurityConfig.sanitize_user_input(input_with_nulls) == "textwithwithws"

        # Preserve allowed whitespace
        assert (
            SecurityConfig.sanitize_user_input("line1\nline2\tindented")
            == "line1\nline2\tindented"
        )

        # Truncate long input
        long_input = "a" * 2000
        result = SecurityConfig.sanitize_user_input(long_input, 100)
        assert len(result) == 100

        # Non-string input
        assert SecurityConfig.sanitize_user_input(None) == ""
        assert SecurityConfig.sanitize_user_input(123) == ""

    def test_get_security_headers(self):
        """Test security headers generation."""
        headers = SecurityConfig.get_security_headers()

        # Check required security headers are present
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Strict-Transport-Security" in headers
        assert "Content-Security-Policy" in headers
        assert "Referrer-Policy" in headers
        assert "Permissions-Policy" in headers

        # Check header values
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert "max-age=" in headers["Strict-Transport-Security"]
        assert "default-src 'self'" in headers["Content-Security-Policy"]


class TestSecureEnvironment:
    """Test secure environment validation."""

    def test_ensure_secure_environment_success(self):
        """Test successful environment validation."""
        with patch.dict(
            os.environ,
            {
                "JWT_SECRET_KEY": "a" * 64,  # 64-character secret
                "DATABASE_URL": "postgresql://user:pass@localhost/db",
            },
        ):
            # Should not raise any exception
            ensure_secure_environment()

    def test_ensure_secure_environment_missing_jwt(self):
        """Test environment validation with missing JWT secret."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@localhost/db"},
            clear=True,
        ):
            with pytest.raises(ValueError) as exc_info:
                ensure_secure_environment()
            assert "JWT_SECRET_KEY" in str(exc_info.value)

    def test_ensure_secure_environment_weak_jwt(self):
        """Test environment validation with weak JWT secret."""
        with patch.dict(
            os.environ,
            {
                "JWT_SECRET_KEY": "weak",  # Too short
                "DATABASE_URL": "postgresql://user:pass@localhost/db",
            },
        ):
            with pytest.raises(ValueError) as exc_info:
                ensure_secure_environment()
            assert "insufficient entropy" in str(exc_info.value)

    def test_ensure_secure_environment_missing_database(self):
        """Test environment validation with missing database URL."""
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "a" * 64}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                ensure_secure_environment()
            assert "DATABASE_URL" in str(exc_info.value)


class TestSecurityUtilities:
    """Test security utility functions."""

    def test_get_secure_random_string(self):
        """Test secure random string generation."""
        from revitpy_package_manager.security.config import get_secure_random_string

        # Generate multiple strings
        string1 = get_secure_random_string(32)
        string2 = get_secure_random_string(32)
        string3 = get_secure_random_string(16)

        # Should be different
        assert string1 != string2

        # Should have correct lengths
        assert len(string1) == 32
        assert len(string2) == 32
        assert len(string3) == 16

        # Should contain only alphanumeric characters
        import string as string_module

        allowed_chars = string_module.ascii_letters + string_module.digits
        assert all(c in allowed_chars for c in string1)
        assert all(c in allowed_chars for c in string2)
        assert all(c in allowed_chars for c in string3)


class TestSecurityConstants:
    """Test security configuration constants."""

    def test_security_limits(self):
        """Test security limits are reasonable."""
        assert SecurityConfig.MIN_PASSWORD_LENGTH >= 8
        assert SecurityConfig.MIN_JWT_SECRET_LENGTH >= 32
        assert SecurityConfig.MAX_UPLOAD_SIZE > 0
        assert SecurityConfig.MAX_REQUEST_SIZE > 0
        assert SecurityConfig.MAX_UPLOAD_SIZE >= SecurityConfig.MAX_REQUEST_SIZE

    def test_allowed_extensions(self):
        """Test allowed file extensions."""
        # Should include Python files
        assert ".py" in SecurityConfig.ALLOWED_EXTENSIONS
        assert ".pyi" in SecurityConfig.ALLOWED_EXTENSIONS

        # Should include common text files
        assert ".txt" in SecurityConfig.ALLOWED_EXTENSIONS
        assert ".md" in SecurityConfig.ALLOWED_EXTENSIONS
        assert ".json" in SecurityConfig.ALLOWED_EXTENSIONS
        assert ".yaml" in SecurityConfig.ALLOWED_EXTENSIONS

        # Should include package formats
        assert ".zip" in SecurityConfig.ALLOWED_EXTENSIONS
        assert ".whl" in SecurityConfig.ALLOWED_EXTENSIONS

        # Should NOT include dangerous extensions
        assert ".exe" not in SecurityConfig.ALLOWED_EXTENSIONS
        assert ".bat" not in SecurityConfig.ALLOWED_EXTENSIONS
        assert ".sh" not in SecurityConfig.ALLOWED_EXTENSIONS

    def test_forbidden_patterns(self):
        """Test forbidden filename patterns."""
        patterns = SecurityConfig.FORBIDDEN_PATTERNS

        # Should include path traversal patterns
        assert ".." in patterns
        assert "~/" in patterns

        # Should include system directories
        assert any("/etc/" in p for p in patterns)
        assert any("system32" in p for p in patterns)

        # Should include version control
        assert any(".git" in p for p in patterns)

    def test_rate_limits(self):
        """Test rate limit configurations."""
        # Should have reasonable defaults
        assert SecurityConfig.DEFAULT_RATE_LIMIT
        assert SecurityConfig.AUTH_RATE_LIMIT
        assert SecurityConfig.UPLOAD_RATE_LIMIT

        # Should be in correct format (number/timeunit)
        import re

        rate_pattern = r"^\d+/(second|minute|hour|day)$"
        assert re.match(rate_pattern, SecurityConfig.DEFAULT_RATE_LIMIT)
        assert re.match(rate_pattern, SecurityConfig.AUTH_RATE_LIMIT)
        assert re.match(rate_pattern, SecurityConfig.UPLOAD_RATE_LIMIT)
