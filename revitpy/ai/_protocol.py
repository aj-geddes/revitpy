"""
MCP JSON-RPC protocol message classes.

Provides dataclass-based representations for JSON-RPC 2.0 messages
used by the Model Context Protocol, including serialization and
deserialization helpers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .types import McpMessageType


@dataclass
class McpMessage:
    """Base JSON-RPC 2.0 message."""

    jsonrpc: str = "2.0"
    id: str | int | None = None

    @property
    def message_type(self) -> McpMessageType:
        """Return the message type discriminator."""
        raise NotImplementedError

    def to_json(self) -> str:
        """Serialize the message to a JSON string."""
        raise NotImplementedError

    @classmethod
    def from_json(cls, data: str | dict) -> McpMessage:
        """Deserialize a JSON string or dict into the appropriate message.

        Args:
            data: A JSON string or already-parsed dictionary.

        Returns:
            An ``McpRequest``, ``McpResponse``, or ``McpNotification``.

        Raises:
            ValueError: If the data cannot be parsed or classified.
        """
        if isinstance(data, str):
            parsed = json.loads(data)
        else:
            parsed = data

        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object")

        msg_id = parsed.get("id")

        # Response: has "result" or "error" key
        if "result" in parsed or "error" in parsed:
            return McpResponse(
                jsonrpc=parsed.get("jsonrpc", "2.0"),
                id=msg_id,
                result=parsed.get("result"),
                error=parsed.get("error"),
            )

        method = parsed.get("method")
        if method is None:
            raise ValueError(
                "Cannot determine message type: missing 'method', 'result', and 'error'"
            )

        # Request: has "method" + "id"
        if msg_id is not None:
            return McpRequest(
                jsonrpc=parsed.get("jsonrpc", "2.0"),
                id=msg_id,
                method=method,
                params=parsed.get("params", {}),
            )

        # Notification: has "method" but no "id"
        return McpNotification(
            jsonrpc=parsed.get("jsonrpc", "2.0"),
            method=method,
            params=parsed.get("params", {}),
        )


@dataclass
class McpRequest(McpMessage):
    """JSON-RPC request (expects a response)."""

    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = str(uuid4())

    @property
    def message_type(self) -> McpMessageType:
        return McpMessageType.REQUEST

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method,
        }
        if self.params:
            payload["params"] = self.params
        return json.dumps(payload)


@dataclass
class McpResponse(McpMessage):
    """JSON-RPC response."""

    result: Any = None
    error: dict[str, Any] | None = None

    @property
    def message_type(self) -> McpMessageType:
        return McpMessageType.RESPONSE

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
        }
        if self.error is not None:
            payload["error"] = self.error
        else:
            payload["result"] = self.result
        return json.dumps(payload)


@dataclass
class McpNotification(McpMessage):
    """JSON-RPC notification (no id, no response expected)."""

    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def message_type(self) -> McpMessageType:
        return McpMessageType.NOTIFICATION

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
        }
        if self.params:
            payload["params"] = self.params
        return json.dumps(payload)
