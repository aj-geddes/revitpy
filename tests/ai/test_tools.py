"""
Unit tests for RevitTools registration, execution, and MCP format.
"""

import csv
import io
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


class TestBuiltinToolsNotConnected:
    """Built-in tools fail clearly when no Revit document is connected."""

    @pytest.mark.parametrize(
        ("tool_name", "args"),
        [
            ("query_elements", {"category": "Walls"}),
            ("get_element", {"element_id": 1}),
            (
                "modify_parameter",
                {"element_id": 1, "parameter_name": "Mark", "value": "X"},
            ),
            ("get_quantities", {"category": "Walls"}),
            ("validate_model", {}),
            ("export_data", {"category": "Walls"}),
        ],
    )
    def test_not_connected_raises(self, revit_tools, tool_name, args):
        """Every built-in raises ToolExecutionError without a context."""
        with pytest.raises(
            ToolExecutionError, match="Not connected to a Revit document"
        ):
            revit_tools.execute_tool(tool_name, args)

    def test_no_active_document_raises(self, fake_api):
        """A context without an active document is treated as not connected."""
        fake_api.active_document = None
        tools = RevitTools(fake_api)
        with pytest.raises(
            ToolExecutionError, match="Not connected to a Revit document"
        ):
            tools.execute_tool("query_elements", {"category": "Walls"})

    def test_modify_parameter_never_reports_fake_success(self, revit_tools):
        """modify_parameter without a document does not claim success."""
        with pytest.raises(ToolExecutionError):
            revit_tools.execute_tool(
                "modify_parameter",
                {"element_id": 1, "parameter_name": "Mark", "value": "X"},
            )


class TestBuiltinToolsConnected:
    """Built-in tools operate on the connected document."""

    def test_query_elements_by_category(self, connected_tools):
        """query_elements returns the elements in the category."""
        result = connected_tools.execute_tool("query_elements", {"category": "Walls"})
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["count"] == 3
        assert [e["element_id"] for e in result.data["elements"]] == [1, 2, 3]
        for elem in result.data["elements"]:
            assert elem["name"]
            assert elem["category"] == "Walls"

    def test_query_elements_with_filter(self, connected_tools):
        """The filter is a case-insensitive name substring match."""
        result = connected_tools.execute_tool(
            "query_elements", {"category": "Walls", "filter": "wall b"}
        )
        assert result.data["count"] == 1
        assert result.data["elements"][0]["element_id"] == 2

    def test_get_element(self, connected_tools):
        """get_element returns the element's name and parameters."""
        result = connected_tools.execute_tool("get_element", {"element_id": 1})
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["name"] == "Wall A"
        assert result.data["parameters"]["Mark"] == "W1"

    def test_get_element_not_found(self, connected_tools):
        """An unknown element id is a clear failure."""
        with pytest.raises(ToolExecutionError, match="Element 999 not found"):
            connected_tools.execute_tool("get_element", {"element_id": 999})

    def test_modify_parameter_inside_transaction(self, connected_tools, fake_api):
        """modify_parameter sets the value inside a committed transaction."""
        result = connected_tools.execute_tool(
            "modify_parameter",
            {"element_id": 3, "parameter_name": "Mark", "value": "W9"},
        )
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["success"] is True
        assert result.data["old_value"] is None
        assert result.data["new_value"] == "W9"
        assert fake_api.elements[2].params["Mark"] == "W9"
        assert fake_api.log == [
            ("start", "MCP: set Mark on element 3"),
            ("set", 3, "Mark", "W9"),
            ("commit",),
        ]

    def test_modify_parameter_reports_old_value(self, connected_tools):
        """The previous parameter value is reported."""
        result = connected_tools.execute_tool(
            "modify_parameter",
            {"element_id": 1, "parameter_name": "Mark", "value": "W2"},
        )
        assert result.data["old_value"] == "W1"

    def test_modify_parameter_failure_rolls_back(self, connected_tools, fake_api):
        """A failing set rolls the transaction back and raises."""
        fake_api.elements[0].fail_on_set = True
        with pytest.raises(ToolExecutionError, match="read-only"):
            connected_tools.execute_tool(
                "modify_parameter",
                {"element_id": 1, "parameter_name": "Mark", "value": "X"},
            )
        assert fake_api.log[-1] == ("rollback",)

    def test_modify_parameter_unknown_element(self, connected_tools, fake_api):
        """An unknown element fails before any transaction is opened."""
        with pytest.raises(ToolExecutionError, match="Element 999 not found"):
            connected_tools.execute_tool(
                "modify_parameter",
                {"element_id": 999, "parameter_name": "Mark", "value": "X"},
            )
        assert fake_api.log == []

    def test_get_quantities(self, connected_tools):
        """get_quantities counts elements per type."""
        result = connected_tools.execute_tool("get_quantities", {"category": "Walls"})
        assert result.status == ToolResultStatus.SUCCESS
        assert result.data["total"] == 3
        assert result.data["quantities"] == [
            {"group": "Brick 300", "count": 1},
            {"group": "Generic 200", "count": 2},
        ]

    def test_validate_model_default_checks(self, connected_tools):
        """validate_model finds unnamed elements and duplicate marks."""
        result = connected_tools.execute_tool("validate_model", {})
        data = result.data
        assert data["passed"] is False
        assert data["checks_run"] == ["unnamed_elements", "duplicate_marks"]
        unnamed = [i for i in data["issues"] if i["check"] == "unnamed_elements"]
        assert [i["element_id"] for i in unnamed] == [4]
        dupes = [i for i in data["issues"] if i["check"] == "duplicate_marks"]
        assert len(dupes) == 1
        assert dupes[0]["mark"] == "W1"
        assert dupes[0]["element_ids"] == [1, 2]

    def test_validate_model_unknown_check(self, connected_tools):
        """Unsupported checks are rejected."""
        with pytest.raises(ToolExecutionError, match="Unknown checks"):
            connected_tools.execute_tool("validate_model", {"checks": ["bogus"]})

    def test_export_data_json(self, connected_tools):
        """JSON export returns one row per element."""
        result = connected_tools.execute_tool("export_data", {"category": "Walls"})
        assert result.data["format"] == "json"
        assert result.data["row_count"] == 3
        assert all(isinstance(row, dict) for row in result.data["data"])

    def test_export_data_csv(self, connected_tools):
        """CSV export produces parseable CSV text."""
        result = connected_tools.execute_tool(
            "export_data", {"category": "Walls", "format": "csv"}
        )
        rows = list(csv.DictReader(io.StringIO(result.data["data"])))
        assert [r["element_id"] for r in rows] == ["1", "2", "3"]

    def test_export_data_unsupported_format(self, connected_tools):
        """Unsupported formats are rejected rather than faked."""
        with pytest.raises(ToolExecutionError, match="Unsupported export format"):
            connected_tools.execute_tool(
                "export_data", {"category": "Walls", "format": "xlsx"}
            )

    def test_unreadable_name_falls_back_to_raw_revit_name(self, fake_api):
        """If Element.name raises, the raw Revit element's Name is used."""

        class BrokenName:
            id = 9
            category = "Walls"
            _revit_element = type("Raw", (), {"Name": "Raw Wall"})()

            @property
            def name(self):
                raise RuntimeError("parameter lookup failed")

            def get_parameter_value(self, name):
                raise KeyError(name)

        fake_api.elements.append(BrokenName())
        result = RevitTools(fake_api).execute_tool(
            "query_elements", {"category": "Walls", "filter": "raw"}
        )
        assert result.data["elements"] == [
            {"element_id": 9, "name": "Raw Wall", "category": "Walls"}
        ]
