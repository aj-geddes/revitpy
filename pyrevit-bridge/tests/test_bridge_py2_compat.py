"""The pyRevit-side files must run on IronPython 2.7 as well as CPython 3."""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from bridge_support import EXTENSION_DIR

PY2_FILES = sorted(EXTENSION_DIR.rglob("*.py"))


def _vermin() -> str | None:
    beside_python = Path(sys.executable).with_name("vermin")
    if beside_python.exists():
        return str(beside_python)
    return shutil.which("vermin")


def test_files_found() -> None:
    names = {path.name for path in PY2_FILES}
    assert "revitpy_bridge.py" in names
    assert len([p for p in PY2_FILES if p.name == "script.py"]) == 2


@pytest.mark.parametrize(
    "path", PY2_FILES, ids=[str(p.relative_to(EXTENSION_DIR)) for p in PY2_FILES]
)
def test_python27_compatible(path: Path) -> None:
    vermin = _vermin()
    if vermin is None:
        pytest.skip("vermin is not installed (pip install vermin)")
    result = subprocess.run(
        [vermin, "--no-tips", "--violations", "-t=2.7-", "-t=3-", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "path", PY2_FILES, ids=[str(p.relative_to(EXTENSION_DIR)) for p in PY2_FILES]
)
def test_no_python3_only_syntax(path: Path) -> None:
    """Belt and braces for what vermin reports only as a minimum version."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        assert not isinstance(node, ast.JoinedStr), f"f-string at line {node.lineno}"
        assert not isinstance(
            node, ast.AsyncFunctionDef | ast.Await | ast.Nonlocal | ast.AnnAssign
        ), f"Python 3 only syntax at line {node.lineno}"
        if isinstance(node, ast.FunctionDef):
            assert node.returns is None, f"return annotation at line {node.lineno}"
            arguments = node.args
            assert not arguments.kwonlyargs, f"keyword-only args at {node.lineno}"
            for arg in arguments.args + arguments.posonlyargs:
                assert arg.annotation is None, f"annotation at line {node.lineno}"
