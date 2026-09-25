# @revitpy/dev-server

The edit-save-see loop for RevitPy: watch your Python files, and on every save
reload the changed modules inside a running Revit and re-run your script.

It is a small client of the **RevitPy Live Server**, the authenticated JSON-RPC
WebSocket endpoint that the RevitPy add-in runs inside Revit (see
[Live Server protocol](../docs/developer/live-server.md)). It has no server of its own and
does nothing Revit could not already do through `revitpy live ...`. It does the
watching, debouncing, reconnecting and output formatting for you.

## Requirements

- Node.js 20 or newer.
- Revit with the RevitPy add-in, and the Live Server started (the **Live Server** button on
  the RevitPy ribbon tab, or `start_live_server = true` in `%APPDATA%\RevitPy\settings.ini`).
- The dev server runs on the same machine as Revit. It finds the server through the discovery
  file `~/.revitpy/live.json` (or `$REVITPY_LIVE_DISCOVERY`), and file paths are sent to Revit
  as local absolute paths.

## Install

From this directory:

```bash
npm ci
npm run build
npm install -g .        # or: npx revitpy-dev-server ... / node dist/bin.js ...
```

## Usage

### `watch`: reload on save

```bash
revitpy-dev-server watch [paths...] --run <entry.py> [--debounce <ms>] [--ignore <glob>...]
revitpy-dev-server watch [paths...] --reload-only    [--debounce <ms>] [--ignore <glob>...]
```

- Watches `paths` (default: the current directory) recursively for added or changed `.py`
  files. `__pycache__`, dot-directories (`.venv`, `.git`, ...) and `node_modules` are always
  ignored; add more with `--ignore` (repeatable, globs relative to a watched path, for example
  `--ignore 'build/**'`).
- Changes are debounced (`--debounce`, default 150 ms after the last change) and handled as one
  batch. chokidar reports saves of the same file less than about 50 ms apart as one event, so
  keep the debounce at 50 ms or more; the server always reads the file as it is when the batch
  runs. The batch:
  1. `live/reload {paths: [...changed files]}`: every module already imported in Revit whose
     source is one of the changed files is reloaded with `importlib.reload`. Files that are not
     imported modules are ignored by the server.
  2. With `--run entry.py`: `live/runFile {path: entry}`. The script runs as `__main__` with
     `__revit__` bound; its output and, on failure, its traceback are printed. If the reload
     reported an error (a syntax error, say) the run is skipped so you do not run stale code.
- Exactly one of `--run` or `--reload-only` is required.
- Saves that arrive while a cycle is running are merged into one follow-up cycle.
- If Revit or the Live Server is not running yet, or restarts (new port and token), the dev
  server re-reads the discovery file and retries with backoff (250 ms, doubling to at most 5 s),
  printing `waiting ...` once per distinct problem and `connected ...` when it gets through.
  A request that was cut off by a disconnect is reported, not re-sent, because it may already
  have run in Revit.
- Ctrl+C stops watching and closes the connection (a second Ctrl+C exits immediately).

Example session (captured against `test/fixtures/real_live_server.py`, the real Live Server
running outside Revit; inside Revit the times depend on your script and on Revit):

```text
$ revitpy-dev-server watch src --run src/report.py
Watching src for .py changes; running src/report.py after each reload. Press Ctrl+C to stop.
connected to the RevitPy Live Server at ws://127.0.0.1:33675 (Revit 2026)

[18:52:23] changed src/report.py
  reload  no imported module matched (18 ms)
  run     src/report.py ok in 6 ms (Revit 0 ms)
  | walls: 128 in DevServer.rvt

[18:52:24] changed src/walls.py
  reload  1 module (walls) in 16 ms
  run     src/report.py ok in 6 ms (Revit 0 ms)
  | walls: 131 in DevServer.rvt
^CStopped.
```

The first save runs the script, which imports `walls`; after that, saving `walls.py` reloads
it before the re-run. The two times on the `run` line are the round trip seen by the dev server
and the execution time reported by the Live Server.

### `run`: run a file once

```bash
revitpy-dev-server run script.py
```

Prints the output (and traceback). Exit code 0 on success, 1 when the script fails or the Live
Server cannot be reached, 2 when the file does not exist. Unlike `watch`, it does not wait for a
server that is not running.

### `status`

```bash
revitpy-dev-server status
```

Shows the Live Server URL, Revit version, open document, RevitPy and Python versions, debugger
state and registered analyses (`live/status`).

### Options for all commands

| Option | Meaning |
|---|---|
| `--discovery <file>` | Discovery file to use instead of `$REVITPY_LIVE_DISCOVERY` / `~/.revitpy/live.json` |
| `NO_COLOR=1` / `FORCE_COLOR=1` | Disable / force colored output (default: color on a terminal) |

## Library use

The pieces are exported for editor integrations and scripts:

```ts
import { LiveClient, LiveSession, readDiscovery } from '@revitpy/dev-server';

const client = await LiveClient.connect(await readDiscovery());
console.log(await client.status());
const result = await client.runFile('C:/scripts/report.py');
await client.close();
```

`LiveSession` adds reconnect-with-backoff on top of `LiveClient`; `DevLoop`, `ChangeBatcher`
and `watchPython` are the building blocks of `watch`.

## Design notes

- **File watching: chokidar 4.** Node's built-in `fs.watch` is recursive on Linux only since
  Node 20 and reports editors' atomic saves (write to a temp file, then rename) as rename events
  that vary by platform and editor. chokidar normalises those into `add`/`change` (its `atomic`
  option) on Windows, macOS and Linux, and v4 has a single dependency. Globs for `--ignore` are
  matched with picomatch.
- The protocol client (`src/client.ts`) mirrors `revitpy/live_client.py`: one WebSocket,
  `Authorization: Bearer <token>`, no `Origin` header, JSON-RPC 2.0 requests matched by id, a
  330 s request timeout (the server waits up to 300 s for Revit's main thread).

## Development

```bash
npm ci
npm run lint     # eslint (typescript-eslint strict, type-checked) + tsc --noEmit
npm run build    # tsc -> dist/
npm test         # vitest
```

The tests run headless. Most use an in-process fake Live Server (`test/helpers/fakeLiveServer.ts`)
that enforces the bearer token and speaks JSON-RPC. `test/real-server.test.ts` starts the real
Python Live Server outside Revit (`test/fixtures/real_live_server.py`, with a stand-in for
Revit's main-thread dispatcher) and runs `status`, `run` and `watch` against it. It needs a
Python with revitpy installed (`pip install -e .` at the repository root): set `REVITPY_PYTHON`
to that interpreter, otherwise `python3` (`python` on Windows) is tried and the suite is skipped
with the reason in its name. With `REVITPY_REQUIRE_REAL_SERVER=1` (as in CI) a missing revitpy
fails the run instead.

## License

MIT
