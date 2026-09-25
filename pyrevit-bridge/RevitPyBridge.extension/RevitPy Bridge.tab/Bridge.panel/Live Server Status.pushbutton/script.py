"""Check the connection to the RevitPy Live Server and list its analyses."""

from __future__ import print_function

from pyrevit import forms, script
from revitpy_bridge import BridgeError, RevitPyBridge, discovery_path

output = script.get_output()
bridge = RevitPyBridge(timeout=15)
try:
    status = bridge.status()
except BridgeError as e:
    forms.alert(str(e), title="RevitPy Bridge", exitscript=True)

rows = [
    ["Discovery file", discovery_path()],
    ["RevitPy", status.get("revitpy_version")],
    ["Python", status.get("python_version")],
    ["Revit", status.get("revit_version")],
    ["Document", status.get("document") or "(none)"],
]

debug_info = status.get("debug") or {}
if debug_info.get("listening"):
    port = debug_info.get("port", "unknown")
    rows.append(["Debugger", "listening on %s" % port])
else:
    rows.append(["Debugger", "off"])

output.print_md("# RevitPy Live Server")
output.print_table(table_data=rows, columns=["Property", "Value"])

analyses = status.get("analyses") or []
output.print_md("## Analyses")
if analyses:
    bullet_list = ["- `%s`" % name for name in analyses]
    output.print_md("\n".join(bullet_list))
else:
    output.print_md(
        "_No analyses registered. Install revitpy-bridge-analyses into RevitPy's "
        "Python and restart the Live Server._"
    )
