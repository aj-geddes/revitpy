"""
Tests for the batch processing module.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from revitpy.cloud.batch import BatchProcessor
from revitpy.cloud.exceptions import JobExecutionError
from revitpy.cloud.jobs import JobManager
from revitpy.cloud.types import (
    BatchConfig,
    BatchResult,
    JobConfig,
    JobResult,
    JobStatus,
)


def _make_job_config(idx: int) -> JobConfig:
    """Create a dummy job config for testing."""
    return JobConfig(
        activity_id="Test.Activity+prod",
        input_file=f"https://storage.example.com/file_{idx}.rvt",
    )


class TestBatchProcessor:
    """Tests for BatchProcessor."""

    def test_init_with_defaults(self, mock_job_manager):
        """BatchProcessor should use default config when none provided."""
        processor = BatchProcessor(mock_job_manager)
        assert processor._config.max_parallel == 5
        assert processor._config.retry_count == 2

    def test_init_with_custom_config(self, mock_job_manager, sample_batch_config):
        """BatchProcessor should use the provided config."""
        processor = BatchProcessor(mock_job_manager, config=sample_batch_config)
        assert processor._config.max_parallel == 3
        assert processor._config.retry_count == 1

    @pytest.mark.asyncio
    async def test_process_all_succeed(self, mock_aps_client):
        """process() should return BatchResult with all completed."""
        job_manager = MagicMock(spec=JobManager)
        job_manager.submit = AsyncMock(return_value="job-1")
        job_manager.wait_for_completion = AsyncMock(
            return_value=JobResult(
                job_id="job-1",
                status=JobStatus.COMPLETED,
            )
        )

        config = BatchConfig(
            max_parallel=2,
            retry_count=0,
            retry_delay=0.0,
        )
        processor = BatchProcessor(job_manager, config=config)
        jobs = [_make_job_config(i) for i in range(3)]

        result = await processor.process(jobs)

        assert isinstance(result, BatchResult)
        assert result.total_jobs == 3
        assert result.completed == 3
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_process_with_failures(self, mock_aps_client):
        """process() should track failed jobs."""
        call_count = 0

        async def mock_submit(cfg):
            nonlocal call_count
            call_count += 1
            return f"job-{call_count}"

        async def mock_wait(job_id, timeout=600.0):
            if job_id == "job-2":
                raise JobExecutionError(
                    "Job failed",
                    job_id=job_id,
                    status="failed",
                )
            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
            )

        job_manager = MagicMock(spec=JobManager)
        job_manager.submit = AsyncMock(side_effect=mock_submit)
        job_manager.wait_for_completion = AsyncMock(side_effect=mock_wait)

        config = BatchConfig(
            max_parallel=5,
            retry_count=0,
            retry_delay=0.0,
            continue_on_error=True,
        )
        processor = BatchProcessor(job_manager, config=config)
        jobs = [_make_job_config(i) for i in range(3)]

        result = await processor.process(jobs)

        assert result.total_jobs == 3
        assert result.completed == 2
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_process_with_retry(self, mock_aps_client):
        """process() should retry failed jobs up to retry_count."""
        submit_count = 0

        async def mock_submit(cfg):
            nonlocal submit_count
            submit_count += 1
            return f"job-{submit_count}"

        attempt_tracker: dict[str, int] = {}

        async def mock_wait(job_id, timeout=600.0):
            attempt_tracker.setdefault(job_id, 0)
            attempt_tracker[job_id] += 1

            # First attempt fails, retry succeeds
            if submit_count <= 1 and attempt_tracker.get(job_id, 0) == 1:
                raise JobExecutionError(
                    "Transient error",
                    job_id=job_id,
                    status="failed",
                )
            return JobResult(
                job_id=job_id,
                status=JobStatus.COMPLETED,
            )

        job_manager = MagicMock(spec=JobManager)
        job_manager.submit = AsyncMock(side_effect=mock_submit)
        job_manager.wait_for_completion = AsyncMock(side_effect=mock_wait)

        config = BatchConfig(
            max_parallel=1,
            retry_count=2,
            retry_delay=0.0,
        )
        processor = BatchProcessor(job_manager, config=config)
        jobs = [_make_job_config(0)]

        with patch(
            "revitpy.cloud.batch.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await processor.process(jobs)

        assert result.completed == 1
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_process_progress_callback(self, mock_aps_client):
        """process() should invoke the progress callback."""
        job_manager = MagicMock(spec=JobManager)
        job_manager.submit = AsyncMock(return_value="job-1")
        job_manager.wait_for_completion = AsyncMock(
            return_value=JobResult(
                job_id="job-1",
                status=JobStatus.COMPLETED,
            )
        )

        config = BatchConfig(
            max_parallel=5,
            retry_count=0,
            retry_delay=0.0,
        )
        processor = BatchProcessor(job_manager, config=config)
        jobs = [_make_job_config(i) for i in range(2)]

        progress_calls = []

        def on_progress(done, total):
            progress_calls.append((done, total))

        await processor.process(jobs, progress=on_progress)

        assert len(progress_calls) == 2
        assert progress_calls[-1] == (2, 2)

    @pytest.mark.asyncio
    async def test_process_cancel_event(self, mock_aps_client):
        """process() should stop submitting when cancel is set."""
        job_manager = MagicMock(spec=JobManager)
        job_manager.submit = AsyncMock(return_value="job-1")
        job_manager.wait_for_completion = AsyncMock(
            return_value=JobResult(
                job_id="job-1",
                status=JobStatus.COMPLETED,
            )
        )

        config = BatchConfig(
            max_parallel=1,
            retry_count=0,
            retry_delay=0.0,
        )
        processor = BatchProcessor(job_manager, config=config)

        cancel_event = asyncio.Event()
        cancel_event.set()  # Pre-cancel

        jobs = [_make_job_config(i) for i in range(3)]
        result = await processor.process(jobs, cancel=cancel_event)

        assert result.cancelled == 3

    @pytest.mark.asyncio
    async def test_process_directory(self, mock_aps_client, tmp_output_dir):
        """process_directory() should find .rvt files and process them."""
        # Create fake .rvt files
        for i in range(3):
            (tmp_output_dir / f"model_{i}.rvt").touch()

        # Also create a non-rvt file that should be ignored
        (tmp_output_dir / "readme.txt").touch()

        job_manager = MagicMock(spec=JobManager)
        job_manager.submit = AsyncMock(return_value="job-dir")
        job_manager.wait_for_completion = AsyncMock(
            return_value=JobResult(
                job_id="job-dir",
                status=JobStatus.COMPLETED,
            )
        )

        config = BatchConfig(
            max_parallel=5,
            retry_count=0,
            retry_delay=0.0,
        )
        processor = BatchProcessor(job_manager, config=config)

        result = await processor.process_directory(
            tmp_output_dir,
            Path("validate.py"),
        )

        assert result.total_jobs == 3
        assert result.completed == 3

    @pytest.mark.asyncio
    async def test_process_directory_empty(self, mock_aps_client, tmp_output_dir):
        """process_directory() should return empty result for no .rvt files."""
        job_manager = MagicMock(spec=JobManager)
        config = BatchConfig(retry_count=0, retry_delay=0.0)
        processor = BatchProcessor(job_manager, config=config)

        result = await processor.process_directory(
            tmp_output_dir,
            Path("validate.py"),
        )

        assert result.total_jobs == 0
