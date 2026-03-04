"""
Sustainability-specific exceptions for RevitPy.

This module defines all exceptions used throughout the sustainability layer,
providing specific error types for carbon calculation, EPD lookup,
compliance checking, and report generation.
"""

from __future__ import annotations


class SustainabilityError(Exception):
    """Base exception for all sustainability-related errors."""

    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause


class CarbonCalculationError(SustainabilityError):
    """Exception raised when carbon calculation fails."""

    def __init__(
        self,
        message: str,
        *,
        material_name: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.material_name = material_name


class EpdLookupError(SustainabilityError):
    """Exception raised when EPD lookup fails."""

    def __init__(
        self,
        message: str,
        *,
        material_name: str | None = None,
        category: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.material_name = material_name
        self.category = category


class ComplianceError(SustainabilityError):
    """Exception raised when compliance checking fails."""

    def __init__(
        self,
        message: str,
        *,
        standard: str | None = None,
        requirement: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.standard = standard
        self.requirement = requirement


class ReportGenerationError(SustainabilityError):
    """Exception raised when report generation fails."""

    def __init__(
        self,
        message: str,
        *,
        report_format: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.report_format = report_format
