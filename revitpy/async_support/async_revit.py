"""
Async wrapper for RevitAPI providing async/await patterns.
"""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeVar

from loguru import logger

from ..api.element import Element, ElementSet
from ..api.query import QueryBuilder
from ..api.wrapper import IRevitApplication, RevitAPI
from .cancellation import CancellationToken
from .context_managers import (
    async_element_scope,
    async_progress_scope,
    async_transaction,
)
from .progress import ProgressReporter, create_progress_reporter
from .task_queue import Task, TaskPriority, TaskQueue

T = TypeVar("T")


class AsyncRevit:
    """
    Async wrapper for RevitAPI that provides async/await patterns
    for long-running operations and non-blocking execution.
    """

    def __init__(self, revit_application: IRevitApplication | None = None) -> None:
        self._revit_api = RevitAPI(revit_application)
        self._task_queue: TaskQueue | None = None
        self._background_tasks: dict[str, asyncio.Task] = {}
        self._is_initialized = False

    @property
    def api(self) -> RevitAPI:
        """Get the underlying RevitAPI instance."""
        return self._revit_api

    @property
    def is_connected(self) -> bool:
        """Check if connected to Revit."""
        return self._revit_api.is_connected

    @property
    def task_queue(self) -> TaskQueue:
        """Get the task queue."""
        if not self._task_queue:
            self._task_queue = TaskQueue(name="AsyncRevitTaskQueue")
        return self._task_queue

    async def initialize(
        self,
        max_concurrent_tasks: int = 4,
        revit_application: IRevitApplication | None = None,
    ) -> None:
        """
        Initialize the async Revit interface.

        Args:
            max_concurrent_tasks: Maximum concurrent tasks
            revit_application: Optional Revit application instance
        """
        if self._is_initialized:
            return

        # Connect to Revit
        if revit_application or not self.is_connected:
            await asyncio.get_event_loop().run_in_executor(
                None, self._revit_api.connect, revit_application
            )

        # Initialize task queue
        if not self._task_queue:
            self._task_queue = TaskQueue(
                max_concurrent_tasks=max_concurrent_tasks, name="AsyncRevitTaskQueue"
            )

        await self._task_queue.start()

        self._is_initialized = True
        logger.info("AsyncRevit initialized successfully")

    async def shutdown(self, timeout: float | None = None) -> None:
        """
        Shutdown the async Revit interface.

        Args:
            timeout: Optional timeout for shutdown
        """
        if not self._is_initialized:
            return

        # Cancel background tasks
        for task_id, task in self._background_tasks.items():
            task.cancel()
            logger.debug(f"Cancelled background task: {task_id}")

        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(
                *self._background_tasks.values(), return_exceptions=True
            )

        self._background_tasks.clear()

        # Stop task queue
        if self._task_queue:
            await self._task_queue.stop(timeout)

        # Disconnect from Revit
        await asyncio.get_event_loop().run_in_executor(None, self._revit_api.disconnect)

        self._is_initialized = False
        logger.info("AsyncRevit shutdown completed")

    # Async Document Operations

    async def open_document_async(self, file_path: str) -> Any:
        """
        Open a document asynchronously.

        Args:
            file_path: Path to the Revit file

        Returns:
            Document provider
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self._revit_api.open_document, file_path
        )

    async def create_document_async(self, template_path: str | None = None) -> Any:
        """
        Create a new document asynchronously.

        Args:
            template_path: Optional template path

        Returns:
            Document provider
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self._revit_api.create_document, template_path
        )

    async def save_document_async(self, provider: Any | None = None) -> bool:
        """
        Save document asynchronously.

        Args:
            provider: Optional document provider

        Returns:
            Success status
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self._revit_api.save_document, provider
        )

    async def close_document_async(
        self, provider: Any | None = None, save_changes: bool = True
    ) -> bool:
        """
        Close document asynchronously.

        Args:
            provider: Optional document provider
            save_changes: Whether to save changes

        Returns:
            Success status
        """
        return await asyncio.get_event_loop().run_in_executor(
            None, self._revit_api.close_document, provider, save_changes
        )

    # Async Element Operations

    async def get_elements_async(
        self,
        progress_reporter: ProgressReporter | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> ElementSet[Element]:
        """
        Get all elements asynchronously with progress reporting.

        Args:
            progress_reporter: Optional progress reporter
            cancellation_token: Optional cancellation token

        Returns:
            Element set
        """

        async def get_elements():
            if progress_reporter:
                progress_reporter.start("Retrieving elements...")

            # Run in executor to avoid blocking
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._revit_api.elements.execute()
            )

            if progress_reporter:
                progress_reporter.complete(f"Retrieved {result.count} elements")

            return result

        if cancellation_token:
            from .cancellation import with_cancellation

            return await with_cancellation(get_elements(), cancellation_token)
        else:
            return await get_elements()

    async def query_elements_async(
        self,
        query_func: Callable[[QueryBuilder], QueryBuilder],
        progress_reporter: ProgressReporter | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> ElementSet[Element]:
        """
        Query elements asynchronously.

        Args:
            query_func: Function to build the query
            progress_reporter: Optional progress reporter
            cancellation_token: Optional cancellation token

        Returns:
            Element set
        """

        async def execute_query():
            if progress_reporter:
                progress_reporter.start("Executing query...")

            # Build and execute query
            query_builder = query_func(self._revit_api.elements)
            result = await asyncio.get_event_loop().run_in_executor(
                None, query_builder.execute
            )

            if progress_reporter:
                progress_reporter.complete(f"Query returned {result.count} elements")

            return result

        if cancellation_token:
            from .cancellation import with_cancellation

            return await with_cancellation(execute_query(), cancellation_token)
        else:
            return await execute_query()

    async def update_elements_async(
        self,
        elements: list[Element],
        update_func: Callable[[Element], None],
        batch_size: int = 100,
        progress_reporter: ProgressReporter | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> int:
        """
        Update multiple elements asynchronously with batching.

        Args:
            elements: Elements to update
            update_func: Function to update each element
            batch_size: Batch size for processing
            progress_reporter: Optional progress reporter
            cancellation_token: Optional cancellation token

        Returns:
            Number of elements updated
        """
        if not elements:
            return 0

        if progress_reporter:
            progress_reporter.set_total(len(elements))
            progress_reporter.start("Updating elements...")

        updated_count = 0

        try:
            # Process in batches
            for i in range(0, len(elements), batch_size):
                # Check cancellation
                if cancellation_token and cancellation_token.is_cancelled:
                    break

                batch = elements[i : i + batch_size]

                # Update batch in executor
                def update_batch():
                    for element in batch:
                        update_func(element)
                    return len(batch)

                batch_count = await asyncio.get_event_loop().run_in_executor(
                    None, update_batch
                )

                updated_count += batch_count

                if progress_reporter:
                    await progress_reporter.async_increment(
                        batch_count, f"Updated {updated_count}/{len(elements)} elements"
                    )

                # Small delay between batches to avoid overwhelming Revit
                await asyncio.sleep(0.01)

            if progress_reporter:
                if cancellation_token and cancellation_token.is_cancelled:
                    progress_reporter.cancel(
                        f"Update cancelled, processed {updated_count} elements"
                    )
                else:
                    progress_reporter.complete(f"Updated {updated_count} elements")

            return updated_count

        except Exception as e:
            if progress_reporter:
                progress_reporter.fail(f"Update failed: {e}")
            raise

    # Async Transaction Operations

    def async_transaction(
        self, name: str | None = None, timeout: timedelta | None = None, **kwargs
    ):
        """
        Create an async transaction context manager.

        Args:
            name: Transaction name
            timeout: Optional timeout
            **kwargs: Additional transaction options

        Returns:
            Async transaction context manager
        """
        if not self._revit_api.active_document:
            raise RuntimeError("No active document")

        return async_transaction(
            self._revit_api.active_document, name=name, timeout=timeout, **kwargs
        )

    async def execute_in_transaction_async(
        self,
        operation: Callable[[], T],
        name: str | None = None,
        timeout: timedelta | None = None,
        **kwargs,
    ) -> T:
        """
        Execute an operation in a transaction asynchronously.

        Args:
            operation: Operation to execute
            name: Transaction name
            timeout: Optional timeout
            **kwargs: Additional transaction options

        Returns:
            Operation result
        """
        async with self.async_transaction(name, timeout, **kwargs):
            if asyncio.iscoroutinefunction(operation):
                return await operation()
            else:
                return await asyncio.get_event_loop().run_in_executor(None, operation)

    # Background Task Operations

    async def run_background_task(
        self,
        operation: Callable[..., T],
        *args,
        name: str | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: timedelta | None = None,
        progress: bool = False,
        **kwargs,
    ) -> str:
        """
        Run an operation as a background task.

        Args:
            operation: Operation to run
            *args: Operation arguments
            name: Task name
            priority: Task priority
            timeout: Optional timeout
            progress: Whether to enable progress reporting
            **kwargs: Operation keyword arguments

        Returns:
            Task ID
        """
        progress_reporter = None
        if progress:
            progress_reporter = create_progress_reporter()

        task = Task(
            operation,
            *args,
            name=name or operation.__name__,
            priority=priority,
            timeout=timeout,
            progress_reporter=progress_reporter,
            **kwargs,
        )

        return await self.task_queue.enqueue(task)

    async def wait_for_background_task(
        self, task_id: str, timeout: float | None = None
    ) -> Any:
        """
        Wait for a background task to complete.

        Args:
            task_id: Task ID
            timeout: Optional timeout

        Returns:
            Task result
        """
        result = await self.task_queue.wait_for_task(task_id, timeout)
        return result.get_result_or_raise()

    def start_background_task(
        self, operation: Callable[[], Any], name: str | None = None
    ) -> str:
        """
        Start a long-running background task.

        Args:
            operation: Operation to run
            name: Task name

        Returns:
            Task ID
        """
        task_name = name or f"BackgroundTask_{len(self._background_tasks)}"
        task_id = f"bg_{task_name}_{asyncio.get_event_loop().time()}"

        async def run_background():
            try:
                if asyncio.iscoroutinefunction(operation):
                    await operation()
                else:
                    await asyncio.get_event_loop().run_in_executor(None, operation)
            except Exception as e:
                logger.error(f"Background task {task_name} failed: {e}")
            finally:
                if task_id in self._background_tasks:
                    del self._background_tasks[task_id]

        task = asyncio.create_task(run_background())
        self._background_tasks[task_id] = task

        logger.debug(f"Started background task: {task_name} ({task_id})")
        return task_id

    async def cancel_background_task(self, task_id: str) -> bool:
        """
        Cancel a background task.

        Args:
            task_id: Task ID

        Returns:
            True if task was cancelled
        """
        if task_id in self._background_tasks:
            task = self._background_tasks[task_id]
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            del self._background_tasks[task_id]
            logger.debug(f"Cancelled background task: {task_id}")
            return True

        return False

    # Context Managers

    def element_scope(self, elements: list[Element], **kwargs):
        """
        Create an async element scope context manager.

        Args:
            elements: Elements to manage
            **kwargs: Additional options

        Returns:
            Async element scope context manager
        """
        return async_element_scope(elements, **kwargs)

    def progress_scope(self, **kwargs):
        """
        Create an async progress scope context manager.

        Args:
            **kwargs: Progress options

        Returns:
            Async progress scope context manager
        """
        return async_progress_scope(**kwargs)

    # Utility Methods

    async def batch_process(
        self,
        items: list[T],
        process_func: Callable[[T], Any],
        batch_size: int = 100,
        delay_between_batches: timedelta = timedelta(milliseconds=100),
        progress_reporter: ProgressReporter | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> list[Any]:
        """
        Process items in batches asynchronously.

        Args:
            items: Items to process
            process_func: Function to process each item
            batch_size: Batch size
            delay_between_batches: Delay between batches
            progress_reporter: Optional progress reporter
            cancellation_token: Optional cancellation token

        Returns:
            List of results
        """
        if not items:
            return []

        if progress_reporter:
            progress_reporter.set_total(len(items))
            progress_reporter.start("Batch processing...")

        results = []

        try:
            for i in range(0, len(items), batch_size):
                # Check cancellation
                if cancellation_token and cancellation_token.is_cancelled:
                    break

                batch = items[i : i + batch_size]

                # Process batch
                batch_tasks = []
                for item in batch:
                    if asyncio.iscoroutinefunction(process_func):
                        batch_tasks.append(asyncio.create_task(process_func(item)))
                    else:
                        batch_tasks.append(
                            asyncio.create_task(
                                asyncio.get_event_loop().run_in_executor(
                                    None, process_func, item
                                )
                            )
                        )

                batch_results = await asyncio.gather(
                    *batch_tasks, return_exceptions=True
                )
                results.extend(batch_results)

                if progress_reporter:
                    await progress_reporter.async_increment(
                        len(batch), f"Processed {len(results)}/{len(items)} items"
                    )

                # Delay between batches
                if (
                    i + batch_size < len(items)
                    and delay_between_batches.total_seconds() > 0
                ):
                    await asyncio.sleep(delay_between_batches.total_seconds())

            if progress_reporter:
                if cancellation_token and cancellation_token.is_cancelled:
                    progress_reporter.cancel(
                        f"Processing cancelled, completed {len(results)} items"
                    )
                else:
                    progress_reporter.complete(f"Processed {len(results)} items")

            return results

        except Exception as e:
            if progress_reporter:
                progress_reporter.fail(f"Batch processing failed: {e}")
            raise

    # Context Manager Support

    async def __aenter__(self) -> "AsyncRevit":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.shutdown()
