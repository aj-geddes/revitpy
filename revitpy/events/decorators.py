"""
Decorators for event handling in RevitPy.
"""

import asyncio
import functools
from collections.abc import Callable
from typing import Any, TypeVar, cast

from loguru import logger

from .filters import EventFilter
from .handlers import AsyncCallableEventHandler, CallableEventHandler
from .types import EventData, EventPriority, EventResult, EventType

F = TypeVar("F", bound=Callable[..., Any])


def event_handler(
    event_types: list[EventType] | None = None,
    priority: EventPriority = EventPriority.NORMAL,
    event_filter: EventFilter | None = None,
    max_errors: int = 10,
    enabled: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to register a function as an event handler.

    Args:
        event_types: List of event types to handle
        priority: Handler priority
        event_filter: Optional event filter
        max_errors: Maximum errors before disabling
        enabled: Whether handler starts enabled

    Returns:
        Decorated function

    Example:
        @event_handler([EventType.ELEMENT_CREATED])
        def on_element_created(event_data: EventData) -> EventResult:
            print(f"Element created: {event_data.element_id}")
            return EventResult.CONTINUE
    """

    def decorator(func: F) -> F:
        # Create appropriate handler based on whether function is async
        if asyncio.iscoroutinefunction(func):
            handler = AsyncCallableEventHandler(
                callback=func,
                name=func.__name__,
                priority=priority,
                event_filter=event_filter,
                max_errors=max_errors,
            )
        else:
            handler = CallableEventHandler(
                callback=func,
                name=func.__name__,
                priority=priority,
                event_filter=event_filter,
                max_errors=max_errors,
            )

        # Store handler metadata on function
        func._event_handler = handler
        func._event_types = event_types or []
        func._is_event_handler = True

        if not enabled:
            handler.disable()

        logger.debug(f"Registered event handler: {func.__name__}")

        return func

    return decorator


def async_event_handler(
    event_types: list[EventType] | None = None,
    priority: EventPriority = EventPriority.NORMAL,
    event_filter: EventFilter | None = None,
    max_errors: int = 10,
    enabled: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to register an async function as an event handler.

    Args:
        event_types: List of event types to handle
        priority: Handler priority
        event_filter: Optional event filter
        max_errors: Maximum errors before disabling
        enabled: Whether handler starts enabled

    Returns:
        Decorated async function

    Example:
        @async_event_handler([EventType.ELEMENT_MODIFIED])
        async def on_element_modified(event_data: EventData) -> EventResult:
            await some_async_operation()
            return EventResult.CONTINUE
    """

    def decorator(func: F) -> F:
        if not asyncio.iscoroutinefunction(func):
            logger.warning(
                f"Function {func.__name__} is not async but decorated with @async_event_handler"
            )

        handler = AsyncCallableEventHandler(
            callback=func,
            name=func.__name__,
            priority=priority,
            event_filter=event_filter,
            max_errors=max_errors,
        )

        # Store handler metadata on function
        func._event_handler = handler
        func._event_types = event_types or []
        func._is_event_handler = True
        func._is_async_handler = True

        if not enabled:
            handler.disable()

        logger.debug(f"Registered async event handler: {func.__name__}")

        return func

    return decorator


def event_filter(filter_instance: EventFilter) -> Callable[[F], F]:
    """
    Decorator to add an event filter to a handler.

    Args:
        filter_instance: Event filter to apply

    Returns:
        Decorated function

    Example:
        @event_handler([EventType.ELEMENT_MODIFIED])
        @event_filter(element_type("Wall"))
        def on_wall_modified(event_data: EventData) -> EventResult:
            print("A wall was modified")
            return EventResult.CONTINUE
    """

    def decorator(func: F) -> F:
        if hasattr(func, "_event_handler"):
            # Update existing handler's filter
            existing_filter = func._event_handler.event_filter
            if existing_filter:
                # Combine filters with AND
                func._event_handler.event_filter = existing_filter & filter_instance
            else:
                func._event_handler.event_filter = filter_instance
        else:
            # Store filter for later when event_handler decorator is applied
            func._pending_event_filter = filter_instance

        return func

    return decorator


def throttled_handler(interval_seconds: float = 0.1) -> Callable[[F], F]:
    """
    Decorator to throttle event handler execution.

    Args:
        interval_seconds: Minimum interval between executions

    Returns:
        Decorated function

    Example:
        @event_handler([EventType.SELECTION_CHANGED])
        @throttled_handler(0.5)  # At most once per 500ms
        def on_selection_changed(event_data: EventData) -> EventResult:
            print("Selection changed")
            return EventResult.CONTINUE
    """

    def decorator(func: F) -> F:
        last_execution = [0.0]  # Use list for mutable reference

        @functools.wraps(func)
        def throttled_wrapper(*args, **kwargs) -> Any:
            import time

            current_time = time.perf_counter()

            if current_time - last_execution[0] < interval_seconds:
                logger.debug(f"Throttling handler {func.__name__}")
                return EventResult.CONTINUE

            last_execution[0] = current_time
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_throttled_wrapper(*args, **kwargs) -> Any:
            import time

            current_time = time.perf_counter()

            if current_time - last_execution[0] < interval_seconds:
                logger.debug(f"Throttling async handler {func.__name__}")
                return EventResult.CONTINUE

            last_execution[0] = current_time

            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            wrapper = async_throttled_wrapper
        else:
            wrapper = throttled_wrapper

        # Preserve event handler metadata
        if hasattr(func, "_event_handler"):
            wrapper._event_handler = func._event_handler
        if hasattr(func, "_event_types"):
            wrapper._event_types = func._event_types
        if hasattr(func, "_is_event_handler"):
            wrapper._is_event_handler = func._is_event_handler

        return cast(F, wrapper)

    return decorator


def conditional_handler(condition: Callable[[EventData], bool]) -> Callable[[F], F]:
    """
    Decorator to add a condition to an event handler.

    Args:
        condition: Function that returns True if handler should execute

    Returns:
        Decorated function

    Example:
        @event_handler([EventType.ELEMENT_MODIFIED])
        @conditional_handler(lambda event: event.get_data('user_initiated', False))
        def on_user_modified(event_data: EventData) -> EventResult:
            print("User modified an element")
            return EventResult.CONTINUE
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def conditional_wrapper(event_data: EventData, *args, **kwargs) -> Any:
            if not condition(event_data):
                logger.debug(f"Condition failed for handler {func.__name__}")
                return EventResult.CONTINUE

            return func(event_data, *args, **kwargs)

        @functools.wraps(func)
        async def async_conditional_wrapper(
            event_data: EventData, *args, **kwargs
        ) -> Any:
            if not condition(event_data):
                logger.debug(f"Condition failed for async handler {func.__name__}")
                return EventResult.CONTINUE

            if asyncio.iscoroutinefunction(func):
                return await func(event_data, *args, **kwargs)
            else:
                return func(event_data, *args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            wrapper = async_conditional_wrapper
        else:
            wrapper = conditional_wrapper

        # Preserve event handler metadata
        if hasattr(func, "_event_handler"):
            wrapper._event_handler = func._event_handler
        if hasattr(func, "_event_types"):
            wrapper._event_types = func._event_types
        if hasattr(func, "_is_event_handler"):
            wrapper._is_event_handler = func._is_event_handler

        return cast(F, wrapper)

    return decorator


def retry_on_error(
    max_retries: int = 3, delay_seconds: float = 1.0
) -> Callable[[F], F]:
    """
    Decorator to retry event handler on errors.

    Args:
        max_retries: Maximum number of retries
        delay_seconds: Delay between retries

    Returns:
        Decorated function

    Example:
        @event_handler([EventType.ELEMENT_CREATED])
        @retry_on_error(max_retries=2, delay_seconds=0.5)
        def on_element_created(event_data: EventData) -> EventResult:
            # May fail occasionally, will be retried
            return EventResult.CONTINUE
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def retry_wrapper(*args, **kwargs) -> Any:
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    if attempt < max_retries:
                        logger.warning(
                            f"Handler {func.__name__} failed on attempt {attempt + 1}, retrying: {e}"
                        )
                        import time

                        time.sleep(delay_seconds)
                    else:
                        logger.error(
                            f"Handler {func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )

            raise last_error

        @functools.wraps(func)
        async def async_retry_wrapper(*args, **kwargs) -> Any:
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    if attempt < max_retries:
                        logger.warning(
                            f"Async handler {func.__name__} failed on attempt {attempt + 1}, retrying: {e}"
                        )
                        await asyncio.sleep(delay_seconds)
                    else:
                        logger.error(
                            f"Async handler {func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )

            raise last_error

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            wrapper = async_retry_wrapper
        else:
            wrapper = retry_wrapper

        # Preserve event handler metadata
        if hasattr(func, "_event_handler"):
            wrapper._event_handler = func._event_handler
        if hasattr(func, "_event_types"):
            wrapper._event_types = func._event_types
        if hasattr(func, "_is_event_handler"):
            wrapper._is_event_handler = func._is_event_handler

        return cast(F, wrapper)

    return decorator


def log_events(log_level: str = "DEBUG") -> Callable[[F], F]:
    """
    Decorator to log event handling.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Decorated function

    Example:
        @event_handler([EventType.ELEMENT_DELETED])
        @log_events("INFO")
        def on_element_deleted(event_data: EventData) -> EventResult:
            return EventResult.CONTINUE
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def logging_wrapper(event_data: EventData, *args, **kwargs) -> Any:
            logger.log(
                log_level,
                f"Handler {func.__name__} processing event {event_data.event_type.value} "
                f"(ID: {event_data.event_id})",
            )

            try:
                result = func(event_data, *args, **kwargs)

                logger.log(
                    log_level,
                    f"Handler {func.__name__} completed with result: {result}",
                )

                return result
            except Exception as e:
                logger.error(f"Handler {func.__name__} failed: {e}")
                raise

        @functools.wraps(func)
        async def async_logging_wrapper(event_data: EventData, *args, **kwargs) -> Any:
            logger.log(
                log_level,
                f"Async handler {func.__name__} processing event {event_data.event_type.value} "
                f"(ID: {event_data.event_id})",
            )

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(event_data, *args, **kwargs)
                else:
                    result = func(event_data, *args, **kwargs)

                logger.log(
                    log_level,
                    f"Async handler {func.__name__} completed with result: {result}",
                )

                return result
            except Exception as e:
                logger.error(f"Async handler {func.__name__} failed: {e}")
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            wrapper = async_logging_wrapper
        else:
            wrapper = logging_wrapper

        # Preserve event handler metadata
        if hasattr(func, "_event_handler"):
            wrapper._event_handler = func._event_handler
        if hasattr(func, "_event_types"):
            wrapper._event_types = func._event_types
        if hasattr(func, "_is_event_handler"):
            wrapper._is_event_handler = func._is_event_handler

        return cast(F, wrapper)

    return decorator


# Convenience decorators for common event types


def on_element_created(
    element_type: str | None = None, priority: EventPriority = EventPriority.NORMAL
) -> Callable[[F], F]:
    """Decorator for element creation events."""
    filter_instance = None
    if element_type:
        from .filters import element_type as element_type_filter

        filter_instance = element_type_filter(element_type)

    return event_handler(
        event_types=[EventType.ELEMENT_CREATED],
        priority=priority,
        event_filter=filter_instance,
    )


def on_element_modified(
    element_type: str | None = None,
    parameter_name: str | None = None,
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable[[F], F]:
    """Decorator for element modification events."""
    filter_instance = None
    if element_type or parameter_name:
        from .filters import element_type as element_type_filter
        from .filters import parameter_changed

        filters = []
        if element_type:
            filters.append(element_type_filter(element_type))
        if parameter_name:
            filters.append(parameter_changed(parameter_name))

        if len(filters) == 1:
            filter_instance = filters[0]
        else:
            filter_instance = filters[0] & filters[1]

    return event_handler(
        event_types=[EventType.ELEMENT_MODIFIED],
        priority=priority,
        event_filter=filter_instance,
    )


def on_element_deleted(
    element_type: str | None = None, priority: EventPriority = EventPriority.NORMAL
) -> Callable[[F], F]:
    """Decorator for element deletion events."""
    filter_instance = None
    if element_type:
        from .filters import element_type as element_type_filter

        filter_instance = element_type_filter(element_type)

    return event_handler(
        event_types=[EventType.ELEMENT_DELETED],
        priority=priority,
        event_filter=filter_instance,
    )


def on_parameter_changed(
    parameter_name: str,
    element_type: str | None = None,
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable[[F], F]:
    """Decorator for parameter change events."""
    from .filters import element_type as element_type_filter
    from .filters import parameter_changed

    filter_instance = parameter_changed(parameter_name)
    if element_type:
        filter_instance = filter_instance & element_type_filter(element_type)

    return event_handler(
        event_types=[EventType.PARAMETER_CHANGED],
        priority=priority,
        event_filter=filter_instance,
    )


def on_document_opened(
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable[[F], F]:
    """Decorator for document opened events."""
    return event_handler(event_types=[EventType.DOCUMENT_OPENED], priority=priority)


def on_document_saved(
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable[[F], F]:
    """Decorator for document saved events."""
    return event_handler(event_types=[EventType.DOCUMENT_SAVED], priority=priority)
