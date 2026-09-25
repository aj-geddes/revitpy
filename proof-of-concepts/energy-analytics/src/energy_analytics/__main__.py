"""``python -m energy_analytics``: run against the demo model and print a report."""

from __future__ import annotations

import argparse
from pathlib import Path

from poc_common import quiet_logging

from . import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m energy_analytics")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--wall-u-max", type=float, default=1.0)
    parser.add_argument("--window-u-max", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--html", type=Path, help="write a Plotly chart here")
    parser.add_argument("--no-write", action="store_true", help="skip write-back")
    args = parser.parse_args(argv)

    quiet_logging()
    report = run(
        days=args.days,
        wall_u_max=args.wall_u_max,
        window_u_max=args.window_u_max,
        seed=args.seed,
        write=not args.no_write,
        html=args.html,
    )
    print(report.to_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
