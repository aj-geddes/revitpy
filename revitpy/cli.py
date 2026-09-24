"""
``revitpy`` command-line interface.

Commands:
    revitpy version      Print the installed RevitPy version.
    revitpy doctor       Check the Python environment and optional integrations.
    revitpy mcp-serve    Run the RevitPy MCP server for AI agents.
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


if __name__ == "__main__":
    main()
