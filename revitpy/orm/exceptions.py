"""
ORM-specific exceptions for RevitPy.

This module defines all exceptions used throughout the ORM layer,
providing specific error types for different ORM operations.
"""

from __future__ import annotations

from typing import Any

# Import base exception - adjust path as needed
try:
    from ..api.exceptions import RevitPyException
except ImportError:
    # Fallback if api module not available
    class RevitPyException(Exception):
        def __init__(self, message: str, *, cause: Exception | None = None):
            super().__init__(message)
            self.cause = cause


class ORMException(RevitPyException):
    """Base exception for all ORM-related errors."""

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        entity_type: str | None = None,
        entity_id: Any | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.operation = operation
        self.entity_type = entity_type
        self.entity_id = entity_id


class RelationshipError(ORMException):
    """Exception raised when relationship operations fail."""

    def __init__(
        self,
        message: str,
        *,
        relationship_name: str | None = None,
        source_entity: Any | None = None,
        target_entity: Any | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="relationship", cause=cause)
        self.relationship_name = relationship_name
        self.source_entity = source_entity
        self.target_entity = target_entity


class CacheError(ORMException):
    """Exception raised when cache operations fail."""

    def __init__(
        self,
        message: str,
        *,
        cache_key: str | None = None,
        cache_operation: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="cache", cause=cause)
        self.cache_key = cache_key
        self.cache_operation = cache_operation


class ChangeTrackingError(ORMException):
    """Exception raised when change tracking operations fail."""

    def __init__(
        self,
        message: str,
        *,
        entity: Any | None = None,
        property_name: str | None = None,
        tracking_operation: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="change_tracking", cause=cause)
        self.entity = entity
        self.property_name = property_name
        self.tracking_operation = tracking_operation


class QueryError(ORMException):
    """Exception raised when query operations fail."""

    def __init__(
        self,
        message: str,
        *,
        query_expression: str | None = None,
        query_operation: str | None = None,
        element_count: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="query", cause=cause)
        self.query_expression = query_expression
        self.query_operation = query_operation
        self.element_count = element_count


class LazyLoadingError(ORMException):
    """Exception raised when lazy loading fails."""

    def __init__(
        self,
        message: str,
        *,
        property_name: str | None = None,
        entity: Any | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="lazy_loading", cause=cause)
        self.property_name = property_name
        self.entity = entity


class AsyncOperationError(ORMException):
    """Exception raised when async operations fail."""

    def __init__(
        self,
        message: str,
        *,
        async_operation: str | None = None,
        task_id: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="async", cause=cause)
        self.async_operation = async_operation
        self.task_id = task_id


class BatchOperationError(ORMException):
    """Exception raised when batch operations fail."""

    def __init__(
        self,
        message: str,
        *,
        batch_size: int | None = None,
        failed_operations: list[dict[str, Any]] | None = None,
        successful_operations: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="batch", cause=cause)
        self.batch_size = batch_size
        self.failed_operations = failed_operations or []
        self.successful_operations = successful_operations or 0


class ValidationError(ORMException):
    """Exception raised when entity validation fails."""

    def __init__(
        self,
        message: str,
        *,
        validation_errors: dict[str, list[str]] | None = None,
        entity: Any | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="validation", cause=cause)
        self.validation_errors = validation_errors or {}
        self.entity = entity


class ConcurrencyError(ORMException):
    """Exception raised when concurrency conflicts occur."""

    def __init__(
        self,
        message: str,
        *,
        entity: Any | None = None,
        conflicting_changes: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="concurrency", cause=cause)
        self.entity = entity
        self.conflicting_changes = conflicting_changes or {}


class TransactionError(ORMException):
    """Exception raised when transaction operations fail."""

    def __init__(
        self,
        message: str,
        *,
        transaction_id: str | None = None,
        transaction_state: str | None = None,
        nested_level: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, operation="transaction", cause=cause)
        self.transaction_id = transaction_id
        self.transaction_state = transaction_state
        self.nested_level = nested_level
