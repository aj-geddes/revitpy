---
layout: page
title: AI & MCP Server
description: Expose RevitPy operations as MCP tools for AI agents via WebSocket. Includes tool registration, configurable safety guardrails, and Jinja2 templates.
doc_tier: user
---

RevitPy includes a full AI integration layer that exposes Revit operations through the Model Context Protocol (MCP). This enables AI agents and LLMs to query, analyze, modify, and export Revit model data through a standardized WebSocket interface, with configurable safety guardrails and reusable prompt templates.

## Overview

The `revitpy.ai` module provides four core components:

- **`RevitTools`** -- A tool registry and execution engine that manages tool definitions, validates arguments, dispatches execution, and converts tools to MCP-compatible JSON Schema format.
- **`SafetyGuard`** -- A safety policy enforcer that controls which tools an AI agent may execute based on a configurable safety mode, with preview and undo support.
- **`PromptLibrary`** -- A Jinja2-based template library for constructing prompts used in LLM interactions, exposed in MCP prompt-list format.
- **`McpServer`** -- An asynchronous WebSocket server implementing the tools and prompts parts of MCP, with optional bearer-token authentication. It wires together tools, prompts, and safety controls.

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

from revitpy.api import RevitAPI

# With a connected RevitPy API: built-in tools work on its active document
api = RevitAPI(revit_application)
api.connect()
tools = RevitTools(context=api)

# Without a context: only custom tools are useful. Every built-in tool fails
# with ToolExecutionError("Not connected to a Revit document") instead of
# returning made-up data.
tools = RevitTools()
```

The context can be any object with the shape of `revitpy.ai.tools.RevitContext`:
an `active_document` (with `get_all_elements()`), `get_element_by_id(id)`, and
`transaction(name)` returning a context manager that commits on success and rolls
back on error. `revitpy.api.RevitAPI` satisfies it.

### Built-in Tools

The following tools are registered automatically when a `RevitTools` instance is created:

| Tool Name | Category | Required Parameters | Optional Parameters | Description |
|---|---|---|---|---|
| `query_elements` | `QUERY` | `category` (string) | `filter` (string, default `""`) | Elements in a category; `filter` is a case-insensitive substring match on element names |
| `get_element` | `QUERY` | `element_id` (integer) | -- | One element with its parameters |
| `modify_parameter` | `MODIFY` | `element_id` (integer), `parameter_name` (string), `value` (string) | -- | Sets a parameter inside a RevitPy transaction; returns `old_value` and `new_value`. The transaction rolls back if the set fails. |
| `get_quantities` | `ANALYZE` | `category` (string) | `group_by` (string, default `"type"`) | Element **counts** per group (`type`, `family_name`, `level`, or any parameter name). No lengths, areas, or volumes. |
| `validate_model` | `ANALYZE` | -- | `checks` (array, default: all) | Runs `unnamed_elements` and/or `duplicate_marks`. Unknown check names are rejected. |
| `export_data` | `EXPORT` | `category` (string) | `format` (`"json"` or `"csv"`, default `"json"`) | Element id, name, and category rows. Other formats are rejected. |

All built-in tools need a connected document. Without one they raise
`ToolExecutionError` (reported to MCP clients as an `isError` result).

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
        "description": "Optional case-insensitive substring matched against element names",
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
| `SafetyMode.CAUTIOUS` | `"cautious"` | Tools in `require_confirmation_for` categories (by default `MODIFY`) run only when the `confirmation_callback` returns `True`. With no callback they are **denied**. Other tools are allowed. This is the default mode. |
| `SafetyMode.FULL_ACCESS` | `"full_access"` | Allows all tools without restriction, except those in the `blocked_tools` list. |

### SafetyConfig Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `mode` | `SafetyMode` | `SafetyMode.CAUTIOUS` | The active safety enforcement level |
| `max_undo_stack` | `int` | `50` | Maximum number of entries in the undo stack |
| `require_confirmation_for` | `list[ToolCategory]` | `[ToolCategory.MODIFY]` | Categories that require confirmation in `CAUTIOUS` mode |
| `blocked_tools` | `list[str]` | `[]` | Tool names that are always denied regardless of mode |

### Creating a SafetyGuard

```python
from revitpy.ai import SafetyGuard, SafetyConfig, SafetyMode, ToolCategory

# Default: CAUTIOUS mode. MODIFY tools are denied because no callback is set.
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

### Confirming Tool Calls

In `CAUTIOUS` mode, a tool whose category is in `require_confirmation_for` runs
only when a person (or your own policy code) approves it. You supply that
decision through `confirmation_callback`. It is called with the
`ToolDefinition` and the arguments, and it can be sync or async. Only a literal
`True` approves the call. `False`, any other value, or an exception denies it
with a `SafetyViolationError`. If no callback is configured, the call is denied.

```python
from revitpy.ai import SafetyGuard, SafetyConfig, SafetyMode, ToolCategory

def confirm(tool, arguments) -> bool:
    answer = input(f"Allow {tool.name} with {arguments}? [y/N] ")
    return answer.strip().lower() == "y"

guard = SafetyGuard(
    config=SafetyConfig(mode=SafetyMode.CAUTIOUS),  # MODIFY needs confirmation
    confirmation_callback=confirm,
)

# The callback can also be set or replaced later.
guard.confirmation_callback = confirm
```

`McpServer` awaits async callbacks through `avalidate_tool_call`. The
synchronous `validate_tool_call` cannot await, so it denies calls that need an
async callback. Use `await guard.avalidate_tool_call(...)` from async code.

Use `SafetyMode.FULL_ACCESS` to skip confirmation, or `SafetyMode.READ_ONLY` to
refuse modifications outright.

### Validating Tool Calls

`validate_tool_call` (or `avalidate_tool_call` in async code) returns `True` when the call is allowed. It raises `SafetyViolationError` when the call is blocked or confirmation is not granted:

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
#     "confirmation_configured": False,
#     "is_blocked": False,
# }
```

### Undo Stack

The undo stack is a bounded history of changes. `McpServer` pushes an entry (`tool`, `arguments`, `result`, including `old_value` for `modify_parameter`) after each successful `MODIFY` tool call. Nothing is reverted automatically. Your code has to apply the reversal itself. The stack is bounded by `SafetyConfig.max_undo_stack` (default 50), and the oldest entry is discarded when the limit is reached.

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

{% raw %}
```python
prompts.register_template(
    "cost_estimate",
    "Estimate the cost of {{ count }} {{ material }} elements "
    "at ${{ unit_price }} per unit.\n"
    "Total estimated cost: ${{ count * unit_price }}\n",
)

text = prompts.render("cost_estimate", count=50, material="steel beams", unit_price=120)
```
{% endraw %}

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
| `auth_token` | `str` or `None` | `None` | Shared secret. When set, the WebSocket handshake must include `Authorization: Bearer <token>`, or it is rejected with HTTP 401. Excluded from `repr()`. |
| `allowed_origins` | `list[str]` | `[]` | Browser origins that may connect. A handshake with an `Origin` header not in this list is rejected with HTTP 403. |

### Authentication and Network Exposure

The server binds to `localhost` by default, and authentication is **off** unless
you set `auth_token`. On an unauthenticated server, any local process can connect
and run tools against the open model. Set a token whenever the machine is shared,
and always before binding to a non-loopback address. If you bind to a non-loopback
host such as `0.0.0.0` without a token, the server logs a loud warning at startup.

```python
import secrets
from revitpy.ai import McpServer, McpServerConfig, RevitTools

token = secrets.token_urlsafe(32)  # give this to the MCP client out of band
server = McpServer(
    RevitTools(context=api),
    config=McpServerConfig(host="localhost", port=8765, auth_token=token),
)
```

Clients send the token during the WebSocket handshake:

```python
from websockets.asyncio.client import connect

async with connect(
    "ws://localhost:8765",
    additional_headers={"Authorization": f"Bearer {token}"},
) as ws:
    ...
```

The token is compared in constant time (`hmac.compare_digest`). Because it
travels as plain `ws://` traffic, use it on loopback or on a trusted network, or
put a TLS-terminating proxy in front of the server. Browser pages are rejected by
default through the `Origin` check. Add their origins to `allowed_origins` only
when you mean to allow them.

The server uses the `websockets` asyncio API (`websockets.asyncio.server`) when it
is available (websockets 13 or later). It falls back to the legacy implementation
only on older releases.

### Creating and Starting a Server

```python
from revitpy.ai import McpServer, RevitTools, McpServerConfig

tools = RevitTools(context=api)
server = McpServer(
    tools,
    config=McpServerConfig(host="localhost", port=9000, auth_token=token),
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
    tools = RevitTools(context=api)

    async with McpServer(tools) as server:
        print(f"Server running on {server.config.host}:{server.config.port}")
        # Server starts on __aenter__, stops on __aexit__
        await asyncio.sleep(3600)  # Run for one hour
```

### Injecting Safety and Prompts

Pass custom `SafetyGuard` and `PromptLibrary` instances to the server:

{% raw %}
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

guard = SafetyGuard(
    config=SafetyConfig(
        mode=SafetyMode.CAUTIOUS,
        require_confirmation_for=[ToolCategory.MODIFY],
    ),
    confirmation_callback=confirm,  # see "Confirming Tool Calls"
)

prompts = PromptLibrary()
prompts.register_template("custom_prompt", "Hello, {{ name }}!")

server = McpServer(
    RevitTools(context=api),
    safety_guard=guard,
    prompt_library=prompts,
)
```
{% endraw %}

### Supported MCP Methods

The server handles the following JSON-RPC methods over the WebSocket connection:

| Method | Description |
|---|---|
| `initialize` | Negotiates the protocol version and returns capabilities and server info. If the client's version is one of `2025-11-25`, `2025-06-18`, `2025-03-26`, or `2024-11-05`, the server echoes it back. Otherwise it answers with `2025-11-25`. |
| `ping` | Returns an empty result |
| `tools/list` | Returns all registered tools in MCP JSON Schema format |
| `tools/call` | Validates the call through the safety guard (including confirmation), then runs the tool. The result has JSON `text` content, plus `structuredContent` when the tool returns a dict. |
| `prompts/list` | Returns all registered prompt templates |
| `prompts/get` | Renders a prompt template with the supplied arguments |

Notifications such as `notifications/initialized` get no reply. JSON-RPC batches
are rejected. Resources, sampling, and `listChanged` notifications are not implemented.

### Error Handling

Every error response carries the `id` of the request that caused it. The `id` is
`null` only when it cannot be read, for example on a parse error. Standard
JSON-RPC 2.0 codes are used:

| Code | Meaning | Examples |
|---|---|---|
| `-32700` | Parse error | Invalid JSON or invalid UTF-8 |
| `-32600` | Invalid request | Missing `jsonrpc: "2.0"` or `method`, batch arrays, bad `id` type |
| `-32601` | Method not found | Unsupported method |
| `-32602` | Invalid params | `params`/`arguments` not an object, unknown tool or prompt, bad prompt arguments |
| `-32603` | Internal error | Unexpected server exception |

Following the MCP spec, a tool that **fails while running** is not a protocol
error. This covers safety denials, missing tool arguments, a disconnected document,
and exceptions raised by the handler. The failure comes back as a normal
`tools/call` result, so the model can see it and correct itself:

```json
{"jsonrpc": "2.0", "id": 13, "result": {
  "content": [{"type": "text", "text": "Tool 'get_element' failed: Element 999 not found"}],
  "isError": true
}}
```

### Server Properties

```python
# Access the active server configuration
config = server.config
print(config.host, config.port)

# View active WebSocket connections
connections = server.connections  # Returns a set copy

# Actual bound port while running (useful with port=0)
print(server.port)
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
| `CAUTIOUS` | `"cautious"` | Requires callback confirmation for `require_confirmation_for` categories (default `MODIFY`). Denies them when no callback is set. |
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

{% raw %}
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

# 1. Set up tools against a connected RevitPy API
tools = RevitTools(context=api)

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
async def confirm(tool, arguments) -> bool:
    # Ask the user through your UI; return True only on explicit approval.
    return await ask_user_to_approve(tool.name, arguments)

guard = SafetyGuard(
    config=SafetyConfig(
        mode=SafetyMode.CAUTIOUS,
        require_confirmation_for=[ToolCategory.MODIFY],
        max_undo_stack=100,
    ),
    confirmation_callback=confirm,
)

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
        config=McpServerConfig(host="localhost", port=8765, auth_token=token),
        safety_guard=guard,
        prompt_library=prompts,
    ) as server:
        print(f"MCP server running on {server.config.host}:{server.config.port}")
        await asyncio.Event().wait()  # Run until interrupted

asyncio.run(main())
```
{% endraw %}
