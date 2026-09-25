"""
Client for the RevitPy Live Server (JSON-RPC 2.0 over WebSocket inside Revit).

Connection details come from the discovery file the server writes
(``~/.revitpy/live.json``, or ``REVITPY_LIVE_DISCOVERY``)::

    import asyncio
    from revitpy.live_client import LiveClient, call_live

    print(call_live("live/status"))             # one-off, synchronous

    async def main() -> None:
        async with LiveClient() as client:      # one connection, many calls
            result = await client.run_file("C:/scripts/report.py")
            print(result["output"])

    asyncio.run(main())

See ``docs/developer/live-server.md`` for the protocol.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "LiveClient",
    "LiveConnectionInfo",
    "LiveServerError",
    "LiveServerNotFoundError",
    "call_live",
]

SUPPORTED_PROTOCOL = 1


class LiveServerNotFoundError(RuntimeError):
    """No running Live Server could be found."""


class LiveServerError(RuntimeError):
    """The Live Server answered with a JSON-RPC error."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"{message} (code {code})")
        self.code = code
        self.message = message


def _discovery_path() -> Path:
    override = os.environ.get("REVITPY_LIVE_DISCOVERY")
    return Path(override) if override else Path.home() / ".revitpy" / "live.json"


@dataclass(frozen=True)
class LiveConnectionInfo:
    url: str
    token: str
    protocol: int = SUPPORTED_PROTOCOL
    revit_version: str | None = None
    pid: int | None = None

    @classmethod
    def from_discovery(cls, path: Path | None = None) -> LiveConnectionInfo:
        """Read the discovery file written by a running Live Server."""
        path = path or _discovery_path()
        hint = (
            "Start it from the RevitPy ribbon in Revit, or set "
            "start_live_server = true in %APPDATA%\\RevitPy\\settings.ini."
        )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise LiveServerNotFoundError(
                f"RevitPy Live Server is not running (no {path}). {hint}"
            ) from None
        except (OSError, ValueError) as exc:
            raise LiveServerNotFoundError(
                f"Unreadable Live Server discovery file {path}: {exc}"
            ) from exc
        if not isinstance(data, dict) or not {"url", "token"} <= data.keys():
            raise LiveServerNotFoundError(f"Invalid Live Server discovery file {path}")
        protocol = int(data.get("protocol", SUPPORTED_PROTOCOL))
        if protocol != SUPPORTED_PROTOCOL:
            raise LiveServerError(
                0,
                f"Live Server speaks protocol {protocol}; this client supports "
                f"{SUPPORTED_PROTOCOL}. Update revitpy on one side.",
            )
        return cls(
            url=str(data["url"]),
            token=str(data["token"]),
            protocol=protocol,
            revit_version=data.get("revit_version"),
            pid=data.get("pid"),
        )


def _connect(url: str, headers: dict[str, str], timeout: float) -> Any:
    """Return an async context manager connecting with *headers*."""
    try:
        from websockets.asyncio.client import connect
    except ImportError:  # websockets < 13
        from websockets.client import connect as legacy_connect

        return legacy_connect(
            url, extra_headers=headers, max_size=None, open_timeout=timeout
        )
    return connect(url, additional_headers=headers, max_size=None, open_timeout=timeout)


class LiveClient:
    """One WebSocket connection to the Live Server; use as ``async with``."""

    def __init__(
        self, info: LiveConnectionInfo | None = None, *, timeout: float = 330.0
    ) -> None:
        self._info = info or LiveConnectionInfo.from_discovery()
        self._timeout = timeout
        self._connection: Any = None
        self._websocket: Any = None
        self._next_id = 0

    @property
    def info(self) -> LiveConnectionInfo:
        return self._info

    async def __aenter__(self) -> LiveClient:
        headers = {"Authorization": f"Bearer {self._info.token}"}
        connection = _connect(self._info.url, headers, min(self._timeout, 30.0))
        try:
            self._websocket = await connection.__aenter__()
        except OSError as exc:
            raise LiveServerNotFoundError(
                f"Cannot reach the RevitPy Live Server at {self._info.url} ({exc}). "
                "Is Revit running with the Live Server started?"
            ) from exc
        except Exception as exc:  # handshake rejected (bad/stale token, ...)
            raise LiveServerError(
                0, f"Live Server at {self._info.url} refused the connection: {exc}"
            ) from exc
        self._connection = connection
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        connection, self._connection, self._websocket = self._connection, None, None
        if connection is not None:
            await connection.__aexit__(*exc_info)

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send one request and return its ``result``.

        Raises:
            LiveServerError: The server returned a JSON-RPC error.
            TimeoutError: No response within the client timeout.
        """
        if self._websocket is None:
            raise RuntimeError("LiveClient must be used as 'async with LiveClient()'")
        self._next_id += 1
        request_id = self._next_id
        await self._websocket.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params or {},
                }
            )
        )
        async with asyncio.timeout(self._timeout):
            while True:
                reply = json.loads(await self._websocket.recv())
                if reply.get("id") == request_id:
                    break
        error = reply.get("error")
        if error is not None:
            raise LiveServerError(int(error.get("code", 0)), str(error.get("message")))
        return reply.get("result")

    async def status(self) -> dict[str, Any]:
        return await self.call("live/status")

    async def execute(
        self, code: str, filename: str = "<live>", cwd: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"code": code, "filename": filename}
        if cwd is not None:
            params["cwd"] = cwd
        return await self.call("live/execute", params)

    async def run_file(self, path: str | Path) -> dict[str, Any]:
        return await self.call("live/runFile", {"path": str(Path(path).resolve())})

    async def reload(
        self,
        modules: list[str] | None = None,
        paths: list[str | Path] | None = None,
    ) -> dict[str, Any]:
        return await self.call(
            "live/reload",
            {
                "modules": list(modules or []),
                "paths": [str(Path(p).resolve()) for p in paths or []],
            },
        )

    async def start_debugger(self, port: int = 5678) -> dict[str, Any]:
        return await self.call("debug/start", {"port": port})

    async def list_analyses(self) -> list[str]:
        result = await self.call("bridge/listAnalyses")
        return list(result["analyses"])

    async def analyze(
        self,
        analysis: str,
        elements: list[Any],
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.call(
            "bridge/analyze",
            {"analysis": analysis, "elements": elements, "options": options or {}},
        )


def call_live(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    info: LiveConnectionInfo | None = None,
    timeout: float = 330.0,
) -> Any:
    """Synchronously open a connection, make one call and close it."""

    async def run() -> Any:
        async with LiveClient(info, timeout=timeout) as client:
            return await client.call(method, params)

    return asyncio.run(run())
