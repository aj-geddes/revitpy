"""
Decorators for extension components.
"""

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from loguru import logger

F = TypeVar("F", bound=Callable[..., Any])


def extension(
    name: str,
    version: str,
    description: str = "",
    author: str = "",
    dependencies: list[str] | None = None,
    **kwargs,
) -> Callable[[type], type]:
    """
    Decorator to mark a class as a RevitPy extension.

    Args:
        name: Extension name
        version: Extension version
        description: Extension description
        author: Extension author
        dependencies: List of dependency extension names
        **kwargs: Additional metadata

    Returns:
        Decorated class
    """

    def decorator(cls: type) -> type:
        from .extension import ExtensionMetadata

        # Create metadata
        metadata = ExtensionMetadata(
            name=name,
            version=version,
            description=description,
            author=author,
            dependencies=dependencies or [],
            **kwargs,
        )

        # Store metadata on class
        cls._extension_metadata = metadata
        cls._is_extension = True

        logger.debug(f"Registered extension class: {name} v{version}")
        return cls

    return decorator


def command(
    name: str | None = None,
    description: str = "",
    icon: str | None = None,
    tooltip: str | None = None,
    shortcut: str | None = None,
    category: str = "General",
    enabled: bool = True,
    visible: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to mark a method as a RevitPy command.

    Args:
        name: Command name (defaults to method name)
        description: Command description
        icon: Icon path or name
        tooltip: Tooltip text
        shortcut: Keyboard shortcut
        category: Command category
        enabled: Whether command is initially enabled
        visible: Whether command is initially visible

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        func_name = name or func.__name__

        # Store command metadata
        func._is_command = True
        func._command_info = {
            "name": func_name,
            "description": description,
            "icon": icon,
            "tooltip": tooltip or description,
            "shortcut": shortcut,
            "category": category,
            "enabled": enabled,
            "visible": visible,
            "method": func.__name__,
        }

        logger.debug(f"Registered command: {func_name}")
        return func

    return decorator


def service(
    name: str | None = None,
    description: str = "",
    auto_start: bool = True,
    singleton: bool = True,
    dependencies: list[str] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to mark a method or class as a RevitPy service.

    Args:
        name: Service name (defaults to method/class name)
        description: Service description
        auto_start: Whether to start service automatically
        singleton: Whether service should be singleton
        dependencies: List of service dependencies

    Returns:
        Decorated method or class
    """

    def decorator(func_or_class: F) -> F:
        obj_name = name or func_or_class.__name__

        # Store service metadata
        func_or_class._is_service = True
        func_or_class._service_info = {
            "name": obj_name,
            "description": description,
            "auto_start": auto_start,
            "singleton": singleton,
            "dependencies": dependencies or [],
        }

        logger.debug(f"Registered service: {obj_name}")
        return func_or_class

    return decorator


def tool(
    name: str | None = None,
    description: str = "",
    icon: str | None = None,
    tooltip: str | None = None,
    category: str = "Tools",
    interactive: bool = True,
    preview: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to mark a method as a RevitPy tool.

    Args:
        name: Tool name (defaults to method name)
        description: Tool description
        icon: Icon path or name
        tooltip: Tooltip text
        category: Tool category
        interactive: Whether tool is interactive
        preview: Whether tool shows preview

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        func_name = name or func.__name__

        # Store tool metadata
        func._is_tool = True
        func._tool_info = {
            "name": func_name,
            "description": description,
            "icon": icon,
            "tooltip": tooltip or description,
            "category": category,
            "interactive": interactive,
            "preview": preview,
            "method": func.__name__,
        }

        logger.debug(f"Registered tool: {func_name}")
        return func

    return decorator


def analyzer(
    name: str | None = None,
    description: str = "",
    element_types: list[str] | None = None,
    categories: list[str] | None = None,
    real_time: bool = False,
    on_demand: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to mark a method as a RevitPy analyzer.

    Args:
        name: Analyzer name (defaults to method name)
        description: Analyzer description
        element_types: List of element types to analyze
        categories: List of categories to analyze
        real_time: Whether analyzer runs in real-time
        on_demand: Whether analyzer runs on-demand

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        func_name = name or func.__name__

        # Store analyzer metadata
        func._is_analyzer = True
        func._analyzer_info = {
            "name": func_name,
            "description": description,
            "element_types": element_types or [],
            "categories": categories or [],
            "real_time": real_time,
            "on_demand": on_demand,
            "method": func.__name__,
        }

        logger.debug(f"Registered analyzer: {func_name}")
        return func

    return decorator


def panel(
    name: str | None = None,
    title: str = "",
    width: int = 300,
    height: int = 400,
    resizable: bool = True,
    dockable: bool = True,
    floating: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to mark a method as a RevitPy panel.

    Args:
        name: Panel name (defaults to method name)
        title: Panel title
        width: Panel width
        height: Panel height
        resizable: Whether panel is resizable
        dockable: Whether panel is dockable
        floating: Whether panel starts floating

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        func_name = name or func.__name__

        # Store panel metadata
        func._is_panel = True
        func._panel_info = {
            "name": func_name,
            "title": title or func_name,
            "width": width,
            "height": height,
            "resizable": resizable,
            "dockable": dockable,
            "floating": floating,
            "method": func.__name__,
        }

        logger.debug(f"Registered panel: {func_name}")
        return func

    return decorator


def startup(priority: int = 0) -> Callable[[F], F]:
    """
    Decorator to mark a method as a startup task.

    Args:
        priority: Startup priority (lower numbers run first)

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        func._is_startup = True
        func._startup_priority = priority

        logger.debug(f"Registered startup task: {func.__name__} (priority: {priority})")
        return func

    return decorator


def shutdown(priority: int = 0) -> Callable[[F], F]:
    """
    Decorator to mark a method as a shutdown task.

    Args:
        priority: Shutdown priority (lower numbers run first)

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        func._is_shutdown = True
        func._shutdown_priority = priority

        logger.debug(
            f"Registered shutdown task: {func.__name__} (priority: {priority})"
        )
        return func

    return decorator


def config(
    key: str,
    default_value: Any = None,
    description: str = "",
    required: bool = False,
    validator: Callable[[Any], bool] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to mark a property as configurable.

    Args:
        key: Configuration key
        default_value: Default value
        description: Configuration description
        required: Whether configuration is required
        validator: Optional validation function

    Returns:
        Decorated property
    """

    def decorator(func: F) -> F:
        func._is_config = True
        func._config_info = {
            "key": key,
            "default_value": default_value,
            "description": description,
            "required": required,
            "validator": validator,
        }

        logger.debug(f"Registered config property: {key}")
        return func

    return decorator


def permission(
    name: str, description: str = "", required: bool = True, category: str = "General"
) -> Callable[[F], F]:
    """
    Decorator to mark a method as requiring a permission.

    Args:
        name: Permission name
        description: Permission description
        required: Whether permission is required
        category: Permission category

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        if not hasattr(func, "_permissions"):
            func._permissions = []

        func._permissions.append(
            {
                "name": name,
                "description": description,
                "required": required,
                "category": category,
            }
        )

        logger.debug(f"Added permission requirement: {name} to {func.__name__}")
        return func

    return decorator


def cache(
    ttl: float | None = None,
    max_size: int = 128,
    key_func: Callable[..., str] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to cache method results.

    Args:
        ttl: Time to live in seconds
        max_size: Maximum cache size
        key_func: Function to generate cache key

    Returns:
        Decorated method
    """

    def decorator(func: F) -> F:
        import time
        from typing import Any

        cache_dict: dict[str, Any] = {}
        cache_times: dict[str, float] = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = str(args) + str(sorted(kwargs.items()))

            current_time = time.time()

            # Check if cached result is valid
            if key in cache_dict:
                if ttl is None or (current_time - cache_times.get(key, 0)) < ttl:
                    return cache_dict[key]

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            if len(cache_dict) >= max_size:
                # Remove oldest entry
                oldest_key = min(cache_times, key=cache_times.get)
                del cache_dict[oldest_key]
                del cache_times[oldest_key]

            cache_dict[key] = result
            cache_times[key] = current_time

            return result

        wrapper._is_cached = True
        wrapper._cache_info = {
            "ttl": ttl,
            "max_size": max_size,
            "key_func": key_func,
        }

        return wrapper

    return decorator
