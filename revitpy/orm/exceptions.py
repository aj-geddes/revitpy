"""
ORM-specific exceptions for RevitPy.

This module defines all exceptions used throughout the ORM layer,
providing specific error types for different ORM operations.
"""

from __future__ import annotations

from typing import Any, Optional, Dict, List

# Import base exception - adjust path as needed
try:
    from ..api.exceptions import RevitPyException
except ImportError:
    # Fallback if api module not available
    class RevitPyException(Exception):
        def __init__(self, message: str, *, cause: Optional[Exception] = None):
            super().__init__(message)
            self.cause = cause


class ORMException(RevitPyException):
    """Base exception for all ORM-related errors."""
    
    def __init__(
        self,
        message: str,
        *,
        operation: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[Any] = None,
        cause: Optional[Exception] = None
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
        relationship_name: Optional[str] = None,
        source_entity: Optional[Any] = None,
        target_entity: Optional[Any] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(
            message,
            operation="relationship",
            cause=cause
        )
        self.relationship_name = relationship_name
        self.source_entity = source_entity
        self.target_entity = target_entity


class CacheError(ORMException):
    """Exception raised when cache operations fail."""
    
    def __init__(
        self,
        message: str,
        *,
        cache_key: Optional[str] = None,
        cache_operation: Optional[str] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(
            message,
            operation="cache",
            cause=cause
        )
        self.cache_key = cache_key
        self.cache_operation = cache_operation


class ChangeTrackingError(ORMException):
    """Exception raised when change tracking operations fail."""
    
    def __init__(
        self,
        message: str,
        *,
        entity: Optional[Any] = None,
        property_name: Optional[str] = None,
        tracking_operation: Optional[str] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(
            message,
            operation="change_tracking",
            cause=cause
        )
        self.entity = entity
        self.property_name = property_name
        self.tracking_operation = tracking_operation


class QueryError(ORMException):
    """Exception raised when query operations fail."""
    
    def __init__(
        self,
        message: str,
        *,
        query_expression: Optional[str] = None,
        query_operation: Optional[str] = None,
        element_count: Optional[int] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(
            message,
            operation="query",
            cause=cause
        )
        self.query_expression = query_expression
        self.query_operation = query_operation
        self.element_count = element_count


class LazyLoadingError(ORMException):
    """Exception raised when lazy loading fails."""
    
    def __init__(
        self,
        message: str,
        *,
        property_name: Optional[str] = None,
        entity: Optional[Any] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(
            message,
            operation="lazy_loading",
            cause=cause
        )
        self.property_name = property_name
        self.entity = entity


class AsyncOperationError(ORMException):
    """Exception raised when async operations fail."""
    
    def __init__(
        self,
        message: str,
        *,
        async_operation: Optional[str] = None,
        task_id: Optional[str] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(
            message,
            operation="async",
            cause=cause
        )
        self.async_operation = async_operation
        self.task_id = task_id


class BatchOperationError(ORMException):
    """Exception raised when batch operations fail."""
    
    def __init__(
        self,
        message: str,
        *,
        batch_size: Optional[int] = None,
        failed_operations: Optional[List[Dict[str, Any]]] = None,
        successful_operations: Optional[int] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(
            message,
            operation="batch",
            cause=cause
        )
        self.batch_size = batch_size
        self.failed_operations = failed_operations or []
        self.successful_operations = successful_operations or 0


class ValidationError(ORMException):
    """Exception raised when entity validation fails."""
    
    def __init__(
        self,
        message: str,
        *,
        validation_errors: Optional[Dict[str, List[str]]] = None,
        entity: Optional[Any] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(
            message,
            operation="validation",
            cause=cause
        )
        self.validation_errors = validation_errors or {}
        self.entity = entity


class ConcurrencyError(ORMException):
    """Exception raised when concurrency conflicts occur."""
    
    def __init__(
        self,
        message: str,
        *,
        entity: Optional[Any] = None,
        conflicting_changes: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(
            message,
            operation="concurrency",
            cause=cause
        )
        self.entity = entity
        self.conflicting_changes = conflicting_changes or {}


class TransactionError(ORMException):
    """Exception raised when transaction operations fail."""
    
    def __init__(
        self,
        message: str,
        *,
        transaction_id: Optional[str] = None,
        transaction_state: Optional[str] = None,
        nested_level: Optional[int] = None,
        cause: Optional[Exception] = None
    ) -> None:
        super().__init__(
            message,
            operation="transaction",
            cause=cause
        )
        self.transaction_id = transaction_id
        self.transaction_state = transaction_state
        self.nested_level = nested_level