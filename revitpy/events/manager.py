"""
Main event manager for RevitPy event system.
"""

import asyncio
import importlib
import inspect
import threading
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .dispatcher import EventDispatcher, EventDispatchResult
from .filters import EventFilter
from .handlers import (
    AsyncCallableEventHandler,
    BaseEventHandler,
    CallableEventHandler,
)
from .types import EventData, EventPriority, EventType, create_event_data


class EventManager:
    """
    Main event manager that coordinates the RevitPy event system.

    Provides high-level interface for:
    - Registering event handlers
    - Dispatching events
    - Managing handler lifecycle
    - Auto-discovery of event handlers
    """

    _instance: Optional["EventManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventManager":
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return

        self._dispatcher = EventDispatcher()
        self._registered_modules: set[str] = set()
        self._auto_discovery_paths: list[Path] = []
        self._event_listeners: dict[EventType, list[Callable]] = defaultdict(list)
        self._is_running = False

        # Revit integration
        self._revit_event_bridge: Any | None = None

        self._initialized = True
        logger.info("EventManager initialized")

    @classmethod
    def get_instance(cls) -> "EventManager":
        """Get the singleton instance."""
        return cls()

    @property
    def dispatcher(self) -> EventDispatcher:
        """Get the event dispatcher."""
        return self._dispatcher

    @property
    def is_running(self) -> bool:
        """Check if event manager is running."""
        return self._is_running

    @property
    def stats(self) -> dict[str, Any]:
        """Get event processing statistics."""
        return {
            "dispatcher_stats": self._dispatcher.stats,
            "handler_stats": self._dispatcher.get_handler_stats(),
            "registered_modules": list(self._registered_modules),
            "auto_discovery_paths": [str(p) for p in self._auto_discovery_paths],
            "event_listeners_count": {
                event_type.value: len(listeners)
                for event_type, listeners in self._event_listeners.items()
            },
        }

    def start(self, auto_discover: bool = True) -> None:
        """
        Start the event manager.

        Args:
            auto_discover: Whether to auto-discover event handlers
        """
        if self._is_running:
            return

        self._is_running = True

        if auto_discover:
            self.discover_handlers()

        logger.info("EventManager started")

    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the event manager.

        Args:
            timeout: Timeout in seconds
        """
        if not self._is_running:
            return

        self._dispatcher.stop_processing(timeout)
        self._is_running = False

        logger.info("EventManager stopped")

    # Handler Registration

    def register_handler(
        self, handler: BaseEventHandler, event_types: list[EventType] | None = None
    ) -> None:
        """
        Register an event handler.

        Args:
            handler: Event handler to register
            event_types: Event types to handle (None for all events)
        """
        self._dispatcher.register_handler(handler, event_types)
        logger.debug(f"Registered handler: {handler.name}")

    def register_function(
        self,
        func: Callable[[EventData], Any],
        event_types: list[EventType],
        priority: EventPriority = EventPriority.NORMAL,
        event_filter: EventFilter | None = None,
        name: str | None = None,
    ) -> BaseEventHandler:
        """
        Register a function as an event handler.

        Args:
            func: Function to register
            event_types: Event types to handle
            priority: Handler priority
            event_filter: Optional event filter
            name: Optional handler name

        Returns:
            Created handler instance
        """
        handler_name = name or func.__name__

        if asyncio.iscoroutinefunction(func):
            handler = AsyncCallableEventHandler(
                callback=func,
                name=handler_name,
                priority=priority,
                event_filter=event_filter,
            )
        else:
            handler = CallableEventHandler(
                callback=func,
                name=handler_name,
                priority=priority,
                event_filter=event_filter,
            )

        self.register_handler(handler, event_types)
        return handler

    def unregister_handler(
        self, handler: BaseEventHandler, event_types: list[EventType] | None = None
    ) -> None:
        """
        Unregister an event handler.

        Args:
            handler: Handler to unregister
            event_types: Event types to unregister from (None for all)
        """
        self._dispatcher.unregister_handler(handler, event_types)
        logger.debug(f"Unregistered handler: {handler.name}")

    def register_class_handlers(self, instance: Any) -> list[BaseEventHandler]:
        """
        Register all decorated methods in a class instance as event handlers.

        Args:
            instance: Class instance to scan for handlers

        Returns:
            List of registered handlers
        """
        registered_handlers = []

        # Find all methods with event handler decorations
        for name in dir(instance):
            method = getattr(instance, name)

            if hasattr(method, "_is_event_handler"):
                # Extract handler info from decoration
                event_types = getattr(method, "_event_types", [])
                handler_obj = getattr(method, "_event_handler", None)

                if handler_obj:
                    self.register_handler(handler_obj, event_types)
                    registered_handlers.append(handler_obj)

                    logger.debug(
                        f"Registered class method handler: {instance.__class__.__name__}.{name}"
                    )

        return registered_handlers

    # Event Dispatching

    def dispatch_event(
        self, event_type: EventType, immediate: bool = False, **event_data
    ) -> EventDispatchResult:
        """
        Dispatch an event.

        Args:
            event_type: Type of event to dispatch
            immediate: Whether to process immediately
            **event_data: Event-specific data

        Returns:
            Dispatch result
        """
        event = create_event_data(event_type, **event_data)
        return self._dispatcher.dispatch_event(event, immediate)

    async def dispatch_event_async(
        self, event_type: EventType, **event_data
    ) -> EventDispatchResult:
        """
        Dispatch an event asynchronously.

        Args:
            event_type: Type of event to dispatch
            **event_data: Event-specific data

        Returns:
            Dispatch result
        """
        event = create_event_data(event_type, **event_data)
        return await self._dispatcher.dispatch_event_async(event)

    def emit(
        self,
        event_type: EventType,
        data: dict[str, Any] | None = None,
        source: Any | None = None,
        cancellable: bool = False,
        immediate: bool = False,
    ) -> EventDispatchResult:
        """
        Emit an event with simple interface.

        Args:
            event_type: Type of event to emit
            data: Event data dictionary
            source: Event source object
            cancellable: Whether event can be cancelled
            immediate: Whether to process immediately

        Returns:
            Dispatch result
        """
        return self.dispatch_event(
            event_type,
            data=data or {},
            source=source,
            cancellable=cancellable,
            immediate=immediate,
        )

    async def emit_async(
        self,
        event_type: EventType,
        data: dict[str, Any] | None = None,
        source: Any | None = None,
        cancellable: bool = False,
    ) -> EventDispatchResult:
        """
        Emit an event asynchronously with simple interface.

        Args:
            event_type: Type of event to emit
            data: Event data dictionary
            source: Event source object
            cancellable: Whether event can be cancelled

        Returns:
            Dispatch result
        """
        return await self.dispatch_event_async(
            event_type, data=data or {}, source=source, cancellable=cancellable
        )

    # Handler Discovery

    def add_discovery_path(self, path: Path) -> None:
        """
        Add a path for auto-discovery of event handlers.

        Args:
            path: Directory path to scan
        """
        if path not in self._auto_discovery_paths:
            self._auto_discovery_paths.append(path)
            logger.debug(f"Added discovery path: {path}")

    def discover_handlers(self, paths: list[Path] | None = None) -> int:
        """
        Discover and register event handlers from specified paths.

        Args:
            paths: Paths to scan (uses registered discovery paths if None)

        Returns:
            Number of handlers discovered
        """
        scan_paths = paths or self._auto_discovery_paths
        total_discovered = 0

        for path in scan_paths:
            try:
                discovered = self._discover_handlers_in_path(path)
                total_discovered += discovered
                logger.debug(f"Discovered {discovered} handlers in {path}")
            except Exception as e:
                logger.error(f"Failed to discover handlers in {path}: {e}")

        logger.info(f"Discovery complete: {total_discovered} handlers found")
        return total_discovered

    def _discover_handlers_in_path(self, path: Path) -> int:
        """Discover handlers in a specific path."""
        if not path.exists() or not path.is_dir():
            return 0

        discovered_count = 0

        # Walk through Python files
        for py_file in path.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue  # Skip private modules

            try:
                # Convert path to module name
                relative_path = py_file.relative_to(path)
                module_name = (
                    str(relative_path.with_suffix(""))
                    .replace("/", ".")
                    .replace("\\", ".")
                )

                if module_name in self._registered_modules:
                    continue  # Already processed

                # Import module
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Scan for decorated functions and classes
                discovered_count += self._scan_module_for_handlers(module)

                self._registered_modules.add(module_name)

            except Exception as e:
                logger.warning(f"Failed to process module {py_file}: {e}")

        return discovered_count

    def _scan_module_for_handlers(self, module: Any) -> int:
        """Scan a module for event handlers."""
        discovered_count = 0

        for name in dir(module):
            obj = getattr(module, name)

            # Check functions
            if inspect.isfunction(obj) and hasattr(obj, "_is_event_handler"):
                event_types = getattr(obj, "_event_types", [])
                handler = getattr(obj, "_event_handler", None)

                if handler:
                    self.register_handler(handler, event_types)
                    discovered_count += 1
                    logger.debug(
                        f"Discovered function handler: {module.__name__}.{name}"
                    )

            # Check classes
            elif inspect.isclass(obj):
                # Look for class methods with handlers
                for method_name in dir(obj):
                    method = getattr(obj, method_name)
                    if hasattr(method, "_is_event_handler"):
                        logger.debug(
                            f"Found handler method in class {obj.__name__}.{method_name}"
                        )
                        # Note: We can't register class methods without instances
                        # This would require instantiation or registration by user

        return discovered_count

    # Event Listeners (Simple callback interface)

    def add_listener(
        self,
        event_type: EventType,
        callback: Callable[[EventData], Any],
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """
        Add a simple event listener.

        Args:
            event_type: Event type to listen for
            callback: Callback function
            priority: Listener priority
        """
        self._event_listeners[event_type].append(callback)

        # Register as handler
        self.register_function(callback, [event_type], priority)

        logger.debug(f"Added event listener for {event_type.value}")

    def remove_listener(
        self, event_type: EventType, callback: Callable[[EventData], Any]
    ) -> bool:
        """
        Remove an event listener.

        Args:
            event_type: Event type
            callback: Callback to remove

        Returns:
            True if listener was removed
        """
        listeners = self._event_listeners.get(event_type, [])
        if callback in listeners:
            listeners.remove(callback)
            logger.debug(f"Removed event listener for {event_type.value}")
            return True
        return False

    # Revit Integration

    def connect_to_revit(self, revit_application: Any) -> None:
        """
        Connect to Revit application for native event bridging.

        Args:
            revit_application: Revit Application object
        """
        try:
            from .revit_bridge import RevitEventBridge

            self._revit_event_bridge = RevitEventBridge(self, revit_application)
            self._revit_event_bridge.connect()
            logger.info("Connected to Revit event system")
        except ImportError:
            logger.warning("Revit event bridge not available")
        except Exception as e:
            logger.error(f"Failed to connect to Revit events: {e}")

    def disconnect_from_revit(self) -> None:
        """Disconnect from Revit application."""
        if self._revit_event_bridge:
            try:
                self._revit_event_bridge.disconnect()
                self._revit_event_bridge = None
                logger.info("Disconnected from Revit event system")
            except Exception as e:
                logger.error(f"Failed to disconnect from Revit events: {e}")

    # Utility Methods

    def enable_debug(self) -> None:
        """Enable debug logging for events."""
        self._dispatcher.enable_debug(True)
        logger.info("Event debugging enabled")

    def disable_debug(self) -> None:
        """Disable debug logging for events."""
        self._dispatcher.enable_debug(False)
        logger.info("Event debugging disabled")

    def clear_event_queue(self) -> int:
        """Clear pending events from queue."""
        return self._dispatcher.clear_queue()

    def reset_statistics(self) -> None:
        """Reset all event statistics."""
        self._dispatcher.reset_stats()
        logger.info("Event statistics reset")

    def get_registered_handlers(self) -> dict[EventType, list[str]]:
        """Get list of registered handlers by event type."""
        result = {}

        for event_type in EventType:
            handlers = self._dispatcher.get_handlers_for_event(event_type)
            result[event_type] = [handler.name for handler in handlers]

        return result

    # Context Manager Support

    def __enter__(self) -> "EventManager":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.stop()

    async def __aenter__(self) -> "EventManager":
        """Async context manager entry."""
        self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        self.stop()


# Global instance
_event_manager: EventManager | None = None


def get_event_manager() -> EventManager:
    """Get the global event manager instance."""
    global _event_manager
    if _event_manager is None:
        _event_manager = EventManager.get_instance()
    return _event_manager


# Convenience functions


def register_handler(
    handler: BaseEventHandler, event_types: list[EventType] | None = None
) -> None:
    """Register an event handler globally."""
    get_event_manager().register_handler(handler, event_types)


def emit_event(
    event_type: EventType, data: dict[str, Any] | None = None, **kwargs
) -> EventDispatchResult:
    """Emit an event globally."""
    return get_event_manager().emit(event_type, data, **kwargs)


async def emit_event_async(
    event_type: EventType, data: dict[str, Any] | None = None, **kwargs
) -> EventDispatchResult:
    """Emit an event globally (async)."""
    return await get_event_manager().emit_async(event_type, data, **kwargs)


def add_event_listener(
    event_type: EventType,
    callback: Callable[[EventData], Any],
    priority: EventPriority = EventPriority.NORMAL,
) -> None:
    """Add an event listener globally."""
    get_event_manager().add_listener(event_type, callback, priority)
