"""
Batch processing for Design Automation jobs.

This module provides a ``BatchProcessor`` that can run many
``JobConfig`` items in parallel (bounded by a semaphore), with
automatic retry and optional progress / cancellation callbacks.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from .exceptions import JobExecutionError
from .jobs import JobManager
from .types import (
    BatchConfig,
    BatchResult,
    JobConfig,
    JobResult,
    JobStatus,
)


class BatchProcessor:
    """Processes multiple Design Automation jobs concurrently."""

    def __init__(
        self,
        job_manager: JobManager,
        *,
        config: BatchConfig | None = None,
    ) -> None:
        self._job_manager = job_manager
        self._config = config or BatchConfig()

    async def process(
        self,
        jobs: list[JobConfig],
        progress: Callable[[int, int], Any] | None = None,
        cancel: asyncio.Event | None = None,
    ) -> BatchResult:
        """Process a list of jobs with bounded concurrency.

        Args:
            jobs: Job configurations to process.
            progress: Optional callback ``(completed, total)``.
            cancel: Optional event; when set, no new jobs start.

        Returns:
            ``BatchResult`` with per-job results and aggregate counts.
        """
        start = time.monotonic()
        semaphore = asyncio.Semaphore(self._config.max_parallel)
        results: list[JobResult] = []
        completed = 0
        failed = 0
        cancelled = 0

        async def _run_one(cfg: JobConfig) -> JobResult:
            if cancel is not None and cancel.is_set():
                return JobResult(
                    job_id="",
                    status=JobStatus.CANCELLED,
                )

            async with semaphore:
                return await self._run_with_retry(cfg)

        tasks = [asyncio.create_task(_run_one(cfg)) for cfg in jobs]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)

            if result.status == JobStatus.COMPLETED:
                completed += 1
            elif result.status == JobStatus.FAILED:
                failed += 1
            elif result.status == JobStatus.CANCELLED:
                cancelled += 1

            if progress is not None:
                progress(len(results), len(jobs))

            if not self._config.continue_on_error and result.status == JobStatus.FAILED:
                if cancel is not None:
                    cancel.set()
                break

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            "Batch complete: {}/{} succeeded, {} failed, {} cancelled in {:.0f}ms",
            completed,
            len(jobs),
            failed,
            cancelled,
            elapsed_ms,
        )

        return BatchResult(
            total_jobs=len(jobs),
            completed=completed,
            failed=failed,
            cancelled=cancelled,
            results=results,
            total_duration_ms=elapsed_ms,
        )

    async def process_directory(
        self,
        input_dir: Path,
        script_path: Path,
        *,
        activity_id: str = "RevitPy.Validate+prod",
        **kwargs: Any,
    ) -> BatchResult:
        """Create and process jobs for every ``.rvt`` file in a directory.

        Args:
            input_dir: Directory containing Revit files.
            script_path: Path to the validation script.
            activity_id: Design Automation activity ID.
            **kwargs: Forwarded to :meth:`process`.

        Returns:
            ``BatchResult`` for the discovered files.
        """
        rvt_files = sorted(input_dir.glob("*.rvt"))
        if not rvt_files:
            logger.warning("No .rvt files found in {}", input_dir)
            return BatchResult()

        configs = [
            JobConfig(
                activity_id=activity_id,
                input_file=rvt_file,
                script_path=script_path,
            )
            for rvt_file in rvt_files
        ]

        logger.info("Found {} .rvt files in {}", len(configs), input_dir)
        return await self.process(configs, **kwargs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_with_retry(self, config: JobConfig) -> JobResult:
        """Submit and wait for a single job, retrying on failure."""
        last_error: str | None = None

        for attempt in range(self._config.retry_count + 1):
            try:
                job_id = await self._job_manager.submit(config)
                result = await self._job_manager.wait_for_completion(
                    job_id,
                    timeout=config.timeout,
                )
                return result

            except JobExecutionError as exc:
                last_error = str(exc)
                if attempt < self._config.retry_count:
                    logger.warning(
                        "Job failed (attempt {}/{}), retrying in {:.0f}s: {}",
                        attempt + 1,
                        self._config.retry_count + 1,
                        self._config.retry_delay,
                        exc,
                    )
                    await asyncio.sleep(self._config.retry_delay)
                else:
                    logger.error(
                        "Job failed after {} attempts: {}",
                        self._config.retry_count + 1,
                        exc,
                    )

            except Exception as exc:
                last_error = str(exc)
                logger.error("Unexpected error submitting job: {}", exc)
                break

        return JobResult(
            job_id="",
            status=JobStatus.FAILED,
            error=last_error,
        )
