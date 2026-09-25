"""
``revitpy`` command-line interface.

Commands:
    revitpy version      Print the installed RevitPy version.
    revitpy doctor       Check the Python environment and optional integrations.
    revitpy mcp-serve    Run the RevitPy MCP server for AI agents.
    revitpy live ...     Run code in Revit through the Live Server.
"""

from __future__ import annotations

import asyncio
import json
import platform
import sys
from importlib import metadata
from typing import Any

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

CORE_DEPENDENCIES = [
    "pydantic",
    "loguru",
    "httpx",
    "websockets",
    "pyyaml",
    "click",
    "rich",
    "jinja2",
    "aiofiles",
]

OPTIONAL_DEPENDENCIES = [
    ("pythonnet", "Only needed outside the RevitPy host add-in, which bundles it"),
    ("ifcopenshell", "IFC import/export - pip install revitpy[ifc]"),
    ("specklepy", "Speckle interop - pip install revitpy[interop]"),
    ("defusedxml", "Hardened XML parsing for BCF - pip install revitpy[ifc]"),
]

_STATUS_STYLES = {
    "ok": Text("✓ ok", style="green"),
    "warn": Text("! warn", style="yellow"),
    "missing": Text("✗ missing", style="red"),
}


def _package_version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def _dependency_check(distribution: str, hint: str = "not installed") -> dict[str, str]:
    installed = _package_version(distribution)
    if installed is None:
        return {"name": distribution, "status": "missing", "detail": hint}
    return {"name": distribution, "status": "ok", "detail": installed}


def collect_checks() -> list[dict[str, str]]:
    """Run all environment checks and return them as dicts."""
    checks: list[dict[str, str]] = []

    python_version = platform.python_version()
    checks.append(
        {
            "name": "Python",
            "status": "ok" if sys.version_info >= (3, 11) else "warn",
            "detail": python_version,
        }
    )
    checks.append({"name": "Platform", "status": "ok", "detail": platform.platform()})
    if sys.platform != "win32":
        checks.append(
            {
                "name": "Revit connectivity",
                "status": "warn",
                "detail": "Revit runs on Windows only; use MockRevit for testing",
            }
        )

    checks.extend(_dependency_check(dep) for dep in CORE_DEPENDENCIES)
    checks.extend(_dependency_check(dep, hint) for dep, hint in OPTIONAL_DEPENDENCIES)

    try:
        from .revit import load_revit_api

        load_revit_api()
        checks.append(
            {"name": "Revit API", "status": "ok", "detail": "Autodesk.Revit.DB loaded"}
        )
    except Exception:
        checks.append(
            {
                "name": "Revit API",
                "status": "missing",
                "detail": "not running inside Revit",
            }
        )

    return checks


@click.group()
@click.version_option(package_name="revitpy", prog_name="revitpy")
def main() -> None:
    """RevitPy - modern Python framework for Revit."""


@main.command()
def version() -> None:
    """Print the installed RevitPy version."""
    click.echo(f"revitpy {_package_version('revitpy') or 'unknown'}")


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON.")
@click.pass_context
def doctor(ctx: click.Context, as_json: bool) -> None:
    """Check the environment. Exits 1 if a core dependency is missing."""
    checks = collect_checks()

    if as_json:
        click.echo(json.dumps({"checks": checks}, indent=2))
    else:
        table = Table(title="RevitPy environment")
        table.add_column("Check", style="cyan")
        table.add_column("Status")
        table.add_column("Detail")
        for check in checks:
            table.add_row(
                check["name"], _STATUS_STYLES[check["status"]], check["detail"]
            )
        Console().print(table)

    missing_core = any(
        c["status"] == "missing" and c["name"] in CORE_DEPENDENCIES for c in checks
    )
    if missing_core:
        ctx.exit(1)


async def _serve_forever(server: Any) -> None:
    await server.start()
    try:
        await asyncio.Event().wait()
    finally:
        await server.stop()


@main.command("mcp-serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind address.")
@click.option("--port", default=8765, show_default=True, type=int, help="Bind port.")
@click.option(
    "--token",
    default=None,
    envvar="REVITPY_MCP_TOKEN",
    help="Bearer token clients must send (or set REVITPY_MCP_TOKEN).",
)
def mcp_serve(host: str, port: int, token: str | None) -> None:
    """Run the MCP server without a live Revit connection.

    Tools that need a document report that RevitPy is not connected; embed
    ``McpServer`` in a Revit session to operate on a live model.
    """
    from .ai import McpServer, RevitTools, SafetyGuard
    from .ai.types import McpServerConfig

    config = McpServerConfig(host=host, port=port, auth_token=token)

    server = McpServer(RevitTools(), config=config, safety_guard=SafetyGuard())
    console = Console()
    console.print(
        f"RevitPy MCP server listening on ws://{host}:{port} (Ctrl+C to stop)"
    )
    try:
        asyncio.run(_serve_forever(server))
    except KeyboardInterrupt:
        console.print("Stopped.")


# -- revitpy live -------------------------------------------------------------


@main.group()
def live() -> None:
    """Talk to the Live Server running inside Revit."""


def _live_call(method: str, params: dict[str, Any] | None = None) -> Any:
    from .live_client import LiveServerError, LiveServerNotFoundError, call_live

    try:
        return call_live(method, params)
    except (LiveServerNotFoundError, LiveServerError, OSError, TimeoutError) as exc:
        raise click.ClickException(str(exc)) from exc


def _report(result: dict[str, Any]) -> None:
    if result.get("output"):
        click.echo(result["output"], nl=False)
    if not result.get("success", False):
        click.echo(result.get("error") or "Failed", err=True)
        raise SystemExit(1)


@live.command("status")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON.")
def live_status(as_json: bool) -> None:
    """Show the connected Revit session."""
    status = _live_call("live/status")
    if as_json:
        click.echo(json.dumps(status, indent=2))
        return
    click.echo(f"Revit {status.get('revit_version') or '?'}")
    click.echo(f"Document: {status.get('document') or '(none)'}")
    click.echo(
        f"RevitPy {status.get('revitpy_version')} on Python {status.get('python_version')}"
    )
    debug = status.get("debug") or {}
    if debug.get("listening"):
        click.echo(f"debugpy listening on port {debug.get('port')}")


@live.command("run")
@click.argument("script", type=click.Path(exists=True, dir_okay=False))
def live_run(script: str) -> None:
    """Run SCRIPT inside Revit (the path must be readable on the Revit machine)."""
    from pathlib import Path

    _report(_live_call("live/runFile", {"path": str(Path(script).resolve())}))


@live.command("exec")
@click.argument("code")
def live_exec(code: str) -> None:
    """Execute CODE inside Revit."""
    _report(_live_call("live/execute", {"code": code, "filename": "<revitpy live>"}))


@live.command("reload")
@click.argument("modules", nargs=-1, required=True)
def live_reload(modules: tuple[str, ...]) -> None:
    """Reload imported MODULES (names or .py paths) inside Revit."""
    from pathlib import Path

    names = [m for m in modules if not m.endswith(".py")]
    paths = [str(Path(m).resolve()) for m in modules if m.endswith(".py")]
    result = _live_call("live/reload", {"modules": names, "paths": paths})
    for name in result.get("reloaded", []):
        click.echo(f"reloaded {name}")
    for name, error in (result.get("errors") or {}).items():
        click.echo(f"{name}: {error}", err=True)
    if result.get("errors"):
        raise SystemExit(1)


@live.command("debug")
@click.option("--port", default=5678, show_default=True, type=int)
def live_debug(port: int) -> None:
    """Start debugpy inside Revit so an editor can attach."""
    result = _live_call("debug/start", {"port": port})
    if not result.get("listening"):
        raise click.ClickException(result.get("error") or "debugger did not start")
    click.echo(
        f"debugpy listening on 127.0.0.1:{result['port']}; attach with a "
        '"debugpy" attach configuration.'
    )


if __name__ == "__main__":
    main()
