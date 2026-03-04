"""
Design Automation job management for RevitPy.

This module wraps the APS Design Automation v3 WorkItems API, providing
high-level operations for submitting, polling, downloading, and
cancelling cloud-based Revit processing jobs.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx
from loguru import logger

from .client import ApsClient
from .exceptions import JobExecutionError, JobSubmissionError
from .types import JobConfig, JobResult, JobStatus

DA_BASE = "/da/us-east/v3/workitems"


class JobManager:
    """Manages Design Automation work items through the APS API."""

    def __init__(self, client: ApsClient) -> None:
        self._client = client

    async def submit(self, config: JobConfig) -> str:
        """Submit a new Design Automation work item.

        Args:
            config: Job configuration with activity, input/output files,
                and optional parameters.

        Returns:
            The ``job_id`` of the newly created work item.

        Raises:
            JobSubmissionError: If the API rejects the work item.
        """
        payload: dict = {
            "activityId": config.activity_id,
            "arguments": {
                "inputFile": {
                    "url": str(config.input_file),
                    "verb": "get",
                },
            },
        }

        if config.output_file is not None:
            payload["arguments"]["outputFile"] = {
                "url": str(config.output_file),
                "verb": "put",
            }

        if config.script_path is not None:
            payload["arguments"]["scriptPath"] = {
                "url": str(config.script_path),
                "verb": "get",
            }

        if config.parameters:
            payload["arguments"]["parameters"] = config.parameters

        try:
            response = await self._client.post(
                DA_BASE,
                json=payload,
            )
        except Exception as exc:
            raise JobSubmissionError(
                f"Failed to submit job for activity '{config.activity_id}'",
                job_config=config,
                cause=exc,
            ) from exc

        job_id = response.get("id", "")
        if not job_id:
            raise JobSubmissionError(
                "APS returned a response without a job ID",
                job_config=config,
            )

        logger.info("Submitted job {}", job_id)
        return job_id

    async def get_status(self, job_id: str) -> JobStatus:
        """Get the current status of a work item.

        Args:
            job_id: The work-item identifier.

        Returns:
            Current ``JobStatus``.
        """
        response = await self._client.get(f"{DA_BASE}/{job_id}")
        raw = response.get("status", "pending")
        return _parse_status(raw)

    async def wait_for_completion(
        self,
        job_id: str,
        timeout: float = 600.0,
        poll_interval: float = 5.0,
    ) -> JobResult:
        """Poll a work item until it reaches a terminal state.

        Args:
            job_id: The work-item identifier.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between status polls.

        Returns:
            ``JobResult`` with the final status and metadata.

        Raises:
            JobExecutionError: If the job fails or times out.
        """
        start = time.monotonic()

        while True:
            elapsed_ms = (time.monotonic() - start) * 1000
            if (time.monotonic() - start) > timeout:
                raise JobExecutionError(
                    f"Job {job_id} timed out after {timeout}s",
                    job_id=job_id,
                    status="timed_out",
                )

            response = await self._client.get(f"{DA_BASE}/{job_id}")
            status = _parse_status(response.get("status", "pending"))

            if status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
                JobStatus.TIMED_OUT,
            ):
                result = JobResult(
                    job_id=job_id,
                    status=status,
                    output_files=response.get("outputFiles", []),
                    logs=response.get("reportUrl", ""),
                    duration_ms=elapsed_ms,
                    error=response.get("error"),
                )

                if status == JobStatus.FAILED:
                    raise JobExecutionError(
                        f"Job {job_id} failed: {result.error or 'unknown error'}",
                        job_id=job_id,
                        status=status.value,
                    )

                logger.info("Job {} finished with status {}", job_id, status.value)
                return result

            logger.debug(
                "Job {} status: {} ({:.0f}ms elapsed)",
                job_id,
                status.value,
                elapsed_ms,
            )
            await asyncio.sleep(poll_interval)

    async def download_results(
        self,
        job_id: str,
        output_dir: Path,
    ) -> list[Path]:
        """Download output files for a completed work item.

        Args:
            job_id: The work-item identifier.
            output_dir: Local directory to save files to.

        Returns:
            List of local ``Path`` objects for the downloaded files.
        """
        response = await self._client.get(f"{DA_BASE}/{job_id}")
        output_urls: list[str] = response.get("outputFiles", [])
        output_dir.mkdir(parents=True, exist_ok=True)

        downloaded: list[Path] = []
        async with httpx.AsyncClient() as http:
            for url in output_urls:
                filename = url.rsplit("/", 1)[-1] or f"output_{len(downloaded)}"
                dest = output_dir / filename
                resp = await http.get(url)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
                downloaded.append(dest)
                logger.debug("Downloaded {} -> {}", url, dest)

        return downloaded

    async def cancel(self, job_id: str) -> bool:
        """Cancel a running work item.

        Args:
            job_id: The work-item identifier.

        Returns:
            ``True`` if the cancellation succeeded.
        """
        try:
            await self._client.delete(f"{DA_BASE}/{job_id}")
            logger.info("Cancelled job {}", job_id)
            return True
        except Exception:
            logger.warning("Failed to cancel job {}", job_id)
            return False

    async def get_logs(self, job_id: str) -> str:
        """Retrieve execution logs for a work item.

        Args:
            job_id: The work-item identifier.

        Returns:
            Log text as a string.
        """
        response = await self._client.get(f"{DA_BASE}/{job_id}")
        report_url = response.get("reportUrl", "")
        if not report_url:
            return ""

        async with httpx.AsyncClient() as http:
            resp = await http.get(report_url)
            resp.raise_for_status()
            return resp.text


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_STATUS_MAP: dict[str, JobStatus] = {s.value: s for s in JobStatus}


def _parse_status(raw: str) -> JobStatus:
    """Map a raw status string to a ``JobStatus`` enum member."""
    return _STATUS_MAP.get(raw.lower(), JobStatus.PENDING)
