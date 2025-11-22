"""
Async task queue system for background processing.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import uuid4

from loguru import logger

from .cancellation import CancellationToken, OperationCancelledError
from .progress import ProgressReport, ProgressReporter

T = TypeVar("T")


class TaskStatus(Enum):
    """Task status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority enumeration."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TaskResult(Generic[T]):
    """Result of task execution."""

    task_id: str
    status: TaskStatus
    result: T | None = None
    error: Exception | None = None
    execution_time: timedelta | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_successful(self) -> bool:
        """Check if task completed successfully."""
        return self.status == TaskStatus.COMPLETED and self.error is None

    @property
    def is_failed(self) -> bool:
        """Check if task failed."""
        return self.status == TaskStatus.FAILED or self.error is not None

    def get_result_or_raise(self) -> T:
        """Get result or raise exception if failed."""
        if self.error:
            raise self.error

        if self.status == TaskStatus.CANCELLED:
            raise OperationCancelledError("Task was cancelled")

        if self.status != TaskStatus.COMPLETED:
            raise RuntimeError(f"Task not completed, status: {self.status}")

        return self.result


class Task(Generic[T]):
    """
    Represents an async task that can be queued for execution.
    """

    def __init__(
        self,
        func: Callable[..., T],
        *args,
        name: str | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: timedelta | None = None,
        retry_count: int = 0,
        retry_delay: timedelta = timedelta(seconds=1),
        cancellation_token: CancellationToken | None = None,
        progress_reporter: ProgressReporter | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        self.id = str(uuid4())
        self.name = name or f"Task_{self.id[:8]}"
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.priority = priority
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.cancellation_token = cancellation_token
        self.progress_reporter = progress_reporter
        self.metadata = metadata or {}

        # Execution state
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.result: T | None = None
        self.error: Exception | None = None
        self.attempts = 0

        # Callbacks
        self._completion_callbacks: list[Callable[[TaskResult[T]], None]] = []
        self._progress_callbacks: list[Callable[[ProgressReport], None]] = []

    @property
    def execution_time(self) -> timedelta | None:
        """Get task execution time."""
        if not self.started_at:
            return None

        end_time = self.completed_at or datetime.now()
        return end_time - self.started_at

    @property
    def is_complete(self) -> bool:
        """Check if task is complete."""
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        )

    def add_completion_callback(
        self, callback: Callable[[TaskResult[T]], None]
    ) -> None:
        """Add completion callback."""
        self._completion_callbacks.append(callback)

    def add_progress_callback(self, callback: Callable[[ProgressReport], None]) -> None:
        """Add progress callback."""
        self._progress_callbacks.append(callback)

    async def execute(self) -> TaskResult[T]:
        """Execute the task."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

        try:
            # Check cancellation before starting
            if self.cancellation_token and self.cancellation_token.is_cancelled:
                raise OperationCancelledError("Task cancelled before execution")

            # Setup progress reporting
            if self.progress_reporter:
                self.progress_reporter.add_callback(self._on_progress)
                self.progress_reporter.start(f"Executing {self.name}")

            # Execute with timeout and retry logic
            result = await self._execute_with_retry()

            # Complete successfully
            self.result = result
            self.status = TaskStatus.COMPLETED
            self.completed_at = datetime.now()

            if self.progress_reporter:
                self.progress_reporter.complete(f"Task {self.name} completed")

            task_result = TaskResult(
                task_id=self.id,
                status=self.status,
                result=result,
                execution_time=self.execution_time,
                metadata=self.metadata,
            )

            self._notify_completion_callbacks(task_result)
            return task_result

        except OperationCancelledError as e:
            self.status = TaskStatus.CANCELLED
            self.error = e
            self.completed_at = datetime.now()

            if self.progress_reporter:
                self.progress_reporter.cancel(f"Task {self.name} cancelled")

            task_result = TaskResult(
                task_id=self.id,
                status=self.status,
                error=e,
                execution_time=self.execution_time,
                metadata=self.metadata,
            )

            self._notify_completion_callbacks(task_result)
            return task_result

        except Exception as e:
            self.status = TaskStatus.FAILED
            self.error = e
            self.completed_at = datetime.now()

            if self.progress_reporter:
                self.progress_reporter.fail(f"Task {self.name} failed", e)

            logger.error(f"Task {self.name} failed: {e}")

            task_result = TaskResult(
                task_id=self.id,
                status=self.status,
                error=e,
                execution_time=self.execution_time,
                metadata=self.metadata,
            )

            self._notify_completion_callbacks(task_result)
            return task_result

    async def _execute_with_retry(self) -> T:
        """Execute function with retry logic."""
        last_error = None

        for attempt in range(self.retry_count + 1):
            self.attempts = attempt + 1

            try:
                # Check cancellation before each attempt
                if self.cancellation_token and self.cancellation_token.is_cancelled:
                    raise OperationCancelledError("Task cancelled during retry")

                # Execute with timeout
                if self.timeout:
                    return await asyncio.wait_for(
                        self._call_function(), timeout=self.timeout.total_seconds()
                    )
                else:
                    return await self._call_function()

            except OperationCancelledError:
                # Don't retry cancellation
                raise

            except Exception as e:
                last_error = e
                logger.warning(f"Task {self.name} attempt {attempt + 1} failed: {e}")

                # If we have more retries, wait and try again
                if attempt < self.retry_count:
                    await asyncio.sleep(self.retry_delay.total_seconds())

                    if self.progress_reporter:
                        self.progress_reporter.report_progress(
                            current=attempt + 1,
                            total=self.retry_count + 1,
                            message=f"Retrying after failure (attempt {attempt + 2}/{self.retry_count + 1})",
                        )

        # If we get here, all retries failed
        raise last_error

    async def _call_function(self) -> T:
        """Call the task function."""
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(*self.args, **self.kwargs)
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._call_sync_function)

    def _call_sync_function(self) -> T:
        """Call synchronous function."""
        return self.func(*self.args, **self.kwargs)

    def _on_progress(self, progress: ProgressReport) -> None:
        """Handle progress updates."""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.error(f"Error in task progress callback: {e}")

    def _notify_completion_callbacks(self, result: TaskResult[T]) -> None:
        """Notify completion callbacks."""
        for callback in self._completion_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Error in task completion callback: {e}")

    def __lt__(self, other: "Task") -> bool:
        """Compare tasks by priority for queue ordering."""
        if not isinstance(other, Task):
            return NotImplemented

        # Higher priority values come first
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value

        # If same priority, older tasks come first
        return self.created_at < other.created_at


class TaskQueue:
    """
    Async task queue with priority support and concurrent execution.
    """

    def __init__(
        self,
        max_concurrent_tasks: int = 4,
        max_queue_size: int | None = None,
        name: str | None = None,
    ) -> None:
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_queue_size = max_queue_size
        self.name = name or f"TaskQueue_{uuid4().hex[:8]}"

        # Task storage
        self._pending_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=max_queue_size or 0
        )
        self._running_tasks: dict[str, Task] = {}
        self._completed_tasks: dict[str, TaskResult] = {}

        # Queue state
        self._is_running = False
        self._worker_tasks: list[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()

        # Statistics
        self._stats = {
            "total_queued": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
        }

    @property
    def is_running(self) -> bool:
        """Check if queue is running."""
        return self._is_running

    @property
    def pending_count(self) -> int:
        """Get number of pending tasks."""
        return self._pending_queue.qsize()

    @property
    def running_count(self) -> int:
        """Get number of running tasks."""
        return len(self._running_tasks)

    @property
    def completed_count(self) -> int:
        """Get number of completed tasks."""
        return len(self._completed_tasks)

    @property
    def stats(self) -> dict[str, int]:
        """Get queue statistics."""
        return self._stats.copy()

    async def enqueue(self, task: Task[T]) -> str:
        """
        Enqueue a task for execution.

        Returns:
            Task ID
        """
        if not self._is_running:
            raise RuntimeError("Task queue is not running")

        # Check queue size limit
        if self.max_queue_size and self._pending_queue.qsize() >= self.max_queue_size:
            raise RuntimeError("Task queue is full")

        await self._pending_queue.put((0, task))  # Priority handled by Task.__lt__
        self._stats["total_queued"] += 1

        logger.debug(f"Enqueued task {task.name} ({task.id})")
        return task.id

    def enqueue_sync(self, task: Task[T]) -> str:
        """
        Synchronous version of enqueue.

        Returns:
            Task ID
        """
        if not self._is_running:
            raise RuntimeError("Task queue is not running")

        try:
            self._pending_queue.put_nowait((0, task))
            self._stats["total_queued"] += 1
            logger.debug(f"Enqueued task {task.name} ({task.id}) synchronously")
            return task.id
        except asyncio.QueueFull:
            raise RuntimeError("Task queue is full")

    async def submit(self, func: Callable[..., T], *args, **kwargs) -> str:
        """
        Submit a function as a task.

        Returns:
            Task ID
        """
        task = Task(func, *args, **kwargs)
        return await self.enqueue(task)

    async def wait_for_task(
        self, task_id: str, timeout: float | None = None
    ) -> TaskResult[T]:
        """
        Wait for a specific task to complete.

        Args:
            task_id: ID of the task to wait for
            timeout: Optional timeout in seconds

        Returns:
            Task result

        Raises:
            asyncio.TimeoutError: If timeout is reached
            KeyError: If task ID not found
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check if task is completed
            if task_id in self._completed_tasks:
                return self._completed_tasks[task_id]

            # Check timeout
            if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                raise TimeoutError(f"Timeout waiting for task {task_id}")

            # Check if task exists
            if (
                task_id not in self._running_tasks
                and task_id not in self._completed_tasks
            ):
                # Search pending queue
                found = False
                temp_items = []

                while not self._pending_queue.empty():
                    try:
                        priority, task = self._pending_queue.get_nowait()
                        temp_items.append((priority, task))
                        if task.id == task_id:
                            found = True
                    except asyncio.QueueEmpty:
                        break

                # Put items back
                for item in temp_items:
                    await self._pending_queue.put(item)

                if not found:
                    raise KeyError(f"Task {task_id} not found")

            # Wait a bit before checking again
            await asyncio.sleep(0.1)

    def get_task_status(self, task_id: str) -> TaskStatus | None:
        """Get status of a task."""
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id].status
        elif task_id in self._running_tasks:
            return self._running_tasks[task_id].status
        else:
            return None

    def get_task_result(self, task_id: str) -> TaskResult[T] | None:
        """Get result of a completed task."""
        return self._completed_tasks.get(task_id)

    async def start(self) -> None:
        """Start the task queue."""
        if self._is_running:
            return

        self._is_running = True
        self._shutdown_event.clear()

        # Start worker tasks
        self._worker_tasks = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_concurrent_tasks)
        ]

        logger.info(
            f"Started task queue {self.name} with {self.max_concurrent_tasks} workers"
        )

    async def stop(self, timeout: float | None = None) -> None:
        """Stop the task queue."""
        if not self._is_running:
            return

        self._is_running = False
        self._shutdown_event.set()

        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()

        # Wait for workers to finish
        if self._worker_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._worker_tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except TimeoutError:
                logger.warning(f"Task queue {self.name} shutdown timeout")

        self._worker_tasks.clear()

        # Cancel running tasks
        for task in self._running_tasks.values():
            if task.cancellation_token:
                task.cancellation_token._cancel("Queue shutdown")

        logger.info(f"Stopped task queue {self.name}")

    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine that processes tasks."""
        logger.debug(f"Worker {worker_id} started for queue {self.name}")

        try:
            while self._is_running:
                try:
                    # Wait for task or shutdown
                    try:
                        priority, task = await asyncio.wait_for(
                            self._pending_queue.get(), timeout=1.0
                        )
                    except TimeoutError:
                        continue

                    # Check if we should shutdown
                    if self._shutdown_event.is_set():
                        # Put task back
                        await self._pending_queue.put((priority, task))
                        break

                    # Execute task
                    self._running_tasks[task.id] = task

                    try:
                        result = await task.execute()

                        # Store result
                        self._completed_tasks[task.id] = result

                        # Update statistics
                        if result.status == TaskStatus.COMPLETED:
                            self._stats["total_completed"] += 1
                        elif result.status == TaskStatus.FAILED:
                            self._stats["total_failed"] += 1
                        elif result.status == TaskStatus.CANCELLED:
                            self._stats["total_cancelled"] += 1

                        logger.debug(
                            f"Task {task.name} completed with status {result.status}"
                        )

                    finally:
                        # Remove from running tasks
                        if task.id in self._running_tasks:
                            del self._running_tasks[task.id]

                except Exception as e:
                    logger.error(f"Worker {worker_id} error: {e}")

        except asyncio.CancelledError:
            logger.debug(f"Worker {worker_id} cancelled")

        except Exception as e:
            logger.error(f"Worker {worker_id} failed: {e}")

        logger.debug(f"Worker {worker_id} stopped for queue {self.name}")

    async def clear_completed(self, older_than: timedelta | None = None) -> int:
        """
        Clear completed tasks from memory.

        Args:
            older_than: Only clear tasks older than this duration

        Returns:
            Number of tasks cleared
        """
        if not older_than:
            count = len(self._completed_tasks)
            self._completed_tasks.clear()
            return count

        datetime.now() - older_than
        to_remove = []

        for task_id, _result in self._completed_tasks.items():
            # Check if we have completion time info (would need to be added to TaskResult)
            # For now, just clear all if older_than is specified
            to_remove.append(task_id)

        for task_id in to_remove:
            del self._completed_tasks[task_id]

        return len(to_remove)

    async def __aenter__(self) -> "TaskQueue":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.stop()
