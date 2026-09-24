"""
Safety guard for AI tool execution.

Enforces safety policies that control which tools may be executed
based on the configured ``SafetyMode``, gates ``CAUTIOUS``-mode tools
behind an explicit confirmation callback, and provides an undo stack
so that modifications can be tracked.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias

from loguru import logger

from .exceptions import SafetyViolationError
from .types import (
    SafetyConfig,
    SafetyMode,
    ToolCategory,
    ToolDefinition,
)

# Called with the tool and its arguments when a tool needs confirmation.
# May be sync or async.  Only a literal ``True`` approves the call; any
# other return value (or an exception) denies it.
ConfirmationCallback: TypeAlias = Callable[
    [ToolDefinition, dict[str, Any]], "bool | Awaitable[bool]"
]


class SafetyGuard:
    """Validates tool calls against a safety policy.

    Args:
        config: Safety configuration.  Defaults to ``CAUTIOUS`` mode
            when not supplied.
        confirmation_callback: Invoked for tools whose category is listed
            in ``SafetyConfig.require_confirmation_for`` while in
            ``CAUTIOUS`` mode.  Anything other than ``True`` denies the
            call.  When ``None``, such tools are always denied.
    """

    def __init__(
        self,
        config: SafetyConfig | None = None,
        *,
        confirmation_callback: ConfirmationCallback | None = None,
    ) -> None:
        self._config = config or SafetyConfig(mode=SafetyMode.CAUTIOUS)
        self._confirmation_callback = confirmation_callback
        self._undo_stack: list[dict[str, Any]] = []

    @property
    def config(self) -> SafetyConfig:
        """Return the active safety configuration."""
        return self._config

    @property
    def confirmation_callback(self) -> ConfirmationCallback | None:
        """Return the configured confirmation callback, if any."""
        return self._confirmation_callback

    @confirmation_callback.setter
    def confirmation_callback(self, callback: ConfirmationCallback | None) -> None:
        self._confirmation_callback = callback

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_tool_call(
        self,
        tool: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """Check whether a tool call is allowed under the current policy.

        Synchronous variant.  An async confirmation callback cannot be
        awaited here and results in denial; use
        :meth:`avalidate_tool_call` from async code.

        Args:
            tool: The tool about to be executed.
            arguments: The arguments that would be passed.

        Returns:
            ``True`` when the call is permitted.

        Raises:
            SafetyViolationError: When the call is blocked by policy or
                confirmation is required and not granted.
        """
        if not self._check_policy(tool):
            return True

        decision = self._invoke_callback(tool, arguments)
        if inspect.isawaitable(decision):
            close = getattr(decision, "close", None)
            if callable(close):
                close()
            raise self._deny(
                tool, "confirmation callback is async; use avalidate_tool_call()"
            )
        return self._finish(tool, decision)

    async def avalidate_tool_call(
        self,
        tool: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """Async variant of :meth:`validate_tool_call`.

        Supports both sync and async confirmation callbacks.

        Raises:
            SafetyViolationError: When the call is blocked by policy or
                confirmation is required and not granted.
        """
        if not self._check_policy(tool):
            return True

        decision: object = self._invoke_callback(tool, arguments)
        if inspect.isawaitable(decision):
            try:
                decision = await decision
            except Exception as exc:
                raise self._deny(tool, f"confirmation callback failed: {exc}") from exc
        return self._finish(tool, decision)

    def _check_policy(self, tool: ToolDefinition) -> bool:
        """Apply blocked-list and mode rules.

        Returns:
            ``True`` when the call additionally needs confirmation.

        Raises:
            SafetyViolationError: When the tool is denied outright.
        """
        mode = self._config.mode

        # Explicitly blocked tools are always denied
        if tool.name in self._config.blocked_tools:
            logger.warning("Tool '{}' is blocked by safety policy", tool.name)
            raise SafetyViolationError(
                f"Tool '{tool.name}' is blocked by safety policy",
                tool_name=tool.name,
                safety_mode=mode.value,
                reason="Tool is in the blocked list",
            )

        if mode == SafetyMode.READ_ONLY and tool.category == ToolCategory.MODIFY:
            logger.warning("READ_ONLY mode blocked modify tool '{}'", tool.name)
            raise SafetyViolationError(
                f"Modify tool '{tool.name}' denied in READ_ONLY mode",
                tool_name=tool.name,
                safety_mode=mode.value,
                reason="Modify operations are not allowed in READ_ONLY mode",
            )

        if self._needs_confirmation(tool):
            return True

        logger.debug("Tool '{}' validated under {} mode", tool.name, mode.value)
        return False

    def _needs_confirmation(self, tool: ToolDefinition) -> bool:
        return (
            self._config.mode == SafetyMode.CAUTIOUS
            and tool.category in self._config.require_confirmation_for
        )

    def _invoke_callback(
        self,
        tool: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool | Awaitable[bool]:
        callback = self._confirmation_callback
        if callback is None:
            raise self._deny(tool, "no confirmation callback is configured")
        try:
            return callback(tool, arguments)
        except Exception as exc:
            raise self._deny(tool, f"confirmation callback failed: {exc}") from exc

    def _finish(self, tool: ToolDefinition, decision: object) -> bool:
        if decision is not True:
            raise self._deny(tool, "denied by confirmation callback")
        logger.info("Confirmation granted for tool '{}'", tool.name)
        return True

    def _deny(self, tool: ToolDefinition, reason: str) -> SafetyViolationError:
        logger.warning("Confirmation denied for tool '{}': {}", tool.name, reason)
        return SafetyViolationError(
            f"Tool '{tool.name}' requires confirmation: {reason}",
            tool_name=tool.name,
            safety_mode=self._config.mode.value,
            reason=reason,
        )

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
            "requires_confirmation": self._needs_confirmation(tool),
            "confirmation_configured": self._confirmation_callback is not None,
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
