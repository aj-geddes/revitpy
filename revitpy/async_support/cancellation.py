"""
Cancellation token system for async operations.
"""

import asyncio
from typing import Optional, Callable, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger


@dataclass
class CancellationToken:
    """Token that can be used to signal cancellation of async operations."""
    
    _is_cancelled: bool = field(default=False, init=False)
    _callbacks: List[Callable[[], None]] = field(default_factory=list, init=False)
    _cancelled_at: Optional[datetime] = field(default=None, init=False)
    _reason: Optional[str] = field(default=None, init=False)
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._is_cancelled
    
    @property
    def cancelled_at(self) -> Optional[datetime]:
        """Get the time when cancellation was requested."""
        return self._cancelled_at
    
    @property
    def reason(self) -> Optional[str]:
        """Get the reason for cancellation."""
        return self._reason
    
    def throw_if_cancellation_requested(self) -> None:
        """Throw OperationCancelledError if cancellation has been requested."""
        if self._is_cancelled:
            raise OperationCancelledError(self._reason or "Operation was cancelled")
    
    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when cancellation is requested."""
        if self._is_cancelled:
            # If already cancelled, call immediately
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in cancellation callback: {e}")
        else:
            self._callbacks.append(callback)
    
    def _cancel(self, reason: Optional[str] = None) -> None:
        """Internal method to cancel the token."""
        if self._is_cancelled:
            return
        
        self._is_cancelled = True
        self._cancelled_at = datetime.now()
        self._reason = reason
        
        # Call all registered callbacks
        for callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in cancellation callback: {e}")
        
        # Clear callbacks after calling them
        self._callbacks.clear()


class CancellationTokenSource:
    """Source for creating and controlling cancellation tokens."""
    
    def __init__(self, timeout: Optional[timedelta] = None) -> None:
        self._token = CancellationToken()
        self._timeout = timeout
        self._timeout_task: Optional[asyncio.Task] = None
        
        if timeout:
            self._setup_timeout()
    
    @property
    def token(self) -> CancellationToken:
        """Get the cancellation token."""
        return self._token
    
    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._token.is_cancelled
    
    def cancel(self, reason: Optional[str] = None) -> None:
        """Request cancellation."""
        if self._timeout_task:
            self._timeout_task.cancel()
        
        self._token._cancel(reason)
        logger.debug(f"Cancellation requested: {reason or 'No reason provided'}")
    
    def cancel_after(self, timeout: timedelta, reason: Optional[str] = None) -> None:
        """Request cancellation after a timeout."""
        if self._timeout_task:
            self._timeout_task.cancel()
        
        self._timeout = timeout
        self._setup_timeout(reason)
    
    def _setup_timeout(self, reason: Optional[str] = None) -> None:
        """Setup automatic cancellation after timeout."""
        async def timeout_cancellation():
            await asyncio.sleep(self._timeout.total_seconds())
            if not self._token.is_cancelled:
                timeout_reason = reason or f"Operation timed out after {self._timeout}"
                self.cancel(timeout_reason)
        
        self._timeout_task = asyncio.create_task(timeout_cancellation())
    
    def dispose(self) -> None:
        """Dispose of the cancellation token source."""
        if self._timeout_task:
            self._timeout_task.cancel()
        
        if not self._token.is_cancelled:
            self.cancel("Token source disposed")


class OperationCancelledError(Exception):
    """Exception raised when an operation is cancelled."""
    
    def __init__(self, message: str = "Operation was cancelled") -> None:
        super().__init__(message)


def combine_tokens(*tokens: CancellationToken) -> CancellationToken:
    """Combine multiple cancellation tokens into one."""
    combined_token = CancellationToken()
    
    def check_cancellation():
        for token in tokens:
            if token.is_cancelled:
                combined_token._cancel(f"Combined token cancelled due to: {token.reason}")
                break
    
    # Register callback on all tokens
    for token in tokens:
        token.register_callback(check_cancellation)
    
    # Check immediately in case any are already cancelled
    check_cancellation()
    
    return combined_token


async def with_cancellation(
    coro: Any, 
    cancellation_token: Optional[CancellationToken] = None,
    timeout: Optional[timedelta] = None
) -> Any:
    """
    Execute a coroutine with cancellation support.
    
    Args:
        coro: The coroutine to execute
        cancellation_token: Optional cancellation token
        timeout: Optional timeout duration
        
    Returns:
        The result of the coroutine
        
    Raises:
        OperationCancelledError: If operation is cancelled
        asyncio.TimeoutError: If operation times out
    """
    if not cancellation_token and not timeout:
        return await coro
    
    # Create cancellation token source if needed
    token_source = None
    if not cancellation_token:
        token_source = CancellationTokenSource(timeout)
        cancellation_token = token_source.token
    elif timeout:
        # Create combined token with timeout
        timeout_source = CancellationTokenSource(timeout)
        cancellation_token = combine_tokens(cancellation_token, timeout_source.token)
    
    try:
        # Create monitoring task for cancellation
        async def monitor_cancellation():
            while not cancellation_token.is_cancelled:
                await asyncio.sleep(0.1)  # Check every 100ms
            
            # If we get here, cancellation was requested
            raise OperationCancelledError(cancellation_token.reason)
        
        monitor_task = asyncio.create_task(monitor_cancellation())
        coro_task = asyncio.create_task(coro)
        
        # Wait for either the coroutine or cancellation
        done, pending = await asyncio.wait(
            [coro_task, monitor_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Get result from completed task
        completed_task = done.pop()
        if completed_task == coro_task:
            return completed_task.result()
        else:
            # Monitor task completed first (cancellation requested)
            completed_task.result()  # This will raise OperationCancelledError
    
    finally:
        if token_source:
            token_source.dispose()


class CancellationTokenContext:
    """Context manager for cancellation tokens."""
    
    def __init__(self, timeout: Optional[timedelta] = None, reason: Optional[str] = None) -> None:
        self._timeout = timeout
        self._reason = reason
        self._token_source: Optional[CancellationTokenSource] = None
    
    @property
    def token(self) -> Optional[CancellationToken]:
        """Get the cancellation token."""
        return self._token_source.token if self._token_source else None
    
    def cancel(self, reason: Optional[str] = None) -> None:
        """Request cancellation."""
        if self._token_source:
            self._token_source.cancel(reason or self._reason)
    
    def __enter__(self) -> 'CancellationTokenContext':
        self._token_source = CancellationTokenSource(self._timeout)
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._token_source:
            self._token_source.dispose()
    
    async def __aenter__(self) -> 'CancellationTokenContext':
        self._token_source = CancellationTokenSource(self._timeout)
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._token_source:
            self._token_source.dispose()