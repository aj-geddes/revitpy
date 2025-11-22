"""
Event dispatcher for managing event propagation and handler execution.
"""

import asyncio
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from ..async_support.task_queue import TaskQueue
from .handlers import AsyncEventHandler, BaseEventHandler
from .types import EventData, EventResult, EventType


@dataclass
class EventDispatchResult:
    """Result of event dispatching."""

    event_id: str
    handlers_executed: int = 0
    handlers_failed: int = 0
    execution_time: float = 0.0
    was_cancelled: bool = False
    final_result: EventResult = EventResult.CONTINUE
    errors: list[Exception] = field(default_factory=list)


@dataclass
class EventStats:
    """Statistics for event processing."""

    total_events: int = 0
    events_by_type: dict[EventType, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    total_handlers_executed: int = 0
    total_handlers_failed: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    peak_queue_size: int = 0

    def update_from_result(self, result: EventDispatchResult) -> None:
        """Update statistics from dispatch result."""
        self.total_events += 1
        self.total_handlers_executed += result.handlers_executed
        self.total_handlers_failed += result.handlers_failed
        self.total_execution_time += result.execution_time

        if self.total_events > 0:
            self.average_execution_time = self.total_execution_time / self.total_events


class EventDispatcher:
    """
    Manages event dispatching, handler execution, and event queuing.
    """

    def __init__(
        self,
        max_queue_size: int = 10000,
        batch_size: int = 100,
        max_concurrent_async_handlers: int = 10,
    ) -> None:
        self.max_queue_size = max_queue_size
        self.batch_size = batch_size

        # Handler storage
        self._handlers: dict[EventType, list[BaseEventHandler]] = defaultdict(list)
        self._global_handlers: list[BaseEventHandler] = []

        # Event queue
        self._event_queue: deque = deque()
        self._queue_lock = threading.RLock()

        # Async processing
        self._task_queue: TaskQueue | None = None
        self._async_handlers_semaphore = asyncio.Semaphore(
            max_concurrent_async_handlers
        )

        # Statistics
        self._stats = EventStats()

        # Processing state
        self._is_processing = False
        self._processing_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        # Event filtering
        self._event_filters: list[Callable[[EventData], bool]] = []

        # Debug mode
        self._debug_mode = False

    @property
    def stats(self) -> EventStats:
        """Get event processing statistics."""
        return self._stats

    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        with self._queue_lock:
            return len(self._event_queue)

    @property
    def is_processing(self) -> bool:
        """Check if dispatcher is processing events."""
        return self._is_processing

    def enable_debug(self, enabled: bool = True) -> None:
        """Enable or disable debug mode."""
        self._debug_mode = enabled
        if enabled:
            logger.info("Event dispatcher debug mode enabled")
        else:
            logger.info("Event dispatcher debug mode disabled")

    def add_global_filter(self, filter_func: Callable[[EventData], bool]) -> None:
        """
        Add a global event filter.

        Args:
            filter_func: Function that returns True if event should be processed
        """
        self._event_filters.append(filter_func)
        logger.debug("Added global event filter")

    def remove_global_filter(self, filter_func: Callable[[EventData], bool]) -> None:
        """Remove a global event filter."""
        if filter_func in self._event_filters:
            self._event_filters.remove(filter_func)
            logger.debug("Removed global event filter")

    def register_handler(
        self, handler: BaseEventHandler, event_types: list[EventType] | None = None
    ) -> None:
        """
        Register an event handler for specific event types.

        Args:
            handler: Event handler to register
            event_types: List of event types to handle (None for all events)
        """
        if event_types is None:
            # Global handler for all events
            self._global_handlers.append(handler)
            self._global_handlers.sort(key=lambda h: h.priority.value, reverse=True)
            logger.debug(f"Registered global handler: {handler.name}")
        else:
            # Type-specific handlers
            for event_type in event_types:
                self._handlers[event_type].append(handler)
                self._handlers[event_type].sort(
                    key=lambda h: h.priority.value, reverse=True
                )

                logger.debug(
                    f"Registered handler {handler.name} for event type {event_type.value}"
                )

    def unregister_handler(
        self, handler: BaseEventHandler, event_types: list[EventType] | None = None
    ) -> None:
        """
        Unregister an event handler.

        Args:
            handler: Event handler to unregister
            event_types: List of event types to unregister from (None for all)
        """
        if event_types is None:
            # Remove from global handlers
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)
                logger.debug(f"Unregistered global handler: {handler.name}")

            # Remove from all type-specific handlers
            for event_type_handlers in self._handlers.values():
                if handler in event_type_handlers:
                    event_type_handlers.remove(handler)
        else:
            # Remove from specific event types
            for event_type in event_types:
                if handler in self._handlers[event_type]:
                    self._handlers[event_type].remove(handler)
                    logger.debug(
                        f"Unregistered handler {handler.name} from event type {event_type.value}"
                    )

    def get_handlers_for_event(self, event_type: EventType) -> list[BaseEventHandler]:
        """
        Get all handlers that should process an event of the given type.

        Args:
            event_type: Event type

        Returns:
            List of handlers sorted by priority
        """
        handlers = []

        # Add type-specific handlers
        handlers.extend(self._handlers.get(event_type, []))

        # Add global handlers
        handlers.extend(self._global_handlers)

        # Sort by priority (highest first)
        handlers.sort(key=lambda h: h.priority.value, reverse=True)

        return handlers

    def dispatch_event(
        self, event_data: EventData, immediate: bool = False
    ) -> EventDispatchResult:
        """
        Dispatch an event to registered handlers.

        Args:
            event_data: Event data to dispatch
            immediate: Whether to process immediately or queue

        Returns:
            Dispatch result
        """
        if self._debug_mode:
            logger.debug(
                f"Dispatching event: {event_data.event_type.value} (ID: {event_data.event_id})"
            )

        # Apply global filters
        for filter_func in self._event_filters:
            if not filter_func(event_data):
                if self._debug_mode:
                    logger.debug(f"Event filtered out: {event_data.event_id}")
                return EventDispatchResult(
                    event_id=event_data.event_id, final_result=EventResult.CONTINUE
                )

        if immediate:
            return self._process_event_immediate(event_data)
        else:
            return self._queue_event(event_data)

    def _queue_event(self, event_data: EventData) -> EventDispatchResult:
        """Queue an event for processing."""
        with self._queue_lock:
            if len(self._event_queue) >= self.max_queue_size:
                # Queue is full, drop oldest event
                dropped_event = self._event_queue.popleft()
                logger.warning(
                    f"Event queue full, dropped event: {dropped_event.event_id}"
                )

            self._event_queue.append(event_data)

            # Update peak queue size
            if len(self._event_queue) > self._stats.peak_queue_size:
                self._stats.peak_queue_size = len(self._event_queue)

        # Start processing if not already running
        if not self._is_processing:
            self._start_processing()

        return EventDispatchResult(
            event_id=event_data.event_id, final_result=EventResult.CONTINUE
        )

    def _process_event_immediate(self, event_data: EventData) -> EventDispatchResult:
        """Process an event immediately (synchronously)."""
        start_time = time.perf_counter()
        result = EventDispatchResult(event_id=event_data.event_id)

        try:
            # Get handlers for this event
            handlers = self.get_handlers_for_event(event_data.event_type)

            # Process handlers
            for handler in handlers:
                if not handler.should_handle(event_data):
                    continue

                try:
                    handler_result = handler.handle_event_safely(event_data)
                    result.handlers_executed += 1

                    if handler_result == EventResult.CANCEL and event_data.cancellable:
                        event_data.cancel()
                        result.was_cancelled = True
                        result.final_result = EventResult.CANCEL
                        break
                    elif handler_result == EventResult.STOP:
                        result.final_result = EventResult.STOP
                        break

                except Exception as e:
                    result.handlers_failed += 1
                    result.errors.append(e)
                    logger.error(f"Handler {handler.name} failed: {e}")

        finally:
            result.execution_time = time.perf_counter() - start_time
            self._stats.update_from_result(result)
            self._stats.events_by_type[event_data.event_type] += 1

        return result

    async def dispatch_event_async(self, event_data: EventData) -> EventDispatchResult:
        """
        Dispatch an event asynchronously.

        Args:
            event_data: Event data to dispatch

        Returns:
            Dispatch result
        """
        if self._debug_mode:
            logger.debug(
                f"Dispatching event async: {event_data.event_type.value} (ID: {event_data.event_id})"
            )

        # Apply global filters
        for filter_func in self._event_filters:
            if not filter_func(event_data):
                if self._debug_mode:
                    logger.debug(f"Event filtered out: {event_data.event_id}")
                return EventDispatchResult(
                    event_id=event_data.event_id, final_result=EventResult.CONTINUE
                )

        return await self._process_event_async(event_data)

    async def _process_event_async(self, event_data: EventData) -> EventDispatchResult:
        """Process an event asynchronously."""
        start_time = time.perf_counter()
        result = EventDispatchResult(event_id=event_data.event_id)

        try:
            # Get handlers for this event
            handlers = self.get_handlers_for_event(event_data.event_type)

            # Separate sync and async handlers
            sync_handlers = [
                h for h in handlers if not isinstance(h, AsyncEventHandler)
            ]
            async_handlers = [h for h in handlers if isinstance(h, AsyncEventHandler)]

            # Process sync handlers first
            for handler in sync_handlers:
                if not handler.should_handle(event_data):
                    continue

                try:
                    # Run sync handler in executor to avoid blocking
                    loop = asyncio.get_event_loop()
                    handler_result = await loop.run_in_executor(
                        None, handler.handle_event_safely, event_data
                    )

                    result.handlers_executed += 1

                    if handler_result == EventResult.CANCEL and event_data.cancellable:
                        event_data.cancel()
                        result.was_cancelled = True
                        result.final_result = EventResult.CANCEL
                        break
                    elif handler_result == EventResult.STOP:
                        result.final_result = EventResult.STOP
                        break

                except Exception as e:
                    result.handlers_failed += 1
                    result.errors.append(e)
                    logger.error(f"Sync handler {handler.name} failed: {e}")

            # Process async handlers if event wasn't cancelled/stopped
            if result.final_result == EventResult.CONTINUE and async_handlers:
                async_tasks = []

                for handler in async_handlers:
                    if not handler.should_handle(event_data):
                        continue

                    # Create async task with semaphore for rate limiting
                    async def process_async_handler(
                        h: AsyncEventHandler,
                    ) -> EventResult:
                        async with self._async_handlers_semaphore:
                            return await h.handle_event_safely_async(event_data)

                    async_tasks.append(process_async_handler(handler))

                if async_tasks:
                    # Execute async handlers concurrently
                    async_results = await asyncio.gather(
                        *async_tasks, return_exceptions=True
                    )

                    for _i, async_result in enumerate(async_results):
                        if isinstance(async_result, Exception):
                            result.handlers_failed += 1
                            result.errors.append(async_result)
                            logger.error(f"Async handler failed: {async_result}")
                        else:
                            result.handlers_executed += 1

                            if (
                                async_result == EventResult.CANCEL
                                and event_data.cancellable
                            ):
                                event_data.cancel()
                                result.was_cancelled = True
                                result.final_result = EventResult.CANCEL
                            elif async_result == EventResult.STOP:
                                result.final_result = EventResult.STOP

        finally:
            result.execution_time = time.perf_counter() - start_time
            self._stats.update_from_result(result)
            self._stats.events_by_type[event_data.event_type] += 1

        return result

    def _start_processing(self) -> None:
        """Start the event processing thread."""
        if self._is_processing:
            return

        self._is_processing = True
        self._shutdown_event.clear()

        self._processing_thread = threading.Thread(
            target=self._process_events_loop, name="EventDispatcherThread", daemon=True
        )
        self._processing_thread.start()

        logger.debug("Started event processing thread")

    def _process_events_loop(self) -> None:
        """Main event processing loop (runs in background thread)."""
        try:
            while self._is_processing and not self._shutdown_event.is_set():
                # Process batch of events
                batch = []

                with self._queue_lock:
                    # Get batch of events
                    for _ in range(min(self.batch_size, len(self._event_queue))):
                        if self._event_queue:
                            batch.append(self._event_queue.popleft())

                if not batch:
                    # No events to process, sleep briefly
                    time.sleep(0.01)
                    continue

                # Process batch
                for event_data in batch:
                    if self._shutdown_event.is_set():
                        break

                    try:
                        self._process_event_immediate(event_data)
                    except Exception as e:
                        logger.error(
                            f"Error processing event {event_data.event_id}: {e}"
                        )

        except Exception as e:
            logger.error(f"Event processing loop failed: {e}")

        finally:
            self._is_processing = False
            logger.debug("Event processing thread stopped")

    def stop_processing(self, timeout: float = 5.0) -> None:
        """
        Stop event processing.

        Args:
            timeout: Timeout in seconds to wait for processing to stop
        """
        if not self._is_processing:
            return

        logger.info("Stopping event processing...")

        self._shutdown_event.set()

        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout)

            if self._processing_thread.is_alive():
                logger.warning("Event processing thread did not stop within timeout")
            else:
                logger.info("Event processing stopped")

        self._is_processing = False

    def clear_queue(self) -> int:
        """
        Clear the event queue.

        Returns:
            Number of events cleared
        """
        with self._queue_lock:
            count = len(self._event_queue)
            self._event_queue.clear()

        logger.info(f"Cleared {count} events from queue")
        return count

    def get_handler_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all registered handlers."""
        stats = {}

        # Collect stats from all handlers
        all_handlers = self._global_handlers.copy()
        for handlers_list in self._handlers.values():
            all_handlers.extend(handlers_list)

        for handler in all_handlers:
            stats[handler.name] = {
                "priority": handler.priority.value,
                "enabled": handler.is_enabled,
                "execution_count": handler.metadata.execution_count,
                "error_count": handler.metadata.error_count,
                "average_execution_time": handler.metadata.average_execution_time,
                "total_execution_time": handler.metadata.total_execution_time,
                "last_error": str(handler.metadata.last_error)
                if handler.metadata.last_error
                else None,
            }

        return stats

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self._stats = EventStats()

        # Reset handler stats
        all_handlers = self._global_handlers.copy()
        for handlers_list in self._handlers.values():
            all_handlers.extend(handlers_list)

        for handler in all_handlers:
            handler.metadata.execution_count = 0
            handler.metadata.error_count = 0
            handler.metadata.total_execution_time = 0.0
            handler.metadata.last_error = None

        logger.info("Reset event dispatcher statistics")

    def __del__(self) -> None:
        """Cleanup on destruction."""
        if self._is_processing:
            self.stop_processing()
