"""
Unit tests for McpServer initialization, configuration, and message dispatch.

Tests use mock WebSocket objects so no real network server is started.
"""

import json
from unittest.mock import AsyncMock

import pytest

from revitpy.ai._protocol import McpRequest, McpResponse
from revitpy.ai.prompts import PromptLibrary
from revitpy.ai.safety import SafetyGuard
from revitpy.ai.server import McpServer
from revitpy.ai.tools import RevitTools
from revitpy.ai.types import (
    McpServerConfig,
    SafetyConfig,
    SafetyMode,
)


class _AsyncIterFromList:
    """Helper: wraps a list into an async iterator for mock websockets."""

    def __init__(self, items):
        self._items = list(items)
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


@pytest.fixture
def server() -> McpServer:
    """An McpServer with defaults for unit testing."""
    tools = RevitTools()
    return McpServer(tools)


@pytest.fixture
def custom_server() -> McpServer:
    """An McpServer with explicit config objects."""
    tools = RevitTools()
    config = McpServerConfig(
        host="127.0.0.1", port=9999, name="test-mcp", version="0.1.0"
    )
    safety = SafetyGuard(SafetyConfig(mode=SafetyMode.READ_ONLY))
    prompts = PromptLibrary()
    return McpServer(
        tools,
        config=config,
        safety_guard=safety,
        prompt_library=prompts,
    )


class TestMcpServer:
    """Tests for McpServer setup and message handling."""

    # ----------------------------------------------------------
    # Initialization
    # ----------------------------------------------------------

    def test_default_config(self, server):
        """Server uses default McpServerConfig when none given."""
        assert server.config.host == "localhost"
        assert server.config.port == 8765
        assert server.config.name == "revitpy-mcp"

    def test_custom_config(self, custom_server):
        """Server respects explicitly provided config."""
        assert custom_server.config.host == "127.0.0.1"
        assert custom_server.config.port == 9999
        assert custom_server.config.name == "test-mcp"

    def test_connections_initially_empty(self, server):
        """No connections exist before the server starts."""
        assert len(server.connections) == 0

    # ----------------------------------------------------------
    # Message dispatch: initialize
    # ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_initialize(self, server):
        """The initialize method returns server info."""
        request = McpRequest(id=1, method="initialize")
        response = await server._handle_message(request)

        assert isinstance(response, McpResponse)
        assert response.id == 1
        result = response.result
        assert result["protocolVersion"] == "2024-11-05"
        assert "tools" in result["capabilities"]
        assert "prompts" in result["capabilities"]
        assert result["serverInfo"]["name"] == "revitpy-mcp"

    # ----------------------------------------------------------
    # Message dispatch: tools/list
    # ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_tools_list(self, server):
        """tools/list returns the MCP-format tool definitions."""
        request = McpRequest(id=2, method="tools/list")
        response = await server._handle_message(request)

        assert response.error is None
        tools = response.result["tools"]
        assert isinstance(tools, list)
        assert len(tools) >= 6  # built-ins
        names = {t["name"] for t in tools}
        assert "query_elements" in names

    # ----------------------------------------------------------
    # Message dispatch: tools/call
    # ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_tools_call_success(self, server):
        """tools/call with valid args returns a success response."""
        request = McpRequest(
            id=3,
            method="tools/call",
            params={
                "name": "get_element",
                "arguments": {"element_id": 42},
            },
        )
        response = await server._handle_message(request)

        assert response.error is None
        content = response.result["content"]
        assert len(content) >= 1
        assert response.result["isError"] is False

    @pytest.mark.asyncio
    async def test_handle_tools_call_unknown_tool(self, server):
        """tools/call with unknown tool returns an error response."""
        request = McpRequest(
            id=4,
            method="tools/call",
            params={"name": "nonexistent", "arguments": {}},
        )
        response = await server._handle_message(request)
        assert response.error is not None
        assert response.error["code"] == -32602

    @pytest.mark.asyncio
    async def test_handle_tools_call_safety_violation(self, custom_server):
        """tools/call blocked by safety returns isError response."""
        request = McpRequest(
            id=5,
            method="tools/call",
            params={
                "name": "modify_parameter",
                "arguments": {
                    "element_id": 1,
                    "parameter_name": "Height",
                    "value": "10",
                },
            },
        )
        response = await custom_server._handle_message(request)
        # Safety violation returns as result with isError
        assert response.result is not None
        assert response.result["isError"] is True

    # ----------------------------------------------------------
    # Message dispatch: prompts/list
    # ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_prompts_list(self, server):
        """prompts/list returns prompt definitions."""
        request = McpRequest(id=6, method="prompts/list")
        response = await server._handle_message(request)

        assert response.error is None
        prompts = response.result["prompts"]
        assert isinstance(prompts, list)
        names = {p["name"] for p in prompts}
        assert "element_summary" in names

    # ----------------------------------------------------------
    # Message dispatch: prompts/get
    # ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_prompts_get_success(self, server):
        """prompts/get renders a known prompt."""
        request = McpRequest(
            id=7,
            method="prompts/get",
            params={
                "name": "validation_report",
                "arguments": {"issues": []},
            },
        )
        response = await server._handle_message(request)

        assert response.error is None
        messages = response.result["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "No issues found" in messages[0]["content"]["text"]

    @pytest.mark.asyncio
    async def test_handle_prompts_get_unknown(self, server):
        """prompts/get with unknown name returns error."""
        request = McpRequest(
            id=8,
            method="prompts/get",
            params={"name": "nonexistent", "arguments": {}},
        )
        response = await server._handle_message(request)
        assert response.error is not None

    # ----------------------------------------------------------
    # Unknown method
    # ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self, server):
        """Unknown methods return a -32601 error."""
        request = McpRequest(id=9, method="resources/list")
        response = await server._handle_message(request)
        assert response.error is not None
        assert response.error["code"] == -32601

    # ----------------------------------------------------------
    # Connection handling with mock websocket
    # ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_connection_lifecycle(self, server):
        """Connections are tracked during their lifetime."""
        request = McpRequest(id=10, method="initialize")
        ws = _AsyncIterFromList([request.to_json()])
        ws.send = AsyncMock()

        await server._handle_connection(ws)

        # After the connection ends it should be removed
        assert ws not in server.connections
        # The server should have sent a response
        ws.send.assert_called_once()
        sent = json.loads(ws.send.call_args[0][0])
        assert sent["id"] == 10

    @pytest.mark.asyncio
    async def test_handle_connection_error_sends_error_response(self, server):
        """Malformed messages get an error response."""
        ws = _AsyncIterFromList(["not valid json{{{"])
        ws.send = AsyncMock()

        await server._handle_connection(ws)

        ws.send.assert_called_once()
        sent = json.loads(ws.send.call_args[0][0])
        assert "error" in sent
