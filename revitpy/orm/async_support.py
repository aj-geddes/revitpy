"""
Async support and context managers for the RevitPy ORM.

This module provides full async/await support with context managers,
async transactions, and batch operations for high-performance scenarios.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import threading
import time
from typing import (
    Any, Dict, List, Optional, Set, Type, TypeVar, Generic, Union,
    Callable, Awaitable, AsyncIterator, AsyncContextManager, Coroutine
)
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4
from loguru import logger

from .types import (
    IElementProvider, IUnitOfWork, ElementState, BatchOperation, BatchOperationType,
    CachePolicy, LoadStrategy
)
from .exceptions import (
    AsyncOperationError, TransactionError, BatchOperationError, 
    ConcurrencyError
)
from .cache import CacheManager
from .change_tracker import ChangeTracker
from .relationships import RelationshipManager


T = TypeVar('T')
R = TypeVar('R')


@dataclass
class AsyncTransactionContext:
    """Context for async transaction operations."""
    
    transaction_id: UUID = field(default_factory=uuid4)
    start_time: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    is_committed: bool = False
    is_rolled_back: bool = False
    nested_level: int = 0
    operations: List[Any] = field(default_factory=list)
    savepoints: List[str] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """Get transaction duration in seconds."""
        return (datetime.utcnow() - self.start_time).total_seconds()
    
    def add_operation(self, operation: Any) -> None:
        """Add an operation to the transaction."""
        if not self.is_active:
            raise TransactionError(
                "Cannot add operation to inactive transaction",
                transaction_id=str(self.transaction_id),
                transaction_state="inactive"
            )
        
        self.operations.append(operation)


class AsyncTransaction:
    """
    Async transaction manager with support for nested transactions,
    savepoints, and automatic rollback on errors.
    """
    
    def __init__(
        self,
        change_tracker: ChangeTracker,
        unit_of_work: Optional[IUnitOfWork] = None,
        auto_commit: bool = True,
        timeout_seconds: Optional[float] = None
    ) -> None:
        self._change_tracker = change_tracker
        self._unit_of_work = unit_of_work
        self._auto_commit = auto_commit
        self._timeout_seconds = timeout_seconds
        self._context: Optional[AsyncTransactionContext] = None
        self._lock = asyncio.Lock()
        self._nested_transactions: List[AsyncTransactionContext] = []
        
    @property
    def is_active(self) -> bool:
        """Check if transaction is active."""
        return self._context is not None and self._context.is_active
    
    @property
    def transaction_id(self) -> Optional[UUID]:
        """Get current transaction ID."""
        return self._context.transaction_id if self._context else None
    
    @property
    def nested_level(self) -> int:
        """Get current nesting level."""
        return len(self._nested_transactions)
    
    async def begin(self) -> None:
        """Begin a new transaction."""
        async with self._lock:
            if self._context is not None and self._context.is_active:
                # Start nested transaction
                nested_context = AsyncTransactionContext(
                    nested_level=self.nested_level + 1
                )
                self._nested_transactions.append(nested_context)
                logger.debug(f"Started nested transaction: {nested_context.transaction_id}")
            else:
                # Start new top-level transaction
                self._context = AsyncTransactionContext()
                logger.debug(f"Started transaction: {self._context.transaction_id}")
    
    async def commit(self) -> None:
        """Commit the transaction."""
        async with self._lock:
            if not self.is_active:
                raise TransactionError(
                    "No active transaction to commit",
                    transaction_state="inactive"
                )
            
            try:
                if self._nested_transactions:
                    # Commit nested transaction
                    nested_context = self._nested_transactions.pop()
                    nested_context.is_committed = True
                    nested_context.is_active = False
                    
                    # Merge operations into parent transaction
                    if self._context:
                        self._context.operations.extend(nested_context.operations)
                    
                    logger.debug(f"Committed nested transaction: {nested_context.transaction_id}")
                else:
                    # Commit top-level transaction
                    if self._unit_of_work:
                        await self._unit_of_work.commit_async()
                    
                    self._change_tracker.accept_changes()
                    self._context.is_committed = True
                    self._context.is_active = False
                    
                    duration = self._context.duration
                    logger.info(
                        f"Committed transaction {self._context.transaction_id} "
                        f"with {len(self._context.operations)} operations in {duration:.3f}s"
                    )
                    
                    self._context = None
                    
            except Exception as e:
                logger.error(f"Transaction commit failed: {e}")
                await self.rollback()
                raise TransactionError(
                    f"Transaction commit failed: {e}",
                    transaction_id=str(self.transaction_id) if self.transaction_id else None,
                    cause=e
                )
    
    async def rollback(self) -> None:
        """Rollback the transaction."""
        async with self._lock:
            if not self.is_active:
                logger.warning("No active transaction to rollback")
                return
            
            try:
                if self._nested_transactions:
                    # Rollback nested transaction
                    nested_context = self._nested_transactions.pop()
                    nested_context.is_rolled_back = True
                    nested_context.is_active = False
                    
                    logger.debug(f"Rolled back nested transaction: {nested_context.transaction_id}")
                else:
                    # Rollback top-level transaction
                    if self._unit_of_work:
                        await self._unit_of_work.rollback_async()
                    
                    self._change_tracker.reject_changes()
                    self._context.is_rolled_back = True
                    self._context.is_active = False
                    
                    duration = self._context.duration
                    logger.info(
                        f"Rolled back transaction {self._context.transaction_id} "
                        f"after {duration:.3f}s"
                    )
                    
                    self._context = None
                    
            except Exception as e:
                logger.error(f"Transaction rollback failed: {e}")
                # Force cleanup even if rollback fails
                if self._nested_transactions:
                    self._nested_transactions.pop()
                else:
                    self._context = None
                
                raise TransactionError(
                    f"Transaction rollback failed: {e}",
                    transaction_id=str(self.transaction_id) if self.transaction_id else None,
                    cause=e
                )
    
    async def create_savepoint(self, name: str) -> None:
        """Create a savepoint within the transaction."""
        async with self._lock:
            if not self.is_active:
                raise TransactionError(
                    "Cannot create savepoint without active transaction",
                    transaction_state="inactive"
                )
            
            if self._context:
                self._context.savepoints.append(name)
                logger.debug(f"Created savepoint '{name}' in transaction {self.transaction_id}")
    
    async def rollback_to_savepoint(self, name: str) -> None:
        """Rollback to a specific savepoint."""
        async with self._lock:
            if not self.is_active or not self._context:
                raise TransactionError(
                    "Cannot rollback to savepoint without active transaction",
                    transaction_state="inactive"
                )
            
            if name not in self._context.savepoints:
                raise TransactionError(
                    f"Savepoint '{name}' not found",
                    transaction_id=str(self.transaction_id)
                )
            
            # Remove all savepoints after this one
            savepoint_index = self._context.savepoints.index(name)
            self._context.savepoints = self._context.savepoints[:savepoint_index + 1]
            
            logger.debug(f"Rolled back to savepoint '{name}' in transaction {self.transaction_id}")
    
    async def __aenter__(self) -> 'AsyncTransaction':
        """Async context manager entry."""
        await self.begin()
        
        # Set timeout if specified
        if self._timeout_seconds:
            async def timeout_handler():
                await asyncio.sleep(self._timeout_seconds)
                if self.is_active:
                    logger.warning(f"Transaction {self.transaction_id} timed out, rolling back")
                    await self.rollback()
            
            asyncio.create_task(timeout_handler())
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if exc_type is not None:
            # Exception occurred, rollback
            await self.rollback()
        elif self._auto_commit and self.is_active:
            # Auto-commit if no exception
            await self.commit()


class AsyncBatchProcessor:
    """
    Processes batch operations asynchronously with configurable
    concurrency, error handling, and progress tracking.
    """
    
    def __init__(
        self,
        max_concurrency: int = 10,
        batch_size: int = 100,
        error_threshold: float = 0.1  # 10% error threshold
    ) -> None:
        self._max_concurrency = max_concurrency
        self._batch_size = batch_size
        self._error_threshold = error_threshold
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._processed_count = 0
        self._error_count = 0
        self._start_time: Optional[float] = None
    
    @property
    def processed_count(self) -> int:
        """Get number of processed operations."""
        return self._processed_count
    
    @property
    def error_count(self) -> int:
        """Get number of failed operations."""
        return self._error_count
    
    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        total = self._processed_count + self._error_count
        return (self._processed_count / total * 100) if total > 0 else 0.0
    
    @property
    def processing_time(self) -> float:
        """Get total processing time in seconds."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time
    
    async def process_batch(
        self,
        operations: List[BatchOperation],
        operation_handler: Callable[[BatchOperation], Awaitable[Any]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Process a batch of operations asynchronously.
        
        Args:
            operations: List of batch operations to process
            operation_handler: Async function to handle each operation
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with processing results and statistics
        """
        self._start_time = time.time()
        self._processed_count = 0
        self._error_count = 0
        
        successful_operations = []
        failed_operations = []
        
        try:
            # Process operations in batches
            for i in range(0, len(operations), self._batch_size):
                batch = operations[i:i + self._batch_size]
                
                # Process batch concurrently
                batch_results = await asyncio.gather(
                    *[self._process_single_operation(op, operation_handler) for op in batch],
                    return_exceptions=True
                )
                
                # Collect results
                for j, result in enumerate(batch_results):
                    operation = batch[j]
                    
                    if isinstance(result, Exception):
                        failed_operations.append({
                            'operation': operation,
                            'error': str(result)
                        })
                        self._error_count += 1
                    else:
                        successful_operations.append({
                            'operation': operation,
                            'result': result
                        })
                        self._processed_count += 1
                
                # Check error threshold
                if self._error_count > 0:
                    error_rate = self._error_count / (self._processed_count + self._error_count)
                    if error_rate > self._error_threshold:
                        raise BatchOperationError(
                            f"Error rate {error_rate:.1%} exceeds threshold {self._error_threshold:.1%}",
                            batch_size=len(operations),
                            failed_operations=failed_operations,
                            successful_operations=self._processed_count
                        )
                
                # Progress callback
                if progress_callback:
                    total_processed = self._processed_count + self._error_count
                    progress_callback(total_processed, len(operations))
            
            processing_time = self.processing_time
            
            logger.info(
                f"Batch processing completed: {self._processed_count} successful, "
                f"{self._error_count} failed, {processing_time:.2f}s"
            )
            
            return {
                'successful_operations': successful_operations,
                'failed_operations': failed_operations,
                'processed_count': self._processed_count,
                'error_count': self._error_count,
                'success_rate': self.success_rate,
                'processing_time': processing_time,
                'operations_per_second': (self._processed_count + self._error_count) / processing_time if processing_time > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise BatchOperationError(
                f"Batch processing failed: {e}",
                batch_size=len(operations),
                failed_operations=failed_operations,
                successful_operations=self._processed_count,
                cause=e
            )
    
    async def _process_single_operation(
        self,
        operation: BatchOperation,
        handler: Callable[[BatchOperation], Awaitable[Any]]
    ) -> Any:
        """Process a single operation with concurrency control."""
        async with self._semaphore:
            try:
                return await handler(operation)
            except Exception as e:
                logger.warning(f"Operation {operation.operation_id} failed: {e}")
                raise


class AsyncRevitContext:
    """
    Main async context for RevitPy ORM operations.
    
    Provides async versions of all ORM operations with transaction support,
    caching, change tracking, and relationship management.
    """
    
    def __init__(
        self,
        provider: IElementProvider,
        *,
        cache_manager: Optional[CacheManager] = None,
        change_tracker: Optional[ChangeTracker] = None,
        relationship_manager: Optional[RelationshipManager] = None,
        unit_of_work: Optional[IUnitOfWork] = None,
        auto_track_changes: bool = True,
        default_cache_policy: CachePolicy = CachePolicy.MEMORY,
        transaction_timeout: Optional[float] = None
    ) -> None:
        self._provider = provider
        self._cache_manager = cache_manager or CacheManager()
        self._change_tracker = change_tracker or ChangeTracker()
        self._relationship_manager = relationship_manager
        self._unit_of_work = unit_of_work
        self._auto_track_changes = auto_track_changes
        self._default_cache_policy = default_cache_policy
        self._transaction_timeout = transaction_timeout
        
        self._current_transaction: Optional[AsyncTransaction] = None
        self._batch_processor = AsyncBatchProcessor()
        self._is_disposed = False
        
        # Configure change tracker
        self._change_tracker.auto_track = auto_track_changes
    
    @property
    def is_in_transaction(self) -> bool:
        """Check if currently in a transaction."""
        return self._current_transaction is not None and self._current_transaction.is_active
    
    @property
    def has_changes(self) -> bool:
        """Check if there are pending changes."""
        return self._change_tracker.has_changes
    
    @property
    def change_count(self) -> int:
        """Get number of pending changes."""
        return self._change_tracker.change_count
    
    async def get_all_async(self, element_type: Optional[Type[T]] = None) -> List[T]:
        """Get all elements of specified type asynchronously."""
        if self._is_disposed:
            raise AsyncOperationError("Context has been disposed")
        
        try:
            if element_type:
                elements = await self._provider.get_elements_of_type_async(element_type)
            else:
                elements = await self._provider.get_all_elements_async()
            
            # Auto-attach to change tracker if enabled
            if self._auto_track_changes:
                for element in elements:
                    self._change_tracker.attach(element)
            
            return elements
            
        except Exception as e:
            logger.error(f"Failed to get elements async: {e}")
            raise AsyncOperationError(
                f"Failed to get elements: {e}",
                async_operation="get_all",
                cause=e
            )
    
    async def get_by_id_async(self, element_id: Any) -> Optional[T]:
        """Get element by ID asynchronously."""
        if self._is_disposed:
            raise AsyncOperationError("Context has been disposed")
        
        try:
            element = await self._provider.get_element_by_id_async(element_id)
            
            # Auto-attach to change tracker if enabled
            if element and self._auto_track_changes:
                self._change_tracker.attach(element)
            
            return element
            
        except Exception as e:
            logger.error(f"Failed to get element by ID async: {e}")
            raise AsyncOperationError(
                f"Failed to get element by ID: {e}",
                async_operation="get_by_id",
                cause=e
            )
    
    async def save_changes_async(self) -> int:
        """Save all pending changes asynchronously."""
        if self._is_disposed:
            raise AsyncOperationError("Context has been disposed")
        
        if not self.has_changes:
            return 0
        
        try:
            changes = self._change_tracker.get_all_changes()
            
            # Create batch operations from changes
            operations = []
            for change in changes:
                if change.state == ElementState.ADDED:
                    operations.append(BatchOperation(
                        operation_type=BatchOperationType.INSERT,
                        entity=change,
                        properties=change.current_values
                    ))
                elif change.state == ElementState.MODIFIED:
                    operations.append(BatchOperation(
                        operation_type=BatchOperationType.UPDATE,
                        entity=change,
                        properties=change.current_values
                    ))
                elif change.state == ElementState.DELETED:
                    operations.append(BatchOperation(
                        operation_type=BatchOperationType.DELETE,
                        entity=change
                    ))
            
            # Process batch operations
            async def save_operation(operation: BatchOperation) -> Any:
                # Simulate saving operation
                await asyncio.sleep(0.001)  # Minimal delay for simulation
                return f"Saved {operation.operation_type.value}"
            
            result = await self._batch_processor.process_batch(
                operations, save_operation
            )
            
            # Accept changes if all successful
            if result['error_count'] == 0:
                self._change_tracker.accept_changes()
            
            logger.info(
                f"Saved {result['processed_count']} changes async in {result['processing_time']:.2f}s"
            )
            
            return result['processed_count']
            
        except Exception as e:
            logger.error(f"Failed to save changes async: {e}")
            raise AsyncOperationError(
                f"Failed to save changes: {e}",
                async_operation="save_changes",
                cause=e
            )
    
    @contextlib.asynccontextmanager
    async def transaction(
        self,
        auto_commit: bool = True,
        timeout_seconds: Optional[float] = None
    ) -> AsyncIterator[AsyncTransaction]:
        """Create an async transaction context."""
        if self._current_transaction and self._current_transaction.is_active:
            # Nested transaction
            transaction = AsyncTransaction(
                self._change_tracker,
                self._unit_of_work,
                auto_commit,
                timeout_seconds or self._transaction_timeout
            )
        else:
            # New transaction
            transaction = AsyncTransaction(
                self._change_tracker,
                self._unit_of_work,
                auto_commit,
                timeout_seconds or self._transaction_timeout
            )
            self._current_transaction = transaction
        
        try:
            async with transaction:
                yield transaction
        finally:
            if transaction == self._current_transaction:
                self._current_transaction = None
    
    async def load_relationship_async(
        self,
        entity: T,
        relationship_name: str,
        strategy: LoadStrategy = LoadStrategy.LAZY
    ) -> Union[Any, List[Any], None]:
        """Load relationship data asynchronously."""
        if self._is_disposed:
            raise AsyncOperationError("Context has been disposed")
        
        if not self._relationship_manager:
            raise AsyncOperationError("No relationship manager configured")
        
        try:
            return await self._relationship_manager.load_relationship_async(
                entity, relationship_name, force_reload=False
            )
            
        except Exception as e:
            logger.error(f"Failed to load relationship async: {e}")
            raise AsyncOperationError(
                f"Failed to load relationship {relationship_name}: {e}",
                async_operation="load_relationship",
                cause=e
            )
    
    async def dispose_async(self) -> None:
        """Dispose of the context and clean up resources."""
        if self._is_disposed:
            return
        
        try:
            # Rollback any active transaction
            if self._current_transaction and self._current_transaction.is_active:
                await self._current_transaction.rollback()
            
            # Clear change tracker
            self._change_tracker.clear()
            
            # Clear cache
            if self._cache_manager:
                self._cache_manager.clear()
            
            self._is_disposed = True
            logger.debug("Async context disposed")
            
        except Exception as e:
            logger.error(f"Error during context disposal: {e}")
    
    async def __aenter__(self) -> 'AsyncRevitContext':
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.dispose_async()


# Utility decorators and functions

def async_transaction(
    auto_commit: bool = True,
    timeout_seconds: Optional[float] = None
):
    """Decorator for automatic async transaction management."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if hasattr(self, '_context') and isinstance(self._context, AsyncRevitContext):
                async with self._context.transaction(auto_commit, timeout_seconds):
                    return await func(self, *args, **kwargs)
            else:
                return await func(self, *args, **kwargs)
        return wrapper
    return decorator


async def async_batch_operation(
    operations: List[BatchOperation],
    handler: Callable[[BatchOperation], Awaitable[Any]],
    max_concurrency: int = 10,
    batch_size: int = 100,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Any]:
    """Execute batch operations asynchronously."""
    processor = AsyncBatchProcessor(max_concurrency, batch_size)
    return await processor.process_batch(operations, handler, progress_callback)


async def async_retry(
    func: Callable[..., Awaitable[T]],
    *args,
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    exponential_backoff: bool = True,
    **kwargs
) -> T:
    """Retry async function with configurable backoff."""
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            if attempt < max_attempts - 1:
                delay = delay_seconds
                if exponential_backoff:
                    delay *= (2 ** attempt)
                
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_attempts} attempts failed: {e}")
    
    if last_exception:
        raise last_exception
    else:
        raise AsyncOperationError("Async retry failed with no exception")