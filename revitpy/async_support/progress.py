"""
Progress reporting system for long-running async operations.
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from loguru import logger


class ProgressState(Enum):
    """Progress state enumeration."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressReport:
    """Progress report containing current status information."""

    current: int
    total: int
    message: str | None = None
    state: ProgressState = ProgressState.IN_PROGRESS
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def percentage(self) -> float:
        """Get progress as percentage (0-100)."""
        if self.total <= 0:
            return 0.0
        return min(100.0, max(0.0, (self.current / self.total) * 100))

    @property
    def is_complete(self) -> bool:
        """Check if progress is complete."""
        return self.state == ProgressState.COMPLETED or self.current >= self.total

    @property
    def is_indeterminate(self) -> bool:
        """Check if progress is indeterminate."""
        return self.total <= 0

    def with_message(self, message: str) -> "ProgressReport":
        """Create a new progress report with updated message."""
        return ProgressReport(
            current=self.current,
            total=self.total,
            message=message,
            state=self.state,
            data=self.data.copy(),
            timestamp=datetime.now(),
        )

    def with_data(self, **data) -> "ProgressReport":
        """Create a new progress report with updated data."""
        new_data = self.data.copy()
        new_data.update(data)

        return ProgressReport(
            current=self.current,
            total=self.total,
            message=self.message,
            state=self.state,
            data=new_data,
            timestamp=datetime.now(),
        )


ProgressCallback = Callable[[ProgressReport], None]


class IProgressReporter(ABC):
    """Abstract interface for progress reporters."""

    @abstractmethod
    def report(self, progress: ProgressReport) -> None:
        """Report progress."""
        pass

    @abstractmethod
    def report_progress(
        self, current: int, total: int, message: str | None = None, **data
    ) -> None:
        """Report progress with current/total values."""
        pass


class ProgressReporter(IProgressReporter):
    """
    Progress reporter that can notify multiple callbacks.
    """

    def __init__(self, total: int | None = None) -> None:
        self._callbacks: list[ProgressCallback] = []
        self._current = 0
        self._total = total or 0
        self._state = ProgressState.NOT_STARTED
        self._last_report: ProgressReport | None = None
        self._start_time: datetime | None = None
        self._throttle_interval = timedelta(
            milliseconds=100
        )  # Throttle to 10 updates per second
        self._last_report_time: datetime | None = None

    @property
    def current(self) -> int:
        """Get current progress value."""
        return self._current

    @property
    def total(self) -> int:
        """Get total progress value."""
        return self._total

    @property
    def percentage(self) -> float:
        """Get progress as percentage."""
        if self._total <= 0:
            return 0.0
        return min(100.0, max(0.0, (self._current / self._total) * 100))

    @property
    def state(self) -> ProgressState:
        """Get current progress state."""
        return self._state

    @property
    def last_report(self) -> ProgressReport | None:
        """Get the last progress report."""
        return self._last_report

    @property
    def elapsed_time(self) -> timedelta | None:
        """Get elapsed time since progress started."""
        if self._start_time is None:
            return None
        return datetime.now() - self._start_time

    @property
    def estimated_remaining(self) -> timedelta | None:
        """Get estimated remaining time."""
        elapsed = self.elapsed_time
        if not elapsed or self._current <= 0 or self._total <= 0:
            return None

        if self._current >= self._total:
            return timedelta(0)

        rate = self._current / elapsed.total_seconds()
        if rate <= 0:
            return None

        remaining_items = self._total - self._current
        remaining_seconds = remaining_items / rate

        return timedelta(seconds=remaining_seconds)

    def add_callback(self, callback: ProgressCallback) -> None:
        """Add a progress callback."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: ProgressCallback) -> None:
        """Remove a progress callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def set_total(self, total: int) -> None:
        """Set the total progress value."""
        self._total = total
        self._update_progress()

    def start(self, message: str | None = None) -> None:
        """Start progress reporting."""
        self._state = ProgressState.IN_PROGRESS
        self._start_time = datetime.now()
        self._current = 0

        report = ProgressReport(
            current=self._current,
            total=self._total,
            message=message or "Starting...",
            state=self._state,
        )

        self._notify_callbacks(report)

    def increment(self, amount: int = 1, message: str | None = None, **data) -> None:
        """Increment progress by amount."""
        self._current = min(self._total, self._current + amount)
        self._update_progress(message, **data)

    def set_progress(self, current: int, message: str | None = None, **data) -> None:
        """Set current progress value."""
        self._current = max(0, min(self._total, current))
        self._update_progress(message, **data)

    def report_progress(
        self, current: int, total: int, message: str | None = None, **data
    ) -> None:
        """Report progress with current/total values."""
        self._current = max(0, current)
        self._total = max(0, total)
        self._update_progress(message, **data)

    def report(self, progress: ProgressReport) -> None:
        """Report progress using a ProgressReport object."""
        self._current = progress.current
        self._total = progress.total
        self._state = progress.state
        self._notify_callbacks(progress)

    def complete(self, message: str | None = None, **data) -> None:
        """Mark progress as complete."""
        self._current = self._total
        self._state = ProgressState.COMPLETED

        report = ProgressReport(
            current=self._current,
            total=self._total,
            message=message or "Completed",
            state=self._state,
            data=data,
        )

        self._notify_callbacks(report)

    def fail(
        self, message: str | None = None, error: Exception | None = None, **data
    ) -> None:
        """Mark progress as failed."""
        self._state = ProgressState.FAILED

        failure_data = data.copy()
        if error:
            failure_data["error"] = str(error)
            failure_data["error_type"] = type(error).__name__

        report = ProgressReport(
            current=self._current,
            total=self._total,
            message=message or f"Failed: {error}" if error else "Failed",
            state=self._state,
            data=failure_data,
        )

        self._notify_callbacks(report)

    def cancel(self, message: str | None = None, **data) -> None:
        """Mark progress as cancelled."""
        self._state = ProgressState.CANCELLED

        report = ProgressReport(
            current=self._current,
            total=self._total,
            message=message or "Cancelled",
            state=self._state,
            data=data,
        )

        self._notify_callbacks(report)

    def _update_progress(self, message: str | None = None, **data) -> None:
        """Update progress and notify callbacks."""
        # Throttle updates to avoid overwhelming callbacks
        now = datetime.now()
        if (
            self._last_report_time
            and now - self._last_report_time < self._throttle_interval
            and self._current < self._total
        ):
            return

        self._last_report_time = now

        # Auto-complete if we've reached the total
        if self._current >= self._total and self._state == ProgressState.IN_PROGRESS:
            self._state = ProgressState.COMPLETED

        report = ProgressReport(
            current=self._current,
            total=self._total,
            message=message,
            state=self._state,
            data=data,
        )

        self._notify_callbacks(report)

    def _notify_callbacks(self, report: ProgressReport) -> None:
        """Notify all registered callbacks."""
        self._last_report = report

        for callback in self._callbacks:
            try:
                callback(report)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")


class ConsoleProgressReporter(ProgressReporter):
    """Progress reporter that prints to console."""

    def __init__(self, total: int | None = None, show_percentage: bool = True) -> None:
        super().__init__(total)
        self._show_percentage = show_percentage
        self.add_callback(self._console_callback)

    def _console_callback(self, report: ProgressReport) -> None:
        """Console progress callback."""
        if report.is_indeterminate:
            status = f"Progress: {report.current} items"
        else:
            if self._show_percentage:
                status = f"Progress: {report.current}/{report.total} ({report.percentage:.1f}%)"
            else:
                status = f"Progress: {report.current}/{report.total}"

        if report.message:
            status += f" - {report.message}"

        # Add timing information if available
        if report.state == ProgressState.COMPLETED and self.elapsed_time:
            status += f" (completed in {self.elapsed_time.total_seconds():.1f}s)"
        elif self.estimated_remaining and report.state == ProgressState.IN_PROGRESS:
            remaining = self.estimated_remaining
            status += f" (ETA: {remaining.total_seconds():.1f}s)"

        print(status)


class AsyncProgressReporter(ProgressReporter):
    """Async-aware progress reporter."""

    def __init__(self, total: int | None = None) -> None:
        super().__init__(total)
        self._async_callbacks: list[Callable[[ProgressReport], Any]] = []

    def add_async_callback(self, callback: Callable[[ProgressReport], Any]) -> None:
        """Add an async progress callback."""
        self._async_callbacks.append(callback)

    def remove_async_callback(self, callback: Callable[[ProgressReport], Any]) -> None:
        """Remove an async progress callback."""
        if callback in self._async_callbacks:
            self._async_callbacks.remove(callback)

    async def _notify_async_callbacks(self, report: ProgressReport) -> None:
        """Notify all async callbacks."""
        for callback in self._async_callbacks:
            try:
                result = callback(report)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in async progress callback: {e}")

    async def async_report(self, progress: ProgressReport) -> None:
        """Async version of report method."""
        self.report(progress)
        await self._notify_async_callbacks(progress)

    async def async_increment(
        self, amount: int = 1, message: str | None = None, **data
    ) -> None:
        """Async version of increment method."""
        self.increment(amount, message, **data)
        if self._last_report:
            await self._notify_async_callbacks(self._last_report)

    async def async_complete(self, message: str | None = None, **data) -> None:
        """Async version of complete method."""
        self.complete(message, **data)
        if self._last_report:
            await self._notify_async_callbacks(self._last_report)


def create_progress_reporter(
    total: int | None = None, console_output: bool = False, **kwargs
) -> ProgressReporter:
    """Factory function to create progress reporters."""
    if console_output:
        return ConsoleProgressReporter(total, **kwargs)
    else:
        return AsyncProgressReporter(total)
