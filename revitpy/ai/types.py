"""
Type definitions and enums for the RevitPy AI/MCP layer.

This module provides all type definitions, enums, and dataclasses used
throughout the AI system for tool definitions, safety configuration,
and MCP server settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SafetyMode(Enum):
    """Safety enforcement levels for tool execution."""

    READ_ONLY = "read_only"
    CAUTIOUS = "cautious"
    FULL_ACCESS = "full_access"


class ToolCategory(Enum):
    """Categories of available tools."""

    QUERY = "query"
    MODIFY = "modify"
    ANALYZE = "analyze"
    EXPORT = "export"


class ToolResultStatus(Enum):
    """Outcome status of a tool execution."""

    SUCCESS = "success"
    ERROR = "error"
    DENIED = "denied"


class McpMessageType(Enum):
    """Types of MCP JSON-RPC messages."""

    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"


class ParameterType(Enum):
    """JSON Schema parameter types for tool definitions."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """Definition of a single tool parameter."""

    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolDefinition:
    """Full definition of a tool exposed via MCP."""

    name: str
    description: str
    category: ToolCategory
    parameters: list[ToolParameter] = field(default_factory=list)
    returns_description: str = ""


@dataclass
class ToolResult:
    """Result returned from tool execution."""

    status: ToolResultStatus
    data: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0


@dataclass
class SafetyConfig:
    """Safety policy configuration."""

    mode: SafetyMode = SafetyMode.CAUTIOUS
    max_undo_stack: int = 50
    require_confirmation_for: list[ToolCategory] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)


@dataclass
class McpServerConfig:
    """Configuration for the MCP WebSocket server."""

    host: str = "localhost"
    port: int = 8765
    name: str = "revitpy-mcp"
    version: str = "1.0.0"
