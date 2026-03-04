"""
Unit tests for RevitTools registration, execution, and MCP format.
"""

from typing import Any

import pytest

from revitpy.ai.exceptions import ToolExecutionError
from revitpy.ai.tools import RevitTools
from revitpy.ai.types import (
    ParameterType,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
    ToolResult,
    ToolResultStatus,
)


class TestRevitTools:
    """Tests for the RevitTools registry and execution engine."""

    # ----------------------------------------------------------
    # Registration
    # ----------------------------------------------------------

    def test_register_tool(self, revit_tools, sample_tool_definition):
        """Registering a tool makes it retrievable by name."""

        def handler(**kw):
            return {"ok": True}

        revit_tools.register_tool(sample_tool_definition, handler)

        defn = revit_tools.get_tool("test_tool")
        assert defn is not None
        assert defn.name == "test_tool"
        assert defn.category == ToolCategory.QUERY

    def test_register_overwrites_existing(self, revit_tools, sample_tool_definition):
        """Re-registering under the same name replaces the entry."""
        revit_tools.register_tool(sample_tool_definition, lambda **kw: "first")
        revit_tools.register_tool(sample_tool_definition, lambda **kw: "second")

        result = revit_tools.execute_tool("test_tool", {"query": "x"})
        assert result.data == "second"

    def test_get_tool_unknown_returns_none(self, revit_tools):
        """Getting an unregistered tool returns None."""
        assert revit_tools.get_tool("nonexistent") is None

    # ----------------------------------------------------------
    # Listing
    # ----------------------------------------------------------

    def test_list_tools_includes_builtins(self, revit_tools):
        """Built-in tools are registered at init time."""
        tools = revit_tools.list_tools()
        names = {t.name for t in tools}
        assert "query_elements" in names
        assert "get_element" in names
        assert "modify_parameter" in names
        assert "get_quantities" in names
        assert "validate_model" in names
        assert "export_data" in names

    def test_list_tools_includes_custom(self, revit_tools, sample_tool_definition):
        """Custom tools appear in the list alongside builtins."""
        revit_tools.register_tool(sample_tool_definition, lambda **kw: None)
        names = {t.name for t in revit_tools.list_tools()}
        assert "test_tool" in names

    # ----------------------------------------------------------
    # Execution
    # ----------------------------------------------------------

    def test_execute_builtin_query_elements(self, revit_tools):
        """Built-in query_elements returns placeholder data."""
        result = revit_tools.execute_tool("query_elements", {"category": "Walls"})
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["category"] == "Walls"
        assert result.execution_time_ms >= 0

    def test_execute_builtin_get_element(self, revit_tools):
        """Built-in get_element returns placeholder data."""
        result = revit_tools.execute_tool("get_element", {"element_id": 42})
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["element_id"] == 42

    def test_execute_builtin_modify_parameter(self, revit_tools):
        """Built-in modify_parameter returns success."""
        result = revit_tools.execute_tool(
            "modify_parameter",
            {
                "element_id": 1,
                "parameter_name": "Height",
                "value": "10",
            },
        )
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["success"] is True

    def test_execute_builtin_get_quantities(self, revit_tools):
        """Built-in get_quantities returns placeholder data."""
        result = revit_tools.execute_tool("get_quantities", {"category": "Walls"})
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["category"] == "Walls"

    def test_execute_builtin_validate_model(self, revit_tools):
        """Built-in validate_model returns a passing report."""
        result = revit_tools.execute_tool("validate_model", {})
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["passed"] is True

    def test_execute_builtin_export_data(self, revit_tools):
        """Built-in export_data returns placeholder data."""
        result = revit_tools.execute_tool("export_data", {"category": "Doors"})
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["category"] == "Doors"

    def test_execute_custom_tool(self, revit_tools, sample_tool_definition):
        """Executing a custom tool invokes its handler."""
        revit_tools.register_tool(
            sample_tool_definition,
            lambda query, limit=10: {"results": [query], "limit": limit},
        )
        result = revit_tools.execute_tool("test_tool", {"query": "find walls"})
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["results"] == ["find walls"]
        assert result.data["limit"] == 10

    def test_execute_unknown_tool_returns_error(self, revit_tools):
        """Executing a non-existent tool returns an ERROR result."""
        result = revit_tools.execute_tool("no_such_tool", {})
        assert result.status == ToolResultStatus.ERROR
        assert "Unknown tool" in result.error

    def test_execute_missing_required_param_returns_error(self, revit_tools):
        """Missing required parameters are reported as errors."""
        result = revit_tools.execute_tool("get_element", {})
        assert result.status == ToolResultStatus.ERROR
        assert "Missing required parameters" in result.error

    def test_execute_handler_raises_wraps_in_tool_error(self, revit_tools):
        """Handler exceptions are wrapped in ToolExecutionError."""
        defn = ToolDefinition(
            name="boom",
            description="Always fails",
            category=ToolCategory.QUERY,
        )
        revit_tools.register_tool(
            defn, lambda: (_ for _ in ()).throw(RuntimeError("bang"))
        )
        with pytest.raises(ToolExecutionError, match="bang"):
            revit_tools.execute_tool("boom", {})

    # ----------------------------------------------------------
    # MCP format
    # ----------------------------------------------------------

    def test_to_mcp_tool_list_structure(self, revit_tools):
        """MCP tool list entries have correct schema keys."""
        mcp_list = revit_tools.to_mcp_tool_list()
        assert isinstance(mcp_list, list)
        assert len(mcp_list) >= 6  # built-ins

        first = mcp_list[0]
        assert "name" in first
        assert "description" in first
        assert "inputSchema" in first
        assert first["inputSchema"]["type"] == "object"

    def test_to_mcp_tool_list_required_params(self, revit_tools):
        """Required parameters appear in the inputSchema."""
        mcp_list = revit_tools.to_mcp_tool_list()
        get_elem = next(t for t in mcp_list if t["name"] == "get_element")
        schema = get_elem["inputSchema"]
        assert "element_id" in schema["properties"]
        assert "element_id" in schema.get("required", [])

    def test_to_mcp_tool_list_optional_params(self, revit_tools):
        """Optional parameters have defaults and are not in required."""
        mcp_list = revit_tools.to_mcp_tool_list()
        export = next(t for t in mcp_list if t["name"] == "export_data")
        schema = export["inputSchema"]
        props = schema["properties"]
        assert "format" in props
        assert props["format"].get("default") == "json"
        required = schema.get("required", [])
        assert "format" not in required

    def test_to_mcp_tool_list_with_custom_tool(
        self, revit_tools, sample_tool_definition
    ):
        """Custom registered tools also appear in the MCP list."""
        revit_tools.register_tool(sample_tool_definition, lambda **kw: None)
        mcp_list = revit_tools.to_mcp_tool_list()
        names = {t["name"] for t in mcp_list}
        assert "test_tool" in names
