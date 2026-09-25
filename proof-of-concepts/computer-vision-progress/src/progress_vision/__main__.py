"""``python -m progress_vision``: detect facade progress on the demo model."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from poc_common import quiet_logging

from . import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m progress_vision")
    parser.add_argument(
        "--image", type=Path, help="rectified facade image as a 2-D uint8 .npy file"
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-write", action="store_true", help="skip write-back")
    args = parser.parse_args(argv)

    quiet_logging()
    image = np.load(args.image) if args.image else None
    print(run(image=image, seed=args.seed, write=not args.no_write).to_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
