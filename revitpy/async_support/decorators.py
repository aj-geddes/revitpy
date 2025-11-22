"""
Decorators for async Revit operations.
"""

import asyncio
import functools
from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeVar, cast

from loguru import logger

from .cancellation import CancellationToken, with_cancellation
from .progress import ProgressReporter, create_progress_reporter
from .task_queue import Task, TaskPriority, TaskQueue

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def async_revit_operation(
    timeout: timedelta | None = None,
    retry_count: int = 0,
    retry_delay: timedelta = timedelta(seconds=1),
    cancellation_token: CancellationToken | None = None,
    progress_reporter: ProgressReporter | None = None,
) -> Callable[[F], F]:
    """
    Decorator to make Revit operations async-aware.

    Args:
        timeout: Optional timeout for the operation
        retry_count: Number of retry attempts
        retry_delay: Delay between retries
        cancellation_token: Optional cancellation token
        progress_reporter: Optional progress reporter
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            async def operation():
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    # Run sync function in executor
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, func, *args, **kwargs)

            # Apply retry logic
            if retry_count > 0:
                last_error = None

                for attempt in range(retry_count + 1):
                    try:
                        return await with_cancellation(
                            operation(), cancellation_token, timeout
                        )
                    except Exception as e:
                        last_error = e
                        if attempt < retry_count:
                            logger.warning(
                                f"Operation {func.__name__} failed on attempt {attempt + 1}, retrying: {e}"
                            )
                            await asyncio.sleep(retry_delay.total_seconds())
                        else:
                            logger.error(
                                f"Operation {func.__name__} failed after {retry_count + 1} attempts: {e}"
                            )
                            raise

                raise last_error
            else:
                return await with_cancellation(operation(), cancellation_token, timeout)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)

        # Return async version if called in async context, sync otherwise
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context
                return async_wrapper(*args, **kwargs)
            except RuntimeError:
                # No event loop running, use sync version
                return sync_wrapper(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def background_task(
    priority: TaskPriority = TaskPriority.NORMAL,
    timeout: timedelta | None = None,
    retry_count: int = 0,
    retry_delay: timedelta = timedelta(seconds=1),
    progress: bool = False,
    task_queue: TaskQueue | None = None,
) -> Callable[[F], F]:
    """
    Decorator to run functions as background tasks.

    Args:
        priority: Task priority
        timeout: Optional timeout
        retry_count: Number of retry attempts
        retry_delay: Delay between retries
        progress: Whether to enable progress reporting
        task_queue: Optional task queue to use
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> str:
            # Create progress reporter if requested
            progress_reporter = None
            if progress:
                progress_reporter = create_progress_reporter()

            # Create task
            task = Task(
                func,
                *args,
                name=func.__name__,
                priority=priority,
                timeout=timeout,
                retry_count=retry_count,
                retry_delay=retry_delay,
                progress_reporter=progress_reporter,
                **kwargs,
            )

            # Get or create task queue
            queue = task_queue
            if not queue:
                # Use a global task queue (would be managed by RevitPy)
                queue = get_default_task_queue()

            # Enqueue task
            return await queue.enqueue(task)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                loop = asyncio.get_running_loop()
                return async_wrapper(*args, **kwargs)
            except RuntimeError:
                return sync_wrapper(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def revit_transaction(
    name: str | None = None, auto_commit: bool = True, timeout: timedelta | None = None
) -> Callable[[F], F]:
    """
    Decorator to wrap functions in Revit transactions.

    Args:
        name: Transaction name
        auto_commit: Whether to auto-commit the transaction
        timeout: Optional timeout
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # This would integrate with the RevitAPI transaction system
            from ..api import RevitAPI

            api = RevitAPI()  # Would get current instance
            if not api.active_document:
                raise RuntimeError("No active Revit document")

            transaction_name = name or func.__name__

            async with api.transaction(transaction_name, auto_commit=auto_commit):
                return await async_revit_operation(timeout=timeout)(func)(
                    *args, **kwargs
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            from ..api import RevitAPI

            api = RevitAPI()  # Would get current instance
            if not api.active_document:
                raise RuntimeError("No active Revit document")

            transaction_name = name or func.__name__

            with api.transaction(transaction_name, auto_commit=auto_commit):
                return func(*args, **kwargs)

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                loop = asyncio.get_running_loop()
                return async_wrapper(*args, **kwargs)
            except RuntimeError:
                return sync_wrapper(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def rate_limited(max_calls: int, time_window: timedelta) -> Callable[[F], F]:
    """
    Decorator to rate limit function calls.

    Args:
        max_calls: Maximum number of calls allowed
        time_window: Time window for rate limiting
    """

    def decorator(func: F) -> F:
        calls = []
        lock = asyncio.Lock()

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            async with lock:
                now = asyncio.get_event_loop().time()
                cutoff = now - time_window.total_seconds()

                # Remove old calls
                while calls and calls[0] < cutoff:
                    calls.pop(0)

                # Check rate limit
                if len(calls) >= max_calls:
                    sleep_time = calls[0] + time_window.total_seconds() - now
                    if sleep_time > 0:
                        logger.debug(
                            f"Rate limiting {func.__name__}, sleeping {sleep_time:.2f}s"
                        )
                        await asyncio.sleep(sleep_time)

                # Record this call
                calls.append(now)

            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # For sync version, we can't easily implement rate limiting
            # without blocking, so just log and proceed
            logger.debug(
                f"Rate limiting not available for sync call to {func.__name__}"
            )
            return func(*args, **kwargs)

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                loop = asyncio.get_running_loop()
                return async_wrapper(*args, **kwargs)
            except RuntimeError:
                return sync_wrapper(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def cache_result(ttl: timedelta | None = None, max_size: int = 128) -> Callable[[F], F]:
    """
    Decorator to cache function results.

    Args:
        ttl: Time to live for cached results
        max_size: Maximum cache size
    """

    def decorator(func: F) -> F:
        cache = {}
        cache_times = {}

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Create cache key
            key = (args, tuple(sorted(kwargs.items())))

            # Check if we have a cached result
            if key in cache:
                if ttl is None:
                    return cache[key]

                cache_time = cache_times.get(key)
                if (
                    cache_time
                    and (asyncio.get_event_loop().time() - cache_time)
                    < ttl.total_seconds()
                ):
                    return cache[key]
                else:
                    # Expired, remove from cache
                    del cache[key]
                    if key in cache_times:
                        del cache_times[key]

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            if len(cache) >= max_size:
                # Remove oldest entry
                oldest_key = (
                    min(cache_times, key=cache_times.get)
                    if cache_times
                    else next(iter(cache))
                )
                del cache[oldest_key]
                if oldest_key in cache_times:
                    del cache_times[oldest_key]

            cache[key] = result
            if ttl is not None:
                cache_times[key] = asyncio.get_event_loop().time()

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Simple sync cache (without TTL for simplicity)
            key = (args, tuple(sorted(kwargs.items())))

            if key in cache:
                return cache[key]

            result = func(*args, **kwargs)

            if len(cache) >= max_size:
                # Remove first entry (FIFO)
                first_key = next(iter(cache))
                del cache[first_key]

            cache[key] = result
            return result

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                loop = asyncio.get_running_loop()
                return async_wrapper(*args, **kwargs)
            except RuntimeError:
                return sync_wrapper(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


# Global task queue instance
_default_task_queue: TaskQueue | None = None


def get_default_task_queue() -> TaskQueue:
    """Get the default task queue, creating if necessary."""
    global _default_task_queue

    if _default_task_queue is None:
        _default_task_queue = TaskQueue(name="DefaultTaskQueue")

        # Start the queue (this would be managed by RevitPy initialization)
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(_default_task_queue.start())
        except RuntimeError:
            # No event loop, create one temporarily
            async def start_queue():
                await _default_task_queue.start()

            asyncio.run(start_queue())

    return _default_task_queue


def set_default_task_queue(queue: TaskQueue) -> None:
    """Set the default task queue."""
    global _default_task_queue
    _default_task_queue = queue
