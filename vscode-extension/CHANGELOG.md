# Changelog

All notable changes to the RevitPy VS Code extension.

## [2.0.0] - Unreleased

Rewritten as a client of the RevitPy Live Server (JSON-RPC 2.0 over WebSocket inside Revit). The
1.0.0 extension talked to a C# host WebSocket (`ws://host:port/revitpy`) that no longer exists, so
none of its Revit features worked.

### Added
- Connection manager that finds the Live Server through its discovery file
  (`~/.revitpy/live.json` / `REVITPY_LIVE_DISCOVERY` / `revitpy.discoveryFile`), authenticates with
  the bearer token and reconnects on demand. Commands **Connect to Revit**, **Disconnect from Revit**,
  **Show Status**; status bar item with Revit version and active document.
- **Run Script in Revit** (`live/runFile`, saves first; `live/execute` for untitled editors) and
  **Run Selection in Revit** (`live/execute`, dedented, current line when nothing is selected).
  Output and tracebacks go to the **RevitPy** output channel.
- **Reload Current Module in Revit** and the `revitpy.reloadOnSave` setting (`live/reload`).
- **Attach Debugger to Revit**: `debug/start`, then a standard `debugpy` attach session
  (requires the `ms-python.debugpy` extension and `debugpy` in Revit's Python).
- **Create Project**: runs `revitpy-dev create project` in a terminal.
- **Configure Revit API Stubs Folder**: adds a stubs folder to `python.analysis.extraPaths`.
- Unit tests (vitest) against an in-process fake Live Server.

### Changed
- Snippets rewritten for Python files against the current `revitpy` API and the Revit API.
- Toolchain: TypeScript 5.9, esbuild bundle (`out/extension.js`), ESLint 10 flat config with
  typescript-eslint, `@vscode/vsce` 3, VS Code engine `^1.110.0`; `package-lock.json` is committed.
- Settings: `revitpy.host`, `revitpy.port`, `revitpy.enableHotReload`, `revitpy.enableIntelliSense`
  and `revitpy.logLevel` are gone (the connection comes from the discovery file); see the README
  for the current settings.

### Removed
- The custom language server (`src/server/*`) and its hard-coded Revit API completion data: Python
  files are handled by the Python extension / Pylance, with real stubs configured as above.
- The custom `revitpy` debug adapter: debugging uses the standard debugpy attach.
- The `.rvtpy` language, its TextMate grammar and language configuration: RevitPy scripts are
  ordinary `.py` files.
- The package manager tree view and the "RevitPy Packages"/"RevitPy Connection" views: they were
  not connected to any working backend. Use the `revitpy-dev` / `revitpy-install` CLIs for packages.
- The broken `postinstall` script and the `scripts/build.js` / `scripts/install.js` helpers.

## [1.0.0] - 2024-01-15

Initial release (targeted the retired C# host WebSocket API).
