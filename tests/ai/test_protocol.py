"""
Unit tests for MCP JSON-RPC protocol message classes.
"""

import json

import pytest

from revitpy.ai._protocol import (
    McpMessage,
    McpNotification,
    McpRequest,
    McpResponse,
)
from revitpy.ai.types import McpMessageType


class TestMcpProtocol:
    """Tests for JSON-RPC serialization and deserialization."""

    # ----------------------------------------------------------
    # McpRequest
    # ----------------------------------------------------------

    def test_request_auto_generates_id(self):
        """McpRequest generates an id when none is supplied."""
        req = McpRequest(method="tools/list")
        assert req.id is not None
        assert isinstance(req.id, str)

    def test_request_preserves_explicit_id(self):
        """McpRequest keeps the id when one is provided."""
        req = McpRequest(id=42, method="tools/list")
        assert req.id == 42

    def test_request_to_json(self):
        """McpRequest serializes to valid JSON-RPC."""
        req = McpRequest(
            id="abc",
            method="tools/call",
            params={"name": "query_elements"},
        )
        payload = json.loads(req.to_json())
        assert payload["jsonrpc"] == "2.0"
        assert payload["id"] == "abc"
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == "query_elements"

    def test_request_to_json_omits_empty_params(self):
        """Empty params dict is omitted from the JSON payload."""
        req = McpRequest(id="x", method="initialize")
        payload = json.loads(req.to_json())
        assert "params" not in payload

    def test_request_message_type(self):
        """McpRequest reports its message_type as REQUEST."""
        req = McpRequest(method="test")
        assert req.message_type == McpMessageType.REQUEST

    # ----------------------------------------------------------
    # McpResponse
    # ----------------------------------------------------------

    def test_response_with_result(self):
        """McpResponse serializes the result field."""
        resp = McpResponse(id=1, result={"tools": []})
        payload = json.loads(resp.to_json())
        assert payload["result"] == {"tools": []}
        assert "error" not in payload

    def test_response_with_error(self):
        """McpResponse serializes the error field."""
        resp = McpResponse(
            id=1,
            error={"code": -32601, "message": "Method not found"},
        )
        payload = json.loads(resp.to_json())
        assert payload["error"]["code"] == -32601
        assert "result" not in payload

    def test_response_message_type(self):
        """McpResponse reports its message_type as RESPONSE."""
        resp = McpResponse(id=1, result=None)
        assert resp.message_type == McpMessageType.RESPONSE

    # ----------------------------------------------------------
    # McpNotification
    # ----------------------------------------------------------

    def test_notification_has_no_id(self):
        """McpNotification does not include an id."""
        notif = McpNotification(method="notifications/tools/list_changed")
        payload = json.loads(notif.to_json())
        assert "id" not in payload

    def test_notification_to_json(self):
        """McpNotification serializes correctly."""
        notif = McpNotification(
            method="progress",
            params={"token": "abc", "value": 50},
        )
        payload = json.loads(notif.to_json())
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "progress"
        assert payload["params"]["value"] == 50

    def test_notification_to_json_omits_empty_params(self):
        """Empty params dict is omitted from notifications."""
        notif = McpNotification(method="ping")
        payload = json.loads(notif.to_json())
        assert "params" not in payload

    def test_notification_message_type(self):
        """McpNotification reports NOTIFICATION type."""
        notif = McpNotification(method="test")
        assert notif.message_type == McpMessageType.NOTIFICATION

    # ----------------------------------------------------------
    # from_json deserialization
    # ----------------------------------------------------------

    def test_from_json_parses_request_from_string(self):
        """from_json parses a JSON string into McpRequest."""
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            }
        )
        msg = McpMessage.from_json(raw)
        assert isinstance(msg, McpRequest)
        assert msg.id == 1
        assert msg.method == "tools/list"

    def test_from_json_parses_request_from_dict(self):
        """from_json accepts a pre-parsed dictionary."""
        data = {
            "jsonrpc": "2.0",
            "id": "x",
            "method": "tools/call",
            "params": {"name": "test"},
        }
        msg = McpMessage.from_json(data)
        assert isinstance(msg, McpRequest)
        assert msg.params["name"] == "test"

    def test_from_json_parses_response_with_result(self):
        """from_json recognizes a response by the result key."""
        data = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        msg = McpMessage.from_json(data)
        assert isinstance(msg, McpResponse)
        assert msg.result == {"ok": True}
        assert msg.error is None

    def test_from_json_parses_response_with_error(self):
        """from_json recognizes a response by the error key."""
        data = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid"},
        }
        msg = McpMessage.from_json(data)
        assert isinstance(msg, McpResponse)
        assert msg.error["code"] == -32600

    def test_from_json_parses_notification(self):
        """from_json parses a notification (method without id)."""
        data = {
            "jsonrpc": "2.0",
            "method": "notifications/tools/list_changed",
        }
        msg = McpMessage.from_json(data)
        assert isinstance(msg, McpNotification)
        assert msg.method == "notifications/tools/list_changed"

    def test_from_json_raises_on_invalid_data(self):
        """from_json raises ValueError for unclassifiable data."""
        with pytest.raises(ValueError, match="Cannot determine"):
            McpMessage.from_json({"jsonrpc": "2.0"})

    def test_from_json_raises_on_non_object(self):
        """from_json raises ValueError for non-object JSON."""
        with pytest.raises(ValueError, match="Expected a JSON object"):
            McpMessage.from_json("[1, 2, 3]")

    # ----------------------------------------------------------
    # Round-trip
    # ----------------------------------------------------------

    def test_request_round_trip(self):
        """Request survives a to_json / from_json round trip."""
        original = McpRequest(
            id=99,
            method="tools/call",
            params={"name": "query_elements", "arguments": {}},
        )
        restored = McpMessage.from_json(original.to_json())
        assert isinstance(restored, McpRequest)
        assert restored.id == 99
        assert restored.method == "tools/call"
        assert restored.params == original.params

    def test_response_round_trip(self):
        """Response survives a to_json / from_json round trip."""
        original = McpResponse(id=99, result={"tools": [{"name": "test"}]})
        restored = McpMessage.from_json(original.to_json())
        assert isinstance(restored, McpResponse)
        assert restored.result == original.result

    def test_notification_round_trip(self):
        """Notification survives a to_json / from_json round trip."""
        original = McpNotification(method="progress", params={"value": 100})
        restored = McpMessage.from_json(original.to_json())
        assert isinstance(restored, McpNotification)
        assert restored.params["value"] == 100
