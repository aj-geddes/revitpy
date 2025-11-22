"""
Base extension class and metadata definitions.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from loguru import logger

from ..config import Config
from ..events.manager import EventManager
from .dependency_injection import DIContainer


class ExtensionStatus(Enum):
    """Extension status enumeration."""

    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    DEACTIVATED = "deactivated"
    ERROR = "error"
    DISPOSED = "disposed"


@dataclass
class ExtensionMetadata:
    """Metadata for an extension."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    website: str = ""
    license: str = ""

    # Dependencies
    dependencies: list[str] = field(default_factory=list)
    revit_versions: list[str] = field(default_factory=list)
    python_version: str = ">=3.11"

    # Capabilities
    provides_commands: list[str] = field(default_factory=list)
    provides_services: list[str] = field(default_factory=list)
    provides_tools: list[str] = field(default_factory=list)
    provides_analyzers: list[str] = field(default_factory=list)

    # Configuration
    config_schema: dict[str, Any] | None = None
    default_config: dict[str, Any] | None = None

    # Internal tracking
    extension_id: str = field(default_factory=lambda: str(uuid4()))
    load_time: datetime | None = None
    activation_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "extension_id": self.extension_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "website": self.website,
            "license": self.license,
            "dependencies": self.dependencies,
            "revit_versions": self.revit_versions,
            "python_version": self.python_version,
            "provides_commands": self.provides_commands,
            "provides_services": self.provides_services,
            "provides_tools": self.provides_tools,
            "provides_analyzers": self.provides_analyzers,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "load_time": self.load_time.isoformat() if self.load_time else None,
            "activation_time": self.activation_time.isoformat()
            if self.activation_time
            else None,
        }


class Extension(ABC):
    """
    Base class for RevitPy extensions.

    Extensions provide additional functionality to RevitPy including:
    - Commands: User-triggered actions
    - Services: Background processes and utilities
    - Tools: Interactive tools with preview
    - Analyzers: Real-time model analysis
    - Event Handlers: React to Revit events
    """

    def __init__(
        self,
        metadata: ExtensionMetadata,
        container: DIContainer | None = None,
        config: Config | None = None,
    ) -> None:
        self.metadata = metadata
        self.container = container or DIContainer()
        self.config = config or Config()

        # Extension state
        self.status = ExtensionStatus.UNLOADED
        self._error: Exception | None = None
        self._loaded_commands: dict[str, Any] = {}
        self._loaded_services: dict[str, Any] = {}
        self._loaded_tools: dict[str, Any] = {}
        self._loaded_analyzers: dict[str, Any] = {}
        self._event_handlers: list[Any] = []

        # Lifecycle callbacks
        self._load_callbacks: list[callable] = []
        self._activation_callbacks: list[callable] = []
        self._deactivation_callbacks: list[callable] = []
        self._disposal_callbacks: list[callable] = []

        logger.debug(f"Extension {self.name} created")

    @property
    def name(self) -> str:
        """Get extension name."""
        return self.metadata.name

    @property
    def version(self) -> str:
        """Get extension version."""
        return self.metadata.version

    @property
    def extension_id(self) -> str:
        """Get extension ID."""
        return self.metadata.extension_id

    @property
    def is_loaded(self) -> bool:
        """Check if extension is loaded."""
        return self.status not in (
            ExtensionStatus.UNLOADED,
            ExtensionStatus.ERROR,
            ExtensionStatus.DISPOSED,
        )

    @property
    def is_active(self) -> bool:
        """Check if extension is active."""
        return self.status == ExtensionStatus.ACTIVE

    @property
    def has_error(self) -> bool:
        """Check if extension has error."""
        return self.status == ExtensionStatus.ERROR

    @property
    def last_error(self) -> Exception | None:
        """Get last error."""
        return self._error

    # Lifecycle Methods (to be overridden by extensions)

    @abstractmethod
    async def load(self) -> None:
        """
        Load the extension.

        This method should:
        - Register services with DI container
        - Set up configuration
        - Prepare resources
        - Register event handlers

        Should not start any active processes or show UI.
        """
        pass

    @abstractmethod
    async def activate(self) -> None:
        """
        Activate the extension.

        This method should:
        - Start background services
        - Register commands and tools
        - Show UI elements
        - Begin active operations
        """
        pass

    @abstractmethod
    async def deactivate(self) -> None:
        """
        Deactivate the extension.

        This method should:
        - Stop background services
        - Unregister commands and tools
        - Hide UI elements
        - Stop active operations

        Should leave the extension in a loadable state.
        """
        pass

    async def dispose(self) -> None:
        """
        Dispose the extension and free all resources.

        This method should:
        - Clean up all resources
        - Unregister from all systems
        - Close connections
        - Free memory

        Extension cannot be reactivated after disposal.
        """
        # Default implementation
        if self.container:
            self.container.dispose()

        self._loaded_commands.clear()
        self._loaded_services.clear()
        self._loaded_tools.clear()
        self._loaded_analyzers.clear()
        self._event_handlers.clear()

    # Public Lifecycle Management

    async def load_extension(self) -> bool:
        """
        Load the extension with error handling.

        Returns:
            True if loaded successfully
        """
        if self.is_loaded:
            return True

        try:
            self.status = ExtensionStatus.LOADING
            self._error = None

            logger.info(f"Loading extension: {self.name} v{self.version}")

            # Setup DI container
            await self._setup_dependency_injection()

            # Load configuration
            await self._load_configuration()

            # Call extension's load method
            await self.load()

            # Execute load callbacks
            for callback in self._load_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self)
                    else:
                        callback(self)
                except Exception as e:
                    logger.error(f"Load callback failed for {self.name}: {e}")

            self.status = ExtensionStatus.LOADED
            self.metadata.load_time = datetime.now()

            logger.info(f"Extension {self.name} loaded successfully")
            return True

        except Exception as e:
            self._error = e
            self.status = ExtensionStatus.ERROR
            logger.error(f"Failed to load extension {self.name}: {e}")
            return False

    async def activate_extension(self) -> bool:
        """
        Activate the extension with error handling.

        Returns:
            True if activated successfully
        """
        if not self.is_loaded:
            success = await self.load_extension()
            if not success:
                return False

        if self.is_active:
            return True

        try:
            self.status = ExtensionStatus.INITIALIZING

            logger.info(f"Activating extension: {self.name}")

            # Call extension's activate method
            await self.activate()

            # Discover and register components
            await self._discover_components()

            # Execute activation callbacks
            for callback in self._activation_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self)
                    else:
                        callback(self)
                except Exception as e:
                    logger.error(f"Activation callback failed for {self.name}: {e}")

            self.status = ExtensionStatus.ACTIVE
            self.metadata.activation_time = datetime.now()

            logger.info(f"Extension {self.name} activated successfully")
            return True

        except Exception as e:
            self._error = e
            self.status = ExtensionStatus.ERROR
            logger.error(f"Failed to activate extension {self.name}: {e}")
            return False

    async def deactivate_extension(self) -> bool:
        """
        Deactivate the extension with error handling.

        Returns:
            True if deactivated successfully
        """
        if not self.is_active:
            return True

        try:
            self.status = ExtensionStatus.DEACTIVATING

            logger.info(f"Deactivating extension: {self.name}")

            # Execute deactivation callbacks
            for callback in self._deactivation_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self)
                    else:
                        callback(self)
                except Exception as e:
                    logger.error(f"Deactivation callback failed for {self.name}: {e}")

            # Unregister components
            await self._unregister_components()

            # Call extension's deactivate method
            await self.deactivate()

            self.status = ExtensionStatus.DEACTIVATED

            logger.info(f"Extension {self.name} deactivated successfully")
            return True

        except Exception as e:
            self._error = e
            self.status = ExtensionStatus.ERROR
            logger.error(f"Failed to deactivate extension {self.name}: {e}")
            return False

    async def dispose_extension(self) -> None:
        """Dispose the extension with error handling."""
        if self.status == ExtensionStatus.DISPOSED:
            return

        try:
            if self.is_active:
                await self.deactivate_extension()

            logger.info(f"Disposing extension: {self.name}")

            # Execute disposal callbacks
            for callback in self._disposal_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self)
                    else:
                        callback(self)
                except Exception as e:
                    logger.error(f"Disposal callback failed for {self.name}: {e}")

            # Call extension's dispose method
            await self.dispose()

            self.status = ExtensionStatus.DISPOSED

            logger.info(f"Extension {self.name} disposed")

        except Exception as e:
            self._error = e
            self.status = ExtensionStatus.ERROR
            logger.error(f"Failed to dispose extension {self.name}: {e}")

    # Component Management

    async def _discover_components(self) -> None:
        """Discover and register extension components."""
        # Scan for decorated methods and classes
        for name in dir(self):
            obj = getattr(self, name)

            # Check for command decorations
            if hasattr(obj, "_is_command"):
                command_info = obj._command_info
                self._loaded_commands[command_info.get("name", name)] = obj
                logger.debug(f"Registered command: {command_info.get('name', name)}")

            # Check for service decorations
            if hasattr(obj, "_is_service"):
                service_info = obj._service_info
                self._loaded_services[service_info.get("name", name)] = obj
                logger.debug(f"Registered service: {service_info.get('name', name)}")

            # Check for tool decorations
            if hasattr(obj, "_is_tool"):
                tool_info = obj._tool_info
                self._loaded_tools[tool_info.get("name", name)] = obj
                logger.debug(f"Registered tool: {tool_info.get('name', name)}")

            # Check for analyzer decorations
            if hasattr(obj, "_is_analyzer"):
                analyzer_info = obj._analyzer_info
                self._loaded_analyzers[analyzer_info.get("name", name)] = obj
                logger.debug(f"Registered analyzer: {analyzer_info.get('name', name)}")

        # Register event handlers
        event_manager = EventManager.get_instance()
        registered_handlers = event_manager.register_class_handlers(self)
        self._event_handlers.extend(registered_handlers)

    async def _unregister_components(self) -> None:
        """Unregister extension components."""
        # Unregister event handlers
        if self._event_handlers:
            event_manager = EventManager.get_instance()
            for handler in self._event_handlers:
                try:
                    event_manager.unregister_handler(handler)
                except Exception as e:
                    logger.error(f"Failed to unregister event handler: {e}")

        # Clear component collections
        self._loaded_commands.clear()
        self._loaded_services.clear()
        self._loaded_tools.clear()
        self._loaded_analyzers.clear()
        self._event_handlers.clear()

    async def _setup_dependency_injection(self) -> None:
        """Setup dependency injection container."""
        # Register common services

        # Register self as extension service
        self.container.register_singleton(Extension, instance=self)
        self.container.register_singleton(type(self), instance=self)

        # Register configuration
        self.container.register_singleton(Config, instance=self.config)

        # Register metadata
        self.container.register_singleton(ExtensionMetadata, instance=self.metadata)

    async def _load_configuration(self) -> None:
        """Load extension configuration."""
        # Load default configuration
        if self.metadata.default_config:
            for key, value in self.metadata.default_config.items():
                if not self.config.has(key):
                    self.config.set(key, value)

        # Load configuration from file if it exists
        config_path = Path(f"{self.name.lower()}_config.yaml")
        if config_path.exists():
            try:
                self.config.load_from_file(str(config_path))
                logger.debug(f"Loaded configuration for {self.name} from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load configuration for {self.name}: {e}")

    # Lifecycle Callbacks

    def on_load(self, callback: callable) -> None:
        """Register a callback for load event."""
        self._load_callbacks.append(callback)

    def on_activation(self, callback: callable) -> None:
        """Register a callback for activation event."""
        self._activation_callbacks.append(callback)

    def on_deactivation(self, callback: callable) -> None:
        """Register a callback for deactivation event."""
        self._deactivation_callbacks.append(callback)

    def on_disposal(self, callback: callable) -> None:
        """Register a callback for disposal event."""
        self._disposal_callbacks.append(callback)

    # Component Access

    def get_command(self, name: str) -> Any | None:
        """Get a registered command by name."""
        return self._loaded_commands.get(name)

    def get_service(self, name: str) -> Any | None:
        """Get a registered service by name."""
        return self._loaded_services.get(name)

    def get_tool(self, name: str) -> Any | None:
        """Get a registered tool by name."""
        return self._loaded_tools.get(name)

    def get_analyzer(self, name: str) -> Any | None:
        """Get a registered analyzer by name."""
        return self._loaded_analyzers.get(name)

    def get_commands(self) -> dict[str, Any]:
        """Get all registered commands."""
        return self._loaded_commands.copy()

    def get_services(self) -> dict[str, Any]:
        """Get all registered services."""
        return self._loaded_services.copy()

    def get_tools(self) -> dict[str, Any]:
        """Get all registered tools."""
        return self._loaded_tools.copy()

    def get_analyzers(self) -> dict[str, Any]:
        """Get all registered analyzers."""
        return self._loaded_analyzers.copy()

    # Utility Methods

    def get_extension_directory(self) -> Path:
        """Get the extension's directory."""
        # This would be set by the extension loader
        return getattr(self, "_extension_directory", Path.cwd())

    def get_data_directory(self) -> Path:
        """Get the extension's data directory."""
        return self.get_extension_directory() / "data"

    def get_resources_directory(self) -> Path:
        """Get the extension's resources directory."""
        return self.get_extension_directory() / "resources"

    def log_info(self, message: str) -> None:
        """Log info message with extension context."""
        logger.info(f"[{self.name}] {message}")

    def log_warning(self, message: str) -> None:
        """Log warning message with extension context."""
        logger.warning(f"[{self.name}] {message}")

    def log_error(self, message: str, exception: Exception | None = None) -> None:
        """Log error message with extension context."""
        if exception:
            logger.error(f"[{self.name}] {message}: {exception}")
        else:
            logger.error(f"[{self.name}] {message}")

    def log_debug(self, message: str) -> None:
        """Log debug message with extension context."""
        logger.debug(f"[{self.name}] {message}")

    def __repr__(self) -> str:
        return f"<Extension {self.name} v{self.version} [{self.status.value}]>"
