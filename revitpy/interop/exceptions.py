"""
Interop-specific exceptions for RevitPy.

This module defines all exceptions used throughout the interop layer,
providing specific error types for Speckle connectivity, synchronisation,
type mapping, and merge conflict resolution.
"""

from __future__ import annotations


class InteropError(Exception):
    """Base exception for all interop-related errors."""

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


class SpeckleConnectionError(InteropError):
    """Exception raised when a connection to a Speckle server fails."""

    def __init__(
        self,
        message: str,
        *,
        server_url: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.server_url = server_url


class SpeckleSyncError(InteropError):
    """Exception raised when a Speckle synchronisation operation fails."""

    def __init__(
        self,
        message: str,
        *,
        stream_id: str | None = None,
        direction: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.stream_id = stream_id
        self.direction = direction


class TypeMappingError(InteropError):
    """Exception raised when type mapping between systems fails."""

    def __init__(
        self,
        message: str,
        *,
        source_type: str | None = None,
        target_type: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.source_type = source_type
        self.target_type = target_type


class MergeConflictError(InteropError):
    """Exception raised when merge conflicts cannot be resolved."""

    def __init__(
        self,
        message: str,
        *,
        element_id: str | None = None,
        conflicts: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.element_id = element_id
        self.conflicts = conflicts or []
