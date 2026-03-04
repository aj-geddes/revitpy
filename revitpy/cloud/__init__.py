"""
RevitPy Cloud Layer - APS integration, Design Automation, and CI/CD.

This module provides cloud-based Revit processing capabilities through
the Autodesk Platform Services (APS), including authentication, Design
Automation job management, batch processing, CI/CD configuration
generation, and webhook handling.

Key Features:
- OAuth2 authentication with APS
- Design Automation work-item submission and monitoring
- Batch processing with bounded concurrency and retry
- GitHub Actions / GitLab CI pipeline generation
- Webhook signature verification and event routing

Usage:
    from revitpy.cloud import submit_job, batch_process

    job_id = await submit_job(credentials, config)
    result = await batch_process(credentials, configs)
"""

from .auth import ApsAuthenticator
from .batch import BatchProcessor
from .ci import CIHelper
from .client import ApsClient
from .exceptions import (
    ApsApiError,
    AuthenticationError,
    CloudError,
    JobExecutionError,
    JobSubmissionError,
    WebhookError,
)
from .jobs import JobManager
from .types import (
    ApsCredentials,
    ApsToken,
    AuthMethod,
    BatchConfig,
    BatchResult,
    CloudRegion,
    JobConfig,
    JobResult,
    JobStatus,
    WebhookConfig,
    WebhookEvent,
)
from .webhooks import WebhookHandler

__all__ = [
    # Authentication
    "ApsAuthenticator",
    "ApsCredentials",
    "ApsToken",
    "AuthMethod",
    # Client
    "ApsClient",
    "CloudRegion",
    # Job management
    "JobManager",
    "JobConfig",
    "JobResult",
    "JobStatus",
    # Batch processing
    "BatchProcessor",
    "BatchConfig",
    "BatchResult",
    # CI/CD
    "CIHelper",
    # Webhooks
    "WebhookHandler",
    "WebhookConfig",
    "WebhookEvent",
    # Exceptions
    "CloudError",
    "AuthenticationError",
    "ApsApiError",
    "JobSubmissionError",
    "JobExecutionError",
    "WebhookError",
]


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


async def submit_job(
    credentials: ApsCredentials,
    config: JobConfig,
) -> str:
    """Submit a single Design Automation job.

    Convenience wrapper that creates an authenticator, client, and
    job manager, then submits the work item.

    Args:
        credentials: APS OAuth2 credentials.
        config: Job configuration.

    Returns:
        The ``job_id`` of the submitted work item.
    """
    auth = ApsAuthenticator(credentials)
    client = ApsClient(auth, region=credentials.region)
    manager = JobManager(client)
    return await manager.submit(config)


async def batch_process(
    credentials: ApsCredentials,
    configs: list[JobConfig],
    *,
    batch_config: BatchConfig | None = None,
) -> BatchResult:
    """Process multiple Design Automation jobs concurrently.

    Args:
        credentials: APS OAuth2 credentials.
        configs: List of job configurations.
        batch_config: Optional batch settings (parallelism, retry, etc.).

    Returns:
        ``BatchResult`` with per-job results and aggregate counts.
    """
    auth = ApsAuthenticator(credentials)
    client = ApsClient(auth, region=credentials.region)
    manager = JobManager(client)
    processor = BatchProcessor(manager, config=batch_config)
    return await processor.process(configs)


def generate_ci_config(
    provider: str = "github",
    **kwargs,
) -> str:
    """Generate a CI/CD pipeline configuration.

    Args:
        provider: ``"github"`` or ``"gitlab"``.
        **kwargs: Forwarded to the generator method.

    Returns:
        YAML string for the requested CI provider.

    Raises:
        ValueError: If the provider is not supported.
    """
    helper = CIHelper()
    if provider == "github":
        return helper.generate_github_workflow(**kwargs)
    if provider == "gitlab":
        return helper.generate_gitlab_ci(**kwargs)
    msg = f"Unsupported CI provider: {provider!r}"
    raise ValueError(msg)
