"""Run the space_planning demo on the model open in Revit.

Use RevitPy > Run Script, or `revitpy live run run_in_revit.py` with the Live
Server on. RevitPy binds `__revit__` to Revit's UIApplication; the
`space_planning` package must be importable from RevitPy's python_path.
"""

from space_planning import run

report = run(__revit__)  # noqa: F821 - provided by the RevitPy host
print(report.to_text())
