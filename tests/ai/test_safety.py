"""
Unit tests for SafetyGuard policy enforcement and undo stack.
"""

import pytest

from revitpy.ai.exceptions import SafetyViolationError
from revitpy.ai.safety import SafetyGuard
from revitpy.ai.types import (
    ParameterType,
    SafetyConfig,
    SafetyMode,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
)


class TestSafetyGuard:
    """Tests for safety policy validation and undo stack."""

    # ----------------------------------------------------------
    # READ_ONLY mode
    # ----------------------------------------------------------

    def test_read_only_blocks_modify_tools(
        self,
        read_only_safety_config,
        modify_tool_definition,
    ):
        """READ_ONLY mode blocks MODIFY-category tools."""
        guard = SafetyGuard(read_only_safety_config)
        with pytest.raises(SafetyViolationError, match="READ_ONLY"):
            guard.validate_tool_call(
                modify_tool_definition, {"element_id": 1, "value": "x"}
            )

    def test_read_only_allows_query_tools(
        self,
        read_only_safety_config,
        sample_tool_definition,
    ):
        """READ_ONLY mode allows QUERY-category tools."""
        guard = SafetyGuard(read_only_safety_config)
        assert guard.validate_tool_call(sample_tool_definition, {"query": "test"})

    def test_read_only_allows_analyze_tools(self, read_only_safety_config):
        """READ_ONLY mode allows ANALYZE-category tools."""
        guard = SafetyGuard(read_only_safety_config)
        analyze_tool = ToolDefinition(
            name="analyze",
            description="Analyze",
            category=ToolCategory.ANALYZE,
        )
        assert guard.validate_tool_call(analyze_tool, {})

    def test_read_only_allows_export_tools(self, read_only_safety_config):
        """READ_ONLY mode allows EXPORT-category tools."""
        guard = SafetyGuard(read_only_safety_config)
        export_tool = ToolDefinition(
            name="export",
            description="Export",
            category=ToolCategory.EXPORT,
        )
        assert guard.validate_tool_call(export_tool, {})

    # ----------------------------------------------------------
    # CAUTIOUS mode
    # ----------------------------------------------------------

    def test_cautious_allows_modify_tools(
        self,
        cautious_safety_config,
        modify_tool_definition,
    ):
        """CAUTIOUS mode permits MODIFY-category tools."""
        guard = SafetyGuard(cautious_safety_config)
        assert guard.validate_tool_call(
            modify_tool_definition, {"element_id": 1, "value": "x"}
        )

    def test_cautious_allows_query_tools(
        self,
        cautious_safety_config,
        sample_tool_definition,
    ):
        """CAUTIOUS mode permits QUERY-category tools."""
        guard = SafetyGuard(cautious_safety_config)
        assert guard.validate_tool_call(sample_tool_definition, {"query": "test"})

    # ----------------------------------------------------------
    # FULL_ACCESS mode
    # ----------------------------------------------------------

    def test_full_access_allows_all(
        self,
        full_access_safety_config,
        modify_tool_definition,
        sample_tool_definition,
    ):
        """FULL_ACCESS mode allows all tool categories."""
        guard = SafetyGuard(full_access_safety_config)
        assert guard.validate_tool_call(
            modify_tool_definition, {"element_id": 1, "value": "x"}
        )
        assert guard.validate_tool_call(sample_tool_definition, {"query": "test"})

    # ----------------------------------------------------------
    # Blocked tools
    # ----------------------------------------------------------

    def test_blocked_tool_always_denied(self, blocked_safety_config):
        """A tool in the blocked list is always denied."""
        guard = SafetyGuard(blocked_safety_config)
        blocked_tool = ToolDefinition(
            name="dangerous_tool",
            description="Bad",
            category=ToolCategory.QUERY,
        )
        with pytest.raises(SafetyViolationError, match="blocked"):
            guard.validate_tool_call(blocked_tool, {})

    def test_blocked_tool_takes_priority_over_full_access(self, blocked_safety_config):
        """Blocked tools are denied even in FULL_ACCESS mode."""
        guard = SafetyGuard(blocked_safety_config)
        blocked_tool = ToolDefinition(
            name="dangerous_tool",
            description="Bad",
            category=ToolCategory.MODIFY,
        )
        with pytest.raises(SafetyViolationError):
            guard.validate_tool_call(blocked_tool, {})

    # ----------------------------------------------------------
    # Default config
    # ----------------------------------------------------------

    def test_default_config_is_cautious(self):
        """SafetyGuard defaults to CAUTIOUS mode."""
        guard = SafetyGuard()
        assert guard.config.mode == SafetyMode.CAUTIOUS

    # ----------------------------------------------------------
    # Preview
    # ----------------------------------------------------------

    def test_preview_changes_returns_summary(
        self,
        cautious_safety_config,
        modify_tool_definition,
    ):
        """preview_changes returns a summary dict."""
        guard = SafetyGuard(cautious_safety_config)
        preview = guard.preview_changes(
            modify_tool_definition,
            {"element_id": 1, "value": "new"},
        )
        assert preview["tool"] == "modify_tool"
        assert preview["category"] == "modify"
        assert preview["safety_mode"] == "cautious"
        assert preview["arguments"]["element_id"] == 1

    # ----------------------------------------------------------
    # Undo stack
    # ----------------------------------------------------------

    def test_push_and_undo_last(self):
        """push_undo / undo_last follow LIFO order."""
        guard = SafetyGuard()
        guard.push_undo({"op": "first"})
        guard.push_undo({"op": "second"})

        assert guard.undo_last() == {"op": "second"}
        assert guard.undo_last() == {"op": "first"}
        assert guard.undo_last() is None

    def test_undo_stack_bounded(self):
        """Undo stack discards oldest entry when limit is reached."""
        config = SafetyConfig(mode=SafetyMode.CAUTIOUS, max_undo_stack=3)
        guard = SafetyGuard(config)

        for i in range(5):
            guard.push_undo({"op": i})

        stack = guard.get_undo_stack()
        assert len(stack) == 3
        assert stack[0]["op"] == 2
        assert stack[-1]["op"] == 4

    def test_get_undo_stack_returns_copy(self):
        """get_undo_stack returns a copy, not a reference."""
        guard = SafetyGuard()
        guard.push_undo({"op": "a"})
        stack = guard.get_undo_stack()
        stack.clear()
        assert len(guard.get_undo_stack()) == 1

    # ----------------------------------------------------------
    # Safety violation error attributes
    # ----------------------------------------------------------

    def test_safety_violation_error_attributes(
        self, read_only_safety_config, modify_tool_definition
    ):
        """SafetyViolationError carries tool_name and safety_mode."""
        guard = SafetyGuard(read_only_safety_config)
        with pytest.raises(SafetyViolationError) as exc_info:
            guard.validate_tool_call(
                modify_tool_definition,
                {"element_id": 1, "value": "x"},
            )
        err = exc_info.value
        assert err.tool_name == "modify_tool"
        assert err.safety_mode == "read_only"
        assert err.reason is not None

    # ----------------------------------------------------------
    # Parametrized malicious input testing
    # ----------------------------------------------------------

    @pytest.mark.parametrize(
        "malicious_value",
        [
            "'; DROP TABLE elements; --",
            "<script>alert('xss')</script>",
            "../../etc/passwd",
            "\x00null_byte",
            "A" * 100_000,
        ],
    )
    def test_validate_accepts_arbitrary_argument_values(
        self,
        full_access_safety_config,
        sample_tool_definition,
        malicious_value,
    ):
        """Validation does not crash on unusual argument values."""
        guard = SafetyGuard(full_access_safety_config)
        result = guard.validate_tool_call(
            sample_tool_definition,
            {"query": malicious_value},
        )
        assert result is True
