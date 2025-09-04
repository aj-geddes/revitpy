"""Logging configuration for RevitPy CLI."""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

console = Console()


class CLIFormatter(logging.Formatter):
    """Custom formatter for CLI logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for CLI output."""
        if record.levelno >= logging.ERROR:
            prefix = "❌"
        elif record.levelno >= logging.WARNING:
            prefix = "⚠️"
        elif record.levelno >= logging.INFO:
            prefix = "ℹ️"
        else:
            prefix = "🔍"
        
        return f"{prefix} {record.getMessage()}"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Set up logging for the CLI application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file to write logs to
        verbose: Enable verbose logging
        debug: Enable debug logging
    """
    # Determine log level
    if debug:
        log_level = logging.DEBUG
    elif verbose:
        log_level = logging.INFO
    else:
        log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger("revitpy_cli")
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler with Rich formatting
    console_handler = RichHandler(
        console=console,
        rich_tracebacks=debug,
        tracebacks_show_locals=debug,
        show_path=debug,
        show_time=debug,
    )
    console_handler.setLevel(log_level)
    
    if debug:
        console_format = "[%(name)s] %(message)s"
    else:
        console_format = "%(message)s"
    
    console_handler.setFormatter(logging.Formatter(console_format))
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always debug level for file
        
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Configure third-party loggers
    logging.getLogger("cookiecutter").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def get_logger(name: str = "revitpy_cli") -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class ProgressLogger:
    """Logger with progress tracking capabilities."""
    
    def __init__(self, name: str = "revitpy_cli") -> None:
        """Initialize progress logger.
        
        Args:
            name: Logger name
        """
        self.logger = get_logger(name)
        self._current_step = 0
        self._total_steps = 0
    
    def start_progress(self, total_steps: int, description: str = "Processing") -> None:
        """Start progress tracking.
        
        Args:
            total_steps: Total number of steps
            description: Description of the process
        """
        self._current_step = 0
        self._total_steps = total_steps
        self.logger.info(f"Starting {description} ({total_steps} steps)")
    
    def step(self, description: str = "") -> None:
        """Log a progress step.
        
        Args:
            description: Description of the current step
        """
        self._current_step += 1
        progress = f"[{self._current_step}/{self._total_steps}]"
        
        if description:
            self.logger.info(f"{progress} {description}")
        else:
            self.logger.debug(f"{progress} Step completed")
    
    def complete(self, description: str = "Complete") -> None:
        """Mark progress as complete.
        
        Args:
            description: Completion message
        """
        self.logger.info(f"✓ {description}")


def log_command_start(command: str, args: dict) -> None:
    """Log the start of a CLI command.
    
    Args:
        command: Command name
        args: Command arguments
    """
    logger = get_logger()
    logger.debug(f"Starting command: {command}")
    
    if args:
        logger.debug(f"Arguments: {args}")


def log_command_complete(command: str, duration: float) -> None:
    """Log the completion of a CLI command.
    
    Args:
        command: Command name
        duration: Command execution duration in seconds
    """
    logger = get_logger()
    logger.info(f"✓ Command '{command}' completed in {duration:.2f}s")