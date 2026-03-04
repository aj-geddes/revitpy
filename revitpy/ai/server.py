"""
MCP WebSocket server for RevitPy.

Provides an asynchronous WebSocket server that implements a subset of
the Model Context Protocol, exposing tools, prompts, and safety
controls to connected clients.
"""

from __future__ import annotations

import asyncio
from typing import Any

import websockets
from loguru import logger

from ._protocol import McpMessage, McpRequest, McpResponse
from .exceptions import McpServerError
from .prompts import PromptLibrary
from .safety import SafetyGuard
from .tools import RevitTools
from .types import McpServerConfig


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
        self._serve_task: asyncio.Task[None] | None = None

    @property
    def config(self) -> McpServerConfig:
        """Return the active server configuration."""
        return self._config

    @property
    def connections(self) -> set[Any]:
        """Return the set of active WebSocket connections."""
        return set(self._connections)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the WebSocket server."""
        logger.info(
            "Starting MCP server on {}:{}",
            self._config.host,
            self._config.port,
        )
        try:
            self._server = await websockets.serve(
                self._handle_connection,
                self._config.host,
                self._config.port,
            )
            logger.info("MCP server started")
        except OSError as exc:
            raise McpServerError(
                f"Failed to start server: {exc}",
                host=self._config.host,
                port=self._config.port,
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
    # Connection handling
    # ------------------------------------------------------------------

    async def _handle_connection(
        self,
        websocket: Any,
        *args: Any,
    ) -> None:
        """Handle a single WebSocket client connection."""
        self._connections.add(websocket)
        logger.info(
            "Client connected; total connections = {}",
            len(self._connections),
        )
        try:
            async for raw_message in websocket:
                try:
                    message = McpMessage.from_json(raw_message)
                    if isinstance(message, McpRequest):
                        response = await self._handle_message(message)
                        await websocket.send(response.to_json())
                except Exception as exc:
                    logger.error("Error handling message: {}", exc)
                    error_response = McpResponse(
                        id=None,
                        error={
                            "code": -32603,
                            "message": str(exc),
                        },
                    )
                    await websocket.send(error_response.to_json())
        finally:
            self._connections.discard(websocket)
            logger.info(
                "Client disconnected; total connections = {}",
                len(self._connections),
            )

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    async def _handle_message(
        self,
        message: McpRequest,
    ) -> McpResponse:
        """Dispatch an MCP request to the appropriate handler."""
        method = message.method
        params = message.params
        logger.debug("Handling method: {}", method)

        if method == "initialize":
            return self._handle_initialize(message)

        if method == "tools/list":
            return self._handle_tools_list(message)

        if method == "tools/call":
            return await self._handle_tools_call(message, params)

        if method == "prompts/list":
            return self._handle_prompts_list(message)

        if method == "prompts/get":
            return self._handle_prompts_get(message, params)

        return McpResponse(
            id=message.id,
            error={
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        )

    # ------------------------------------------------------------------
    # Method handlers
    # ------------------------------------------------------------------

    def _handle_initialize(self, message: McpRequest) -> McpResponse:
        return McpResponse(
            id=message.id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True},
                    "prompts": {"listChanged": True},
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

    async def _handle_tools_call(
        self,
        message: McpRequest,
        params: dict[str, Any],
    ) -> McpResponse:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        definition = self._tools.get_tool(tool_name)
        if definition is None:
            return McpResponse(
                id=message.id,
                error={
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}",
                },
            )

        # Safety check
        try:
            self._safety.validate_tool_call(definition, arguments)
        except Exception as exc:
            return McpResponse(
                id=message.id,
                result={
                    "content": [
                        {
                            "type": "text",
                            "text": f"Safety violation: {exc}",
                        }
                    ],
                    "isError": True,
                },
            )

        result = self._tools.execute_tool(tool_name, arguments)
        return McpResponse(
            id=message.id,
            result={
                "content": [
                    {"type": "text", "text": str(result.data)},
                ],
                "isError": result.error is not None,
            },
        )

    def _handle_prompts_list(self, message: McpRequest) -> McpResponse:
        return McpResponse(
            id=message.id,
            result={"prompts": self._prompts.to_mcp_prompts_list()},
        )

    def _handle_prompts_get(
        self,
        message: McpRequest,
        params: dict[str, Any],
    ) -> McpResponse:
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        source = self._prompts.get_template(name)
        if source is None:
            return McpResponse(
                id=message.id,
                error={
                    "code": -32602,
                    "message": f"Unknown prompt: {name}",
                },
            )

        try:
            rendered = self._prompts.render(name, **arguments)
        except Exception as exc:
            return McpResponse(
                id=message.id,
                error={
                    "code": -32603,
                    "message": f"Prompt render error: {exc}",
                },
            )

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
