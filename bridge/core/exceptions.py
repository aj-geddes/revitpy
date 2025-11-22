"""
Exception classes for the PyRevit-RevitPy bridge.
"""

from typing import Any


class BridgeException(Exception):
    """Base exception for all bridge-related errors."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
        }


class BridgeTimeoutError(BridgeException):
    """Raised when a bridge operation times out."""

    def __init__(
        self,
        operation: str,
        timeout_seconds: int,
        context: dict[str, Any] | None = None,
    ):
        message = (
            f"Bridge operation '{operation}' timed out after {timeout_seconds} seconds"
        )
        super().__init__(message, "BRIDGE_TIMEOUT", context)
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class BridgeConnectionError(BridgeException):
    """Raised when bridge connection fails."""

    def __init__(
        self, connection_type: str, details: str, context: dict[str, Any] | None = None
    ):
        message = f"Bridge connection failed ({connection_type}): {details}"
        super().__init__(message, "BRIDGE_CONNECTION_ERROR", context)
        self.connection_type = connection_type
        self.details = details


class BridgeDataError(BridgeException):
    """Raised when data serialization/deserialization fails."""

    def __init__(
        self,
        operation: str,
        data_type: str,
        details: str,
        context: dict[str, Any] | None = None,
    ):
        message = f"Bridge data {operation} failed for {data_type}: {details}"
        super().__init__(message, "BRIDGE_DATA_ERROR", context)
        self.operation = operation
        self.data_type = data_type
        self.details = details


class BridgeAnalysisError(BridgeException):
    """Raised when analysis execution fails."""

    def __init__(
        self, analysis_type: str, details: str, context: dict[str, Any] | None = None
    ):
        message = f"Analysis '{analysis_type}' failed: {details}"
        super().__init__(message, "BRIDGE_ANALYSIS_ERROR", context)
        self.analysis_type = analysis_type
        self.details = details


class BridgeValidationError(BridgeException):
    """Raised when data validation fails."""

    def __init__(
        self, validation_type: str, errors: list, context: dict[str, Any] | None = None
    ):
        error_summary = "; ".join(errors)
        message = f"Bridge validation failed ({validation_type}): {error_summary}"
        super().__init__(message, "BRIDGE_VALIDATION_ERROR", context)
        self.validation_type = validation_type
        self.errors = errors


class BridgeSecurityError(BridgeException):
    """Raised when security validation fails."""

    def __init__(
        self, security_check: str, details: str, context: dict[str, Any] | None = None
    ):
        message = f"Bridge security check failed ({security_check}): {details}"
        super().__init__(message, "BRIDGE_SECURITY_ERROR", context)
        self.security_check = security_check
        self.details = details


class BridgeResourceError(BridgeException):
    """Raised when resource limits are exceeded."""

    def __init__(
        self,
        resource_type: str,
        limit: Any,
        current: Any,
        context: dict[str, Any] | None = None,
    ):
        message = (
            f"Bridge resource limit exceeded ({resource_type}): {current} > {limit}"
        )
        super().__init__(message, "BRIDGE_RESOURCE_ERROR", context)
        self.resource_type = resource_type
        self.limit = limit
        self.current = current
