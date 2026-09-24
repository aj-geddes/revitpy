"""Start or stop RevitPy's MCP server so AI agents can work with the open model.

Inside Revit (RevitPy host add-in): each run toggles the server. The first run
starts it on a background thread and prints the ``ws://`` URL and bearer token
to give your MCP client; the script then returns while the server keeps
running. Run it again to stop it. The ribbon's **MCP Server** button does the
same thing. Tools that change the model ask for confirmation in a Revit dialog.

Outside Revit, or under pyRevit, it explains what is needed and exits cleanly:
the server relies on the RevitPy add-in's main-thread dispatcher.

Settings (environment variables, read when the server starts):
    REVITPY_MCP_HOST   bind address          (default 127.0.0.1)
    REVITPY_MCP_PORT   port                  (default 8765)
    REVITPY_MCP_TOKEN  bearer token          (default: random per start)

Run it:
    * inside Revit: RevitPy ribbon -> Run Script -> pick this file
    * locally: ``python examples/mcp_server_in_revit.py`` (prints the help text)
"""

from __future__ import annotations

import os

from revitpy.revit.host import in_revit_host, is_mcp_server_running, toggle_mcp_server


def settings_text() -> str:
    """Describe the server settings that will be used."""
    token = "(set)" if os.environ.get("REVITPY_MCP_TOKEN") else "(random per start)"
    return (
        f"  REVITPY_MCP_HOST  = {os.environ.get('REVITPY_MCP_HOST', '127.0.0.1')}\n"
        f"  REVITPY_MCP_PORT  = {os.environ.get('REVITPY_MCP_PORT', '8765')}\n"
        f"  REVITPY_MCP_TOKEN = {token}"
    )


def main() -> None:
    try:
        ui_app = __revit__  # noqa: F821 - injected by the RevitPy host / pyRevit
    except NameError:
        ui_app = None

    if ui_app is None or not in_revit_host():
        print(
            "The RevitPy MCP server runs inside Revit, so this example needs the\n"
            "RevitPy host add-in: open a model, then RevitPy ribbon -> Run Script\n"
            "-> pick this file (or just press the ribbon's 'MCP Server' button).\n"
            "pyRevit alone is not enough - the server uses the add-in's\n"
            "dispatcher to run Revit API calls on Revit's main thread.\n\n"
            "Settings used when the server starts:\n" + settings_text()
        )
        return

    was_running = is_mcp_server_running()
    print(toggle_mcp_server(ui_app))
    if not was_running:
        print(
            "\nPoint your MCP client at the URL above and send the token as an\n"
            "'Authorization: Bearer <token>' header. Run this script again to stop."
        )


if __name__ == "__main__":
    main()
