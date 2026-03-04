"""
Safety guard for AI tool execution.

Enforces safety policies that control which tools may be executed
based on the configured ``SafetyMode``, and provides an undo stack
so that modifications can be rolled back.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .exceptions import SafetyViolationError
from .types import (
    SafetyConfig,
    SafetyMode,
    ToolCategory,
    ToolDefinition,
)


class SafetyGuard:
    """Validates tool calls against a safety policy.

    Args:
        config: Safety configuration.  Defaults to ``CAUTIOUS`` mode
            when not supplied.
    """

    def __init__(self, config: SafetyConfig | None = None) -> None:
        self._config = config or SafetyConfig(mode=SafetyMode.CAUTIOUS)
        self._undo_stack: list[dict[str, Any]] = []

    @property
    def config(self) -> SafetyConfig:
        """Return the active safety configuration."""
        return self._config

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_tool_call(
        self,
        tool: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """Check whether a tool call is allowed under the current policy.

        Args:
            tool: The tool about to be executed.
            arguments: The arguments that would be passed.

        Returns:
            ``True`` when the call is permitted.

        Raises:
            SafetyViolationError: When the call is blocked by policy.
        """
        # Explicitly blocked tools are always denied
        if tool.name in self._config.blocked_tools:
            logger.warning("Tool '{}' is blocked by safety policy", tool.name)
            raise SafetyViolationError(
                f"Tool '{tool.name}' is blocked by safety policy",
                tool_name=tool.name,
                safety_mode=self._config.mode.value,
                reason="Tool is in the blocked list",
            )

        mode = self._config.mode

        if mode == SafetyMode.READ_ONLY:
            if tool.category == ToolCategory.MODIFY:
                logger.warning("READ_ONLY mode blocked modify tool '{}'", tool.name)
                raise SafetyViolationError(
                    f"Modify tool '{tool.name}' denied in READ_ONLY mode",
                    tool_name=tool.name,
                    safety_mode=mode.value,
                    reason="Modify operations are not allowed in READ_ONLY mode",
                )

        if mode == SafetyMode.CAUTIOUS:
            if tool.category in self._config.require_confirmation_for:
                logger.info(
                    "CAUTIOUS mode: tool '{}' requires confirmation",
                    tool.name,
                )

        logger.debug("Tool '{}' validated under {} mode", tool.name, mode.value)
        return True

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def preview_changes(
        self,
        tool: ToolDefinition,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a preview of the changes a tool call would make.

        This is a dry-run summary; no actual changes are applied.

        Args:
            tool: The tool definition.
            arguments: The arguments that would be passed.

        Returns:
            A dictionary describing the prospective changes.
        """
        return {
            "tool": tool.name,
            "category": tool.category.value,
            "arguments": arguments,
            "safety_mode": self._config.mode.value,
            "requires_confirmation": (
                tool.category in self._config.require_confirmation_for
            ),
            "is_blocked": tool.name in self._config.blocked_tools,
        }

    # ------------------------------------------------------------------
    # Undo stack
    # ------------------------------------------------------------------

    def push_undo(self, operation: dict[str, Any]) -> None:
        """Push an operation onto the undo stack.

        The stack is bounded by ``SafetyConfig.max_undo_stack``.
        When the limit is reached the oldest entry is discarded.

        Args:
            operation: A dictionary describing the operation that can
                be reversed.
        """
        if len(self._undo_stack) >= self._config.max_undo_stack:
            self._undo_stack.pop(0)
        self._undo_stack.append(operation)
        logger.debug(
            "Pushed undo operation; stack size = {}",
            len(self._undo_stack),
        )

    def undo_last(self) -> dict[str, Any] | None:
        """Pop and return the most recent undo entry, or ``None``."""
        if not self._undo_stack:
            return None
        entry = self._undo_stack.pop()
        logger.debug(
            "Popped undo operation; stack size = {}",
            len(self._undo_stack),
        )
        return entry

    def get_undo_stack(self) -> list[dict[str, Any]]:
        """Return a copy of the current undo stack."""
        return list(self._undo_stack)
