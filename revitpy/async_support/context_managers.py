"""
Async context managers for RevitPy operations.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from loguru import logger

from ..api.element import Element
from ..api.transaction import ITransactionProvider, Transaction, TransactionOptions
from .cancellation import CancellationToken, CancellationTokenContext
from .progress import ProgressReporter, create_progress_reporter


@asynccontextmanager
async def async_transaction(
    provider: ITransactionProvider,
    name: str | None = None,
    auto_commit: bool = True,
    timeout: timedelta | None = None,
    retry_count: int = 0,
    retry_delay: timedelta = timedelta(seconds=1),
    cancellation_token: CancellationToken | None = None,
) -> AsyncIterator[Transaction]:
    """
    Async context manager for Revit transactions.

    Args:
        provider: Transaction provider
        name: Transaction name
        auto_commit: Whether to auto-commit
        timeout: Optional timeout
        retry_count: Number of retry attempts
        retry_delay: Delay between retries
        cancellation_token: Optional cancellation token

    Yields:
        Transaction instance

    Example:
        async with async_transaction(provider, "My Operation") as trans:
            # Perform Revit operations
            element.name = "New Name"
            # Transaction auto-commits on exit
    """
    options = TransactionOptions(
        name=name,
        auto_commit=auto_commit,
        timeout_seconds=timeout.total_seconds() if timeout else None,
        retry_count=retry_count,
        retry_delay=retry_delay.total_seconds(),
    )

    transaction = Transaction(provider, options)

    # Add cancellation support
    if cancellation_token:

        def cancel_transaction():
            if transaction.is_active:
                transaction.rollback()

        cancellation_token.register_callback(cancel_transaction)

    try:
        async with transaction:
            yield transaction

    except Exception as e:
        logger.error(f"Error in async transaction {name}: {e}")
        raise


@asynccontextmanager
async def async_element_scope(
    elements: list[Element], auto_save: bool = True, rollback_on_error: bool = True
) -> AsyncIterator[list[Element]]:
    """
    Async context manager for managing element changes.

    Args:
        elements: List of elements to manage
        auto_save: Whether to auto-save changes on exit
        rollback_on_error: Whether to rollback changes on error

    Yields:
        List of elements

    Example:
        async with async_element_scope([wall, door]) as managed_elements:
            for element in managed_elements:
                element.name = f"Modified_{element.name}"
            # Changes auto-saved on exit
    """
    # Track original state for rollback
    original_states = {}
    for element in elements:
        original_states[element.id] = element.changes.copy()

    try:
        yield elements

        if auto_save:
            # Save all changes
            save_tasks = []
            for element in elements:
                if element.is_dirty:
                    save_tasks.append(asyncio.create_task(_async_save_element(element)))

            if save_tasks:
                await asyncio.gather(*save_tasks)
                logger.debug(f"Saved changes to {len(save_tasks)} elements")

    except Exception as e:
        if rollback_on_error:
            # Rollback all changes
            for element in elements:
                if element.is_dirty:
                    element.discard_changes()

            logger.warning(f"Rolled back element changes due to error: {e}")

        raise


@asynccontextmanager
async def async_progress_scope(
    total: int | None = None, message: str | None = None, console_output: bool = False
) -> AsyncIterator[ProgressReporter]:
    """
    Async context manager for progress reporting.

    Args:
        total: Total progress items
        message: Initial progress message
        console_output: Whether to output to console

    Yields:
        Progress reporter

    Example:
        async with async_progress_scope(100, "Processing") as progress:
            for i in range(100):
                await do_work(i)
                await progress.async_increment()
    """
    progress = create_progress_reporter(total, console_output)

    try:
        progress.start(message)
        yield progress

        if progress.state.value not in ["completed", "failed", "cancelled"]:
            progress.complete()

    except Exception as e:
        progress.fail("Operation failed", e)
        raise


@asynccontextmanager
async def async_cancellation_scope(
    timeout: timedelta | None = None, reason: str | None = None
) -> AsyncIterator[CancellationToken]:
    """
    Async context manager for cancellation tokens.

    Args:
        timeout: Optional timeout duration
        reason: Cancellation reason

    Yields:
        Cancellation token

    Example:
        async with async_cancellation_scope(timedelta(seconds=30)) as token:
            await long_running_operation(cancellation_token=token)
    """
    async with CancellationTokenContext(timeout, reason) as context:
        yield context.token


@asynccontextmanager
async def async_batch_operations(
    batch_size: int = 100,
    delay_between_batches: timedelta = timedelta(milliseconds=100),
) -> AsyncIterator["BatchOperationManager"]:
    """
    Async context manager for batch operations.

    Args:
        batch_size: Number of operations per batch
        delay_between_batches: Delay between batches

    Yields:
        Batch operation manager

    Example:
        async with async_batch_operations(50) as batch:
            for element in elements:
                await batch.add_operation(lambda: element.update_property())
    """
    manager = BatchOperationManager(batch_size, delay_between_batches)

    try:
        yield manager
        await manager.execute_remaining()

    except Exception as e:
        logger.error(f"Error in batch operations: {e}")
        raise


@asynccontextmanager
async def async_resource_scope(*resources) -> AsyncIterator[tuple]:
    """
    Async context manager for managing multiple resources.

    Args:
        *resources: Resources that need cleanup

    Yields:
        Tuple of resources

    Example:
        async with async_resource_scope(connection, file_handle) as (conn, file):
            # Use resources
            pass
        # Resources automatically cleaned up
    """
    try:
        yield resources
    finally:
        # Cleanup resources
        cleanup_tasks = []
        for resource in resources:
            if hasattr(resource, "cleanup"):
                cleanup_tasks.append(asyncio.create_task(resource.cleanup()))
            elif hasattr(resource, "close"):
                if asyncio.iscoroutinefunction(resource.close):
                    cleanup_tasks.append(asyncio.create_task(resource.close()))
                else:
                    resource.close()
            elif hasattr(resource, "dispose"):
                if asyncio.iscoroutinefunction(resource.dispose):
                    cleanup_tasks.append(asyncio.create_task(resource.dispose()))
                else:
                    resource.dispose()

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)


class BatchOperationManager:
    """Manager for batch operations."""

    def __init__(
        self,
        batch_size: int = 100,
        delay_between_batches: timedelta = timedelta(milliseconds=100),
    ) -> None:
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches
        self._operations = []
        self._executed_count = 0

    async def add_operation(self, operation) -> None:
        """Add an operation to the batch."""
        self._operations.append(operation)

        if len(self._operations) >= self.batch_size:
            await self._execute_batch()

    async def _execute_batch(self) -> None:
        """Execute current batch of operations."""
        if not self._operations:
            return

        current_batch = self._operations[: self.batch_size]
        self._operations = self._operations[self.batch_size :]

        # Execute batch
        tasks = []
        for operation in current_batch:
            if asyncio.iscoroutinefunction(operation):
                tasks.append(asyncio.create_task(operation()))
            else:
                # Run sync operation in executor
                loop = asyncio.get_event_loop()
                tasks.append(asyncio.create_task(loop.run_in_executor(None, operation)))

        await asyncio.gather(*tasks, return_exceptions=True)

        self._executed_count += len(current_batch)

        logger.debug(f"Executed batch of {len(current_batch)} operations")

        # Delay before next batch
        if self._operations and self.delay_between_batches.total_seconds() > 0:
            await asyncio.sleep(self.delay_between_batches.total_seconds())

    async def execute_remaining(self) -> None:
        """Execute any remaining operations."""
        while self._operations:
            await self._execute_batch()

        logger.debug(
            f"Completed all batch operations, total executed: {self._executed_count}"
        )


async def _async_save_element(element: Element) -> None:
    """Helper function to save element asynchronously."""
    # Run save operation in executor to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, element.save_changes)
