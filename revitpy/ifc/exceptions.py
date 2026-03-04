"""
IFC-specific exceptions for RevitPy.

This module defines all exceptions used throughout the IFC layer,
providing specific error types for export, import, validation,
IDS compliance, and BCF operations.
"""

from __future__ import annotations

from typing import Any


class IfcError(Exception):
    """Base exception for all IFC-related errors."""

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


class IfcExportError(IfcError):
    """Exception raised when IFC export operations fail."""

    def __init__(
        self,
        message: str,
        *,
        output_path: str | None = None,
        element_count: int | None = None,
        version: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.output_path = output_path
        self.element_count = element_count
        self.version = version


class IfcImportError(IfcError):
    """Exception raised when IFC import operations fail."""

    def __init__(
        self,
        message: str,
        *,
        input_path: str | None = None,
        entity_type: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.input_path = input_path
        self.entity_type = entity_type


class IfcValidationError(IfcError):
    """Exception raised when IFC data validation fails."""

    def __init__(
        self,
        message: str,
        *,
        entity_id: Any | None = None,
        property_name: str | None = None,
        expected_value: Any | None = None,
        actual_value: Any | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.entity_id = entity_id
        self.property_name = property_name
        self.expected_value = expected_value
        self.actual_value = actual_value


class IdsValidationError(IfcError):
    """Exception raised when IDS (Information Delivery Specification) validation fails."""

    def __init__(
        self,
        message: str,
        *,
        requirement_name: str | None = None,
        failed_count: int | None = None,
        total_count: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.requirement_name = requirement_name
        self.failed_count = failed_count
        self.total_count = total_count


class BcfError(IfcError):
    """Exception raised when BCF (BIM Collaboration Format) operations fail."""

    def __init__(
        self,
        message: str,
        *,
        bcf_path: str | None = None,
        issue_guid: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.bcf_path = bcf_path
        self.issue_guid = issue_guid
