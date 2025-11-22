"""Centralized configuration management for RevitPy Package Manager.

This module provides type-safe, validated configuration using Pydantic.
All environment variables are centralized here instead of scattered os.getenv() calls.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Application environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class StorageType(str, Enum):
    """Storage backend types."""

    LOCAL = "local"
    S3 = "s3"
    AZURE = "azure"


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_", case_sensitive=False)

    url: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/revitpy",
        description="Database connection URL",
    )
    echo: bool = Field(default=False, description="Enable SQL query logging")
    pool_size: int = Field(default=5, ge=1, le=50, description="Connection pool size")
    max_overflow: int = Field(
        default=10, ge=0, le=50, description="Max connections above pool_size"
    )
    pool_timeout: int = Field(
        default=30, ge=1, le=300, description="Seconds to wait for connection"
    )
    pool_recycle: int = Field(
        default=3600,
        ge=0,
        description="Seconds before recycling connections (0=disabled)",
    )

    # Legacy support for DATABASE_URL
    @field_validator("url", mode="before")
    @classmethod
    def support_legacy_database_url(cls, v: Any) -> Any:
        """Support legacy DATABASE_URL environment variable."""
        if v is None or (isinstance(v, str) and not v):
            legacy_url = os.getenv("DATABASE_URL")
            if legacy_url:
                return legacy_url
        return v


class JWTConfig(BaseSettings):
    """JWT authentication configuration."""

    model_config = SettingsConfigDict(env_prefix="JWT_", case_sensitive=False)

    secret_key: str = Field(
        default="dev-secret-key-change-in-production-min-32-chars",
        min_length=32,
        description="JWT secret key (min 32 characters)",
    )
    algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    expire_hours: int = Field(
        default=24, ge=1, le=720, description="Token expiration in hours"
    )
    refresh_expire_days: int = Field(
        default=30, ge=1, le=365, description="Refresh token expiration in days"
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key_strength(cls, v: str) -> str:
        """Validate JWT secret key has sufficient entropy."""
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")

        # Warn if using default secret key in production
        if v == "dev-secret-key-change-in-production-min-32-chars":
            import warnings

            warnings.warn(
                "Using default JWT secret key! This is insecure for production. "
                "Set JWT_SECRET_KEY environment variable.",
                UserWarning,
                stacklevel=2,
            )

        return v


class StorageConfig(BaseSettings):
    """File storage configuration."""

    model_config = SettingsConfigDict(env_prefix="STORAGE_", case_sensitive=False)

    type: StorageType = Field(default=StorageType.LOCAL, description="Storage backend")

    # Local storage settings
    local_path: Path = Field(
        default=Path("./storage/packages"), description="Local storage directory"
    )

    # S3 storage settings
    s3_bucket_name: str = Field(
        default="revitpy-packages", description="S3 bucket name"
    )
    s3_region: str = Field(default="us-east-1", description="AWS region")
    aws_access_key_id: str | None = Field(default=None, description="AWS access key ID")
    aws_secret_access_key: str | None = Field(
        default=None, description="AWS secret access key"
    )
    s3_endpoint_url: str | None = Field(
        default=None, description="Custom S3 endpoint (for S3-compatible services)"
    )

    # Azure storage settings
    azure_account_name: str | None = Field(
        default=None, description="Azure storage account name"
    )
    azure_account_key: str | None = Field(
        default=None, description="Azure storage account key"
    )
    azure_container_name: str = Field(
        default="revitpy-packages", description="Azure container name"
    )

    @field_validator("local_path", mode="before")
    @classmethod
    def resolve_local_path(cls, v: Any) -> Path:
        """Resolve and create local storage path."""
        if isinstance(v, str):
            v = Path(v)
        if isinstance(v, Path):
            v = v.expanduser().resolve()
        return v


class CacheConfig(BaseSettings):
    """Cache configuration."""

    model_config = SettingsConfigDict(env_prefix="CACHE_", case_sensitive=False)

    enabled: bool = Field(default=True, description="Enable caching")
    redis_url: RedisDsn | None = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )
    ttl_default: int = Field(
        default=3600, ge=60, description="Default TTL in seconds (1 hour)"
    )
    ttl_stats: int = Field(
        default=300, ge=60, description="Stats cache TTL in seconds (5 minutes)"
    )
    max_memory: str = Field(
        default="256mb", description="Redis max memory (e.g., 256mb, 1gb)"
    )


class ServerConfig(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="SERVER_", case_sensitive=False)

    host: str = Field(default="0.0.0.0", description="Server bind address")
    port: int = Field(default=8000, ge=1024, le=65535, description="Server port")
    workers: int | None = Field(
        default=None, ge=1, le=32, description="Number of worker processes"
    )
    reload: bool = Field(
        default=False, description="Enable auto-reload on code changes"
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    # CORS settings
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8080",
            "https://registry.revitpy.dev",
            "https://hub.revitpy.dev",
        ],
        description="Allowed CORS origins",
    )

    # Trusted hosts
    trusted_hosts: list[str] = Field(
        default=[
            "localhost",
            "127.0.0.1",
            "registry.revitpy.dev",
            "*.revitpy.dev",
        ],
        description="Trusted host headers",
    )

    @field_validator("workers", mode="before")
    @classmethod
    def set_workers_based_on_environment(cls, v: Any, info: Any) -> int | None:
        """Set workers based on environment if not explicitly set."""
        if v is None:
            # Use 1 worker in development/debug, auto in production
            return 1 if os.getenv("SERVER_DEBUG", "false").lower() == "true" else None
        return v


class MonitoringConfig(BaseSettings):
    """Monitoring and observability configuration."""

    model_config = SettingsConfigDict(env_prefix="MONITORING_", case_sensitive=False)

    enabled: bool = Field(default=True, description="Enable monitoring")
    sentry_dsn: str | None = Field(
        default=None, description="Sentry DSN for error tracking"
    )
    log_level: str = Field(default="INFO", description="Logging level")
    log_json: bool = Field(default=False, description="Use JSON log formatting")
    metrics_enabled: bool = Field(default=True, description="Enable Prometheus metrics")


class SecurityConfig(BaseSettings):
    """Security configuration."""

    model_config = SettingsConfigDict(env_prefix="SECURITY_", case_sensitive=False)

    # Password requirements
    min_password_length: int = Field(
        default=12, ge=8, description="Minimum password length"
    )

    # File upload limits
    max_upload_size: int = Field(
        default=100 * 1024 * 1024, description="Max upload size in bytes (100MB)"
    )
    max_request_size: int = Field(
        default=10 * 1024 * 1024, description="Max request size in bytes (10MB)"
    )

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_default: str = Field(
        default="100/minute", description="Default rate limit"
    )
    rate_limit_auth: str = Field(
        default="10/minute", description="Auth endpoint rate limit"
    )
    rate_limit_upload: str = Field(
        default="5/minute", description="Upload endpoint rate limit"
    )

    # Content Security
    allowed_extensions: set[str] = Field(
        default={
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
        },
        description="Allowed file extensions for uploads",
    )


class CLIConfig(BaseSettings):
    """CLI and Desktop application configuration."""

    model_config = SettingsConfigDict(env_prefix="CLI_", case_sensitive=False)

    # Debug mode
    debug: bool = Field(default=False, description="Enable CLI debug mode")

    # Authentication
    revitpy_token: str | None = Field(
        default=None, description="RevitPy registry authentication token"
    )

    # Registry URL
    registry_url: str = Field(
        default="https://registry.revitpy.dev", description="Package registry URL"
    )

    # Program Files paths (Windows)
    program_files: str | None = Field(
        default=None, description="Custom Program Files path"
    )
    program_files_x86: str | None = Field(
        default=None, description="Custom Program Files (x86) path"
    )


class Settings(BaseSettings):
    """Main application settings combining all configuration sections."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="Application environment"
    )

    # Application metadata
    app_name: str = Field(
        default="RevitPy Package Registry", description="Application name"
    )
    app_version: str = Field(default="1.0.0", description="Application version")

    # Configuration sections
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    jwt: JWTConfig = Field(default_factory=JWTConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    cli: CLIConfig = Field(default_factory=CLIConfig)

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == Environment.TESTING

    def model_post_init(self, __context: Any) -> None:
        """Validate configuration after initialization."""
        # Ensure storage path exists if using local storage
        if self.storage.type == StorageType.LOCAL:
            self.storage.local_path.mkdir(parents=True, exist_ok=True)

        # Validate S3 credentials if using S3
        if self.storage.type == StorageType.S3:
            if (
                not self.storage.aws_access_key_id
                or not self.storage.aws_secret_access_key
            ):
                # Check if AWS credentials are available via environment/IAM
                if not (
                    os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_SECRET_ACCESS_KEY")
                ):
                    raise ValueError(
                        "S3 storage requires AWS credentials "
                        "(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)"
                    )


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get global settings instance (singleton pattern).

    Returns:
        Settings: Global settings instance

    Example:
        >>> from revitpy_package_manager.config import get_settings
        >>> settings = get_settings()
        >>> print(settings.database.url)
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment (useful for testing).

    Returns:
        Settings: Newly loaded settings instance
    """
    global _settings
    _settings = Settings()
    return _settings


# Convenience function for backward compatibility
def get_database_url() -> str:
    """Get database URL string."""
    return str(get_settings().database.url)


def get_jwt_config() -> tuple[str, str, int]:
    """Get JWT configuration (secret, algorithm, expire_hours)."""
    settings = get_settings()
    return (
        settings.jwt.secret_key,
        settings.jwt.algorithm,
        settings.jwt.expire_hours,
    )


def is_debug_mode() -> bool:
    """Check if debug mode is enabled (server or CLI)."""
    settings = get_settings()
    return settings.server.debug or settings.cli.debug


def get_revitpy_token() -> str | None:
    """Get RevitPy registry authentication token."""
    return get_settings().cli.revitpy_token


def get_registry_url() -> str:
    """Get package registry URL."""
    return get_settings().cli.registry_url


def get_program_files_path() -> str:
    """Get Program Files path (Windows)."""
    import os

    settings = get_settings()
    return settings.cli.program_files or os.environ.get(
        "ProgramFiles", "C:\\Program Files"
    )


def get_program_files_x86_path() -> str:
    """Get Program Files (x86) path (Windows)."""
    import os

    settings = get_settings()
    return settings.cli.program_files_x86 or os.environ.get(
        "ProgramFiles(x86)", "C:\\Program Files (x86)"
    )
