"""
Helpers for Python running inside the RevitPy host add-in.

Threading model:
    The add-in initializes CPython on Revit's main thread (so here
    ``threading.main_thread()`` *is* Revit's API thread) and then releases the
    GIL. Scripts run from the ribbon execute on that thread and may call the
    Revit API directly. Code on any other thread (for example the MCP server's
    event loop) must hop onto the main thread first, which
    :func:`call_on_revit_thread` does through an ``ExternalEvent`` exposed by
    the add-in as ``builtins.__revitpy_dispatcher__``::

        import threading
        from revitpy.revit.host import call_on_revit_thread

        def worker():
            title = call_on_revit_thread(
                lambda uiapp: uiapp.ActiveUIDocument.Document.Title
            )
            print(title)

        threading.Thread(target=worker).start()

The dispatcher is polled rather than blocked on, because pythonnet holds the
GIL during .NET calls and a blocking wait would deadlock Revit.
"""

from __future__ import annotations

import asyncio
import builtins
import json
import os
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from loguru import logger

from ..ai import McpServer, RevitTools, SafetyGuard
from ..ai.types import McpServerConfig, ToolDefinition, ToolResult

__all__ = [
    "MainThreadRevitTools",
    "RevitHostUnavailableError",
    "RevitThreadError",
    "call_on_revit_thread",
    "get_dispatcher",
    "in_revit_host",
    "is_mcp_server_running",
    "mcp_server_status",
    "revit_confirmation",
    "set_ui_application",
    "start_mcp_server",
    "stop_mcp_server",
    "toggle_mcp_server",
]

T = TypeVar("T")

_ui_application: Any | None = None


class RevitHostUnavailableError(RuntimeError):
    """Raised when code requires the RevitPy host add-in but isn't running in it."""


class RevitThreadError(RuntimeError):
    """Raised when a callable dispatched to Revit's main thread failed."""


def get_dispatcher() -> Any | None:
    """Return the add-in's dispatcher, or ``None`` outside the RevitPy host."""
    return getattr(builtins, "__revitpy_dispatcher__", None)


def in_revit_host() -> bool:
    """Whether this interpreter is embedded by the RevitPy host add-in."""
    return get_dispatcher() is not None


def set_ui_application(ui_application: Any) -> None:
    """Remember the ``UIApplication`` for calls made on the main thread."""
    global _ui_application
    _ui_application = ui_application


def call_on_revit_thread(
    func: Callable[[Any], T],
    *,
    timeout: float | None = 60.0,
    poll_interval: float = 0.005,
) -> T:
    """Run ``func(uiapp)`` on Revit's main thread and return its result.

    Called on the main thread itself, ``func`` runs immediately (dispatching
    would hang, since the ``ExternalEvent`` cannot fire while the main thread
    is busy).

    Raises:
        RevitHostUnavailableError: Outside the host, or on the main thread
            before a ``UIApplication`` was captured.
        TimeoutError: Revit did not run the request in time.
        RevitThreadError: ``func`` raised; the message holds its traceback.
    """
    if threading.current_thread() is threading.main_thread():
        if _ui_application is None:
            raise RevitHostUnavailableError(
                "call_on_revit_thread() was called on Revit's main thread before a "
                "UIApplication was captured; pass __revit__ to set_ui_application()."
            )
        return func(_ui_application)

    dispatcher = get_dispatcher()
    if dispatcher is None:
        raise RevitHostUnavailableError(
            "Not running inside the RevitPy host add-in; Revit's main thread is "
            "not reachable from here."
        )

    request = dispatcher.Post(func)
    started = time.monotonic()
    while not request.IsCompleted:
        if timeout is not None and time.monotonic() - started > timeout:
            raise TimeoutError(
                f"Revit did not run the request within {timeout}s "
                "(is a modal dialog open?)"
            )
        time.sleep(poll_interval)

    if request.Succeeded:
        return cast(T, request.Result)
    raise RevitThreadError(str(request.Error))


class MainThreadRevitTools(RevitTools):
    """``RevitTools`` whose handlers always execute on Revit's main thread."""

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        parent = super().execute_tool

        def run(_uiapp: Any) -> tuple[ToolResult | None, BaseException | None]:
            # Capture exceptions here so the caller re-raises the original type
            # (e.g. ToolExecutionError, which the MCP server reports as a tool
            # error) instead of a flattened RevitThreadError.
            try:
                return parent(name, arguments), None
            except Exception as e:
                return None, e

        result, error = call_on_revit_thread(run)
        if error is not None:
            raise error
        return cast(ToolResult, result)


def revit_confirmation(tool: ToolDefinition, arguments: dict[str, Any]) -> bool:
    """Ask the Revit user to approve a tool call with a Yes/No ``TaskDialog``.

    Any failure (including a timeout) denies the call.
    """

    def show_dialog(_uiapp: Any) -> bool:
        import clr

        clr.AddReference("RevitAPIUI")
        from Autodesk.Revit.UI import (
            TaskDialog,
            TaskDialogCommonButtons,
            TaskDialogResult,
        )

        dialog = TaskDialog("RevitPy MCP")
        dialog.MainInstruction = f"An AI agent wants to run '{tool.name}'"
        dialog.MainContent = json.dumps(arguments, indent=2, default=str)[:2000]
        dialog.CommonButtons = TaskDialogCommonButtons.Yes | TaskDialogCommonButtons.No
        dialog.DefaultButton = TaskDialogResult.No
        return bool(dialog.Show() == TaskDialogResult.Yes)

    try:
        return call_on_revit_thread(show_dialog, timeout=300.0)
    except Exception as e:
        logger.warning(f"Denying '{tool.name}': confirmation failed: {e}")
        return False


@dataclass
class _ServerHandle:
    thread: threading.Thread
    loop: asyncio.AbstractEventLoop
    stop_event: asyncio.Event
    server: McpServer
    url: str
    token: str


_server: _ServerHandle | None = None
_server_lock = threading.Lock()


def _status(handle: _ServerHandle | None) -> str:
    if handle is None:
        return "RevitPy MCP server is not running."
    return (
        f"RevitPy MCP server running at {handle.url}\n"
        f"Authorization: Bearer {handle.token}\n"
        "Configure your MCP client with this URL and token. "
        "Model changes require confirmation in Revit."
    )


def start_mcp_server(
    ui_application: Any,
    *,
    host: str | None = None,
    port: int | None = None,
    token: str | None = None,
    startup_timeout: float = 10.0,
) -> str:
    """Start the MCP server for this Revit session on a background thread.

    Must be called on Revit's main thread (e.g. from the ribbon command).
    Defaults come from ``REVITPY_MCP_HOST`` / ``REVITPY_MCP_PORT`` /
    ``REVITPY_MCP_TOKEN``; without a token a random one is generated.

    Returns:
        A status message including the URL and bearer token.
    """
    global _server

    from ..api import RevitAPI
    from .adapters import adapt_application

    with _server_lock:
        if _server is not None:
            return _status(_server)

        host = host or os.environ.get("REVITPY_MCP_HOST", "127.0.0.1")
        port = (
            port
            if port is not None
            else int(os.environ.get("REVITPY_MCP_PORT", "8765"))
        )
        token = (
            token or os.environ.get("REVITPY_MCP_TOKEN") or secrets.token_urlsafe(24)
        )

        set_ui_application(ui_application)
        api = RevitAPI()
        api.connect(adapt_application(ui_application))

        server = McpServer(
            MainThreadRevitTools(api),
            config=McpServerConfig(host=host, port=port, auth_token=token),
            safety_guard=SafetyGuard(confirmation_callback=revit_confirmation),
        )

        ready = threading.Event()
        state: dict[str, Any] = {}

        async def run() -> None:
            stop_event = asyncio.Event()
            try:
                await server.start()
            except Exception as e:
                state["error"] = e
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

        thread = threading.Thread(target=thread_main, name="revitpy-mcp", daemon=True)
        thread.start()

        if not ready.wait(startup_timeout):
            raise RuntimeError(f"MCP server did not start within {startup_timeout}s")
        if "error" in state:
            raise RuntimeError(
                f"MCP server failed to start: {state['error']}"
            ) from state["error"]

        _server = _ServerHandle(
            thread=thread,
            loop=state["loop"],
            stop_event=state["stop_event"],
            server=server,
            url=f"ws://{host}:{server.port}",
            token=token,
        )
        logger.info(f"RevitPy MCP server started at {_server.url}")
        return _status(_server)


def stop_mcp_server(timeout: float = 10.0) -> str:
    """Stop the MCP server if it is running."""
    global _server

    with _server_lock:
        handle = _server
        if handle is None:
            return _status(None)
        handle.loop.call_soon_threadsafe(handle.stop_event.set)
        handle.thread.join(timeout)
        if handle.thread.is_alive():
            logger.warning("MCP server thread did not exit within {}s", timeout)
        _server = None
        return "RevitPy MCP server stopped."


def mcp_server_status() -> str:
    """Human-readable server status."""
    with _server_lock:
        return _status(_server)


def is_mcp_server_running() -> bool:
    with _server_lock:
        return _server is not None


def toggle_mcp_server(ui_application: Any) -> str:
    """Start the server if stopped, stop it if running; return the new status."""
    if is_mcp_server_running():
        return stop_mcp_server()
    return start_mcp_server(ui_application)
