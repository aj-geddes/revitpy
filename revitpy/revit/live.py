"""
RevitPy Live Server: run code in the open Revit session from development tools.

Runs inside Revit, in the Python embedded by the RevitPy add-in, and speaks
JSON-RPC 2.0 over WebSocket (see ``docs/developer/live-server.md``). Clients:
the VS Code extension, the file-watching dev server, the pyRevit bridge and
``revitpy live`` on the command line.

Security model:
    * Binds to loopback by default.
    * A bearer token is mandatory; it is random per start unless
      ``REVITPY_LIVE_TOKEN`` is set, and is published only in a discovery file
      readable by the current user (``~/.revitpy/live.json``).
    * Any handshake with a browser ``Origin`` header is rejected.
    * ``live/execute`` and ``live/runFile`` execute arbitrary Python by design.

Methods: ``live/status``, ``live/execute``, ``live/runFile``, ``live/reload``,
``debug/start``, ``bridge/listAnalyses``, ``bridge/analyze``. Code always runs
on Revit's main API thread (via :func:`revitpy.revit.host.call_on_revit_thread`).
"""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import importlib
import importlib.util
import io
import json
import os
import platform
import secrets
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from loguru import logger

from ..rpc import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcWebSocketServer,
)
from .host import RevitThreadError, call_on_revit_thread, set_ui_application

__all__ = [
    "DEFAULT_PORT",
    "PROTOCOL_VERSION",
    "ANALYSIS_ENTRY_POINT_GROUP",
    "LiveServer",
    "discovery_path",
    "load_analysis_plugins",
    "execute_code",
    "is_live_server_running",
    "live_server_status",
    "register_analysis",
    "registered_analyses",
    "reload_modules",
    "start_live_server",
    "stop_live_server",
    "toggle_live_server",
    "unregister_analysis",
]

PROTOCOL_VERSION = 1
DEFAULT_PORT = 8766

AnalysisHandler = Callable[[list[Any], dict[str, Any], Any], Any]


def discovery_path() -> Path:
    """Where the running server publishes its URL and token."""
    override = os.environ.get("REVITPY_LIVE_DISCOVERY")
    return Path(override) if override else Path.home() / ".revitpy" / "live.json"


# -- analysis registry --------------------------------------------------------

_ANALYSES: dict[str, tuple[AnalysisHandler, bool]] = {}


def register_analysis(
    name: str, *, replace: bool = False, main_thread: bool = True
) -> Callable[[AnalysisHandler], AnalysisHandler]:
    """Register ``func(elements, options, uiapp)`` as a ``bridge/analyze`` target.

    With ``main_thread=True`` (the default) the handler runs on Revit's main
    thread and may use the Revit API through ``uiapp``. With
    ``main_thread=False`` it runs on a worker thread and receives
    ``uiapp=None``: use this for analyses that only read the element data they
    are sent. Such analyses also work when the caller itself holds Revit's
    main thread while it waits for the reply (a pyRevit button), where a
    main-thread analysis could not start until the request timed out.
    """

    def decorator(func: AnalysisHandler) -> AnalysisHandler:
        if name in _ANALYSES and not replace:
            raise ValueError(f"Analysis '{name}' is already registered")
        _ANALYSES[name] = (func, main_thread)
        return func

    return decorator


def unregister_analysis(name: str) -> None:
    _ANALYSES.pop(name, None)


def registered_analyses() -> list[str]:
    return sorted(_ANALYSES)


ANALYSIS_ENTRY_POINT_GROUP = "revitpy.analyses"


def load_analysis_plugins() -> list[str]:
    """Import every ``revitpy.analyses`` entry point so its analyses register.

    A package exposes analyses by declaring, e.g. in ``pyproject.toml``::

        [project.entry-points."revitpy.analyses"]
        my_tools = "my_tools.analyses"

    Returns the entry point names that loaded; failures are logged, not raised.
    """
    loaded: list[str] = []
    for entry_point in metadata.entry_points(group=ANALYSIS_ENTRY_POINT_GROUP):
        try:
            entry_point.load()
        except Exception:
            logger.exception("Failed to load analysis plugin {}", entry_point.name)
            continue
        loaded.append(entry_point.name)
    return loaded


# -- operations (run on Revit's main thread) --------------------------------


def execute_code(
    uiapp: Any, code: str, filename: str, cwd: str | None
) -> dict[str, Any]:
    """Execute *code* as ``__main__`` with ``__revit__`` bound; capture output.

    Failures are reported in the result, never raised.
    """
    started = time.perf_counter()
    output = io.StringIO()
    script_dir = cwd
    if not filename.startswith("<"):
        script_dir = str(Path(filename).resolve().parent)
    previous_cwd = os.getcwd()
    added_path = False
    error: str | None = None
    success = True

    try:
        if script_dir:
            sys.path.insert(0, script_dir)
            added_path = True
        if cwd:
            os.chdir(cwd)
        compiled = compile(code, filename, "exec")
        namespace = {
            "__name__": "__main__",
            "__file__": filename,
            "__revit__": uiapp,
            "__builtins__": builtins,
        }
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            exec(compiled, namespace)  # noqa: S102 - authenticated execution endpoint
    except SystemExit as exc:
        if exc.code not in (0, None):
            success, error = False, f"SystemExit: {exc.code}"
    except BaseException:
        success, error = False, traceback.format_exc()
    finally:
        if added_path:
            with contextlib.suppress(ValueError):
                sys.path.remove(script_dir)  # type: ignore[arg-type]
        os.chdir(previous_cwd)

    return {
        "success": success,
        "output": output.getvalue(),
        "error": error,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def reload_modules(names: list[str], paths: list[str]) -> dict[str, Any]:
    """Reload imported modules given by name or by source file path."""
    targets: list[str] = []
    for raw in paths:
        wanted = Path(raw).resolve()
        for name, module in list(sys.modules.items()):
            file = getattr(module, "__file__", None)
            if file and name not in targets:
                with contextlib.suppress(OSError, ValueError):
                    if Path(file).resolve() == wanted:
                        targets.append(name)
    for name in names:
        if name not in targets:
            targets.append(name)

    reloaded: list[str] = []
    errors: dict[str, str] = {}
    for name in targets:
        module = sys.modules.get(name)
        if module is None:
            errors[name] = "not imported"
            continue
        # A script's directory is only on sys.path while the script runs, so
        # modules imported next to it need their import root back to reload.
        file = getattr(module, "__file__", None)
        _discard_bytecode(file)
        root = _import_root(name, file)
        added = root is not None and root not in sys.path
        if added:
            sys.path.insert(0, root)  # type: ignore[arg-type]
        try:
            importlib.reload(module)
            reloaded.append(name)
        except Exception:
            errors[name] = traceback.format_exc()
        finally:
            if added:
                with contextlib.suppress(ValueError):
                    sys.path.remove(root)  # type: ignore[arg-type]
    return {"reloaded": reloaded, "errors": errors}


def _discard_bytecode(file: str | None) -> None:
    """Drop cached bytecode so a reload always recompiles the source.

    ``.pyc`` staleness is judged by source mtime and size, which can miss an
    edit saved within the same second that keeps the file size.
    """
    importlib.invalidate_caches()
    if not file or not file.endswith(".py"):
        return
    with contextlib.suppress(OSError, NotImplementedError, ValueError):
        Path(importlib.util.cache_from_source(file)).unlink(missing_ok=True)


def _import_root(name: str, file: str | None) -> str | None:
    """The sys.path entry from which module *name* at *file* was imported."""
    if not file:
        return None
    path = Path(file).resolve().parent
    depth = name.count(".") + (1 if Path(file).name == "__init__.py" else 0)
    for _ in range(depth):
        path = path.parent
    return str(path)


def _python_executable() -> str:
    """The real interpreter (``sys.executable`` is Revit.exe when embedded)."""
    base = Path(sys.base_prefix)
    return str(base / "python.exe" if os.name == "nt" else base / "bin" / "python3")


class _InvalidParams(Exception):
    """Raised by handlers to produce a JSON-RPC ``-32602`` error."""


# -- server -------------------------------------------------------------------


class LiveServer(JsonRpcWebSocketServer):
    """The Live Server. Use :func:`start_live_server` inside Revit."""

    server_name = "revitpy-live"

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PORT,
        auth_token: str,
        revit_version: str | None = None,
        execute_timeout: float = 300.0,
    ) -> None:
        if not auth_token:
            raise ValueError("The Live Server requires an auth token")
        super().__init__(
            host=host, port=port, auth_token=auth_token, allowed_origins=()
        )
        self._revit_version = revit_version
        self._execute_timeout = execute_timeout
        self._debug_port: int | None = None
        self._methods: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {
            "live/status": self._status,
            "live/execute": self._execute,
            "live/runFile": self._run_file,
            "live/reload": self._reload,
            "debug/start": self._debug_start,
            "bridge/listAnalyses": self._list_analyses,
            "bridge/analyze": self._analyze,
        }

    async def _handle_message(self, message: JsonRpcRequest) -> JsonRpcResponse:
        handler = self._methods.get(message.method)
        if handler is None:
            return self._error(
                message.id, METHOD_NOT_FOUND, f"Method not found: {message.method}"
            )
        try:
            result = await handler(message.params)
        except _InvalidParams as exc:
            return self._error(message.id, INVALID_PARAMS, f"Invalid params: {exc}")
        return JsonRpcResponse(id=message.id, result=result)

    async def _on_revit(self, func: Callable[[Any], Any], timeout: float) -> Any:
        return await asyncio.to_thread(call_on_revit_thread, func, timeout=timeout)

    async def _run_code(
        self, code: str, filename: str, cwd: str | None
    ) -> dict[str, Any]:
        try:
            return await self._on_revit(
                lambda uiapp: execute_code(uiapp, code, filename, cwd),
                self._execute_timeout,
            )
        except TimeoutError:
            return _failure("Timed out waiting for Revit (is a modal dialog open?)")
        except RevitThreadError as exc:
            return _failure(str(exc))

    # -- methods --

    async def _status(self, params: dict[str, Any]) -> dict[str, Any]:
        def title(uiapp: Any) -> str | None:
            ui_document = uiapp.ActiveUIDocument
            return None if ui_document is None else str(ui_document.Document.Title)

        try:
            document = await self._on_revit(title, 5.0)
        except Exception:
            document = None
        try:
            revitpy_version = metadata.version("revitpy")
        except metadata.PackageNotFoundError:
            revitpy_version = "unknown"
        return {
            "protocol": PROTOCOL_VERSION,
            "revitpy_version": revitpy_version,
            "python_version": platform.python_version(),
            "revit_version": self._revit_version,
            "document": document,
            "debug": {
                "listening": self._debug_port is not None,
                "port": self._debug_port,
            },
            "analyses": registered_analyses(),
        }

    async def _execute(self, params: dict[str, Any]) -> dict[str, Any]:
        code = _require(params, "code", str)
        filename = _optional(params, "filename", str, "<live>")
        cwd = _optional(params, "cwd", str, None)
        return await self._run_code(code, filename, cwd)

    async def _run_file(self, params: dict[str, Any]) -> dict[str, Any]:
        path = Path(_require(params, "path", str)).resolve()
        if not path.is_file():
            raise _InvalidParams(f"File not found: {path}")
        code = path.read_text(encoding="utf-8")
        return await self._run_code(code, str(path), str(path.parent))

    async def _reload(self, params: dict[str, Any]) -> dict[str, Any]:
        modules = _string_list(params, "modules")
        paths = _string_list(params, "paths")
        try:
            return await self._on_revit(
                lambda _uiapp: reload_modules(modules, paths), self._execute_timeout
            )
        except TimeoutError:
            return {"reloaded": [], "errors": {"*": "Timed out waiting for Revit"}}

    async def _debug_start(self, params: dict[str, Any]) -> dict[str, Any]:
        port = _optional(params, "port", int, 5678)
        if self._debug_port is not None:
            return {"listening": True, "port": self._debug_port}
        try:
            import debugpy
        except ImportError:
            return {
                "listening": False,
                "error": "debugpy is not installed in the Revit Python environment "
                "(pip install debugpy)",
            }
        try:
            debugpy.configure(python=_python_executable())
            _host, bound = debugpy.listen(("127.0.0.1", port))
        except Exception as exc:
            return {"listening": False, "error": str(exc)}
        self._debug_port = int(bound)
        logger.info("debugpy listening on 127.0.0.1:{}", self._debug_port)
        return {"listening": True, "port": self._debug_port}

    async def _list_analyses(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"analyses": registered_analyses()}

    async def _analyze(self, params: dict[str, Any]) -> dict[str, Any]:
        name = _require(params, "analysis", str)
        entry = _ANALYSES.get(name)
        if entry is None:
            raise _InvalidParams(f"Unknown analysis: {name}")
        handler, main_thread = entry
        elements = _optional(params, "elements", list, [])
        options = _optional(params, "options", dict, {})
        try:
            if main_thread:
                result = await self._on_revit(
                    lambda uiapp: handler(elements, options, uiapp),
                    self._execute_timeout,
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(handler, elements, options, None),
                    self._execute_timeout,
                )
        except TimeoutError:
            return {"success": False, "error": "Timed out waiting for Revit"}
        except Exception:
            return {"success": False, "error": traceback.format_exc()}
        return {"success": True, "result": result}


def _failure(message: str) -> dict[str, Any]:
    return {"success": False, "output": "", "error": message, "duration_ms": 0.0}


def _require(params: dict[str, Any], key: str, kind: type) -> Any:
    value = params.get(key)
    if not isinstance(value, kind) or isinstance(value, bool) and kind is int:
        raise _InvalidParams(f"'{key}' must be a {kind.__name__}")
    return value


def _optional(params: dict[str, Any], key: str, kind: type, default: Any) -> Any:
    if params.get(key) is None:
        return default
    return _require(params, key, kind)


def _string_list(params: dict[str, Any], key: str) -> list[str]:
    value = _optional(params, key, list, [])
    if not all(isinstance(item, str) for item in value):
        raise _InvalidParams(f"'{key}' must be a list of strings")
    return list(value)


# -- lifecycle ----------------------------------------------------------------


@dataclass
class _Handle:
    thread: threading.Thread
    loop: asyncio.AbstractEventLoop
    stop_event: asyncio.Event
    server: LiveServer
    url: str


_handle: _Handle | None = None
_handle_lock = threading.Lock()


def _write_discovery(data: dict[str, Any]) -> None:
    path = discovery_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".live-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
        if os.name != "nt":
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _remove_discovery(url: str) -> None:
    path = discovery_path()
    with contextlib.suppress(OSError, ValueError):
        if json.loads(path.read_text(encoding="utf-8")).get("url") == url:
            path.unlink()


def start_live_server(
    ui_application: Any,
    *,
    host: str | None = None,
    port: int | None = None,
    token: str | None = None,
    startup_timeout: float = 10.0,
) -> str:
    """Start the Live Server on a background thread. Call on Revit's main thread.

    Defaults come from ``REVITPY_LIVE_HOST`` / ``REVITPY_LIVE_PORT`` /
    ``REVITPY_LIVE_TOKEN``; without a token a random one is generated.
    """
    global _handle

    with _handle_lock:
        if _handle is not None:
            return _status_text(_handle)

        host = host or os.environ.get("REVITPY_LIVE_HOST", "127.0.0.1")
        if port is None:
            port = int(os.environ.get("REVITPY_LIVE_PORT", DEFAULT_PORT))
        token = (
            token or os.environ.get("REVITPY_LIVE_TOKEN") or secrets.token_urlsafe(32)
        )

        set_ui_application(ui_application)
        plugins = load_analysis_plugins()
        if plugins:
            logger.info("Loaded analysis plugins: {}", ", ".join(plugins))
        try:
            revit_version: str | None = str(ui_application.Application.VersionNumber)
        except Exception:
            revit_version = None

        server = LiveServer(
            host=host, port=port, auth_token=token, revit_version=revit_version
        )
        ready = threading.Event()
        state: dict[str, Any] = {}

        async def run() -> None:
            stop_event = asyncio.Event()
            try:
                await server.start()
            except Exception as exc:
                state["error"] = exc
                ready.set()
                return
            state["loop"] = asyncio.get_running_loop()
            state["stop_event"] = stop_event
            ready.set()
            try:
                await stop_event.wait()
            finally:
                await server.stop()

        def thread_main() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run())
            finally:
                loop.close()

        thread = threading.Thread(target=thread_main, name="revitpy-live", daemon=True)
        thread.start()
        if not ready.wait(startup_timeout):
            raise RuntimeError(f"Live Server did not start within {startup_timeout}s")
        if "error" in state:
            raise RuntimeError(
                f"Live Server failed to start: {state['error']}"
            ) from state["error"]

        url = f"ws://{host}:{server.port}"
        _write_discovery(
            {
                "protocol": PROTOCOL_VERSION,
                "url": url,
                "token": token,
                "pid": os.getpid(),
                "revit_version": revit_version,
                "started_at": datetime.now(UTC).isoformat(),
            }
        )
        _handle = _Handle(thread, state["loop"], state["stop_event"], server, url)
        logger.info("RevitPy Live Server started at {}", url)
        return _status_text(_handle)


def stop_live_server(timeout: float = 10.0) -> str:
    """Stop the Live Server if it is running."""
    global _handle

    with _handle_lock:
        handle = _handle
        if handle is None:
            return _status_text(None)
        handle.loop.call_soon_threadsafe(handle.stop_event.set)
        handle.thread.join(timeout)
        if handle.thread.is_alive():
            logger.warning("Live Server thread did not exit within {}s", timeout)
        _remove_discovery(handle.url)
        _handle = None
        return "RevitPy Live Server stopped."


def _status_text(handle: _Handle | None) -> str:
    if handle is None:
        return "RevitPy Live Server is not running."
    return (
        f"RevitPy Live Server running at {handle.url}\n"
        f"Connection details: {discovery_path()}"
    )


def live_server_status() -> str:
    with _handle_lock:
        return _status_text(_handle)


def is_live_server_running() -> bool:
    with _handle_lock:
        return _handle is not None


def toggle_live_server(ui_application: Any) -> str:
    """Start the server if stopped, stop it if running; return the new status."""
    if is_live_server_running():
        return stop_live_server()
    return start_live_server(ui_application)
