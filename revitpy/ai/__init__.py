"""
RevitPy AI/MCP Integration Layer.

Provides Model Context Protocol (MCP) server support, tool registration
and execution, safety controls, and prompt template management for
AI-assisted Revit development workflows.
"""

from ._protocol import McpMessage, McpNotification, McpRequest, McpResponse
from .exceptions import (
    AiError,
    McpServerError,
    PromptError,
    SafetyViolationError,
    ToolExecutionError,
)
from .prompts import PromptLibrary
from .safety import SafetyGuard
from .server import McpServer
from .tools import RevitTools
from .types import (
    McpMessageType,
    McpServerConfig,
    ParameterType,
    SafetyConfig,
    SafetyMode,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
    ToolResult,
    ToolResultStatus,
)

__all__ = [
    # Server
    "McpServer",
    # Tools
    "RevitTools",
    "ToolDefinition",
    "ToolParameter",
    "ToolResult",
    # Safety
    "SafetyGuard",
    "SafetyConfig",
    "SafetyMode",
    # Prompts
    "PromptLibrary",
    # Protocol messages
    "McpMessage",
    "McpRequest",
    "McpResponse",
    "McpNotification",
    # Enums
    "ToolCategory",
    "ToolResultStatus",
    "McpMessageType",
    "ParameterType",
    # Configuration
    "McpServerConfig",
    # Exceptions
    "AiError",
    "McpServerError",
    "ToolExecutionError",
    "SafetyViolationError",
    "PromptError",
]
