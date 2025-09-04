"""Configuration management for RevitPy CLI."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

from .exceptions import ConfigurationError
from .logging import get_logger

logger = get_logger(__name__)


class DevServerConfig(BaseModel):
    """Development server configuration."""
    host: str = "localhost"
    port: int = 8000
    websocket_port: int = 8001
    hot_reload: bool = True
    watch_patterns: List[str] = ["*.py", "*.yaml", "*.json"]
    ignore_patterns: List[str] = ["__pycache__", "*.pyc", ".git", ".pytest_cache"]


class BuildConfig(BaseModel):
    """Build configuration."""
    output_dir: str = "dist"
    include_tests: bool = False
    optimize: bool = False
    sign_packages: bool = False
    compression: Optional[str] = None


class PublishConfig(BaseModel):
    """Publishing configuration."""
    registry_url: str = "https://pypi.org"
    max_package_size_mb: int = 100
    sign_packages: bool = True
    verify_ssl: bool = True
    timeout_seconds: int = 60


class InstallConfig(BaseModel):
    """Installation configuration."""
    registry_url: str = "https://pypi.org"
    use_cache: bool = True
    cache_ttl_hours: int = 24
    prefer_binary: bool = True
    verify_ssl: bool = True


class TemplateConfig(BaseModel):
    """Template configuration."""
    template_cache_dir: Optional[str] = None
    default_template: str = "basic-script"
    template_sources: List[str] = [
        "https://github.com/revitpy/templates.git",
    ]
    update_interval_hours: int = 24


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    file_enabled: bool = True
    file_path: Optional[str] = None
    console_enabled: bool = True
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_file_size_mb: int = 10
    backup_count: int = 5

    @validator("level")
    def validate_level(cls, v):
        """Validate logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid logging level: {v}")
        return v.upper()


class PluginConfig(BaseModel):
    """Plugin configuration."""
    enabled: bool = True
    auto_load: bool = True
    plugin_dirs: List[str] = []
    disabled_plugins: List[str] = []


class RevitPyConfig(BaseSettings):
    """Main RevitPy CLI configuration."""
    
    # Core settings
    version: str = "1.0.0"
    debug: bool = False
    cache_dir: Path = Field(default_factory=lambda: Path.home() / ".revitpy" / "cache")
    config_dir: Path = Field(default_factory=lambda: Path.home() / ".revitpy")
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".revitpy" / "data")
    
    # Component configurations
    dev_server: DevServerConfig = Field(default_factory=DevServerConfig)
    build: BuildConfig = Field(default_factory=BuildConfig)
    publish: PublishConfig = Field(default_factory=PublishConfig)
    install: InstallConfig = Field(default_factory=InstallConfig)
    template: TemplateConfig = Field(default_factory=TemplateConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
    
    # User preferences
    editor: Optional[str] = None
    preferred_shell: Optional[str] = None
    
    # Advanced settings
    max_concurrent_downloads: int = 5
    request_timeout: int = 30
    retry_attempts: int = 3
    
    class Config:
        env_prefix = "REVITPY_"
        env_file = ".env"
        case_sensitive = False
        
        # Configuration file locations
        @property
        def config_files(self) -> List[Path]:
            """Get list of configuration file locations in order of precedence."""
            return [
                Path.cwd() / ".revitpy.toml",
                Path.cwd() / "pyproject.toml",  # [tool.revitpy] section
                Path.home() / ".revitpy" / "config.toml",
                Path.home() / ".revitpy.toml",
            ]
    
    def __init__(self, **data):
        """Initialize configuration with file loading."""
        # Load configuration from files
        file_config = self._load_from_files()
        
        # Merge with provided data (provided data takes precedence)
        merged_config = {**file_config, **data}
        
        super().__init__(**merged_config)
        
        # Ensure directories exist
        self._ensure_directories()
    
    @property
    def config_file(self) -> Path:
        """Get the primary configuration file path."""
        return self.config_dir / "config.toml"
    
    def _load_from_files(self) -> Dict[str, Any]:
        """Load configuration from files.
        
        Returns:
            Configuration dictionary
        """
        config = {}
        
        # Check each configuration file location
        config_files = [
            Path.cwd() / ".revitpy.toml",
            Path.cwd() / "pyproject.toml",
            Path.home() / ".revitpy" / "config.toml",
            Path.home() / ".revitpy.toml",
        ]
        
        for config_file in config_files:
            if config_file.exists():
                try:
                    file_config = self._load_config_file(config_file)
                    if file_config:
                        # Merge configurations (later files override earlier ones)
                        config = self._deep_merge(config, file_config)
                        logger.debug(f"Loaded configuration from {config_file}")
                except Exception as e:
                    logger.warning(f"Failed to load configuration from {config_file}: {e}")
        
        return config
    
    def _load_config_file(self, config_file: Path) -> Optional[Dict[str, Any]]:
        """Load configuration from a specific file.
        
        Args:
            config_file: Path to configuration file
            
        Returns:
            Configuration dictionary or None
        """
        if not config_file.exists():
            return None
        
        try:
            if config_file.suffix.lower() == ".toml":
                import tomli
                with open(config_file, "rb") as f:
                    data = tomli.load(f)
                
                # Handle pyproject.toml format
                if config_file.name == "pyproject.toml":
                    return data.get("tool", {}).get("revitpy", {})
                else:
                    return data
            
            elif config_file.suffix.lower() in (".yaml", ".yml"):
                with open(config_file, "r") as f:
                    return yaml.safe_load(f)
            
            elif config_file.suffix.lower() == ".json":
                with open(config_file, "r") as f:
                    return json.load(f)
            
        except Exception as e:
            logger.error(f"Failed to parse configuration file {config_file}: {e}")
        
        return None
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            override: Override dictionary
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        directories = [
            self.cache_dir,
            self.config_dir,
            self.data_dir,
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"Failed to create directory {directory}: {e}")
    
    def save(self, config_file: Optional[Path] = None) -> None:
        """Save configuration to file.
        
        Args:
            config_file: Optional custom config file path
        """
        if config_file is None:
            config_file = self.config_file
        
        try:
            # Convert to dictionary
            config_dict = self.dict()
            
            # Remove computed fields and internal fields
            computed_fields = ["config_file"]
            for field in computed_fields:
                config_dict.pop(field, None)
            
            # Convert Path objects to strings
            config_dict = self._serialize_paths(config_dict)
            
            # Ensure parent directory exists
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save as TOML
            if config_file.suffix.lower() == ".toml":
                import tomli_w
                with open(config_file, "wb") as f:
                    tomli_w.dump(config_dict, f)
            
            elif config_file.suffix.lower() in (".yaml", ".yml"):
                with open(config_file, "w") as f:
                    yaml.dump(config_dict, f, default_flow_style=False)
            
            elif config_file.suffix.lower() == ".json":
                with open(config_file, "w") as f:
                    json.dump(config_dict, f, indent=2)
            
            else:
                # Default to TOML
                import tomli_w
                with open(config_file, "wb") as f:
                    tomli_w.dump(config_dict, f)
            
            logger.info(f"Configuration saved to {config_file}")
        
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {e}") from e
    
    def _serialize_paths(self, data: Any) -> Any:
        """Convert Path objects to strings for serialization.
        
        Args:
            data: Data to serialize
            
        Returns:
            Serialized data
        """
        if isinstance(data, Path):
            return str(data)
        elif isinstance(data, dict):
            return {key: self._serialize_paths(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._serialize_paths(item) for item in data]
        else:
            return data
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        try:
            # Remove existing config file
            if self.config_file.exists():
                self.config_file.unlink()
            
            # Reinitialize with defaults
            self.__init__()
            
            # Save defaults
            self.save()
            
            logger.info("Configuration reset to defaults")
        
        except Exception as e:
            raise ConfigurationError(f"Failed to reset configuration: {e}") from e
    
    def show_config(self) -> None:
        """Display current configuration."""
        from rich.console import Console
        from rich.table import Table
        
        console = Console()
        
        # Main configuration
        table = Table(title="RevitPy CLI Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        config_dict = self.dict()
        
        def add_config_section(section_name: str, section_data: Dict[str, Any], prefix: str = ""):
            """Recursively add configuration sections to table."""
            for key, value in section_data.items():
                if isinstance(value, dict):
                    add_config_section(f"{section_name}.{key}", value, prefix + "  ")
                else:
                    table.add_row(f"{prefix}{section_name}.{key}", str(value))
        
        # Add core settings
        core_settings = {
            "version": config_dict["version"],
            "debug": config_dict["debug"],
            "cache_dir": config_dict["cache_dir"],
            "config_dir": config_dict["config_dir"],
        }
        
        for key, value in core_settings.items():
            table.add_row(key, str(value))
        
        # Add component configurations
        components = ["dev_server", "build", "publish", "install", "template", "logging", "plugins"]
        for component in components:
            if component in config_dict:
                add_config_section(component, config_dict[component])
        
        console.print(table)
        
        # Show configuration file locations
        console.print(f"\n[bold]Configuration file:[/bold] {self.config_file}")
        
        # Show environment variables
        env_vars = [key for key in os.environ.keys() if key.startswith("REVITPY_")]
        if env_vars:
            console.print(f"\n[bold]Environment variables:[/bold]")
            for var in env_vars:
                console.print(f"  {var}={os.environ[var]}")
    
    def validate_config(self) -> List[str]:
        """Validate current configuration.
        
        Returns:
            List of validation errors
        """
        errors = []
        
        # Validate paths
        if not isinstance(self.cache_dir, Path):
            errors.append("cache_dir must be a valid path")
        
        if not isinstance(self.config_dir, Path):
            errors.append("config_dir must be a valid path")
        
        # Validate dev server config
        if self.dev_server.port < 1 or self.dev_server.port > 65535:
            errors.append("dev_server.port must be between 1 and 65535")
        
        if self.dev_server.websocket_port < 1 or self.dev_server.websocket_port > 65535:
            errors.append("dev_server.websocket_port must be between 1 and 65535")
        
        # Validate URLs
        if not self.publish.registry_url.startswith(("http://", "https://")):
            errors.append("publish.registry_url must be a valid HTTP/HTTPS URL")
        
        if not self.install.registry_url.startswith(("http://", "https://")):
            errors.append("install.registry_url must be a valid HTTP/HTTPS URL")
        
        # Validate numeric settings
        if self.max_concurrent_downloads < 1:
            errors.append("max_concurrent_downloads must be positive")
        
        if self.request_timeout < 1:
            errors.append("request_timeout must be positive")
        
        if self.retry_attempts < 0:
            errors.append("retry_attempts must be non-negative")
        
        return errors
    
    def get_effective_config(self) -> Dict[str, Any]:
        """Get effective configuration including environment variables.
        
        Returns:
            Complete effective configuration
        """
        config = self.dict()
        
        # Add environment variable overrides
        env_overrides = {}
        for key, value in os.environ.items():
            if key.startswith("REVITPY_"):
                config_key = key[8:].lower()  # Remove REVITPY_ prefix
                env_overrides[config_key] = value
        
        if env_overrides:
            config["environment_overrides"] = env_overrides
        
        return config


# Global configuration instance
_config: Optional[RevitPyConfig] = None


def get_config() -> RevitPyConfig:
    """Get the global configuration instance.
    
    Returns:
        RevitPy configuration instance
    """
    global _config
    if _config is None:
        _config = RevitPyConfig()
    return _config


def set_config(config: RevitPyConfig) -> None:
    """Set the global configuration instance.
    
    Args:
        config: Configuration instance to set
    """
    global _config
    _config = config


def reload_config() -> RevitPyConfig:
    """Reload configuration from files.
    
    Returns:
        Reloaded configuration instance
    """
    global _config
    _config = RevitPyConfig()
    return _config


def get_config_file_template() -> str:
    """Get a template configuration file.
    
    Returns:
        Template configuration as TOML string
    """
    template = """# RevitPy CLI Configuration File
# This file configures the behavior of the RevitPy CLI tool

# Core settings
debug = false
# cache_dir = "~/.revitpy/cache"
# config_dir = "~/.revitpy"

# Development server configuration
[dev_server]
host = "localhost"
port = 8000
websocket_port = 8001
hot_reload = true
watch_patterns = ["*.py", "*.yaml", "*.json"]
ignore_patterns = ["__pycache__", "*.pyc", ".git", ".pytest_cache"]

# Build configuration
[build]
output_dir = "dist"
include_tests = false
optimize = false
sign_packages = false

# Publishing configuration
[publish]
registry_url = "https://pypi.org"
max_package_size_mb = 100
sign_packages = true
verify_ssl = true
timeout_seconds = 60

# Installation configuration
[install]
registry_url = "https://pypi.org"
use_cache = true
cache_ttl_hours = 24
prefer_binary = true
verify_ssl = true

# Template configuration
[template]
default_template = "basic-script"
template_sources = [
    "https://github.com/revitpy/templates.git"
]
update_interval_hours = 24

# Logging configuration
[logging]
level = "INFO"
file_enabled = true
console_enabled = true
format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
max_file_size_mb = 10
backup_count = 5

# Plugin configuration
[plugins]
enabled = true
auto_load = true
plugin_dirs = []
disabled_plugins = []
"""
    return template.strip()


def create_default_config_file(config_file: Path) -> None:
    """Create a default configuration file.
    
    Args:
        config_file: Path where to create the configuration file
    """
    try:
        # Ensure parent directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write template
        with open(config_file, "w") as f:
            f.write(get_config_file_template())
        
        logger.info(f"Created default configuration file at {config_file}")
    
    except Exception as e:
        raise ConfigurationError(f"Failed to create default configuration file: {e}") from e