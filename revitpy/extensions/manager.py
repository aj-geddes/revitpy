"""
Extension manager for loading, managing and coordinating extensions.
"""

import asyncio
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .dependency_injection import DIContainer, set_current_container
from .extension import Extension, ExtensionMetadata, ExtensionStatus
from .lifecycle import LifecycleManager
from .loader import ExtensionLoader
from .registry import ExtensionRegistry


@dataclass
class ExtensionManagerConfig:
    """Configuration for extension manager."""

    extension_directories: list[Path] = field(default_factory=list)
    auto_load_extensions: bool = True
    auto_activate_extensions: bool = True
    dependency_resolution: bool = True
    max_load_retries: int = 3
    extension_timeout: float = 30.0


class ExtensionManager:
    """
    Manages the lifecycle of all RevitPy extensions.

    Responsibilities:
    - Loading and unloading extensions
    - Dependency resolution
    - Lifecycle coordination
    - Registry management
    - Error handling and recovery
    """

    _instance: Optional["ExtensionManager"] = None
    _lock = threading.Lock()

    def __new__(
        cls, config: ExtensionManagerConfig | None = None
    ) -> "ExtensionManager":
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: ExtensionManagerConfig | None = None) -> None:
        if hasattr(self, "_initialized"):
            return

        self.config = config or ExtensionManagerConfig()

        # Core components
        self.container = DIContainer()
        self.registry = ExtensionRegistry()
        self.loader = ExtensionLoader(self.registry)
        self.lifecycle_manager = LifecycleManager()

        # Extension storage
        self._extensions: dict[str, Extension] = {}
        self._extension_order: list[str] = []

        # State management
        self._is_initialized = False
        self._is_shutting_down = False
        self._load_lock = asyncio.Lock()

        # Set global container
        set_current_container(self.container)

        self._initialized = True
        logger.info("ExtensionManager initialized")

    @classmethod
    def get_instance(
        cls, config: ExtensionManagerConfig | None = None
    ) -> "ExtensionManager":
        """Get the singleton instance."""
        return cls(config)

    @property
    def is_initialized(self) -> bool:
        """Check if manager is initialized."""
        return self._is_initialized

    @property
    def extension_count(self) -> int:
        """Get number of registered extensions."""
        return len(self._extensions)

    @property
    def active_extension_count(self) -> int:
        """Get number of active extensions."""
        return sum(1 for ext in self._extensions.values() if ext.is_active)

    # Initialization and Shutdown

    async def initialize(self) -> None:
        """Initialize the extension manager."""
        if self._is_initialized:
            return

        logger.info("Initializing extension manager...")

        # Register core services
        await self._register_core_services()

        # Discover extensions
        if self.config.auto_load_extensions:
            await self.discover_extensions()

        self._is_initialized = True
        logger.info("Extension manager initialized successfully")

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Shutdown the extension manager."""
        if not self._is_initialized or self._is_shutting_down:
            return

        self._is_shutting_down = True
        logger.info("Shutting down extension manager...")

        try:
            # Deactivate all extensions in reverse order
            for extension_id in reversed(self._extension_order):
                if extension_id in self._extensions:
                    await self._deactivate_extension_safe(extension_id)

            # Dispose all extensions
            for extension in self._extensions.values():
                await self._dispose_extension_safe(extension)

            # Clear registry
            self.registry.clear()

            # Dispose container
            self.container.dispose()

            self._extensions.clear()
            self._extension_order.clear()

            logger.info("Extension manager shutdown complete")

        except Exception as e:
            logger.error(f"Error during extension manager shutdown: {e}")

        finally:
            self._is_initialized = False
            self._is_shutting_down = False

    # Extension Discovery and Loading

    async def discover_extensions(self) -> list[ExtensionMetadata]:
        """
        Discover extensions in configured directories.

        Returns:
            List of discovered extension metadata
        """
        discovered_extensions = []

        for directory in self.config.extension_directories:
            try:
                extensions = await self.loader.discover_extensions(directory)
                discovered_extensions.extend(extensions)
                logger.debug(f"Discovered {len(extensions)} extensions in {directory}")
            except Exception as e:
                logger.error(f"Failed to discover extensions in {directory}: {e}")

        # Register discovered extensions
        for metadata in discovered_extensions:
            self.registry.register_extension(metadata)

        # Auto-load if configured
        if self.config.auto_load_extensions:
            for metadata in discovered_extensions:
                await self.load_extension(metadata.name)

        logger.info(
            f"Discovery complete: {len(discovered_extensions)} extensions found"
        )
        return discovered_extensions

    async def load_extension(self, name_or_id: str) -> bool:
        """
        Load an extension by name or ID.

        Args:
            name_or_id: Extension name or ID

        Returns:
            True if loaded successfully
        """
        async with self._load_lock:
            # Check if already loaded
            if name_or_id in self._extensions:
                extension = self._extensions[name_or_id]
                if extension.is_loaded:
                    return True

            # Get metadata from registry
            metadata = self.registry.get_extension(name_or_id)
            if not metadata:
                logger.error(f"Extension not found in registry: {name_or_id}")
                return False

            try:
                # Load dependencies first
                if self.config.dependency_resolution:
                    success = await self._resolve_dependencies(metadata)
                    if not success:
                        return False

                # Load the extension
                extension = await self.loader.load_extension(metadata, self.container)
                if not extension:
                    return False

                # Store extension
                self._extensions[metadata.extension_id] = extension
                self._extensions[metadata.name] = extension  # Allow lookup by name

                if metadata.extension_id not in self._extension_order:
                    self._extension_order.append(metadata.extension_id)

                # Auto-activate if configured
                if self.config.auto_activate_extensions:
                    await self._activate_extension_safe(metadata.extension_id)

                logger.info(f"Extension {metadata.name} loaded successfully")
                return True

            except Exception as e:
                logger.error(f"Failed to load extension {name_or_id}: {e}")
                return False

    async def unload_extension(self, name_or_id: str) -> bool:
        """
        Unload an extension by name or ID.

        Args:
            name_or_id: Extension name or ID

        Returns:
            True if unloaded successfully
        """
        async with self._load_lock:
            extension = self._extensions.get(name_or_id)
            if not extension:
                return False

            try:
                # Deactivate if active
                if extension.is_active:
                    await extension.deactivate_extension()

                # Dispose extension
                await extension.dispose_extension()

                # Remove from collections
                extension_id = extension.extension_id
                name = extension.name

                if extension_id in self._extensions:
                    del self._extensions[extension_id]
                if name in self._extensions:
                    del self._extensions[name]

                if extension_id in self._extension_order:
                    self._extension_order.remove(extension_id)

                logger.info(f"Extension {name} unloaded successfully")
                return True

            except Exception as e:
                logger.error(f"Failed to unload extension {name_or_id}: {e}")
                return False

    # Extension Activation/Deactivation

    async def activate_extension(self, name_or_id: str) -> bool:
        """
        Activate an extension by name or ID.

        Args:
            name_or_id: Extension name or ID

        Returns:
            True if activated successfully
        """
        extension = self._extensions.get(name_or_id)
        if not extension:
            # Try to load it first
            success = await self.load_extension(name_or_id)
            if not success:
                return False
            extension = self._extensions.get(name_or_id)

        if extension and not extension.is_active:
            return await self._activate_extension_safe(extension.extension_id)

        return extension is not None and extension.is_active

    async def deactivate_extension(self, name_or_id: str) -> bool:
        """
        Deactivate an extension by name or ID.

        Args:
            name_or_id: Extension name or ID

        Returns:
            True if deactivated successfully
        """
        extension = self._extensions.get(name_or_id)
        if extension and extension.is_active:
            return await self._deactivate_extension_safe(extension.extension_id)

        return True

    async def _activate_extension_safe(self, extension_id: str) -> bool:
        """Safely activate an extension with error handling."""
        extension = self._extensions.get(extension_id)
        if not extension:
            return False

        try:
            return await extension.activate_extension()
        except Exception as e:
            logger.error(f"Failed to activate extension {extension.name}: {e}")
            return False

    async def _deactivate_extension_safe(self, extension_id: str) -> bool:
        """Safely deactivate an extension with error handling."""
        extension = self._extensions.get(extension_id)
        if not extension:
            return False

        try:
            return await extension.deactivate_extension()
        except Exception as e:
            logger.error(f"Failed to deactivate extension {extension.name}: {e}")
            return False

    async def _dispose_extension_safe(self, extension: Extension) -> None:
        """Safely dispose an extension with error handling."""
        try:
            await extension.dispose_extension()
        except Exception as e:
            logger.error(f"Failed to dispose extension {extension.name}: {e}")

    # Dependency Resolution

    async def _resolve_dependencies(self, metadata: ExtensionMetadata) -> bool:
        """
        Resolve dependencies for an extension.

        Args:
            metadata: Extension metadata

        Returns:
            True if all dependencies resolved
        """
        for dependency in metadata.dependencies:
            if dependency not in self._extensions:
                # Try to load the dependency
                success = await self.load_extension(dependency)
                if not success:
                    logger.error(
                        f"Failed to resolve dependency {dependency} for {metadata.name}"
                    )
                    return False

        return True

    # Extension Access

    def get_extension(self, name_or_id: str) -> Extension | None:
        """Get an extension by name or ID."""
        return self._extensions.get(name_or_id)

    def get_extensions(self) -> dict[str, Extension]:
        """Get all extensions."""
        return {k: v for k, v in self._extensions.items() if not k.startswith("ext_")}

    def get_active_extensions(self) -> dict[str, Extension]:
        """Get all active extensions."""
        return {k: v for k, v in self.get_extensions().items() if v.is_active}

    def get_extensions_by_status(self, status: ExtensionStatus) -> list[Extension]:
        """Get extensions by status."""
        return [ext for ext in self.get_extensions().values() if ext.status == status]

    def has_extension(self, name_or_id: str) -> bool:
        """Check if extension is registered."""
        return name_or_id in self._extensions

    def is_extension_active(self, name_or_id: str) -> bool:
        """Check if extension is active."""
        extension = self._extensions.get(name_or_id)
        return extension is not None and extension.is_active

    # Service Registration

    async def _register_core_services(self) -> None:
        """Register core RevitPy services."""
        # Register manager itself
        self.container.register_singleton(ExtensionManager, instance=self)

        # Register components
        self.container.register_singleton(ExtensionRegistry, instance=self.registry)
        self.container.register_singleton(ExtensionLoader, instance=self.loader)
        self.container.register_singleton(
            LifecycleManager, instance=self.lifecycle_manager
        )

        # Register core RevitPy services
        try:
            from ..api import RevitAPI
            from ..async_support import AsyncRevit
            from ..events.manager import EventManager

            # These would be registered by the main RevitPy initialization
            # self.container.register_singleton(RevitAPI)
            # self.container.register_singleton(AsyncRevit)
            # self.container.register_singleton(EventManager, instance=EventManager.get_instance())

        except ImportError as e:
            logger.warning(f"Some core services not available: {e}")

    # Statistics and Monitoring

    def get_statistics(self) -> dict[str, Any]:
        """Get extension manager statistics."""
        extensions_by_status = {}
        for status in ExtensionStatus:
            extensions_by_status[status.value] = len(
                self.get_extensions_by_status(status)
            )

        return {
            "total_extensions": self.extension_count,
            "active_extensions": self.active_extension_count,
            "extensions_by_status": extensions_by_status,
            "extension_directories": [
                str(d) for d in self.config.extension_directories
            ],
            "auto_load_enabled": self.config.auto_load_extensions,
            "auto_activate_enabled": self.config.auto_activate_extensions,
        }

    def get_extension_info(self, name_or_id: str) -> dict[str, Any] | None:
        """Get detailed information about an extension."""
        extension = self._extensions.get(name_or_id)
        if not extension:
            return None

        return {
            "metadata": extension.metadata.to_dict(),
            "status": extension.status.value,
            "is_active": extension.is_active,
            "has_error": extension.has_error,
            "last_error": str(extension.last_error) if extension.last_error else None,
            "commands": list(extension.get_commands().keys()),
            "services": list(extension.get_services().keys()),
            "tools": list(extension.get_tools().keys()),
            "analyzers": list(extension.get_analyzers().keys()),
        }

    # Context Manager Support

    async def __aenter__(self) -> "ExtensionManager":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.shutdown()


# Global instance management

_extension_manager: ExtensionManager | None = None


def get_extension_manager(
    config: ExtensionManagerConfig | None = None,
) -> ExtensionManager:
    """Get the global extension manager instance."""
    global _extension_manager
    if _extension_manager is None:
        _extension_manager = ExtensionManager.get_instance(config)
    return _extension_manager


# Convenience functions


async def load_extension(name_or_id: str) -> bool:
    """Load an extension globally."""
    return await get_extension_manager().load_extension(name_or_id)


async def activate_extension(name_or_id: str) -> bool:
    """Activate an extension globally."""
    return await get_extension_manager().activate_extension(name_or_id)


def get_extension(name_or_id: str) -> Extension | None:
    """Get an extension globally."""
    return get_extension_manager().get_extension(name_or_id)
