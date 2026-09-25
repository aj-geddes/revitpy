"""``python -m structural_analysis``: check the demo model's frame and print a report."""

from __future__ import annotations

import argparse

from poc_common import quiet_logging

from . import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m structural_analysis")
    parser.add_argument("--dead-kpa", type=float, default=4.0)
    parser.add_argument("--live-kpa", type=float, default=2.5)
    parser.add_argument("--no-write", action="store_true", help="skip write-back")
    args = parser.parse_args(argv)

    quiet_logging()
    report = run(
        dead_kpa=args.dead_kpa, live_kpa=args.live_kpa, write=not args.no_write
    )
    print(report.to_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
