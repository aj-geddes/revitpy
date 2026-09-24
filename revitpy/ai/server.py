"""
MCP WebSocket server for RevitPy.

Provides an asynchronous WebSocket server that implements a subset of
the Model Context Protocol (tools and prompts), exposing tools, prompts,
and safety controls to connected clients.

Security model:

* The server binds to ``localhost`` by default.
* When ``McpServerConfig.auth_token`` is set, the WebSocket handshake
  must carry ``Authorization: Bearer <token>``; otherwise it is rejected
  with HTTP 401.  Binding to a non-loopback address without a token logs
  a loud warning.
* Handshakes carrying an ``Origin`` header that is not listed in
  ``McpServerConfig.allowed_origins`` are rejected with HTTP 403, so an
  arbitrary web page cannot drive a localhost server.

Every JSON-RPC error response carries the id of the request that caused
it (``null`` only when the id cannot be determined, e.g. parse errors),
using the standard JSON-RPC 2.0 error codes.  Tool execution failures
are reported as ``tools/call`` results with ``isError: true``, per MCP.
"""

from __future__ import annotations

import asyncio
import hmac
import importlib
import ipaddress
import json
from collections.abc import Callable, Mapping
from http import HTTPStatus
from typing import Any, TypeAlias

from loguru import logger

from ._protocol import McpRequest, McpResponse
from .exceptions import (
    McpServerError,
    PromptError,
    SafetyViolationError,
    ToolExecutionError,
)
from .prompts import PromptLibrary
from .safety import SafetyGuard
from .tools import RevitTools
from .types import McpServerConfig, ToolCategory

LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

# JSON-RPC 2.0 error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

RequestId: TypeAlias = str | int | None

# (status, body, extra headers) for a rejected WebSocket handshake.
HandshakeRejection: TypeAlias = tuple[HTTPStatus, str, dict[str, str]]


def _load_serve() -> tuple[Callable[..., Any], bool]:
    """Return ``(serve, is_new_api)`` for the installed websockets.

    Prefers the asyncio implementation (``websockets.asyncio.server``,
    websockets >= 13).  Falls back to the legacy ``websockets.server``
    implementation only for older releases, which the package still
    allows.
    """
    try:
        module = importlib.import_module("websockets.asyncio.server")
        return module.serve, True
    except ImportError:  # pragma: no cover - depends on installed version
        module = importlib.import_module("websockets.server")
        return module.serve, False


def _error(request_id: RequestId, code: int, message: str) -> McpResponse:
    """Build a JSON-RPC error response correlated to *request_id*."""
    return McpResponse(id=request_id, error={"code": code, "message": message})


def _tool_error(request_id: RequestId, text: str) -> McpResponse:
    """Build a ``tools/call`` result that reports a tool execution error."""
    logger.warning("Tool call failed: {}", text)
    return McpResponse(
        id=request_id,
        result={"content": [{"type": "text", "text": text}], "isError": True},
    )


def is_loopback_host(host: str) -> bool:
    """Return ``True`` when *host* only accepts local connections."""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class McpServer:
    """Asynchronous MCP WebSocket server.

    Args:
        tools: The ``RevitTools`` registry to expose.
        config: Server configuration.  Defaults to ``McpServerConfig()``.
        safety_guard: Optional ``SafetyGuard``.  A default one is
            created when not supplied.
        prompt_library: Optional ``PromptLibrary``.  A default one is
            created when not supplied.
    """

    def __init__(
        self,
        tools: RevitTools,
        *,
        config: McpServerConfig | None = None,
        safety_guard: SafetyGuard | None = None,
        prompt_library: PromptLibrary | None = None,
    ) -> None:
        self._tools = tools
        self._config = config or McpServerConfig()
        self._safety = safety_guard or SafetyGuard()
        self._prompts = prompt_library or PromptLibrary()
        self._connections: set[Any] = set()
        self._server: Any | None = None

    @property
    def config(self) -> McpServerConfig:
        """Return the active server configuration."""
        return self._config

    @property
    def connections(self) -> set[Any]:
        """Return the set of active WebSocket connections."""
        return set(self._connections)

    @property
    def port(self) -> int | None:
        """Return the bound port while running (useful with ``port=0``)."""
        if self._server is None:
            return None
        sockets = list(self._server.sockets)
        return int(sockets[0].getsockname()[1]) if sockets else None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the WebSocket server."""
        host = self._config.host
        port = self._config.port
        logger.info("Starting MCP server on {}:{}", host, port)
        if self._config.auth_token is None and not is_loopback_host(host):
            logger.warning(
                "MCP server is binding to non-loopback address {} WITHOUT "
                "authentication - anyone who can reach this port can run tools "
                "against the open Revit model. Set McpServerConfig.auth_token.",
                host,
            )
        try:
            serve, is_new_api = _load_serve()
            process_request = (
                self._process_request if is_new_api else self._legacy_process_request
            )
            self._server = await serve(
                self._handle_connection,
                host,
                port,
                process_request=process_request,
            )
            logger.info("MCP server started on port {}", self.port)
        except OSError as exc:
            raise McpServerError(
                f"Failed to start server: {exc}",
                host=host,
                port=port,
                cause=exc,
            ) from exc

    async def stop(self, timeout: float = 5.0) -> None:
        """Gracefully stop the server.

        Args:
            timeout: Seconds to wait for connections to close.
        """
        logger.info("Stopping MCP server")
        if self._server is not None:
            self._server.close()
            await asyncio.wait_for(self._server.wait_closed(), timeout=timeout)
            self._server = None
        self._connections.clear()
        logger.info("MCP server stopped")

    async def __aenter__(self) -> McpServer:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Handshake checks
    # ------------------------------------------------------------------

    def _check_handshake(self, headers: Mapping[str, str]) -> HandshakeRejection | None:
        """Validate handshake headers; return a rejection or ``None`` to accept.

        Rejects any ``Origin`` not in ``allowed_origins`` (403) and, when
        ``auth_token`` is configured, any request without a matching
        ``Authorization: Bearer`` header (401).  The token comparison is
        constant-time and the token is never logged.
        """
        origin = headers.get("Origin")
        if origin is not None and origin not in self._config.allowed_origins:
            logger.warning(
                "Rejected WebSocket handshake from disallowed origin {}", origin
            )
            return HTTPStatus.FORBIDDEN, "Forbidden origin\n", {}

        token = self._config.auth_token
        if token is not None:
            header = headers.get("Authorization") or ""
            scheme, _, supplied = header.partition(" ")
            authorized = scheme.lower() == "bearer" and hmac.compare_digest(
                supplied.strip().encode("utf-8"), token.encode("utf-8")
            )
            if not authorized:
                logger.warning("Rejected unauthenticated WebSocket handshake")
                return (
                    HTTPStatus.UNAUTHORIZED,
                    "Unauthorized\n",
                    {"WWW-Authenticate": 'Bearer realm="revitpy-mcp"'},
                )

        return None

    def _process_request(self, connection: Any, request: Any) -> Any:
        """``process_request`` hook for the websockets asyncio server."""
        rejection = self._check_handshake(request.headers)
        if rejection is None:
            return None
        status, body, extra_headers = rejection
        response = connection.respond(status, body)
        for name, value in extra_headers.items():
            response.headers[name] = value
        return response

    async def _legacy_process_request(
        self, path: str, request_headers: Any
    ) -> tuple[HTTPStatus, list[tuple[str, str]], bytes] | None:
        """``process_request`` hook for legacy websockets (< 13)."""
        rejection = self._check_handshake(request_headers)
        if rejection is None:
            return None
        status, body, extra_headers = rejection
        return status, list(extra_headers.items()), body.encode("utf-8")

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    async def _handle_connection(self, websocket: Any) -> None:
        """Handle a single WebSocket client connection."""
        self._connections.add(websocket)
        logger.info(
            "Client connected; total connections = {}",
            len(self._connections),
        )
        try:
            async for raw_message in websocket:
                response = await self._process_raw(raw_message)
                if response is not None:
                    await websocket.send(response.to_json())
        finally:
            self._connections.discard(websocket)
            logger.info(
                "Client disconnected; total connections = {}",
                len(self._connections),
            )

    async def _process_raw(self, raw: str | bytes) -> McpResponse | None:
        """Parse and validate one raw frame, then dispatch it.

        Never raises.  Returns ``None`` for notifications and client
        responses, which must not be answered.
        """
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                return _error(None, PARSE_ERROR, "Parse error: invalid UTF-8")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return _error(None, PARSE_ERROR, "Parse error")

        if isinstance(data, list):
            return _error(
                None,
                INVALID_REQUEST,
                "Invalid Request: JSON-RPC batching is not supported",
            )
        if not isinstance(data, dict):
            return _error(
                None, INVALID_REQUEST, "Invalid Request: expected a JSON object"
            )

        request_id = data.get("id")
        if request_id is not None and (
            isinstance(request_id, bool) or not isinstance(request_id, (str, int))
        ):
            return _error(
                None, INVALID_REQUEST, "Invalid Request: id must be a string or integer"
            )

        if "method" not in data:
            if "result" in data or "error" in data:
                logger.debug("Ignoring client response for id {}", request_id)
                return None
            return _error(
                request_id, INVALID_REQUEST, "Invalid Request: missing 'method'"
            )

        if data.get("jsonrpc") != "2.0":
            return _error(
                request_id, INVALID_REQUEST, "Invalid Request: jsonrpc must be '2.0'"
            )

        method = data["method"]
        if not isinstance(method, str):
            return _error(
                request_id, INVALID_REQUEST, "Invalid Request: method must be a string"
            )

        if request_id is None:
            logger.debug("Received notification {}", method)
            return None

        params = data.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return _error(
                request_id, INVALID_PARAMS, "Invalid params: params must be an object"
            )

        return await self._handle_message(
            McpRequest(id=request_id, method=method, params=params)
        )

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    async def _handle_message(self, message: McpRequest) -> McpResponse:
        """Dispatch an MCP request; errors are always correlated by id."""
        method = message.method
        logger.debug("Handling method: {}", method)
        try:
            if method == "initialize":
                return self._handle_initialize(message)
            if method == "ping":
                return McpResponse(id=message.id, result={})
            if method == "tools/list":
                return self._handle_tools_list(message)
            if method == "tools/call":
                return await self._handle_tools_call(message)
            if method == "prompts/list":
                return self._handle_prompts_list(message)
            if method == "prompts/get":
                return self._handle_prompts_get(message)
            return _error(message.id, METHOD_NOT_FOUND, f"Method not found: {method}")
        except Exception as exc:
            logger.exception("Unhandled error while handling {}", method)
            return _error(message.id, INTERNAL_ERROR, f"Internal error: {exc}")

    # ------------------------------------------------------------------
    # Method handlers
    # ------------------------------------------------------------------

    def _handle_initialize(self, message: McpRequest) -> McpResponse:
        requested = message.params.get("protocolVersion")
        version = (
            requested
            if requested in SUPPORTED_PROTOCOL_VERSIONS
            else LATEST_PROTOCOL_VERSION
        )
        return McpResponse(
            id=message.id,
            result={
                "protocolVersion": version,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {
                    "name": self._config.name,
                    "version": self._config.version,
                },
            },
        )

    def _handle_tools_list(self, message: McpRequest) -> McpResponse:
        return McpResponse(
            id=message.id,
            result={"tools": self._tools.to_mcp_tool_list()},
        )

    async def _handle_tools_call(self, message: McpRequest) -> McpResponse:
        params = message.params
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return _error(
                message.id, INVALID_PARAMS, "Invalid params: tool name is required"
            )

        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _error(
                message.id,
                INVALID_PARAMS,
                "Invalid params: arguments must be an object",
            )

        definition = self._tools.get_tool(name)
        if definition is None:
            # Unknown tools are a protocol error per the MCP spec.
            return _error(message.id, INVALID_PARAMS, f"Unknown tool: {name}")

        try:
            await self._safety.avalidate_tool_call(definition, arguments)
        except SafetyViolationError as exc:
            return _tool_error(message.id, f"Safety violation: {exc}")

        try:
            result = self._tools.execute_tool(name, arguments)
        except ToolExecutionError as exc:
            return _tool_error(message.id, str(exc))

        if result.error is not None:
            return _tool_error(message.id, result.error)

        if definition.category == ToolCategory.MODIFY:
            self._safety.push_undo(
                {"tool": name, "arguments": dict(arguments), "result": result.data}
            )

        payload: dict[str, Any] = {
            "content": [
                {"type": "text", "text": json.dumps(result.data, default=str)},
            ],
            "isError": False,
        }
        if isinstance(result.data, dict):
            payload["structuredContent"] = result.data
        return McpResponse(id=message.id, result=payload)

    def _handle_prompts_list(self, message: McpRequest) -> McpResponse:
        return McpResponse(
            id=message.id,
            result={"prompts": self._prompts.to_mcp_prompts_list()},
        )

    def _handle_prompts_get(self, message: McpRequest) -> McpResponse:
        params = message.params
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return _error(
                message.id, INVALID_PARAMS, "Invalid params: prompt name is required"
            )

        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _error(
                message.id,
                INVALID_PARAMS,
                "Invalid params: arguments must be an object",
            )

        if self._prompts.get_template(name) is None:
            return _error(message.id, INVALID_PARAMS, f"Unknown prompt: {name}")

        try:
            rendered = self._prompts.render(name, **arguments)
        except PromptError as exc:
            return _error(
                message.id, INVALID_PARAMS, f"Invalid prompt arguments: {exc}"
            )
        except Exception as exc:
            return _error(message.id, INTERNAL_ERROR, f"Prompt render error: {exc}")

        return McpResponse(
            id=message.id,
            result={
                "description": f"Prompt: {name}",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": rendered,
                        },
                    },
                ],
            },
        )
