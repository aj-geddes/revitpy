"""
Tool registry and execution engine for RevitPy MCP integration.

Provides the ``RevitTools`` class which manages tool definitions,
validates arguments, dispatches execution, and converts tools to
MCP-compatible JSON Schema format.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from loguru import logger

from .exceptions import ToolExecutionError
from .types import (
    ParameterType,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
    ToolResult,
    ToolResultStatus,
)


class RevitTools:
    """Registry of tools that can be invoked through the MCP server.

    Args:
        context: Optional application context forwarded to built-in
            tool handlers.  When ``None`` the built-in handlers return
            placeholder results.
    """

    def __init__(self, context: Any = None) -> None:
        self._context = context
        self._tools: dict[str, tuple[ToolDefinition, Callable]] = {}
        self._register_builtins()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_tool(
        self,
        definition: ToolDefinition,
        handler: Callable,
    ) -> None:
        """Register a tool with its handler.

        Args:
            definition: The tool's metadata and parameter schema.
            handler: A callable invoked when the tool is executed.
        """
        logger.debug("Registering tool: {}", definition.name)
        self._tools[definition.name] = (definition, handler)

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Return the definition of a registered tool, or ``None``."""
        entry = self._tools.get(name)
        return entry[0] if entry else None

    def list_tools(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return [defn for defn, _ in self._tools.values()]

    def execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute a tool by name.

        Validates that the tool exists, checks required parameters, then
        invokes the handler and wraps the outcome in a ``ToolResult``.

        Args:
            name: The tool name.
            arguments: Keyword arguments for the tool handler.

        Returns:
            A ``ToolResult`` indicating success, error, or denial.
        """
        entry = self._tools.get(name)
        if entry is None:
            logger.warning("Unknown tool requested: {}", name)
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Unknown tool: {name}",
            )

        definition, handler = entry

        # Validate required parameters
        missing = [
            p.name
            for p in definition.parameters
            if p.required and p.name not in arguments
        ]
        if missing:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Missing required parameters: {', '.join(missing)}",
            )

        start = time.monotonic()
        try:
            result_data = handler(**arguments)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.debug("Tool {} executed in {:.1f}ms", name, elapsed_ms)
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                data=result_data,
                execution_time_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error("Tool {} failed: {}", name, exc)
            raise ToolExecutionError(
                f"Tool '{name}' failed: {exc}",
                tool_name=name,
                arguments=arguments,
                cause=exc,
            ) from exc

    def to_mcp_tool_list(self) -> list[dict[str, Any]]:
        """Convert all tools to MCP-format JSON Schema definitions."""
        result: list[dict[str, Any]] = []
        for definition, _ in self._tools.values():
            properties: dict[str, Any] = {}
            required: list[str] = []
            for param in definition.parameters:
                properties[param.name] = {
                    "type": param.type.value,
                    "description": param.description,
                }
                if param.default is not None:
                    properties[param.name]["default"] = param.default
                if param.required:
                    required.append(param.name)

            tool_entry: dict[str, Any] = {
                "name": definition.name,
                "description": definition.description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                },
            }
            if required:
                tool_entry["inputSchema"]["required"] = required
            result.append(tool_entry)
        return result

    # ------------------------------------------------------------------
    # Built-in tools
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        """Register the default set of built-in tools."""
        self.register_tool(
            ToolDefinition(
                name="query_elements",
                description="Query Revit elements by category and filter",
                category=ToolCategory.QUERY,
                parameters=[
                    ToolParameter(
                        name="category",
                        type=ParameterType.STRING,
                        description="Element category (e.g. Walls, Doors)",
                    ),
                    ToolParameter(
                        name="filter",
                        type=ParameterType.STRING,
                        description="Optional filter expression",
                        required=False,
                        default="",
                    ),
                ],
                returns_description="List of matching elements",
            ),
            self._handle_query_elements,
        )

        self.register_tool(
            ToolDefinition(
                name="get_element",
                description="Get a single Revit element by ID",
                category=ToolCategory.QUERY,
                parameters=[
                    ToolParameter(
                        name="element_id",
                        type=ParameterType.INTEGER,
                        description="Revit element ID",
                    ),
                ],
                returns_description="Element details",
            ),
            self._handle_get_element,
        )

        self.register_tool(
            ToolDefinition(
                name="modify_parameter",
                description="Modify a parameter value on a Revit element",
                category=ToolCategory.MODIFY,
                parameters=[
                    ToolParameter(
                        name="element_id",
                        type=ParameterType.INTEGER,
                        description="Revit element ID",
                    ),
                    ToolParameter(
                        name="parameter_name",
                        type=ParameterType.STRING,
                        description="Parameter name to modify",
                    ),
                    ToolParameter(
                        name="value",
                        type=ParameterType.STRING,
                        description="New parameter value",
                    ),
                ],
                returns_description="Modification result",
            ),
            self._handle_modify_parameter,
        )

        self.register_tool(
            ToolDefinition(
                name="get_quantities",
                description="Get quantity takeoff for elements",
                category=ToolCategory.ANALYZE,
                parameters=[
                    ToolParameter(
                        name="category",
                        type=ParameterType.STRING,
                        description="Element category for takeoff",
                    ),
                    ToolParameter(
                        name="group_by",
                        type=ParameterType.STRING,
                        description="Property to group quantities by",
                        required=False,
                        default="type",
                    ),
                ],
                returns_description="Quantity takeoff data",
            ),
            self._handle_get_quantities,
        )

        self.register_tool(
            ToolDefinition(
                name="validate_model",
                description="Run validation checks on the Revit model",
                category=ToolCategory.ANALYZE,
                parameters=[
                    ToolParameter(
                        name="checks",
                        type=ParameterType.ARRAY,
                        description="List of validation checks to run",
                        required=False,
                        default=None,
                    ),
                ],
                returns_description="Validation report",
            ),
            self._handle_validate_model,
        )

        self.register_tool(
            ToolDefinition(
                name="export_data",
                description="Export element data to a structured format",
                category=ToolCategory.EXPORT,
                parameters=[
                    ToolParameter(
                        name="category",
                        type=ParameterType.STRING,
                        description="Element category to export",
                    ),
                    ToolParameter(
                        name="format",
                        type=ParameterType.STRING,
                        description="Export format (json, csv, xlsx)",
                        required=False,
                        default="json",
                    ),
                ],
                returns_description="Exported data",
            ),
            self._handle_export_data,
        )

    # ------------------------------------------------------------------
    # Built-in handlers
    # ------------------------------------------------------------------

    def _handle_query_elements(
        self,
        category: str,
        filter: str = "",  # noqa: A002
    ) -> dict[str, Any]:
        if self._context is None:
            return {
                "elements": [],
                "count": 0,
                "category": category,
                "filter": filter,
            }
        return {"elements": [], "count": 0, "category": category}

    def _handle_get_element(
        self,
        element_id: int,
    ) -> dict[str, Any]:
        if self._context is None:
            return {
                "element_id": element_id,
                "name": "Placeholder",
                "category": "Unknown",
                "parameters": {},
            }
        return {"element_id": element_id}

    def _handle_modify_parameter(
        self,
        element_id: int,
        parameter_name: str,
        value: str,
    ) -> dict[str, Any]:
        if self._context is None:
            return {
                "element_id": element_id,
                "parameter_name": parameter_name,
                "old_value": None,
                "new_value": value,
                "success": True,
            }
        return {"success": True}

    def _handle_get_quantities(
        self,
        category: str,
        group_by: str = "type",
    ) -> dict[str, Any]:
        if self._context is None:
            return {
                "category": category,
                "group_by": group_by,
                "quantities": [],
                "total": 0,
            }
        return {"quantities": [], "total": 0}

    def _handle_validate_model(
        self,
        checks: list[str] | None = None,
    ) -> dict[str, Any]:
        if self._context is None:
            return {
                "checks_run": checks or ["all"],
                "issues": [],
                "passed": True,
            }
        return {"issues": [], "passed": True}

    def _handle_export_data(
        self,
        category: str,
        format: str = "json",  # noqa: A002
    ) -> dict[str, Any]:
        if self._context is None:
            return {
                "category": category,
                "format": format,
                "data": [],
                "row_count": 0,
            }
        return {"data": [], "row_count": 0}
