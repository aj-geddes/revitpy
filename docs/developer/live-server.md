---
layout: page
title: Live Server Protocol
description: "The RevitPy Live Server: an authenticated JSON-RPC 2.0 WebSocket endpoint inside Revit used by the VS Code extension, the dev server, the pyRevit bridge and the revitpy live CLI."
doc_tier: developer
---

The **Live Server** runs inside Revit, in the Python embedded by the RevitPy add-in
(`src/RevitPy.Addin`). Development tools use it to run code in the open Revit session:

| Client | Uses it for |
|---|---|
| VS Code extension (`vscode-extension/`) | Run Script, reload modules, start the debugger |
| Dev server (`dev-server/`) | Re-run a script or reload modules when files change |
| pyRevit bridge (`pyrevit-bridge/`) | Send elements from pyRevit scripts to RevitPy analyses |
| `revitpy live ...` CLI | Status, run a file, reload modules from a terminal |

## Starting it

- Click **Live Server** on the RevitPy ribbon tab (click again to stop), or
- set `start_live_server = true` in `%APPDATA%\RevitPy\settings.ini` to start it with Revit, or
- from a script running in Revit: `from revitpy.revit.live import start_live_server; start_live_server(__revit__)`.

`REVITPY_LIVE_HOST` (default `127.0.0.1`), `REVITPY_LIVE_PORT` (default `8766`) and
`REVITPY_LIVE_TOKEN` (default: a random token per start) override the defaults.

## Discovery

When the server starts it writes `~/.revitpy/live.json` (override with
`REVITPY_LIVE_DISCOVERY`), readable only by the current user:

```json
{
  "protocol": 1,
  "url": "ws://127.0.0.1:8766",
  "token": "…",
  "pid": 12345,
  "revit_version": "2025",
  "started_at": "2026-09-25T10:00:00+00:00"
}
```

Clients read this file to find the server and its token; the file is removed when the server
stops.

## Security

- Binds to loopback by default.
- **A bearer token is always required**: the WebSocket handshake must send
  `Authorization: Bearer <token>`, otherwise it is rejected with HTTP 401.
- Any handshake carrying a browser `Origin` header is rejected (HTTP 403), so web pages cannot
  reach it.
- `live/execute` and `live/runFile` execute arbitrary Python in Revit by design. Treat the token
  like a password.

## Transport

JSON-RPC 2.0 over WebSocket, one request per message, no batching. Every error response carries
the id of the request that caused it. Code runs on Revit's main API thread: requests wait while
Revit is busy or a modal dialog is open (up to 300 s).

## Methods

### `live/status`

Result: `{"protocol": 1, "revitpy_version": str, "python_version": str, "revit_version": str | null,
"document": str | null, "debug": {"listening": bool, "port": int | null}, "analyses": [str]}`

### `live/execute`

Params: `{"code": str, "filename"?: str = "<live>", "cwd"?: str}`

Runs `code` as `__main__` with `__revit__` bound to the `UIApplication`. The script's directory
(or `cwd`) is put first on `sys.path` while it runs.

Result: `{"success": bool, "output": str, "error": str | null, "duration_ms": float}`.
Exceptions in the script are reported as `success: false` with the traceback in `error`; they
are not JSON-RPC errors.

### `live/runFile`

Params: `{"path": str}` (absolute path on the Revit machine). Same result as `live/execute`.
A missing file is a JSON-RPC `-32602` error.

### `live/reload`

Params: `{"modules"?: [str], "paths"?: [str]}`

Reloads already-imported modules (`importlib.reload`), given by name or by source file path.

Result: `{"reloaded": [str], "errors": {name: message}}`

### `debug/start`

Params: `{"port"?: int = 5678}`

Starts `debugpy` inside Revit (it must be installed in the Revit Python environment:
`pip install debugpy`) listening on `127.0.0.1:port`. Attach with a standard VS Code
`"type": "debugpy", "request": "attach"` configuration.

Result: `{"listening": bool, "port": int}` or `{"listening": false, "error": str}`.

### `bridge/listAnalyses`

Result: `{"analyses": [str]}`

### `bridge/analyze`

Params: `{"analysis": str, "elements": [object], "options"?: object}`

Calls the analysis registered under that name (see below) on Revit's main thread.

Result: `{"success": true, "result": any}` or `{"success": false, "error": str}`.
An unknown analysis is a `-32602` error.

## Registering analyses

```python
from revitpy.revit.live import register_analysis

@register_analysis("wall_area_summary")
def wall_area_summary(elements, options, uiapp):
    return {"count": len(elements)}
```

Analyses run on Revit's main thread by default and may use the Revit API through `uiapp`.
Register with `main_thread=False` for analyses that only read the element data they are sent:
they run on a worker thread with `uiapp=None`. **Use this for analyses called from pyRevit
buttons.** A pyRevit button holds Revit's main thread while it waits for the reply, so a
main-thread analysis could not start until the request timed out.

```python
@register_analysis("element_summary", main_thread=False)
def element_summary(elements, options, uiapp):  # uiapp is None
    ...
```

Packages can ship analyses that load automatically when the Live Server starts, through the
`revitpy.analyses` entry-point group:

```toml
[project.entry-points."revitpy.analyses"]
my_tools = "my_tools.analyses"   # imported at startup; its @register_analysis calls run
```

## Python client

```python
from revitpy.live_client import LiveClient, call_live

print(call_live("live/status"))

async with LiveClient() as client:
    result = await client.run_file("C:/scripts/report.py")
```

The `revitpy live` command wraps the same client: `revitpy live status`,
`revitpy live run SCRIPT`, `revitpy live exec CODE`, `revitpy live reload MODULE...`.
