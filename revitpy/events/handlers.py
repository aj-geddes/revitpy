"""
Event handler base classes and implementations.
"""

import asyncio
from typing import Any, Optional, Callable, List
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from loguru import logger

from .types import EventData, EventResult, EventPriority
from .filters import EventFilter


@dataclass
class HandlerMetadata:
    """Metadata for event handlers."""
    
    name: str
    priority: EventPriority = EventPriority.NORMAL
    enabled: bool = True
    error_count: int = 0
    max_errors: int = 10
    last_error: Optional[Exception] = None
    execution_count: int = 0
    total_execution_time: float = 0.0
    
    @property
    def average_execution_time(self) -> float:
        """Get average execution time."""
        if self.execution_count == 0:
            return 0.0
        return self.total_execution_time / self.execution_count
    
    @property
    def is_disabled_due_to_errors(self) -> bool:
        """Check if handler is disabled due to errors."""
        return self.error_count >= self.max_errors


class BaseEventHandler(ABC):
    """Abstract base class for event handlers."""
    
    def __init__(
        self,
        name: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
        event_filter: Optional[EventFilter] = None,
        max_errors: int = 10
    ) -> None:
        self.metadata = HandlerMetadata(
            name=name or self.__class__.__name__,
            priority=priority,
            max_errors=max_errors
        )
        self.event_filter = event_filter
    
    @property
    def name(self) -> str:
        """Get handler name."""
        return self.metadata.name
    
    @property
    def priority(self) -> EventPriority:
        """Get handler priority."""
        return self.metadata.priority
    
    @property
    def is_enabled(self) -> bool:
        """Check if handler is enabled."""
        return self.metadata.enabled and not self.metadata.is_disabled_due_to_errors
    
    def enable(self) -> None:
        """Enable the handler."""
        self.metadata.enabled = True
    
    def disable(self) -> None:
        """Disable the handler."""
        self.metadata.enabled = False
    
    def reset_error_count(self) -> None:
        """Reset the error count."""
        self.metadata.error_count = 0
        self.metadata.last_error = None
    
    def should_handle(self, event_data: EventData) -> bool:
        """
        Check if this handler should handle the event.
        
        Args:
            event_data: Event data to check
            
        Returns:
            True if handler should process the event
        """
        if not self.is_enabled:
            return False
        
        if self.event_filter and not self.event_filter.matches(event_data):
            return False
        
        return True
    
    def handle_event_safely(self, event_data: EventData) -> EventResult:
        """
        Handle event with error handling and metrics.
        
        Args:
            event_data: Event data
            
        Returns:
            Event result
        """
        if not self.should_handle(event_data):
            return EventResult.CONTINUE
        
        import time
        start_time = time.perf_counter()
        
        try:
            result = self.handle_event(event_data)
            
            # Update metrics
            execution_time = time.perf_counter() - start_time
            self.metadata.execution_count += 1
            self.metadata.total_execution_time += execution_time
            
            logger.debug(
                f"Handler {self.name} processed event {event_data.event_type.value} "
                f"in {execution_time:.3f}s, result: {result.value}"
            )
            
            return result
        
        except Exception as e:
            # Update error metrics
            self.metadata.error_count += 1
            self.metadata.last_error = e
            
            logger.error(
                f"Handler {self.name} failed to process event {event_data.event_type.value}: {e}"
            )
            
            # Disable if too many errors
            if self.metadata.error_count >= self.metadata.max_errors:
                logger.warning(
                    f"Handler {self.name} disabled due to {self.metadata.error_count} errors"
                )
            
            return EventResult.CONTINUE
    
    @abstractmethod
    def handle_event(self, event_data: EventData) -> EventResult:
        """
        Handle the event.
        
        Args:
            event_data: Event data
            
        Returns:
            Event result
        """
        pass


class AsyncEventHandler(BaseEventHandler):
    """Async event handler base class."""
    
    async def handle_event_safely_async(self, event_data: EventData) -> EventResult:
        """
        Handle event asynchronously with error handling and metrics.
        
        Args:
            event_data: Event data
            
        Returns:
            Event result
        """
        if not self.should_handle(event_data):
            return EventResult.CONTINUE
        
        import time
        start_time = time.perf_counter()
        
        try:
            result = await self.handle_event_async(event_data)
            
            # Update metrics
            execution_time = time.perf_counter() - start_time
            self.metadata.execution_count += 1
            self.metadata.total_execution_time += execution_time
            
            logger.debug(
                f"Async handler {self.name} processed event {event_data.event_type.value} "
                f"in {execution_time:.3f}s, result: {result.value}"
            )
            
            return result
        
        except Exception as e:
            # Update error metrics
            self.metadata.error_count += 1
            self.metadata.last_error = e
            
            logger.error(
                f"Async handler {self.name} failed to process event {event_data.event_type.value}: {e}"
            )
            
            # Disable if too many errors
            if self.metadata.error_count >= self.metadata.max_errors:
                logger.warning(
                    f"Async handler {self.name} disabled due to {self.metadata.error_count} errors"
                )
            
            return EventResult.CONTINUE
    
    def handle_event(self, event_data: EventData) -> EventResult:
        """Sync version calls async version."""
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            task = asyncio.create_task(self.handle_event_async(event_data))
            return EventResult.CONTINUE  # Let async handler complete in background
        except RuntimeError:
            # No event loop, run synchronously
            return asyncio.run(self.handle_event_async(event_data))
    
    @abstractmethod
    async def handle_event_async(self, event_data: EventData) -> EventResult:
        """
        Handle the event asynchronously.
        
        Args:
            event_data: Event data
            
        Returns:
            Event result
        """
        pass


class CallableEventHandler(BaseEventHandler):
    """Event handler that wraps a callable function."""
    
    def __init__(
        self,
        callback: Callable[[EventData], Any],
        name: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
        event_filter: Optional[EventFilter] = None,
        max_errors: int = 10
    ) -> None:
        super().__init__(
            name=name or callback.__name__,
            priority=priority,
            event_filter=event_filter,
            max_errors=max_errors
        )
        self.callback = callback
    
    def handle_event(self, event_data: EventData) -> EventResult:
        """Handle event by calling the wrapped function."""
        result = self.callback(event_data)
        
        # Convert result to EventResult if needed
        if isinstance(result, EventResult):
            return result
        elif result is False:
            return EventResult.STOP
        else:
            return EventResult.CONTINUE


class AsyncCallableEventHandler(AsyncEventHandler):
    """Async event handler that wraps a callable function."""
    
    def __init__(
        self,
        callback: Callable[[EventData], Any],
        name: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
        event_filter: Optional[EventFilter] = None,
        max_errors: int = 10
    ) -> None:
        super().__init__(
            name=name or callback.__name__,
            priority=priority,
            event_filter=event_filter,
            max_errors=max_errors
        )
        self.callback = callback
    
    async def handle_event_async(self, event_data: EventData) -> EventResult:
        """Handle event by calling the wrapped async function."""
        if asyncio.iscoroutinefunction(self.callback):
            result = await self.callback(event_data)
        else:
            # Run sync callback in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.callback, event_data)
        
        # Convert result to EventResult if needed
        if isinstance(result, EventResult):
            return result
        elif result is False:
            return EventResult.STOP
        else:
            return EventResult.CONTINUE


class CompositeEventHandler(BaseEventHandler):
    """Event handler that combines multiple handlers."""
    
    def __init__(
        self,
        handlers: List[BaseEventHandler],
        name: Optional[str] = None,
        priority: EventPriority = EventPriority.NORMAL,
        event_filter: Optional[EventFilter] = None,
        stop_on_first_result: bool = False
    ) -> None:
        super().__init__(
            name=name or "CompositeHandler",
            priority=priority,
            event_filter=event_filter
        )
        self.handlers = sorted(handlers, key=lambda h: h.priority.value, reverse=True)
        self.stop_on_first_result = stop_on_first_result
    
    def handle_event(self, event_data: EventData) -> EventResult:
        """Handle event by delegating to child handlers."""
        for handler in self.handlers:
            if not handler.should_handle(event_data):
                continue
            
            result = handler.handle_event_safely(event_data)
            
            if result == EventResult.CANCEL and event_data.cancellable:
                event_data.cancel()
                return EventResult.CANCEL
            elif result == EventResult.STOP or self.stop_on_first_result:
                return result
        
        return EventResult.CONTINUE
    
    def add_handler(self, handler: BaseEventHandler) -> None:
        """Add a handler to the composite."""
        self.handlers.append(handler)
        self.handlers.sort(key=lambda h: h.priority.value, reverse=True)
    
    def remove_handler(self, handler: BaseEventHandler) -> None:
        """Remove a handler from the composite."""
        if handler in self.handlers:
            self.handlers.remove(handler)


class ConditionalEventHandler(BaseEventHandler):
    """Event handler that only executes under certain conditions."""
    
    def __init__(
        self,
        handler: BaseEventHandler,
        condition: Callable[[EventData], bool],
        name: Optional[str] = None
    ) -> None:
        super().__init__(
            name=name or f"Conditional_{handler.name}",
            priority=handler.priority,
            event_filter=handler.event_filter
        )
        self.handler = handler
        self.condition = condition
    
    def should_handle(self, event_data: EventData) -> bool:
        """Check if handler should handle event including custom condition."""
        return (
            super().should_handle(event_data) and
            self.handler.should_handle(event_data) and
            self.condition(event_data)
        )
    
    def handle_event(self, event_data: EventData) -> EventResult:
        """Handle event by delegating to wrapped handler."""
        return self.handler.handle_event_safely(event_data)


class ThrottledEventHandler(BaseEventHandler):
    """Event handler that throttles execution to avoid overwhelming the system."""
    
    def __init__(
        self,
        handler: BaseEventHandler,
        min_interval_seconds: float = 0.1,
        name: Optional[str] = None
    ) -> None:
        super().__init__(
            name=name or f"Throttled_{handler.name}",
            priority=handler.priority,
            event_filter=handler.event_filter
        )
        self.handler = handler
        self.min_interval_seconds = min_interval_seconds
        self.last_execution_time = 0.0
    
    def should_handle(self, event_data: EventData) -> bool:
        """Check if enough time has passed since last execution."""
        import time
        current_time = time.perf_counter()
        
        if current_time - self.last_execution_time < self.min_interval_seconds:
            return False
        
        return super().should_handle(event_data) and self.handler.should_handle(event_data)
    
    def handle_event(self, event_data: EventData) -> EventResult:
        """Handle event and update last execution time."""
        import time
        self.last_execution_time = time.perf_counter()
        return self.handler.handle_event_safely(event_data)