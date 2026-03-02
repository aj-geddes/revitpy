"""
Configuration management for RevitPy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class Config:
    """RevitPy configuration container."""

    def __init__(self, **kwargs: Any) -> None:
        self._data: dict[str, Any] = kwargs

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._data[key] = value

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._data.get(name)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def to_dict(self) -> dict[str, Any]:
        """Return configuration as a dictionary."""
        return self._data.copy()


class ConfigManager:
    """Manages RevitPy configuration loading and access."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config = Config()
        self._config_path = config_path

    @property
    def config(self) -> Config:
        """Get the current configuration."""
        return self._config

    def load(self, path: Path | None = None) -> Config:
        """Load configuration from a file path."""
        target = path or self._config_path
        if target and target.exists():
            import yaml

            with open(target) as f:
                data = yaml.safe_load(f) or {}
            self._config = Config(**data)
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)
