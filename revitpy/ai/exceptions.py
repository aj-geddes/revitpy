"""
AI module exceptions for RevitPy.

This module defines all exceptions used throughout the AI/MCP layer,
providing specific error types for server, tool, safety, and prompt
operations.
"""

from __future__ import annotations

from typing import Any


class AiError(Exception):
    """Base exception for all AI-related errors."""

    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.cause = cause
        if cause is not None:
            self.__cause__ = cause


class McpServerError(AiError):
    """Exception raised when MCP server operations fail."""

    def __init__(
        self,
        message: str,
        *,
        host: str | None = None,
        port: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.host = host
        self.port = port


class ToolExecutionError(AiError):
    """Exception raised when tool execution fails."""

    def __init__(
        self,
        message: str,
        *,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.tool_name = tool_name
        self.arguments = arguments


class SafetyViolationError(AiError):
    """Exception raised when a safety policy is violated."""

    def __init__(
        self,
        message: str,
        *,
        tool_name: str | None = None,
        safety_mode: str | None = None,
        reason: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.tool_name = tool_name
        self.safety_mode = safety_mode
        self.reason = reason


class PromptError(AiError):
    """Exception raised when prompt rendering or lookup fails."""

    def __init__(
        self,
        message: str,
        *,
        template_name: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
        self.template_name = template_name
