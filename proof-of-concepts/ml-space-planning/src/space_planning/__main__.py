"""``python -m space_planning``: run against the demo model and print a report."""

from __future__ import annotations

import argparse

from poc_common import quiet_logging

from . import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m space_planning")
    parser.add_argument("--days", type=int, default=28)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-write", action="store_true", help="skip write-back")
    args = parser.parse_args(argv)

    quiet_logging()
    print(run(days=args.days, seed=args.seed, write=not args.no_write).to_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
