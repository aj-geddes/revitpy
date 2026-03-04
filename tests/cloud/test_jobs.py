"""
Tests for the Design Automation job manager module.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from revitpy.cloud.exceptions import JobExecutionError, JobSubmissionError
from revitpy.cloud.jobs import DA_BASE, JobManager
from revitpy.cloud.types import JobConfig, JobResult, JobStatus


class TestJobManager:
    """Tests for JobManager."""

    @pytest.mark.asyncio
    async def test_submit_returns_job_id(self, mock_aps_client, sample_job_config):
        """submit() should POST to the DA API and return a job ID."""
        mock_aps_client.post = AsyncMock(return_value={"id": "job-abc-123"})

        manager = JobManager(mock_aps_client)
        job_id = await manager.submit(sample_job_config)

        assert job_id == "job-abc-123"
        mock_aps_client.post.assert_awaited_once()
        call_args = mock_aps_client.post.call_args
        assert call_args[0][0] == DA_BASE

    @pytest.mark.asyncio
    async def test_submit_includes_activity_id(
        self, mock_aps_client, sample_job_config
    ):
        """submit() payload should contain the activity ID."""
        mock_aps_client.post = AsyncMock(return_value={"id": "job-1"})

        manager = JobManager(mock_aps_client)
        await manager.submit(sample_job_config)

        payload = mock_aps_client.post.call_args[1]["json"]
        assert payload["activityId"] == sample_job_config.activity_id

    @pytest.mark.asyncio
    async def test_submit_includes_optional_fields(self, mock_aps_client):
        """submit() should include output_file, script_path, and parameters."""
        config = JobConfig(
            activity_id="Test.Activity+prod",
            input_file="https://example.com/input.rvt",
            output_file="https://example.com/output.json",
            script_path="https://example.com/script.py",
            parameters={"version": "2024"},
        )
        mock_aps_client.post = AsyncMock(return_value={"id": "job-2"})

        manager = JobManager(mock_aps_client)
        await manager.submit(config)

        payload = mock_aps_client.post.call_args[1]["json"]
        assert "outputFile" in payload["arguments"]
        assert "scriptPath" in payload["arguments"]
        assert "parameters" in payload["arguments"]

    @pytest.mark.asyncio
    async def test_submit_raises_on_empty_response(
        self, mock_aps_client, sample_job_config
    ):
        """submit() should raise JobSubmissionError if no ID in response."""
        mock_aps_client.post = AsyncMock(return_value={})

        manager = JobManager(mock_aps_client)
        with pytest.raises(JobSubmissionError):
            await manager.submit(sample_job_config)

    @pytest.mark.asyncio
    async def test_submit_raises_on_api_failure(
        self, mock_aps_client, sample_job_config
    ):
        """submit() should raise JobSubmissionError if the API call fails."""
        mock_aps_client.post = AsyncMock(side_effect=RuntimeError("network error"))

        manager = JobManager(mock_aps_client)
        with pytest.raises(JobSubmissionError) as exc_info:
            await manager.submit(sample_job_config)

        assert exc_info.value.job_config is sample_job_config

    @pytest.mark.asyncio
    async def test_get_status_returns_enum(self, mock_aps_client):
        """get_status() should return a JobStatus enum value."""
        mock_aps_client.get = AsyncMock(return_value={"status": "running"})

        manager = JobManager(mock_aps_client)
        status = await manager.get_status("job-1")

        assert status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_get_status_defaults_to_pending(self, mock_aps_client):
        """get_status() should default to PENDING for unknown statuses."""
        mock_aps_client.get = AsyncMock(return_value={"status": "unknown_status"})

        manager = JobManager(mock_aps_client)
        status = await manager.get_status("job-1")

        assert status == JobStatus.PENDING

    @pytest.mark.asyncio
    async def test_wait_for_completion_success(self, mock_aps_client):
        """wait_for_completion should return a result once completed."""
        mock_aps_client.get = AsyncMock(
            side_effect=[
                {"status": "running"},
                {"status": "running"},
                {
                    "status": "completed",
                    "outputFiles": ["out.json"],
                    "reportUrl": "https://logs.example.com/1",
                },
            ]
        )

        manager = JobManager(mock_aps_client)

        with patch("revitpy.cloud.jobs.asyncio.sleep", new_callable=AsyncMock):
            result = await manager.wait_for_completion(
                "job-1", timeout=60.0, poll_interval=0.01
            )

        assert isinstance(result, JobResult)
        assert result.status == JobStatus.COMPLETED
        assert result.job_id == "job-1"

    @pytest.mark.asyncio
    async def test_wait_for_completion_raises_on_failure(self, mock_aps_client):
        """wait_for_completion should raise JobExecutionError on failure."""
        mock_aps_client.get = AsyncMock(
            return_value={
                "status": "failed",
                "error": "Model validation error",
            }
        )

        manager = JobManager(mock_aps_client)

        with pytest.raises(JobExecutionError) as exc_info:
            await manager.wait_for_completion("job-1", timeout=10.0)

        assert exc_info.value.job_id == "job-1"
        assert exc_info.value.status == "failed"

    @pytest.mark.asyncio
    async def test_wait_for_completion_timeout(self, mock_aps_client):
        """wait_for_completion should raise on timeout."""
        mock_aps_client.get = AsyncMock(return_value={"status": "running"})

        manager = JobManager(mock_aps_client)

        with patch("revitpy.cloud.jobs.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(JobExecutionError) as exc_info:
                await manager.wait_for_completion(
                    "job-1", timeout=0.0, poll_interval=0.01
                )

        assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cancel_returns_true_on_success(self, mock_aps_client):
        """cancel() should return True when the DELETE succeeds."""
        mock_aps_client.delete = AsyncMock(return_value={})

        manager = JobManager(mock_aps_client)
        result = await manager.cancel("job-1")

        assert result is True
        mock_aps_client.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cancel_returns_false_on_failure(self, mock_aps_client):
        """cancel() should return False when the DELETE fails."""
        mock_aps_client.delete = AsyncMock(side_effect=RuntimeError("fail"))

        manager = JobManager(mock_aps_client)
        result = await manager.cancel("job-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_logs_returns_text(self, mock_aps_client):
        """get_logs() should fetch and return the report text."""
        mock_aps_client.get = AsyncMock(
            return_value={"reportUrl": "https://logs.example.com/report"}
        )

        log_text = "Processing model... Done."
        mock_response = MagicMock()
        mock_response.text = log_text
        mock_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.jobs.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            manager = JobManager(mock_aps_client)
            logs = await manager.get_logs("job-1")

        assert logs == log_text

    @pytest.mark.asyncio
    async def test_get_logs_empty_when_no_report_url(self, mock_aps_client):
        """get_logs() should return empty string when no reportUrl."""
        mock_aps_client.get = AsyncMock(return_value={})

        manager = JobManager(mock_aps_client)
        logs = await manager.get_logs("job-1")

        assert logs == ""

    @pytest.mark.asyncio
    async def test_download_results(self, mock_aps_client, tmp_output_dir):
        """download_results() should download files to the output dir."""
        mock_aps_client.get = AsyncMock(
            return_value={
                "outputFiles": [
                    "https://storage.example.com/result.json",
                ]
            }
        )

        mock_response = MagicMock()
        mock_response.content = b'{"result": "ok"}'
        mock_response.raise_for_status = MagicMock()

        with patch("revitpy.cloud.jobs.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            manager = JobManager(mock_aps_client)
            paths = await manager.download_results("job-1", tmp_output_dir)

        assert len(paths) == 1
        assert paths[0].exists()
        assert paths[0].name == "result.json"
