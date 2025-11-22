"""File system watcher with pattern matching."""

import fnmatch
import threading
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..core.logging import get_logger

logger = get_logger(__name__)


class PatternMatchingHandler(FileSystemEventHandler):
    """File system event handler with pattern matching."""

    def __init__(
        self,
        patterns: list[str],
        ignore_patterns: list[str],
        callback: Callable[[Path, str], None],
    ) -> None:
        """Initialize pattern matching handler.

        Args:
            patterns: File patterns to match
            ignore_patterns: File patterns to ignore
            callback: Callback function for file changes
        """
        super().__init__()
        self.patterns = patterns
        self.ignore_patterns = ignore_patterns
        self.callback = callback

        # Debouncing
        self._last_events = {}
        self._debounce_delay = 0.1  # 100ms debounce

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle any file system event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Check if file matches patterns
        if not self._matches_patterns(file_path):
            return

        # Check if file should be ignored
        if self._should_ignore(file_path):
            return

        # Debounce events
        current_time = time.time()
        last_time = self._last_events.get(file_path, 0)

        if current_time - last_time < self._debounce_delay:
            return

        self._last_events[file_path] = current_time

        # Determine event type
        event_type = self._get_event_type(event.event_type)

        try:
            self.callback(file_path, event_type)
        except Exception as e:
            logger.error(f"Error in file change callback: {e}")

    def _matches_patterns(self, file_path: Path) -> bool:
        """Check if file matches any watch patterns.

        Args:
            file_path: File path to check

        Returns:
            True if file matches patterns
        """
        if not self.patterns:
            return True

        file_str = str(file_path)
        file_name = file_path.name

        for pattern in self.patterns:
            if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(
                file_str, pattern
            ):
                return True

        return False

    def _should_ignore(self, file_path: Path) -> bool:
        """Check if file should be ignored.

        Args:
            file_path: File path to check

        Returns:
            True if file should be ignored
        """
        if not self.ignore_patterns:
            return False

        file_str = str(file_path)
        file_name = file_path.name

        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(
                file_str, pattern
            ):
                return True

        return False

    def _get_event_type(self, event_type: str) -> str:
        """Convert watchdog event type to friendly name.

        Args:
            event_type: Watchdog event type

        Returns:
            Friendly event type name
        """
        type_mapping = {
            "modified": "changed",
            "created": "created",
            "deleted": "deleted",
            "moved": "moved",
        }
        return type_mapping.get(event_type, event_type)


class FileWatcher:
    """File system watcher with pattern matching and debouncing."""

    def __init__(
        self,
        watch_path: Path,
        patterns: list[str],
        ignore_patterns: list[str],
        callback: Callable[[Path, str], None],
    ) -> None:
        """Initialize file watcher.

        Args:
            watch_path: Path to watch
            patterns: File patterns to watch
            ignore_patterns: File patterns to ignore
            callback: Callback function for file changes
        """
        self.watch_path = watch_path
        self.patterns = patterns
        self.ignore_patterns = ignore_patterns
        self.callback = callback

        self.observer: Observer | None = None
        self.handler: PatternMatchingHandler | None = None
        self.running = False

    def start(self) -> None:
        """Start watching files."""
        if self.running:
            return

        self.handler = PatternMatchingHandler(
            self.patterns, self.ignore_patterns, self.callback
        )

        self.observer = Observer()
        self.observer.schedule(self.handler, str(self.watch_path), recursive=True)

        self.observer.start()
        self.running = True

        logger.info(f"Started watching {self.watch_path}")
        logger.debug(f"Watch patterns: {self.patterns}")
        logger.debug(f"Ignore patterns: {self.ignore_patterns}")

    def stop(self) -> None:
        """Stop watching files."""
        if not self.running:
            return

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)

        self.running = False
        logger.info("Stopped file watcher")

    def is_running(self) -> bool:
        """Check if watcher is running.

        Returns:
            True if watcher is running
        """
        return self.running and self.observer is not None and self.observer.is_alive()


class BatchedFileWatcher(FileWatcher):
    """File watcher that batches multiple changes into single events."""

    def __init__(
        self,
        watch_path: Path,
        patterns: list[str],
        ignore_patterns: list[str],
        callback: Callable[[list[tuple[Path, str]]], None],
        batch_delay: float = 0.5,
    ) -> None:
        """Initialize batched file watcher.

        Args:
            watch_path: Path to watch
            patterns: File patterns to watch
            ignore_patterns: File patterns to ignore
            callback: Callback function for batched file changes
            batch_delay: Delay before processing batch
        """
        self.batch_callback = callback
        self.batch_delay = batch_delay
        self.pending_changes: list[tuple[Path, str]] = []
        self.batch_timer: threading.Timer | None = None
        self.lock = threading.Lock()

        # Initialize parent with our internal callback
        super().__init__(watch_path, patterns, ignore_patterns, self._on_single_change)

    def _on_single_change(self, file_path: Path, event_type: str) -> None:
        """Handle single file change event.

        Args:
            file_path: Changed file path
            event_type: Type of change
        """
        with self.lock:
            self.pending_changes.append((file_path, event_type))

            # Cancel existing timer
            if self.batch_timer:
                self.batch_timer.cancel()

            # Start new timer
            self.batch_timer = threading.Timer(self.batch_delay, self._process_batch)
            self.batch_timer.start()

    def _process_batch(self) -> None:
        """Process batched file changes."""
        with self.lock:
            if not self.pending_changes:
                return

            changes = list(self.pending_changes)
            self.pending_changes.clear()

            try:
                self.batch_callback(changes)
            except Exception as e:
                logger.error(f"Error in batched file change callback: {e}")

    def stop(self) -> None:
        """Stop watching files."""
        with self.lock:
            if self.batch_timer:
                self.batch_timer.cancel()

            # Process any remaining changes
            if self.pending_changes:
                self._process_batch()

        super().stop()
