"""Security configuration and validation utilities."""

import os
import re
import secrets
import string
from typing import Any


class SecurityConfig:
    """Central security configuration and validation."""

    # Secure defaults
    MIN_PASSWORD_LENGTH = 12
    # bcrypt only accepts up to 72 bytes of input (bcrypt>=5 raises beyond it)
    MAX_PASSWORD_BYTES = 72
    # Usernames: letters/digits with inner '.', '_' or '-' (no markup/spaces)
    USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
    MIN_JWT_SECRET_LENGTH = 32
    MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB

    # Rate limiting defaults
    DEFAULT_RATE_LIMIT = "100/minute"
    AUTH_RATE_LIMIT = "10/minute"
    UPLOAD_RATE_LIMIT = "5/minute"

    # Allowed file extensions for uploads
    ALLOWED_EXTENSIONS = {
        ".py",
        ".pyi",
        ".pyc",
        ".pyo",
        ".pyd",
        ".txt",
        ".md",
        ".rst",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".cfg",
        ".ini",
        ".conf",
        ".zip",
        ".tar.gz",
        ".whl",
    }

    # Forbidden patterns in filenames
    FORBIDDEN_PATTERNS = [
        "..",
        "~/",
        "\\",
        "/etc/",
        "/var/",
        "/tmp/",
        "system32",
        "windows",
        "program files",
        "__pycache__",
        ".git",
        ".svn",
        ".hg",
    ]

    @classmethod
    def generate_jwt_secret(cls) -> str:
        """Generate a cryptographically secure JWT secret key."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(alphabet) for _ in range(64))

    @classmethod
    def validate_jwt_secret(cls, secret: str | None) -> bool:
        """Validate JWT secret meets security requirements."""
        if not secret:
            return False
        return len(secret) >= cls.MIN_JWT_SECRET_LENGTH

    @classmethod
    def validate_password_strength(cls, password: str) -> dict[str, Any]:
        """Validate password strength and return feedback."""
        issues = []
        strength = 0

        if len(password) < cls.MIN_PASSWORD_LENGTH:
            issues.append(f"Must be at least {cls.MIN_PASSWORD_LENGTH} characters")
        else:
            strength += 1

        if not any(c.islower() for c in password):
            issues.append("Must contain lowercase letters")
        else:
            strength += 1

        if not any(c.isupper() for c in password):
            issues.append("Must contain uppercase letters")
        else:
            strength += 1

        if not any(c.isdigit() for c in password):
            issues.append("Must contain numbers")
        else:
            strength += 1

        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            issues.append("Must contain special characters")
        else:
            strength += 1

        if len(password.encode("utf-8")) > cls.MAX_PASSWORD_BYTES:
            issues.append(f"Must be at most {cls.MAX_PASSWORD_BYTES} bytes long")

        return {"valid": len(issues) == 0, "strength": strength, "issues": issues}

    @classmethod
    def validate_username(cls, username: str) -> bool:
        """Check a username contains only safe identifier characters."""
        return isinstance(username, str) and bool(cls.USERNAME_PATTERN.match(username))

    @classmethod
    def validate_filename(cls, filename: str) -> bool:
        """Validate filename for security issues."""
        # Check for forbidden patterns
        filename_lower = filename.lower()
        for pattern in cls.FORBIDDEN_PATTERNS:
            if pattern in filename_lower:
                return False

        # Check extension
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[1].lower()
            return ext in cls.ALLOWED_EXTENSIONS

        return False

    @classmethod
    def sanitize_user_input(cls, value: str, max_length: int = 1000) -> str:
        """Sanitize user input to prevent XSS and injection attacks."""
        if not isinstance(value, str):
            return ""

        # Truncate to max length
        value = value[:max_length]

        # Remove null bytes and control characters
        value = "".join(c for c in value if ord(c) >= 32 or c in "\t\n\r")

        # Strip whitespace
        value = value.strip()

        return value

    @classmethod
    def get_security_headers(cls) -> dict[str, str]:
        """Get recommended security headers."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; object-src 'none';",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
        }


def ensure_secure_environment() -> None:
    """Ensure environment variables are set securely."""
    required_vars = ["JWT_SECRET_KEY", "DATABASE_URL"]
    missing_vars = []

    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        elif var == "JWT_SECRET_KEY" and not SecurityConfig.validate_jwt_secret(value):
            missing_vars.append(f"{var} (insufficient entropy)")

    if missing_vars:
        example_jwt = SecurityConfig.generate_jwt_secret()
        raise ValueError(
            f"Missing or invalid required environment variables: {', '.join(missing_vars)}\n"
            f"Example JWT secret: {example_jwt[:20]}... (use full 64-character key)"
        )


def get_secure_random_string(length: int = 32) -> str:
    """Generate a cryptographically secure random string."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
