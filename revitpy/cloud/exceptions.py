"""
Cloud-specific exceptions for RevitPy.

This module defines all exceptions used throughout the cloud layer,
providing specific error types for authentication, job management,
APS API interactions, and webhook handling.
"""

from __future__ import annotations

from typing import Any


class CloudError(Exception):
    """Base exception for all cloud-related errors."""

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


class AuthenticationError(CloudError):
    """Exception raised when authentication with APS fails."""

    def __init__(
        self,
        message: str,
        *,
        auth_method: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.auth_method = auth_method


class JobSubmissionError(CloudError):
    """Exception raised when a job cannot be submitted."""

    def __init__(
        self,
        message: str,
        *,
        job_config: Any | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.job_config = job_config


class JobExecutionError(CloudError):
    """Exception raised when a job execution fails."""

    def __init__(
        self,
        message: str,
        *,
        job_id: str | None = None,
        status: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.job_id = job_id
        self.status = status


class ApsApiError(CloudError):
    """Exception raised when an APS API call fails."""

    def __init__(
        self,
        message: str,
        *,
        endpoint: str | None = None,
        status_code: int | None = None,
        response_body: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_body = response_body


class WebhookError(CloudError):
    """Exception raised when webhook handling fails."""

    def __init__(
        self,
        message: str,
        *,
        event_type: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.event_type = event_type
