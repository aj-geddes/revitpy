"""
Extraction-specific exceptions for RevitPy.

This module defines all exceptions used throughout the extraction layer,
providing specific error types for quantity extraction, cost estimation,
export operations, and schedule building.
"""

from __future__ import annotations

from typing import Any

from ..api.exceptions import RevitAPIError


class ExtractionError(RevitAPIError):
    """Base exception for all extraction-related errors."""

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        element_id: Any | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.operation = operation
        self.element_id = element_id


class QuantityError(ExtractionError):
    """Exception raised when quantity extraction fails."""

    def __init__(
        self,
        message: str,
        *,
        quantity_type: str | None = None,
        element_id: Any | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            operation="quantity_extraction",
            element_id=element_id,
            cause=cause,
        )
        self.quantity_type = quantity_type


class CostEstimationError(ExtractionError):
    """Exception raised when cost estimation fails."""

    def __init__(
        self,
        message: str,
        *,
        category: str | None = None,
        unit_cost: float | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="cost_estimation", cause=cause)
        self.category = category
        self.unit_cost = unit_cost


class ExportError(ExtractionError):
    """Exception raised when data export fails."""

    def __init__(
        self,
        message: str,
        *,
        export_format: str | None = None,
        output_path: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="export", cause=cause)
        self.export_format = export_format
        self.output_path = output_path


class ScheduleError(ExtractionError):
    """Exception raised when schedule building fails."""

    def __init__(
        self,
        message: str,
        *,
        schedule_config: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="schedule", cause=cause)
        self.schedule_config = schedule_config
