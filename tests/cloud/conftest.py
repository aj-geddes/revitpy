"""
Pytest configuration and shared fixtures for cloud module tests.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from revitpy.cloud.auth import ApsAuthenticator
from revitpy.cloud.client import ApsClient
from revitpy.cloud.jobs import JobManager
from revitpy.cloud.types import (
    ApsCredentials,
    ApsToken,
    BatchConfig,
    CloudRegion,
    JobConfig,
)


@pytest.fixture
def mock_credentials() -> ApsCredentials:
    """Provide mock APS credentials."""
    return ApsCredentials(
        client_id="test-client-id",
        client_secret="test-client-secret",
        region=CloudRegion.US,
    )


@pytest.fixture
def mock_aps_token() -> ApsToken:
    """Provide a mock APS token that is not expired."""
    return ApsToken(
        access_token="mock-access-token-12345",
        token_type="Bearer",
        expires_in=3600,
        scope="code:all data:write data:read",
    )


@pytest.fixture
def mock_authenticator(mock_aps_token) -> ApsAuthenticator:
    """Provide an authenticator with a mocked get_token method."""
    auth = MagicMock(spec=ApsAuthenticator)
    auth.get_token = AsyncMock(return_value=mock_aps_token)
    auth.is_token_valid = MagicMock(return_value=True)
    return auth


@pytest.fixture
def mock_aps_client(mock_authenticator) -> ApsClient:
    """Provide an APS client with mocked HTTP responses."""
    client = MagicMock(spec=ApsClient)
    client._authenticator = mock_authenticator
    client._region = CloudRegion.US
    client.get = AsyncMock(return_value={})
    client.post = AsyncMock(return_value={"id": "mock-job-123"})
    client.delete = AsyncMock(return_value={})
    client.request = AsyncMock(return_value={})
    return client


@pytest.fixture
def sample_job_config() -> JobConfig:
    """Provide a sample job configuration."""
    return JobConfig(
        activity_id="RevitPy.Validate+prod",
        input_file="https://storage.example.com/input.rvt",
        output_file="https://storage.example.com/output.json",
        script_path="https://storage.example.com/validate.py",
        parameters={"version": "2024"},
        timeout=300.0,
    )


@pytest.fixture
def sample_batch_config() -> BatchConfig:
    """Provide a sample batch configuration."""
    return BatchConfig(
        max_parallel=3,
        retry_count=1,
        retry_delay=1.0,
        continue_on_error=True,
    )


@pytest.fixture
def mock_job_manager(mock_aps_client) -> JobManager:
    """Provide a job manager with a mocked client."""
    return JobManager(mock_aps_client)


@pytest.fixture
def tmp_output_dir():
    """Provide a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
