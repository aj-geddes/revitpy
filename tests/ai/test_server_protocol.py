"""
Tests for McpServer JSON-RPC error correlation, MCP response shapes, and
WebSocket handshake authentication.
"""

import asyncio
import base64
import json
import os
from typing import Any

import pytest
from loguru import logger

from revitpy.ai.safety import SafetyGuard
from revitpy.ai.server import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    LATEST_PROTOCOL_VERSION,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    McpServer,
    is_loopback_host,
)
from revitpy.ai.tools import RevitTools
from revitpy.ai.types import McpServerConfig, SafetyConfig, SafetyMode

try:  # websockets >= 13
    from websockets.asyncio.client import connect as ws_connect

    HEADER_KW = "additional_headers"
except ImportError:  # pragma: no cover - legacy websockets
    from websockets.client import connect as ws_connect  # type: ignore[no-redef]

    HEADER_KW = "extra_headers"

TOKEN = "s3cret"


@pytest.fixture
def server(fake_api):
    """Server with FULL_ACCESS safety bound to the fake API."""
    return McpServer(
        RevitTools(fake_api),
        safety_guard=SafetyGuard(SafetyConfig(mode=SafetyMode.FULL_ACCESS)),
    )


@pytest.fixture
def cautious_server(fake_api):
    """Server with the default (CAUTIOUS, no callback) safety guard."""
    return McpServer(RevitTools(fake_api))


async def call(server: McpServer, payload: Any) -> dict[str, Any]:
    """Feed one frame to the server and return the decoded response."""
    raw = payload if isinstance(payload, (str, bytes)) else json.dumps(payload)
    response = await server._process_raw(raw)
    assert response is not None
    return json.loads(response.to_json())


def rpc(method: str, request_id: Any, params: dict | None = None) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 request."""
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


def tool_call(request_id: Any, name: str, arguments: Any) -> dict[str, Any]:
    """Build a tools/call request."""
    return rpc("tools/call", request_id, {"name": name, "arguments": arguments})


class TestErrorCorrelation:
    """Every error carries the right JSON-RPC code and request id."""

    @pytest.mark.asyncio
    async def test_parse_error(self, server):
        """Unparseable JSON yields -32700 with a null id."""
        response = await call(server, "not json{{")
        assert response["error"]["code"] == PARSE_ERROR
        assert response["id"] is None

    @pytest.mark.asyncio
    async def test_batch_rejected(self, server):
        """JSON-RPC batches are rejected as invalid requests."""
        response = await call(server, [rpc("ping", 1)])
        assert response["error"]["code"] == INVALID_REQUEST

    @pytest.mark.asyncio
    async def test_non_object(self, server):
        """A non-object JSON value is an invalid request."""
        response = await call(server, 42)
        assert response["error"]["code"] == INVALID_REQUEST

    @pytest.mark.asyncio
    async def test_missing_jsonrpc_version(self, server):
        """A missing jsonrpc field is rejected with the request id."""
        response = await call(server, {"id": 7, "method": "ping"})
        assert response["error"]["code"] == INVALID_REQUEST
        assert response["id"] == 7

    @pytest.mark.asyncio
    async def test_missing_method(self, server):
        """A message with an id but no method is an invalid request."""
        response = await call(server, {"jsonrpc": "2.0", "id": "abc"})
        assert response["error"]["code"] == INVALID_REQUEST
        assert response["id"] == "abc"

    @pytest.mark.asyncio
    async def test_params_not_object(self, server):
        """Non-object params are invalid params, correlated by id."""
        message = {"jsonrpc": "2.0", "id": 8, "method": "tools/list", "params": [1]}
        response = await call(server, message)
        assert response["error"]["code"] == INVALID_PARAMS
        assert response["id"] == 8

    @pytest.mark.asyncio
    async def test_unknown_method(self, server):
        """Unknown methods yield -32601 with the request id."""
        response = await call(server, rpc("resources/list", 9))
        assert response["error"]["code"] == METHOD_NOT_FOUND
        assert response["id"] == 9

    @pytest.mark.asyncio
    async def test_unknown_tool(self, server):
        """Unknown tools are a protocol error (-32602)."""
        response = await call(server, tool_call(10, "nonexistent", {}))
        assert response["error"]["code"] == INVALID_PARAMS
        assert response["id"] == 10

    @pytest.mark.asyncio
    async def test_missing_tool_name(self, server):
        """tools/call without a name is invalid params."""
        response = await call(server, rpc("tools/call", 11, {}))
        assert response["error"]["code"] == INVALID_PARAMS
        assert response["id"] == 11

    @pytest.mark.asyncio
    async def test_arguments_not_object(self, server):
        """tools/call with non-object arguments is invalid params."""
        response = await call(server, tool_call(12, "query_elements", [1]))
        assert response["error"]["code"] == INVALID_PARAMS
        assert response["id"] == 12

    @pytest.mark.asyncio
    async def test_tool_execution_error_is_result(self, server):
        """ToolExecutionError becomes an isError result, not a protocol error."""
        response = await call(server, tool_call(13, "get_element", {"element_id": 999}))
        assert "error" not in response
        assert response["id"] == 13
        assert response["result"]["isError"] is True
        assert "Element 999 not found" in response["result"]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_not_connected_is_result(self):
        """Without a document, tools/call reports an isError result."""
        server = McpServer(
            RevitTools(),
            safety_guard=SafetyGuard(SafetyConfig(mode=SafetyMode.FULL_ACCESS)),
        )
        response = await call(
            server, tool_call(14, "query_elements", {"category": "W"})
        )
        assert response["id"] == 14
        assert response["result"]["isError"] is True
        text = response["result"]["content"][0]["text"]
        assert "Not connected to a Revit document" in text

    @pytest.mark.asyncio
    async def test_missing_required_argument(self, server):
        """Missing tool arguments are reported so the model can self-correct."""
        response = await call(server, tool_call(15, "get_element", {}))
        assert response["id"] == 15
        assert response["result"]["isError"] is True
        text = response["result"]["content"][0]["text"]
        assert "Missing required parameters" in text

    @pytest.mark.asyncio
    async def test_internal_error_correlated(self, server, monkeypatch):
        """Unexpected exceptions become -32603 carrying the request id."""

        def boom():
            raise RuntimeError("kaboom")

        monkeypatch.setattr(server._tools, "to_mcp_tool_list", boom)
        response = await call(server, rpc("tools/list", 16))
        assert response["error"]["code"] == INTERNAL_ERROR
        assert response["id"] == 16
        assert "kaboom" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_notification_gets_no_response(self, server):
        """Notifications are never answered."""
        raw = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert await server._process_raw(raw) is None

    @pytest.mark.asyncio
    async def test_client_response_ignored(self, server):
        """Responses sent by the client are ignored."""
        raw = json.dumps({"jsonrpc": "2.0", "id": 5, "result": {}})
        assert await server._process_raw(raw) is None

    @pytest.mark.asyncio
    async def test_string_id_preserved(self, server):
        """String ids round-trip unchanged."""
        response = await call(server, rpc("ping", "req-1"))
        assert response["id"] == "req-1"
        assert response["result"] == {}

    @pytest.mark.asyncio
    async def test_bool_id_rejected(self, server):
        """Boolean ids are invalid."""
        response = await call(server, rpc("ping", True))
        assert response["error"]["code"] == INVALID_REQUEST
        assert response["id"] is None

    @pytest.mark.asyncio
    async def test_bytes_frame(self, server):
        """Binary frames containing UTF-8 JSON are accepted."""
        response = await call(server, json.dumps(rpc("ping", 1)).encode())
        assert response["id"] == 1

    @pytest.mark.asyncio
    async def test_invalid_utf8(self, server):
        """Binary frames that are not UTF-8 are parse errors."""
        response = await call(server, b"\xff\xfe")
        assert response["error"]["code"] == PARSE_ERROR


class TestMcpShapes:
    """MCP result shapes for initialize, tools/list and tools/call."""

    @pytest.mark.asyncio
    async def test_initialize_echoes_supported_version(self, server):
        """A supported requested protocol version is echoed back."""
        params = {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "t", "version": "1"},
        }
        response = await call(server, rpc("initialize", 1, params))
        result = response["result"]
        assert result["protocolVersion"] == "2025-06-18"
        assert "tools" in result["capabilities"]
        assert "prompts" in result["capabilities"]
        assert result["serverInfo"]["name"] == "revitpy-mcp"

    @pytest.mark.asyncio
    async def test_initialize_unsupported_version(self, server):
        """An unsupported version gets the server's latest version."""
        params = {"protocolVersion": "1999-01-01", "capabilities": {}}
        response = await call(server, rpc("initialize", 1, params))
        assert response["result"]["protocolVersion"] == LATEST_PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_tools_list_shape(self, server):
        """tools/list entries carry name, description and an object schema."""
        response = await call(server, rpc("tools/list", 1))
        tools = response["result"]["tools"]
        assert tools
        for tool in tools:
            assert tool["name"]
            assert "description" in tool
            assert tool["inputSchema"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_tools_call_success_shape(self, server):
        """Successful calls return JSON text content plus structuredContent."""
        response = await call(
            server, tool_call(1, "query_elements", {"category": "Walls"})
        )
        result = response["result"]
        assert result["isError"] is False
        assert result["content"][0]["type"] == "text"
        assert json.loads(result["content"][0]["text"])["count"] == 3
        assert result["structuredContent"]["count"] == 3

    @pytest.mark.asyncio
    async def test_modify_records_undo(self, server, fake_api):
        """A successful modification is applied and pushed to the undo stack."""
        args = {"element_id": 3, "parameter_name": "Mark", "value": "W9"}
        response = await call(server, tool_call(1, "modify_parameter", args))
        assert response["result"]["isError"] is False
        assert fake_api.elements[2].params["Mark"] == "W9"
        assert server._safety.get_undo_stack()[-1]["tool"] == "modify_parameter"

    @pytest.mark.asyncio
    async def test_cautious_denies_unconfirmed_modify(self, cautious_server, fake_api):
        """Default CAUTIOUS guard denies modifications with no callback."""
        args = {"element_id": 3, "parameter_name": "Mark", "value": "W9"}
        response = await call(cautious_server, tool_call(1, "modify_parameter", args))
        assert response["result"]["isError"] is True
        assert "requires confirmation" in response["result"]["content"][0]["text"]
        assert fake_api.log == []

    @pytest.mark.asyncio
    async def test_cautious_allows_confirmed_modify(self, fake_api):
        """An approving callback lets the modification through."""
        server = McpServer(
            RevitTools(fake_api),
            safety_guard=SafetyGuard(confirmation_callback=lambda tool, args: True),
        )
        args = {"element_id": 3, "parameter_name": "Mark", "value": "W9"}
        response = await call(server, tool_call(1, "modify_parameter", args))
        assert response["result"]["isError"] is False
        assert fake_api.elements[2].params["Mark"] == "W9"


async def handshake_status(port: int, headers: dict[str, str]) -> int:
    """Send a raw WebSocket upgrade request and return the HTTP status."""
    lines = [
        "GET / HTTP/1.1",
        f"Host: 127.0.0.1:{port}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {base64.b64encode(os.urandom(16)).decode()}",
        "Sec-WebSocket-Version: 13",
    ]
    lines.extend(f"{name}: {value}" for name, value in headers.items())
    request = "\r\n".join(lines) + "\r\n\r\n"

    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(request.encode())
        await writer.drain()
        status_line = await asyncio.wait_for(reader.readline(), 5)
        return int(status_line.split()[1])
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except ConnectionError:
            pass


async def status_for(config: McpServerConfig, headers: dict[str, str]) -> int:
    """Start a real server with *config* and return the handshake status."""
    server = McpServer(RevitTools(), config=config)
    await server.start()
    try:
        assert server.port is not None
        return await handshake_status(server.port, headers)
    finally:
        await server.stop()


class TestHandshakeAuth:
    """Bearer-token and Origin checks during the WebSocket handshake."""

    @pytest.mark.parametrize(
        ("headers", "expected"),
        [
            ({}, 401),
            ({"Authorization": "Bearer nope"}, 401),
            ({"Authorization": f"Basic {TOKEN}"}, 401),
            ({"Authorization": "Bearer"}, 401),
            ({"Authorization": f"Bearer {TOKEN}"}, 101),
            ({"Authorization": f"bearer {TOKEN}"}, 101),
        ],
    )
    @pytest.mark.asyncio
    async def test_token_required(self, headers, expected):
        """With auth_token set, only a matching bearer token is accepted."""
        config = McpServerConfig(host="127.0.0.1", port=0, auth_token=TOKEN)
        assert await status_for(config, headers) == expected

    @pytest.mark.asyncio
    async def test_no_token_configured_accepts(self):
        """Without auth_token, a localhost handshake is accepted."""
        config = McpServerConfig(host="127.0.0.1", port=0)
        assert await status_for(config, {}) == 101

    @pytest.mark.asyncio
    async def test_disallowed_origin_rejected(self):
        """A browser Origin not on the allow-list is rejected with 403."""
        config = McpServerConfig(
            host="127.0.0.1",
            port=0,
            auth_token=TOKEN,
            allowed_origins=["https://ok.example"],
        )
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Origin": "https://evil.example",
        }
        assert await status_for(config, headers) == 403

    @pytest.mark.asyncio
    async def test_allowed_origin_accepted(self):
        """An allow-listed Origin is accepted."""
        config = McpServerConfig(
            host="127.0.0.1",
            port=0,
            auth_token=TOKEN,
            allowed_origins=["https://ok.example"],
        )
        headers = {"Authorization": f"Bearer {TOKEN}", "Origin": "https://ok.example"}
        assert await status_for(config, headers) == 101

    @pytest.mark.asyncio
    async def test_token_not_in_repr(self):
        """The auth token never appears in the config repr."""
        config = McpServerConfig(auth_token=TOKEN)
        assert TOKEN not in repr(config)

    @pytest.mark.asyncio
    async def test_end_to_end_round_trip(self):
        """An authenticated client can initialize over a real socket."""
        config = McpServerConfig(host="127.0.0.1", port=0, auth_token=TOKEN)
        server = McpServer(RevitTools(), config=config)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.port}"
            kwargs = {HEADER_KW: {"Authorization": f"Bearer {TOKEN}"}}
            async with ws_connect(uri, **kwargs) as ws:
                await ws.send(json.dumps(rpc("initialize", 1, {})))
                response = json.loads(await asyncio.wait_for(ws.recv(), 5))
            assert response["id"] == 1
            assert "result" in response
        finally:
            await server.stop()


class TestLoopbackWarning:
    """Warn loudly when exposed beyond loopback without a token."""

    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("localhost", True),
            ("127.0.0.1", True),
            ("::1", True),
            ("0.0.0.0", False),  # noqa: S104 - classifier input, nothing binds
            ("", False),
            ("example.com", False),
            ("192.168.1.10", False),
        ],
    )
    def test_is_loopback_host(self, host, expected):
        """is_loopback_host classifies hosts correctly."""
        assert is_loopback_host(host) is expected

    @pytest.mark.asyncio
    async def test_warns_without_token_on_public_bind(self):
        """Binding 0.0.0.0 without auth_token logs a warning."""
        messages: list[str] = []
        sink_id = logger.add(messages.append, level="WARNING")
        server = McpServer(RevitTools(), config=McpServerConfig(host="0.0.0.0", port=0))  # noqa: S104
        try:
            await server.start()
            assert any("WITHOUT" in str(m) for m in messages)
        finally:
            await server.stop()
            logger.remove(sink_id)

    @pytest.mark.asyncio
    async def test_no_warning_with_token(self):
        """Binding 0.0.0.0 with auth_token does not log the warning."""
        messages: list[str] = []
        sink_id = logger.add(messages.append, level="WARNING")
        config = McpServerConfig(host="0.0.0.0", port=0, auth_token=TOKEN)  # noqa: S104
        server = McpServer(RevitTools(), config=config)
        try:
            await server.start()
            assert not any("WITHOUT" in str(m) for m in messages)
        finally:
            await server.stop()
            logger.remove(sink_id)
