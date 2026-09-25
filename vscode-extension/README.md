# RevitPy for VS Code

Run, reload and debug Python scripts inside a running Autodesk Revit session from VS Code.

The extension is a client of the **RevitPy Live Server**, an authenticated JSON-RPC 2.0 WebSocket
endpoint that runs inside Revit in the Python embedded by the RevitPy add-in
(protocol: [`docs/developer/live-server.md`](https://github.com/aj-geddes/revitpy/blob/main/docs/developer/live-server.md)). It uses no
server or language service of its own.

## Requirements

- **Revit with the RevitPy add-in installed and the Live Server started**: click **Live Server** on
  the RevitPy ribbon tab, or set `start_live_server = true` in `%APPDATA%\RevitPy\settings.ini`.
  When the server starts it writes `~/.revitpy/live.json` (URL and a per-start token). The
  extension reads that file, so VS Code has to run as the same user on the same machine as Revit.
- **For debugging only:**
  - the [Python Debugger](https://marketplace.visualstudio.com/items?itemName=ms-python.debugpy)
    extension (`ms-python.debugpy`). The extension offers to install it the first time you attach.
  - `debugpy` installed in the Python environment RevitPy uses inside Revit
    (`python -m pip install debugpy` with that interpreter).
- **For RevitPy: Create Project only:** the RevitPy dev CLI, `revitpy-dev`
  (`pip install ./cli` from a RevitPy checkout; Python 3.11+).
- VS Code 1.110 or later.

## Commands

| Command | What it does | Live Server method |
|---|---|---|
| **RevitPy: Connect to Revit** | Reads the discovery file and connects. | `live/status` |
| **RevitPy: Disconnect from Revit** | Closes the connection. | — |
| **RevitPy: Show Status** | Writes server URL, Revit version, active document, RevitPy and Python versions, debugger state and registered analyses to the **RevitPy** output channel. | `live/status` |
| **RevitPy: Run Script in Revit** | Saves the active `.py` file and runs it in Revit as `__main__` with `__revit__` bound to the `UIApplication`. Also in the editor title bar and the editor and explorer context menus. Untitled editors are sent as code. | `live/runFile` (`live/execute` for untitled) |
| **RevitPy: Run Selection in Revit** | Runs the selected lines, or the current line if nothing is selected, after removing their common indentation. The file's folder is the working directory and is on `sys.path`. | `live/execute` |
| **RevitPy: Reload Current Module in Revit** | Reloads the active file's module if Revit has already imported it. | `live/reload` |
| **RevitPy: Attach Debugger to Revit** | Starts debugpy inside Revit, then starts a standard `debugpy` attach session to `127.0.0.1:<port>`. | `debug/start` |
| **RevitPy: Create Project** | Asks for a name, a template (`basic-script` or `addin`) and a parent folder, runs `revitpy-dev create project NAME --template T --output DIR` in a terminal, then offers to open the new folder. | — (dev CLI) |
| **RevitPy: Configure Revit API Stubs Folder** | Adds a folder of Revit API `.pyi` stubs to `python.analysis.extraPaths` (see below). | — |

Script output (`print`, stderr) goes to the **RevitPy** output channel. When a script fails, the
traceback is written there and an error notification shows the exception line.

Every command connects on demand, so after restarting Revit or the Live Server (which issues a new
token) you don't need to reconnect by hand. Requests wait while Revit is busy or a modal dialog is
open (see `revitpy.requestTimeoutSeconds`).

### Status bar

`$(plug) Revit 2025 · MyModel.rvt` while connected (with a bug icon when debugpy is listening),
`Revit` with a disconnected icon otherwise. Click it to connect, or to show the status when
connected. It refreshes after every command and every `revitpy.statusRefreshSeconds`.

### Reload on save

With `revitpy.reloadOnSave` on, saving a `.py` file sends `live/reload` for it. Only modules Revit has
already imported are reloaded (`importlib.reload`); a module nobody imported yet is reported in the
output channel and otherwise ignored. If Revit isn't reachable the save is not interrupted and the
reason is logged to the output channel. A notification appears only when a reload raises.

## Debugging

1. Install `debugpy` in Revit's Python environment and the Python Debugger extension in VS Code.
2. Run **RevitPy: Attach Debugger to Revit**. The Live Server starts debugpy on
   `127.0.0.1:revitpy.debugPort` and VS Code attaches with:

   ```json
   {
     "type": "debugpy",
     "request": "attach",
     "name": "Attach to Revit (RevitPy)",
     "connect": { "host": "127.0.0.1", "port": 5678 },
     "justMyCode": false
   }
   ```

3. Set breakpoints and use **Run Script in Revit**; the script runs in the process you are attached to.

debugpy keeps listening until Revit exits, so attaching again reuses the same port. You can also
put the configuration above in `launch.json` once debug/start has been called.

## Revit API IntelliSense (stubs)

Autocompletion for `Autodesk.Revit.DB` and friends needs `.pyi` stubs. As of this release **no
maintained stub package for current Revit versions is published on PyPI** (Revit's API assemblies are
Autodesk's, and stubs are usually generated from your own installation). Options:

- Generate stubs from your Revit installation's `RevitAPI.dll` / `RevitAPIUI.dll` with
  [pythonnet-stub-generator](https://github.com/MHDante/pythonnet-stub-generator)
  (`dotnet tool install --global pythonnetstubgenerator.tool`, then
  `GeneratePythonNetStubs --dest-path=<folder> --target-dlls=<Revit folder>\RevitAPI.dll;<Revit folder>\RevitAPIUI.dll`).
  It is a third-party tool; check its output against your Revit version.
- Older IronPython-era stubs such as [gtalarico/ironpython-stubs](https://github.com/gtalarico/ironpython-stubs)
  cover older Revit releases only.

Then run **RevitPy: Configure Revit API Stubs Folder** and pick the folder that *contains* the
`Autodesk` package. The extension appends it to `python.analysis.extraPaths` (workspace settings
if a folder is open, user settings otherwise), replaces the previously configured folder, and remembers
it in `revitpy.stubsPath`.

## Snippets

Python snippets: `revitpy-script` (script skeleton using `revitpy.RevitAPI` and `__revit__`),
`revitpy-query`, `revitpy-transaction`, `revit-transaction` (raw `Autodesk.Revit.DB.Transaction`),
`revit-collector` (`FilteredElementCollector`) and `revitpy-analysis` (`@register_analysis` for
`bridge/analyze`).

## Settings

| Setting | Default | Description |
|---|---|---|
| `revitpy.discoveryFile` | `""` | Discovery file path. Empty uses `REVITPY_LIVE_DISCOVERY` or `~/.revitpy/live.json`. |
| `revitpy.autoConnect` | `true` | Try to connect when the extension starts (failures are only logged). |
| `revitpy.requestTimeoutSeconds` | `330` | How long to wait for Revit to answer a request. |
| `revitpy.statusRefreshSeconds` | `30` | Status bar refresh interval while connected; `0` disables it. |
| `revitpy.reloadOnSave` | `false` | Send `live/reload` for a `.py` file when it is saved. |
| `revitpy.debugPort` | `5678` | Port debugpy listens on inside Revit. |
| `revitpy.debugPathMappings` | `[]` | `pathMappings` for the attach configuration (only when Revit runs the files from a different path). |
| `revitpy.debugJustMyCode` | `false` | `justMyCode` for the attach configuration. |
| `revitpy.devCliPath` | `"revitpy-dev"` | Dev CLI executable for **Create Project**. |
| `revitpy.stubsPath` | `""` | Revit API stubs folder (set by **Configure Revit API Stubs Folder**). |

## Security

The Live Server executes arbitrary Python in Revit for anyone holding its token. The token lives only
in the discovery file (readable by the current user) and the extension sends it only in the
`Authorization` header of the WebSocket handshake to the URL in that file. The server listens on
loopback and rejects browser origins.

## Development

```bash
npm ci
npm run lint       # eslint (typescript-eslint, flat config)
npm run compile    # tsc --noEmit type check + esbuild bundle -> out/extension.js
npm test           # vitest: protocol client, connection manager, commands (mocked vscode)
npx vsce package   # revitpy-vscode-<version>.vsix
```

Press F5 in VS Code with this folder open (and an "Extension Development Host" launch
configuration) to try it. The tests run a fake Live Server in-process (`test/helpers/fakeLiveServer.ts`)
that enforces the same handshake rules as the real one.
