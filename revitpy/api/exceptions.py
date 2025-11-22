"""
Custom exceptions for RevitPy API operations.
"""

from typing import Any


class RevitAPIError(Exception):
    """Base exception for RevitPy API errors."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class TransactionError(RevitAPIError):
    """Exception raised during transaction operations."""

    def __init__(
        self,
        message: str,
        transaction_name: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause)
        self.transaction_name = transaction_name


class ElementNotFoundError(RevitAPIError):
    """Exception raised when an element cannot be found."""

    def __init__(
        self,
        element_id: Any | None = None,
        element_type: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        message = "Element not found"
        if element_id is not None:
            message += f" with ID: {element_id}"
        if element_type is not None:
            message += f" of type: {element_type}"

        super().__init__(message, cause)
        self.element_id = element_id
        self.element_type = element_type


class ValidationError(RevitAPIError):
    """Exception raised when element validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause)
        self.field = field
        self.value = value


class PermissionError(RevitAPIError):
    """Exception raised when operation is not permitted."""

    def __init__(
        self,
        message: str = "Operation not permitted",
        operation: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause)
        self.operation = operation


class ModelError(RevitAPIError):
    """Exception raised when model is in invalid state."""

    def __init__(
        self, message: str = "Model in invalid state", cause: Exception | None = None
    ) -> None:
        super().__init__(message, cause)


class ConnectionError(RevitAPIError):
    """Exception raised when connection to Revit fails."""

    def __init__(
        self,
        message: str = "Connection to Revit failed",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause)
