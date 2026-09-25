"""Send the selected elements to a RevitPy analysis and show the result."""

from __future__ import print_function

import json

from pyrevit import forms, revit, script
from revitpy_bridge import (
    AnalysisFailed,
    BridgeError,
    RevitPyBridge,
    element_id_value,
    serialize_elements,
)

TITLE = "RevitPy Bridge"
SCALARS = (str, int, float, bool, type(None))
try:
    SCALARS = SCALARS + (unicode,)  # noqa: F821 - IronPython 2.7
except NameError:
    pass


def _fmt(value):
    """Readable number: 1,234.6 for large values, 4 significant digits otherwise."""
    if abs(value) >= 1000:
        return "{:,.1f}".format(value)
    if value == int(value):
        return "%d" % value
    return "%.4g" % value


def _cell(output, column, value, ids):
    """Table cell text; element ids become links that select the element."""
    is_id_column = column == "id" or column.endswith("_id")
    if is_id_column and isinstance(value, SCALARS) and value in ids:
        return output.linkify(ids[value])
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = "yes" if value else "no"
    elif isinstance(value, float):
        text = _fmt(value)
    elif isinstance(value, (list, tuple)):
        text = ", ".join(
            _fmt(v) if isinstance(v, float) else "%s" % (v,) for v in value
        )
    elif isinstance(value, dict):
        text = json.dumps(value, sort_keys=True)
    else:
        text = "%s" % (value,)
    return text.replace("|", "\\|")


def _scalar_columns(rows):
    columns = []
    for row in rows:
        for key, value in row.items():
            if isinstance(value, SCALARS + (list,)) and key not in columns:
                columns.append(key)
    return columns


def _table(output, rows, columns, ids):
    if not rows or not columns:
        output.print_md("_(none)_")
        return
    data = [
        [_cell(output, column, row.get(column), ids) for column in columns]
        for row in rows
    ]
    output.print_table(table_data=data, columns=columns)


def render(output, value, ids, level=2):
    """Render an analysis result: scalars as a list, collections as tables."""
    if isinstance(value, SCALARS):
        output.print_md(_cell(output, "", value, ids))
        return
    if isinstance(value, list):
        if not value:
            output.print_md("_(none)_")
        elif all(isinstance(item, dict) for item in value):
            _table(output, value, _scalar_columns(value), ids)
        else:
            output.print_md(
                "\n".join("- " + _cell(output, "", item, ids) for item in value)
            )
        return
    if not value:
        output.print_md("_(none)_")
        return

    scalars = [(k, v) for k, v in value.items() if isinstance(v, SCALARS)]
    if scalars:
        output.print_md(
            "\n".join(
                "- **%s**: %s" % (k, _cell(output, k, v, ids)) for k, v in scalars
            )
        )
    for key, item in value.items():
        if isinstance(item, SCALARS):
            continue
        output.print_md("#" * min(level, 4) + " " + key)
        if (
            isinstance(item, dict)
            and item
            and all(isinstance(v, dict) for v in item.values())
        ):
            rows = []
            for name, inner in item.items():
                row = {"name": name}
                row.update(inner)
                rows.append(row)
            columns = _scalar_columns(rows)
            if len(columns) > 1:
                _table(output, rows, columns, ids)
            else:  # nested dict of dicts (e.g. types per category)
                for name, inner in item.items():
                    output.print_md("#" * min(level + 1, 4) + " " + name)
                    render(output, inner, ids, level + 2)
        elif isinstance(item, dict) and all(
            isinstance(v, SCALARS) for v in item.values()
        ):
            rows = [{"name": k, "value": v} for k, v in item.items()]
            _table(output, rows, ["name", "value"], ids)
        else:
            render(output, item, ids, level + 1)


output = script.get_output()
bridge = RevitPyBridge()

try:
    names = bridge.list_analyses()
except BridgeError as exc:
    forms.alert(str(exc), title=TITLE, exitscript=True)

if not names:
    forms.alert(
        "The RevitPy Live Server is running but has no analyses registered.\n\n"
        "Install revitpy-bridge-analyses into RevitPy's Python and restart the "
        "Live Server.",
        title=TITLE,
        exitscript=True,
    )

elements = list(revit.get_selection().elements)
if not elements:
    forms.alert("Select the elements to analyze first.", title=TITLE, exitscript=True)

name = forms.SelectFromList.show(
    names, title="RevitPy analysis", button_name="Run", multiselect=False
)
if not name:
    script.exit()

payload = serialize_elements(elements)
ids = {}
for element in elements:
    ids[element_id_value(element.Id)] = element.Id

try:
    result = bridge.analyze(name, payload)
except AnalysisFailed as exc:
    output.print_md("## Analysis '%s' failed" % name)
    output.print_code(exc.details)
    script.exit()
except BridgeError as exc:
    forms.alert(str(exc), title=TITLE, exitscript=True)

output.set_title("RevitPy: %s" % name)
output.print_md("# %s" % name)
output.print_md(
    "%d element(s) analyzed. Lengths from Revit are in feet." % len(payload)
)
render(output, result, ids)
