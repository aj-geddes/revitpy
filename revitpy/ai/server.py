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

import json
from typing import Any

from loguru import logger

from ..rpc import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JsonRpcWebSocketServer,
    RequestId,
    is_loopback_host,
)
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

__all__ = [
    "INTERNAL_ERROR",
    "INVALID_PARAMS",
    "INVALID_REQUEST",
    "LATEST_PROTOCOL_VERSION",
    "METHOD_NOT_FOUND",
    "PARSE_ERROR",
    "McpServer",
    "is_loopback_host",
]

LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")


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


class McpServer(JsonRpcWebSocketServer):
    """Asynchronous MCP WebSocket server.

    Args:
        tools: The ``RevitTools`` registry to expose.
        config: Server configuration.  Defaults to ``McpServerConfig()``.
        safety_guard: Optional ``SafetyGuard``.  A default one is
            created when not supplied.
        prompt_library: Optional ``PromptLibrary``.  A default one is
            created when not supplied.
    """

    server_name = "revitpy-mcp"
    request_cls = McpRequest
    response_cls = McpResponse

    def __init__(
        self,
        tools: RevitTools,
        *,
        config: McpServerConfig | None = None,
        safety_guard: SafetyGuard | None = None,
        prompt_library: PromptLibrary | None = None,
    ) -> None:
        self._config = config or McpServerConfig()
        super().__init__(
            host=self._config.host,
            port=self._config.port,
            auth_token=self._config.auth_token,
            allowed_origins=self._config.allowed_origins,
        )
        self._tools = tools
        self._safety = safety_guard or SafetyGuard()
        self._prompts = prompt_library or PromptLibrary()

    @property
    def config(self) -> McpServerConfig:
        """Return the active server configuration."""
        return self._config

    def _startup_error(self, message: str, cause: OSError) -> Exception:
        return McpServerError(
            message, host=self._config.host, port=self._config.port, cause=cause
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
