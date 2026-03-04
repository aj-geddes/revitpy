"""
Type definitions and enums for the RevitPy cloud layer.

This module provides all type definitions, enums, and dataclasses used
throughout the cloud system for APS authentication, Design Automation
job management, batch processing, and webhook handling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class JobStatus(Enum):
    """Status of a Design Automation work item."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class AuthMethod(Enum):
    """OAuth2 authentication methods supported by APS."""

    CLIENT_CREDENTIALS = "client_credentials"
    AUTHORIZATION_CODE = "authorization_code"
    DEVICE_CODE = "device_code"


class CloudRegion(Enum):
    """APS cloud regions."""

    US = "us"
    EMEA = "emea"


@dataclass
class ApsCredentials:
    """Credentials for authenticating with the Autodesk Platform Services."""

    client_id: str
    client_secret: str
    region: CloudRegion = CloudRegion.US


@dataclass
class ApsToken:
    """OAuth2 access token issued by the APS authentication service."""

    access_token: str
    token_type: str = "Bearer"  # noqa: S105
    expires_in: int = 3600
    scope: str = ""
    issued_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Check whether the token has expired (with 60s buffer)."""
        return time.time() >= (self.issued_at + self.expires_in - 60)


@dataclass
class JobConfig:
    """Configuration for a Design Automation work item."""

    activity_id: str
    input_file: str | Path
    output_file: str | Path | None = None
    script_path: str | Path | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout: float = 600.0


@dataclass
class JobResult:
    """Result of a completed Design Automation work item."""

    job_id: str
    status: JobStatus
    output_files: list[str] = field(default_factory=list)
    logs: str = ""
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class BatchConfig:
    """Configuration for batch processing of multiple jobs."""

    max_parallel: int = 5
    retry_count: int = 2
    retry_delay: float = 30.0
    continue_on_error: bool = True


@dataclass
class BatchResult:
    """Aggregated result of a batch processing run."""

    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    results: list[JobResult] = field(default_factory=list)
    total_duration_ms: float = 0.0


@dataclass
class WebhookConfig:
    """Configuration for a webhook listener."""

    url: str
    secret: str
    events: list[str] = field(default_factory=list)


@dataclass
class WebhookEvent:
    """An incoming webhook event from APS."""

    event_type: str
    job_id: str
    status: JobStatus
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)
