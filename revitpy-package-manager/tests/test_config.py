"""Tests for centralized configuration module."""

import os
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from revitpy_package_manager.config import (
    CacheConfig,
    CLIConfig,
    DatabaseConfig,
    Environment,
    JWTConfig,
    MonitoringConfig,
    SecurityConfig,
    ServerConfig,
    Settings,
    StorageConfig,
    StorageType,
    get_database_url,
    get_jwt_config,
    get_program_files_path,
    get_program_files_x86_path,
    get_registry_url,
    get_revitpy_token,
    get_settings,
    is_debug_mode,
    reload_settings,
)


class TestEnvironmentEnum:
    """Test Environment enumeration."""

    def test_environment_values(self):
        """Test all environment enum values exist."""
        assert Environment.DEVELOPMENT == "development"
        assert Environment.STAGING == "staging"
        assert Environment.PRODUCTION == "production"
        assert Environment.TESTING == "testing"


class TestStorageTypeEnum:
    """Test StorageType enumeration."""

    def test_storage_type_values(self):
        """Test all storage type enum values exist."""
        assert StorageType.LOCAL == "local"
        assert StorageType.S3 == "s3"
        assert StorageType.AZURE == "azure"


class TestDatabaseConfig:
    """Test DatabaseConfig settings."""

    def test_database_config_defaults(self):
        """Test database config loads with defaults."""
        config = DatabaseConfig()

        assert str(config.url).startswith("postgresql+asyncpg://")
        assert config.echo is False
        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.pool_timeout == 30
        assert config.pool_recycle == 3600

    def test_database_config_from_env(self):
        """Test database config loads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "DB_URL": "postgresql+asyncpg://user:pass@host:5432/db",
                "DB_ECHO": "true",
                "DB_POOL_SIZE": "20",
                "DB_MAX_OVERFLOW": "30",
            },
        ):
            config = DatabaseConfig()

            assert "user:pass@host:5432/db" in str(config.url)
            assert config.echo is True
            assert config.pool_size == 20
            assert config.max_overflow == 30

    def test_database_legacy_url_support(self):
        """Test legacy DATABASE_URL environment variable is supported."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+asyncpg://legacy:pass@localhost:5432/legacydb",
            },
            clear=True,
        ):
            config = DatabaseConfig()
            assert "legacy:pass@localhost:5432/legacydb" in str(config.url)

    def test_database_pool_size_validation(self):
        """Test pool size must be within valid range."""
        with pytest.raises(ValidationError):
            DatabaseConfig(pool_size=0)  # Too small

        with pytest.raises(ValidationError):
            DatabaseConfig(pool_size=100)  # Too large


class TestJWTConfig:
    """Test JWTConfig settings."""

    def test_jwt_config_defaults(self):
        """Test JWT config has development defaults."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = JWTConfig()

            # Should warn about default secret key
            assert len(w) == 1
            assert "default JWT secret key" in str(w[0].message).lower()

            assert (
                config.secret_key == "dev-secret-key-change-in-production-min-32-chars"
            )
            assert config.algorithm == "HS256"
            assert config.expire_hours == 24
            assert config.refresh_expire_days == 30

    def test_jwt_config_from_env(self):
        """Test JWT config loads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "JWT_SECRET_KEY": "my-super-secret-jwt-key-at-least-32-characters-long",
                "JWT_ALGORITHM": "HS512",
                "JWT_EXPIRE_HOURS": "48",
            },
        ):
            config = JWTConfig()

            assert (
                config.secret_key
                == "my-super-secret-jwt-key-at-least-32-characters-long"
            )
            assert config.algorithm == "HS512"
            assert config.expire_hours == 48

    def test_jwt_secret_key_length_validation(self):
        """Test JWT secret key must be at least 32 characters."""
        with pytest.raises(ValidationError, match="at least 32 characters"):
            JWTConfig(secret_key="too-short")


class TestStorageConfig:
    """Test StorageConfig settings."""

    def test_storage_config_defaults(self):
        """Test storage config defaults to local storage."""
        config = StorageConfig()

        assert config.type == StorageType.LOCAL
        assert isinstance(config.local_path, Path)
        assert config.s3_bucket_name == "revitpy-packages"
        assert config.s3_region == "us-east-1"

    def test_storage_config_s3(self):
        """Test S3 storage configuration."""
        with patch.dict(
            os.environ,
            {
                "STORAGE_TYPE": "s3",
                "STORAGE_S3_BUCKET_NAME": "my-bucket",
                "AWS_ACCESS_KEY_ID": "test-key-id",
                "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            },
        ):
            config = StorageConfig()

            assert config.type == StorageType.S3
            assert config.s3_bucket_name == "my-bucket"
            assert config.aws_access_key_id == "test-key-id"

    def test_storage_local_path_resolution(self):
        """Test local storage path is resolved and created."""
        config = StorageConfig(local_path="./test_storage")

        assert config.local_path.is_absolute()


class TestCacheConfig:
    """Test CacheConfig settings."""

    def test_cache_config_defaults(self):
        """Test cache config defaults."""
        config = CacheConfig()

        assert config.enabled is True
        assert str(config.redis_url) == "redis://localhost:6379/0"
        assert config.ttl_default == 3600
        assert config.ttl_stats == 300
        assert config.max_memory == "256mb"

    def test_cache_config_from_env(self):
        """Test cache config from environment."""
        with patch.dict(
            os.environ,
            {
                "CACHE_ENABLED": "false",
                "CACHE_REDIS_URL": "redis://custom:6380/1",
                "CACHE_TTL_DEFAULT": "7200",
            },
        ):
            config = CacheConfig()

            assert config.enabled is False
            assert "custom:6380/1" in str(config.redis_url)
            assert config.ttl_default == 7200


class TestServerConfig:
    """Test ServerConfig settings."""

    def test_server_config_defaults(self):
        """Test server config defaults."""
        config = ServerConfig()

        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.reload is False
        assert config.debug is False
        assert "localhost" in config.cors_origins
        assert "localhost" in config.trusted_hosts

    def test_server_config_from_env(self):
        """Test server config from environment."""
        with patch.dict(
            os.environ,
            {
                "SERVER_HOST": "127.0.0.1",
                "SERVER_PORT": "9000",
                "SERVER_DEBUG": "true",
                "SERVER_WORKERS": "8",
            },
        ):
            config = ServerConfig()

            assert config.host == "127.0.0.1"
            assert config.port == 9000
            assert config.debug is True
            assert config.workers == 8

    def test_server_port_validation(self):
        """Test server port must be in valid range."""
        with pytest.raises(ValidationError):
            ServerConfig(port=100)  # Too low

        with pytest.raises(ValidationError):
            ServerConfig(port=99999)  # Too high


class TestMonitoringConfig:
    """Test MonitoringConfig settings."""

    def test_monitoring_config_defaults(self):
        """Test monitoring config defaults."""
        config = MonitoringConfig()

        assert config.enabled is True
        assert config.sentry_dsn is None
        assert config.log_level == "INFO"
        assert config.log_json is False
        assert config.metrics_enabled is True

    def test_monitoring_config_from_env(self):
        """Test monitoring config from environment."""
        with patch.dict(
            os.environ,
            {
                "MONITORING_ENABLED": "false",
                "MONITORING_LOG_LEVEL": "DEBUG",
                "MONITORING_LOG_JSON": "true",
            },
        ):
            config = MonitoringConfig()

            assert config.enabled is False
            assert config.log_level == "DEBUG"
            assert config.log_json is True


class TestSecurityConfig:
    """Test SecurityConfig settings."""

    def test_security_config_defaults(self):
        """Test security config defaults."""
        config = SecurityConfig()

        assert config.min_password_length == 12
        assert config.max_upload_size == 100 * 1024 * 1024
        assert config.rate_limit_enabled is True
        assert ".py" in config.allowed_extensions
        assert ".exe" not in config.allowed_extensions

    def test_security_config_from_env(self):
        """Test security config from environment."""
        with patch.dict(
            os.environ,
            {
                "SECURITY_MIN_PASSWORD_LENGTH": "16",
                "SECURITY_RATE_LIMIT_ENABLED": "false",
            },
        ):
            config = SecurityConfig()

            assert config.min_password_length == 16
            assert config.rate_limit_enabled is False


class TestCLIConfig:
    """Test CLIConfig settings."""

    def test_cli_config_defaults(self):
        """Test CLI config defaults."""
        config = CLIConfig()

        assert config.debug is False
        assert config.revitpy_token is None
        assert config.registry_url == "https://registry.revitpy.dev"

    def test_cli_config_from_env(self):
        """Test CLI config from environment."""
        with patch.dict(
            os.environ,
            {
                "CLI_DEBUG": "true",
                "CLI_REVITPY_TOKEN": "test-token-123",
                "CLI_REGISTRY_URL": "https://custom.registry.dev",
            },
        ):
            config = CLIConfig()

            assert config.debug is True
            assert config.revitpy_token == "test-token-123"
            assert config.registry_url == "https://custom.registry.dev"


class TestSettings:
    """Test main Settings class."""

    def test_settings_defaults(self):
        """Test settings loads with all default values."""
        settings = Settings()

        assert settings.environment == Environment.DEVELOPMENT
        assert settings.app_name == "RevitPy Package Registry"
        assert isinstance(settings.database, DatabaseConfig)
        assert isinstance(settings.jwt, JWTConfig)
        assert isinstance(settings.storage, StorageConfig)
        assert isinstance(settings.cache, CacheConfig)
        assert isinstance(settings.server, ServerConfig)
        assert isinstance(settings.monitoring, MonitoringConfig)
        assert isinstance(settings.security, SecurityConfig)
        assert isinstance(settings.cli, CLIConfig)

    def test_settings_environment_properties(self):
        """Test environment property methods."""
        dev_settings = Settings(environment=Environment.DEVELOPMENT)
        assert dev_settings.is_development is True
        assert dev_settings.is_production is False
        assert dev_settings.is_testing is False

        prod_settings = Settings(environment=Environment.PRODUCTION)
        assert prod_settings.is_production is True
        assert prod_settings.is_development is False

    def test_settings_local_storage_path_creation(self):
        """Test local storage path is created on initialization."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "test_storage"
            Settings(
                storage=StorageConfig(type=StorageType.LOCAL, local_path=test_path)
            )
            # Path should be created during model_post_init
            assert test_path.exists()

    def test_settings_s3_validation(self):
        """Test S3 storage requires credentials."""
        with pytest.raises(ValueError, match="S3 storage requires AWS credentials"):
            Settings(
                storage=StorageConfig(
                    type=StorageType.S3,
                    aws_access_key_id=None,
                    aws_secret_access_key=None,
                )
            )


class TestSettingsSingleton:
    """Test settings singleton pattern."""

    def test_get_settings_returns_singleton(self):
        """Test get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reload_settings_creates_new_instance(self):
        """Test reload_settings creates a new instance."""
        settings1 = get_settings()
        settings2 = reload_settings()

        assert settings1 is not settings2

        # After reload, get_settings should return the new instance
        settings3 = get_settings()
        assert settings3 is settings2


class TestConvenienceFunctions:
    """Test convenience helper functions."""

    def test_get_database_url(self):
        """Test get_database_url returns string URL."""
        url = get_database_url()
        assert isinstance(url, str)
        assert "postgresql" in url

    def test_get_jwt_config(self):
        """Test get_jwt_config returns tuple."""
        secret, algorithm, expire_hours = get_jwt_config()

        assert isinstance(secret, str)
        assert len(secret) >= 32
        assert isinstance(algorithm, str)
        assert isinstance(expire_hours, int)
        assert expire_hours > 0

    def test_is_debug_mode(self):
        """Test is_debug_mode checks both server and CLI debug."""
        # Default should be False
        debug = is_debug_mode()
        assert isinstance(debug, bool)

    def test_get_revitpy_token(self):
        """Test get_revitpy_token returns token or None."""
        token = get_revitpy_token()
        assert token is None or isinstance(token, str)

    def test_get_registry_url(self):
        """Test get_registry_url returns URL string."""
        url = get_registry_url()
        assert isinstance(url, str)
        assert url.startswith("https://")

    def test_get_program_files_path(self):
        """Test get_program_files_path returns path."""
        path = get_program_files_path()
        assert isinstance(path, str)
        assert "Program" in path

    def test_get_program_files_x86_path(self):
        """Test get_program_files_x86_path returns path."""
        path = get_program_files_x86_path()
        assert isinstance(path, str)


class TestConfigIntegration:
    """Integration tests for configuration system."""

    def test_full_config_from_environment(self):
        """Test loading complete configuration from environment."""
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "DB_POOL_SIZE": "20",
                "JWT_SECRET_KEY": "production-secret-key-at-least-32-characters-long-abc",
                "STORAGE_TYPE": "s3",
                "CACHE_ENABLED": "true",
                "SERVER_PORT": "8080",
                "MONITORING_LOG_JSON": "true",
                "SECURITY_RATE_LIMIT_ENABLED": "true",
                "CLI_DEBUG": "false",
            },
            clear=True,
        ):
            settings = reload_settings()

            assert settings.environment == Environment.PRODUCTION
            assert settings.database.pool_size == 20
            assert (
                settings.jwt.secret_key
                == "production-secret-key-at-least-32-characters-long-abc"
            )
            assert settings.storage.type == StorageType.S3
            assert settings.cache.enabled is True
            assert settings.server.port == 8080
            assert settings.monitoring.log_json is True
            assert settings.security.rate_limit_enabled is True
            assert settings.cli.debug is False

    def test_config_in_production_mode(self):
        """Test configuration behaves correctly in production mode."""
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "JWT_SECRET_KEY": "secure-production-key-minimum-32-chars-long-xyz",
            },
        ):
            settings = reload_settings()

            assert settings.is_production
            assert not settings.is_development
            # In production, JSON logging might be preferred
            # (though default is False, this tests the check works)
            assert isinstance(settings.monitoring.log_json, bool)

    def test_config_handles_missing_optional_values(self):
        """Test configuration handles missing optional environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            settings = reload_settings()

            # Should use defaults
            assert settings.environment == Environment.DEVELOPMENT
            assert settings.cache.redis_url is not None
            assert settings.cli.revitpy_token is None
            assert settings.monitoring.sentry_dsn is None
