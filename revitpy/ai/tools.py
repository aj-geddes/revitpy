"""
Tool registry and execution engine for RevitPy MCP integration.

Provides the ``RevitTools`` class which manages tool definitions,
validates arguments, dispatches execution, and converts tools to
MCP-compatible JSON Schema format.
"""

from __future__ import annotations

import csv
import io
import time
from collections.abc import Callable
from typing import Any, Protocol

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

NOT_CONNECTED_MESSAGE = "Not connected to a Revit document"

_GROUP_BY_ALIASES: dict[str, str] = {
    "type": "Type",
    "family_name": "Family",
    "level": "Level",
    "name": "Name",
    "mark": "Mark",
    "comments": "Comments",
}
_SUPPORTED_CHECKS = ("unnamed_elements", "duplicate_marks")
_EXPORT_FORMATS = ("json", "csv")
_EXPORT_FIELDS = ["element_id", "name", "category"]


class RevitContext(Protocol):
    """Structural type of the context ``RevitTools`` expects.

    Satisfied by :class:`revitpy.api.RevitAPI`.  ``transaction`` must
    return a context manager that commits on clean exit and rolls back
    when an exception escapes.
    """

    @property
    def active_document(self) -> Any: ...

    def get_element_by_id(self, element_id: Any) -> Any: ...

    def transaction(self, name: str | None = None, **kwargs: Any) -> Any: ...


def _safe_param(element: Any, name: str) -> Any:
    """Return a parameter value, or ``None`` when it cannot be read."""
    try:
        return element.get_parameter_value(name)
    except Exception:
        return None


def _element_category(element: Any) -> Any:
    """Return an element's category name.

    Checks a wrapper-level ``category`` string, then the underlying Revit
    element's ``Category`` (a string or an object with ``Name``), then a
    ``Category`` parameter.
    """
    category = getattr(element, "category", None)
    if isinstance(category, str):
        return category
    raw = getattr(element, "_revit_element", None)
    raw_category = getattr(raw, "Category", None) if raw is not None else None
    if isinstance(raw_category, str):
        return raw_category
    if raw_category is not None:
        name = getattr(raw_category, "Name", None)
        if name is not None:
            return name
    return _safe_param(element, "Category")


def _element_name(element: Any) -> str:
    """Return an element's name, or ``""`` when it cannot be read.

    ``revitpy.api.Element.name`` resolves through a parameter lookup that
    can raise; fall back to the underlying Revit element's ``Name``.
    """
    try:
        name = element.name
    except Exception:
        raw = getattr(element, "_revit_element", None)
        name = getattr(raw, "Name", None) if raw is not None else None
    return name if isinstance(name, str) else ""


def _element_id(element: Any) -> int:
    return int(element.id)


def _summarize(element: Any) -> dict[str, Any]:
    return {
        "element_id": _element_id(element),
        "name": _element_name(element),
        "category": _element_category(element),
    }


def _elements_in_category(api: Any, category: str) -> list[Any]:
    return [
        e
        for e in api.active_document.get_all_elements()
        if _element_category(e) == category
    ]


class RevitTools:
    """Registry of tools that can be invoked through the MCP server.

    Args:
        context: The connected RevitPy API (see :class:`RevitContext`,
            normally a :class:`revitpy.api.RevitAPI`).  Built-in tools
            operate on its active document; when there is no context or
            no active document, every built-in tool fails with
            ``ToolExecutionError("Not connected to a Revit document")``
            rather than returning fabricated data.  Modifications run
            inside a RevitPy transaction.
    """

    def __init__(self, context: RevitContext | Any = None) -> None:
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
                        description=(
                            "Optional case-insensitive substring matched "
                            "against element names"
                        ),
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
                description="Count elements in a category, grouped by a parameter",
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
                        description=(
                            "Parameter to group by (type, family_name, level, "
                            "or a Revit parameter name)"
                        ),
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
                        description=(
                            "Checks to run: unnamed_elements, duplicate_marks "
                            "(default: all)"
                        ),
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
                        description="Export format (json or csv)",
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

    def _require_api(self) -> Any:
        """Return the context, or fail when no Revit document is open."""
        api = self._context
        if api is None or getattr(api, "active_document", None) is None:
            raise ToolExecutionError(NOT_CONNECTED_MESSAGE)
        return api

    def _require_element(self, api: Any, element_id: int) -> Any:
        """Look up an element by ID or fail with a clear error."""
        element = api.get_element_by_id(element_id)
        if element is None:
            raise ToolExecutionError(f"Element {element_id} not found")
        return element

    def _handle_query_elements(
        self,
        category: str,
        filter: str = "",  # noqa: A002
    ) -> dict[str, Any]:
        """Query elements in a category, optionally filtered by name."""
        api = self._require_api()
        elements = _elements_in_category(api, category)
        if filter:
            needle = filter.lower()
            elements = [e for e in elements if needle in _element_name(e).lower()]
        return {
            "category": category,
            "filter": filter,
            "elements": [_summarize(e) for e in elements],
            "count": len(elements),
        }

    def _handle_get_element(self, element_id: int) -> dict[str, Any]:
        """Return a single element with its parameters."""
        api = self._require_api()
        element = self._require_element(api, element_id)
        data = _summarize(element)
        data["parameters"] = {
            name: pv.value for name, pv in element.get_all_parameters().items()
        }
        return data

    def _handle_modify_parameter(
        self,
        element_id: int,
        parameter_name: str,
        value: str,
    ) -> dict[str, Any]:
        """Set a parameter value inside a RevitPy transaction."""
        api = self._require_api()
        element = self._require_element(api, element_id)
        old_value = _safe_param(element, parameter_name)
        # Errors propagate: the transaction rolls back and execute_tool
        # wraps the failure in ToolExecutionError.
        with api.transaction(f"MCP: set {parameter_name} on element {element_id}"):
            element.set_parameter_value(parameter_name, value)
        logger.info(
            "Set {} on element {} ({!r} -> {!r})",
            parameter_name,
            element_id,
            old_value,
            value,
        )
        return {
            "element_id": element_id,
            "parameter_name": parameter_name,
            "old_value": old_value,
            "new_value": value,
            "success": True,
        }

    def _handle_get_quantities(
        self,
        category: str,
        group_by: str = "type",
    ) -> dict[str, Any]:
        """Count elements in a category grouped by a parameter value."""
        api = self._require_api()
        elements = _elements_in_category(api, category)
        param = _GROUP_BY_ALIASES.get(group_by, group_by)
        counts: dict[str, int] = {}
        for element in elements:
            value = _safe_param(element, param)
            key = "<none>" if value is None else str(value)
            counts[key] = counts.get(key, 0) + 1
        return {
            "category": category,
            "group_by": group_by,
            "quantities": [{"group": g, "count": counts[g]} for g in sorted(counts)],
            "total": len(elements),
        }

    def _handle_validate_model(
        self,
        checks: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the supported model checks and report issues."""
        api = self._require_api()
        selected = list(checks) if checks else list(_SUPPORTED_CHECKS)
        unknown = [c for c in selected if c not in _SUPPORTED_CHECKS]
        if unknown:
            raise ToolExecutionError(
                f"Unknown checks: {', '.join(unknown)}; "
                f"supported: {', '.join(_SUPPORTED_CHECKS)}"
            )

        elements = list(api.active_document.get_all_elements())
        issues: list[dict[str, Any]] = []

        if "unnamed_elements" in selected:
            for element in elements:
                if not _element_name(element).strip():
                    issues.append(
                        {
                            "check": "unnamed_elements",
                            "element_id": _element_id(element),
                            "message": "Element has no name",
                        }
                    )

        if "duplicate_marks" in selected:
            marks: dict[str, list[int]] = {}
            for element in elements:
                mark = _safe_param(element, "Mark")
                if mark is None or not str(mark).strip():
                    continue
                marks.setdefault(str(mark), []).append(_element_id(element))
            for mark in sorted(marks):
                ids = marks[mark]
                if len(ids) > 1:
                    issues.append(
                        {
                            "check": "duplicate_marks",
                            "mark": mark,
                            "element_ids": sorted(ids),
                            "message": f"Mark '{mark}' is used by {len(ids)} elements",
                        }
                    )

        return {"checks_run": selected, "issues": issues, "passed": not issues}

    def _handle_export_data(
        self,
        category: str,
        format: str = "json",  # noqa: A002
    ) -> dict[str, Any]:
        """Export element summaries for a category as JSON rows or CSV."""
        fmt = format.lower()
        if fmt not in _EXPORT_FORMATS:
            raise ToolExecutionError(
                f"Unsupported export format '{format}'; "
                f"supported: {', '.join(_EXPORT_FORMATS)}"
            )
        api = self._require_api()
        rows = [_summarize(e) for e in _elements_in_category(api, category)]
        data: Any = rows
        if fmt == "csv":
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=_EXPORT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            data = buffer.getvalue()
        return {
            "category": category,
            "format": fmt,
            "data": data,
            "row_count": len(rows),
        }
