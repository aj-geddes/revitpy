"""Every script in ``examples/`` must run standalone (against the demo model)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
EXAMPLES = sorted(EXAMPLES_DIR.glob("*.py"))


def test_examples_exist() -> None:
    assert EXAMPLES, f"no example scripts found in {EXAMPLES_DIR}"


@pytest.mark.parametrize("script", EXAMPLES, ids=[p.name for p in EXAMPLES])
def test_example_runs(script: Path, tmp_path: Path) -> None:
    args = [sys.executable, str(script)]
    if script.name == "room_schedule_export.py":
        args += ["--output", str(tmp_path / "out")]

    result = subprocess.run(  # noqa: S603 - fixed interpreter and repo script
        args,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, (
        f"{script.name} exited with {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert result.stdout.strip(), f"{script.name} printed nothing"
    if script.name == "room_schedule_export.py":
        assert (tmp_path / "out" / "room_schedule.csv").is_file()
        assert (tmp_path / "out" / "room_schedule.json").is_file()
