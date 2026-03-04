---
layout: page
title: AI & MCP Server
description: Expose RevitPy operations as MCP tools for AI agents via WebSocket. Includes tool registration, configurable safety guardrails, and Jinja2 templates.
doc_tier: user
---

# AI & MCP Server

RevitPy includes a full AI integration layer that exposes Revit operations through the Model Context Protocol (MCP). This enables AI agents and LLMs to query, analyze, modify, and export Revit model data through a standardized WebSocket interface, with configurable safety guardrails and reusable prompt templates.

## Overview

The `revitpy.ai` module provides four core components:

- **`RevitTools`** -- A tool registry and execution engine that manages tool definitions, validates arguments, dispatches execution, and converts tools to MCP-compatible JSON Schema format.
- **`SafetyGuard`** -- A safety policy enforcer that controls which tools an AI agent may execute based on a configurable safety mode, with preview and undo support.
- **`PromptLibrary`** -- A Jinja2-based template library for constructing prompts used in LLM interactions, exposed in MCP prompt-list format.
- **`McpServer`** -- An asynchronous WebSocket server implementing a subset of MCP, wiring together tools, prompts, and safety controls.

```python
from revitpy.ai import (
    McpServer,
    RevitTools,
    SafetyGuard,
    PromptLibrary,
    SafetyConfig,
    SafetyMode,
    McpServerConfig,
    ToolCategory,
)
```

## RevitTools

`RevitTools` is the tool registry. It ships with six built-in tools and allows registering custom ones.

### Creating a Registry

```python
from revitpy.ai import RevitTools

# Without application context (built-in handlers return placeholder data)
tools = RevitTools()

# With application context (forwarded to built-in handlers)
tools = RevitTools(context=revit_app)
```

### Built-in Tools

The following tools are registered automatically when a `RevitTools` instance is created:

| Tool Name | Category | Required Parameters | Optional Parameters | Description |
|---|---|---|---|---|
| `query_elements` | `QUERY` | `category` (string) | `filter` (string, default `""`) | Query Revit elements by category and filter |
| `get_element` | `QUERY` | `element_id` (integer) | -- | Get a single Revit element by ID |
| `modify_parameter` | `MODIFY` | `element_id` (integer), `parameter_name` (string), `value` (string) | -- | Modify a parameter value on a Revit element |
| `get_quantities` | `ANALYZE` | `category` (string) | `group_by` (string, default `"type"`) | Get quantity takeoff for elements |
| `validate_model` | `ANALYZE` | -- | `checks` (array, default `None`) | Run validation checks on the Revit model |
| `export_data` | `EXPORT` | `category` (string) | `format` (string, default `"json"`) | Export element data to a structured format |

### Registering a Custom Tool

Use `register_tool` to add a tool with a `ToolDefinition` and a handler callable:

```python
from revitpy.ai import (
    RevitTools,
    ToolDefinition,
    ToolParameter,
    ToolCategory,
    ParameterType,
)

tools = RevitTools()

tools.register_tool(
    definition=ToolDefinition(
        name="count_by_level",
        description="Count elements on a specific level",
        category=ToolCategory.ANALYZE,
        parameters=[
            ToolParameter(
                name="level_name",
                type=ParameterType.STRING,
                description="Name of the level",
            ),
            ToolParameter(
                name="category",
                type=ParameterType.STRING,
                description="Element category to count",
                required=False,
                default="all",
            ),
        ],
        returns_description="Element count per level",
    ),
    handler=my_count_handler,
)
```

### Executing Tools

`execute_tool` validates required parameters, invokes the handler, and returns a `ToolResult`:

```python
result = tools.execute_tool("query_elements", {"category": "Walls"})

print(result.status)             # ToolResultStatus.SUCCESS
print(result.data)               # {"elements": [...], "count": 5, ...}
print(result.execution_time_ms)  # 12.3
print(result.error)              # None
```

If the tool name is unknown or required parameters are missing, the result has status `ToolResultStatus.ERROR` with a descriptive `error` message. If the handler raises an exception, a `ToolExecutionError` is raised.

### Listing and Inspecting Tools

```python
# List all registered tool definitions
all_tools = tools.list_tools()

# Get a single tool definition by name
defn = tools.get_tool("query_elements")
print(defn.name)          # "query_elements"
print(defn.category)      # ToolCategory.QUERY
print(defn.description)   # "Query Revit elements by category and filter"
print(defn.parameters)    # [ToolParameter(...), ...]
```

### Converting to MCP Format

`to_mcp_tool_list` converts all registered tools to the MCP JSON Schema tool format:

```python
mcp_tools = tools.to_mcp_tool_list()
# Returns a list of dicts, each with "name", "description", and "inputSchema"
```

Each entry in the list has this shape:

```json
{
  "name": "query_elements",
  "description": "Query Revit elements by category and filter",
  "inputSchema": {
    "type": "object",
    "properties": {
      "category": {
        "type": "string",
        "description": "Element category (e.g. Walls, Doors)"
      },
      "filter": {
        "type": "string",
        "description": "Optional filter expression",
        "default": ""
      }
    },
    "required": ["category"]
  }
}
```

## SafetyGuard

`SafetyGuard` validates tool calls against a configurable safety policy to prevent unintended model modifications. It also provides a preview mechanism and an undo stack.

### Safety Modes

| Mode | Value | Behavior |
|---|---|---|
| `SafetyMode.READ_ONLY` | `"read_only"` | Blocks all tools with `ToolCategory.MODIFY`. Query, analyze, and export tools are allowed. |
| `SafetyMode.CAUTIOUS` | `"cautious"` | Allows all tools but flags categories in `require_confirmation_for` as needing confirmation. This is the default. |
| `SafetyMode.FULL_ACCESS` | `"full_access"` | Allows all tools without restriction, except those in the `blocked_tools` list. |

### SafetyConfig Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | `SafetyMode` | `SafetyMode.CAUTIOUS` | The active safety enforcement level |
| `max_undo_stack` | `int` | `50` | Maximum number of entries in the undo stack |
| `require_confirmation_for` | `list[ToolCategory]` | `[]` | Categories that require confirmation in `CAUTIOUS` mode |
| `blocked_tools` | `list[str]` | `[]` | Tool names that are always denied regardless of mode |

### Creating a SafetyGuard

```python
from revitpy.ai import SafetyGuard, SafetyConfig, SafetyMode, ToolCategory

# Default: CAUTIOUS mode
guard = SafetyGuard()

# READ_ONLY mode -- blocks all modify operations
guard = SafetyGuard(config=SafetyConfig(mode=SafetyMode.READ_ONLY))

# CAUTIOUS with confirmation for modify and export
guard = SafetyGuard(config=SafetyConfig(
    mode=SafetyMode.CAUTIOUS,
    require_confirmation_for=[ToolCategory.MODIFY, ToolCategory.EXPORT],
    blocked_tools=["export_data"],
))
```

### Validating Tool Calls

`validate_tool_call` returns `True` when the call is allowed, or raises `SafetyViolationError` when blocked:

```python
from revitpy.ai import ToolDefinition, ToolCategory

tool = tools.get_tool("modify_parameter")
try:
    guard.validate_tool_call(tool, {"element_id": 12345, "parameter_name": "Height", "value": "3.0"})
    print("Tool call allowed")
except SafetyViolationError as e:
    print(f"Blocked: {e}")
```

### Previewing Changes

`preview_changes` returns a dry-run summary without applying any changes:

```python
preview = guard.preview_changes(tool, {"element_id": 12345, "parameter_name": "Height", "value": "3.0"})
print(preview)
# {
#     "tool": "modify_parameter",
#     "category": "modify",
#     "arguments": {"element_id": 12345, ...},
#     "safety_mode": "cautious",
#     "requires_confirmation": True,
#     "is_blocked": False,
# }
```

### Undo Stack

The undo stack records operations so they can be rolled back. The stack is bounded by `SafetyConfig.max_undo_stack` (default 50); the oldest entry is discarded when the limit is reached.

```python
# Push an operation onto the undo stack
guard.push_undo({
    "tool": "modify_parameter",
    "element_id": 12345,
    "parameter_name": "Height",
    "old_value": "2.5",
    "new_value": "3.0",
})

# Pop and return the most recent undo entry
last = guard.undo_last()  # Returns the dict, or None if empty

# Inspect the full stack (returns a copy)
stack = guard.get_undo_stack()
```

## PromptLibrary

`PromptLibrary` manages Jinja2 templates used to construct prompts for LLM interactions. It ships with five built-in templates and supports adding custom ones at runtime.

### Built-in Templates

| Template Name | Variables | Purpose |
|---|---|---|
| `element_summary` | `element_id`, `name`, `category`, `parameters` (dict) | Summarize a Revit element |
| `quantity_takeoff` | `category`, `group_by` (optional), `columns` (optional) | Generate a quantity takeoff report |
| `validation_report` | `issues` (list of dicts with `severity` and `message`) | Format model validation results |
| `natural_language_query` | `user_query`, `categories` (list) | Translate natural language to a Revit query |
| `safety_preview` | `tool_name`, `category`, `arguments` (dict), `safety_mode`, `requires_confirmation` | Preview a tool operation |

### Rendering Templates

```python
from revitpy.ai import PromptLibrary

prompts = PromptLibrary()

text = prompts.render(
    "element_summary",
    element_id=12345,
    name="Basic Wall",
    category="Walls",
    parameters={"Height": "3.0m", "Width": "0.2m"},
)
print(text)
# Summarize the following Revit element:
# - ID: 12345
# - Name: Basic Wall
# - Category: Walls
# - Parameters:
#   - Height: 3.0m
#   - Width: 0.2m
```

The `render` method uses Jinja2 with `StrictUndefined`, so missing variables raise a `PromptError`.

### Registering Custom Templates

```python
prompts.register_template(
    "cost_estimate",
    "Estimate the cost of {{ count }} {{ material }} elements "
    "at ${{ unit_price }} per unit.\n"
    "Total estimated cost: ${{ count * unit_price }}\n",
)

text = prompts.render("cost_estimate", count=50, material="steel beams", unit_price=120)
```

### Listing and Inspecting Templates

```python
# Sorted list of all template names
names = prompts.list_templates()

# Get raw Jinja2 source of a template
source = prompts.get_template("element_summary")
```

### Converting to MCP Format

`to_mcp_prompts_list` converts templates to MCP-format prompt definitions:

```python
mcp_prompts = prompts.to_mcp_prompts_list()
# Returns a list of dicts with "name", "description", and "arguments"
```

## McpServer

`McpServer` is an asynchronous WebSocket server that implements a subset of the Model Context Protocol, wiring together `RevitTools`, `SafetyGuard`, and `PromptLibrary`.

### McpServerConfig Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `host` | `str` | `"localhost"` | Host address to bind to |
| `port` | `int` | `8765` | Port number |
| `name` | `str` | `"revitpy-mcp"` | Server name reported during initialization |
| `version` | `str` | `"1.0.0"` | Server version reported during initialization |

### Creating and Starting a Server

```python
from revitpy.ai import McpServer, RevitTools, McpServerConfig

tools = RevitTools()
server = McpServer(
    tools,
    config=McpServerConfig(host="0.0.0.0", port=9000),
)

# Start and stop manually
import asyncio

async def main():
    await server.start()
    # Server is now accepting WebSocket connections
    # ... wait or do work ...
    await server.stop(timeout=5.0)

asyncio.run(main())
```

### Async Context Manager

`McpServer` supports `async with` for automatic lifecycle management:

```python
async def main():
    tools = RevitTools()

    async with McpServer(tools) as server:
        print(f"Server running on {server.config.host}:{server.config.port}")
        # Server starts on __aenter__, stops on __aexit__
        await asyncio.sleep(3600)  # Run for one hour
```

### Injecting Safety and Prompts

Pass custom `SafetyGuard` and `PromptLibrary` instances to the server:

```python
from revitpy.ai import (
    McpServer,
    RevitTools,
    SafetyGuard,
    SafetyConfig,
    SafetyMode,
    PromptLibrary,
    ToolCategory,
)

guard = SafetyGuard(config=SafetyConfig(
    mode=SafetyMode.CAUTIOUS,
    require_confirmation_for=[ToolCategory.MODIFY],
))

prompts = PromptLibrary()
prompts.register_template("custom_prompt", "Hello, {{ name }}!")

server = McpServer(
    RevitTools(),
    safety_guard=guard,
    prompt_library=prompts,
)
```

### Supported MCP Methods

The server handles the following JSON-RPC methods over the WebSocket connection:

| Method | Description |
|---|---|
| `initialize` | Returns protocol version (`"2024-11-05"`), capabilities, and server info |
| `tools/list` | Returns all registered tools in MCP JSON Schema format |
| `tools/call` | Validates the call through the safety guard, then executes the tool |
| `prompts/list` | Returns all registered prompt templates |
| `prompts/get` | Renders a prompt template with the supplied arguments |

### Server Properties

```python
# Access the active server configuration
config = server.config
print(config.host, config.port)

# View active WebSocket connections
connections = server.connections  # Returns a set copy
```

## Enum Reference

### ToolCategory

| Member | Value | Description |
|---|---|---|
| `QUERY` | `"query"` | Read-only queries against the Revit model |
| `MODIFY` | `"modify"` | Modifies elements or parameters in the model |
| `ANALYZE` | `"analyze"` | Runs analysis, validation, or takeoff operations |
| `EXPORT` | `"export"` | Exports data from the model |

### SafetyMode

| Member | Value | Description |
|---|---|---|
| `READ_ONLY` | `"read_only"` | Blocks all modify operations |
| `CAUTIOUS` | `"cautious"` | Allows all operations but flags categories for confirmation |
| `FULL_ACCESS` | `"full_access"` | Allows all operations (except explicitly blocked tools) |

### ToolResultStatus

| Member | Value | Description |
|---|---|---|
| `SUCCESS` | `"success"` | Tool executed successfully |
| `ERROR` | `"error"` | Tool execution failed or was invalid |
| `DENIED` | `"denied"` | Tool call was denied by the safety guard |

### ParameterType

| Member | Value | Description |
|---|---|---|
| `STRING` | `"string"` | String parameter |
| `INTEGER` | `"integer"` | Integer parameter |
| `NUMBER` | `"number"` | Floating-point number parameter |
| `BOOLEAN` | `"boolean"` | Boolean parameter |
| `ARRAY` | `"array"` | Array/list parameter |
| `OBJECT` | `"object"` | Object/dict parameter |

### McpMessageType

| Member | Value | Description |
|---|---|---|
| `REQUEST` | `"request"` | Client-to-server JSON-RPC request |
| `RESPONSE` | `"response"` | Server-to-client JSON-RPC response |
| `NOTIFICATION` | `"notification"` | One-way notification (no response expected) |

## Dataclass Reference

### ToolParameter

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | -- | Parameter name |
| `type` | `ParameterType` | -- | JSON Schema type |
| `description` | `str` | -- | Human-readable description |
| `required` | `bool` | `True` | Whether the parameter is required |
| `default` | `Any` | `None` | Default value when not supplied |

### ToolDefinition

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | -- | Tool name |
| `description` | `str` | -- | Human-readable tool description |
| `category` | `ToolCategory` | -- | Tool category |
| `parameters` | `list[ToolParameter]` | `[]` | Parameter definitions |
| `returns_description` | `str` | `""` | Description of return value |

### ToolResult

| Field | Type | Default | Description |
|---|---|---|---|
| `status` | `ToolResultStatus` | -- | Outcome status |
| `data` | `Any` | `None` | Result data on success |
| `error` | `str` or `None` | `None` | Error message on failure |
| `execution_time_ms` | `float` | `0.0` | Execution time in milliseconds |

## Full Example

A complete example that wires up all four components and runs the MCP server:

```python
import asyncio
from revitpy.ai import (
    McpServer,
    McpServerConfig,
    RevitTools,
    SafetyGuard,
    SafetyConfig,
    SafetyMode,
    PromptLibrary,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
    ParameterType,
)

# 1. Set up tools
tools = RevitTools(context=revit_app)

tools.register_tool(
    definition=ToolDefinition(
        name="get_room_schedule",
        description="Generate a room schedule from the model",
        category=ToolCategory.ANALYZE,
        parameters=[
            ToolParameter(
                name="level",
                type=ParameterType.STRING,
                description="Building level to filter by",
                required=False,
                default="all",
            ),
        ],
        returns_description="Room schedule data",
    ),
    handler=my_room_schedule_handler,
)

# 2. Configure safety
guard = SafetyGuard(config=SafetyConfig(
    mode=SafetyMode.CAUTIOUS,
    require_confirmation_for=[ToolCategory.MODIFY],
    max_undo_stack=100,
))

# 3. Set up prompts
prompts = PromptLibrary()
prompts.register_template(
    "room_analysis",
    "Analyze the rooms on level {{ level }}:\n"
    "{% for room in rooms %}"
    "- {{ room.name }}: {{ room.area }} m2\n"
    "{% endfor %}",
)

# 4. Start the server
async def main():
    async with McpServer(
        tools,
        config=McpServerConfig(host="localhost", port=8765),
        safety_guard=guard,
        prompt_library=prompts,
    ) as server:
        print(f"MCP server running on {server.config.host}:{server.config.port}")
        await asyncio.Event().wait()  # Run until interrupted

asyncio.run(main())
```
