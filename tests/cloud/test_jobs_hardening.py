"""
Tests for JobManager download timeouts and streaming-to-disk behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from revitpy.cloud.jobs import JobManager

_REAL_ASYNC_CLIENT = httpx.AsyncClient
_JOBS_TARGET = "revitpy.cloud.jobs.httpx.AsyncClient"

Handler = Callable[[httpx.Request], httpx.Response]


def _fake_http(module_path: str, handler: Handler, calls: list[dict[str, Any]]):
    """Patch ``httpx.AsyncClient`` with a real client on a MockTransport."""

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        calls.append(kwargs)
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    return patch(module_path, side_effect=factory)


def _respond(response: httpx.Response) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return response

    return handler


class TestDownloadTimeouts:
    """Downloads and log fetches use the client's download timeout."""

    @pytest.mark.asyncio
    async def test_download_results_uses_download_timeout(
        self, mock_aps_client, tmp_output_dir
    ):
        mock_aps_client.get = AsyncMock(
            return_value={"outputFiles": ["https://s3.example.com/b/out.json"]}
        )
        calls: list[dict[str, Any]] = []

        with _fake_http(
            _JOBS_TARGET, _respond(httpx.Response(200, content=b"{}")), calls
        ):
            await JobManager(mock_aps_client).download_results("job-1", tmp_output_dir)

        assert calls[0]["timeout"] is mock_aps_client.download_timeout
        assert calls[0]["follow_redirects"] is True

    @pytest.mark.asyncio
    async def test_get_logs_uses_download_timeout(self, mock_aps_client):
        mock_aps_client.get = AsyncMock(
            return_value={"reportUrl": "https://logs.example.com/r.txt"}
        )
        calls: list[dict[str, Any]] = []

        with _fake_http(
            _JOBS_TARGET, _respond(httpx.Response(200, text="log line")), calls
        ):
            logs = await JobManager(mock_aps_client).get_logs("job-1")

        assert logs == "log line"
        assert calls[0]["timeout"] is mock_aps_client.download_timeout
        assert calls[0]["follow_redirects"] is True


class TestStreamingDownload:
    """Outputs are streamed to disk via a .part file."""

    @pytest.mark.asyncio
    async def test_large_file_streamed_and_query_stripped(
        self, mock_aps_client, tmp_output_dir
    ):
        body = bytes(range(256)) * 12288  # 3 MiB
        url = "https://s3.example.com/bucket/result.rvt?X-Amz-Signature=abc"
        mock_aps_client.get = AsyncMock(return_value={"outputFiles": [url]})

        with _fake_http(_JOBS_TARGET, _respond(httpx.Response(200, content=body)), []):
            paths = await JobManager(mock_aps_client).download_results(
                "job-1", tmp_output_dir
            )

        assert [p.name for p in paths] == ["result.rvt"]
        assert paths[0].read_bytes() == body
        assert list(tmp_output_dir.glob("*.part")) == []

    @pytest.mark.asyncio
    async def test_http_error_cleans_up_partial_file(
        self, mock_aps_client, tmp_output_dir
    ):
        mock_aps_client.get = AsyncMock(
            return_value={"outputFiles": ["https://s3.example.com/bucket/result.rvt"]}
        )

        with _fake_http(_JOBS_TARGET, _respond(httpx.Response(404, content=b"no")), []):
            with pytest.raises(httpx.HTTPStatusError):
                await JobManager(mock_aps_client).download_results(
                    "job-1", tmp_output_dir
                )

        assert list(tmp_output_dir.iterdir()) == []

    @pytest.mark.asyncio
    async def test_empty_segment_falls_back_to_index_name(
        self, mock_aps_client, tmp_output_dir
    ):
        mock_aps_client.get = AsyncMock(
            return_value={"outputFiles": ["https://s3.example.com/bucket/"]}
        )

        with _fake_http(_JOBS_TARGET, _respond(httpx.Response(200, content=b"t")), []):
            paths = await JobManager(mock_aps_client).download_results(
                "job-1", tmp_output_dir
            )

        assert paths == [tmp_output_dir / "output_0"]
        assert paths[0].read_bytes() == b"t"

    @pytest.mark.asyncio
    async def test_traversal_segment_is_neutralised(
        self, mock_aps_client, tmp_output_dir
    ):
        mock_aps_client.get = AsyncMock(
            return_value={"outputFiles": ["https://s3.example.com/a/..%2F..%2Fevil.sh"]}
        )

        with _fake_http(_JOBS_TARGET, _respond(httpx.Response(200, content=b"t")), []):
            paths = await JobManager(mock_aps_client).download_results(
                "job-1", tmp_output_dir
            )

        assert paths[0].parent == tmp_output_dir
