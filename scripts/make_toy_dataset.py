#!/usr/bin/env python3
"""CLI to write the first-run toy dataset to a folder (roadmap #22).

    python scripts/make_toy_dataset.py [dest_dir] [--lang en] [--clips 8]

Used by the self-test flow (`/api/selftest`) and handy for manual end-to-end
checks. Pure stdlib + numpy.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from talkteach.selftest import make_toy_dataset  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dest", nargs="?", default="./toy_dataset", help="output folder")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--clips", type=int, default=8)
    args = ap.parse_args()
    manifest = make_toy_dataset(args.dest, language=args.lang, clips=args.clips)
    print(f"Wrote {len(manifest)} clips to {args.dest}")
    for m in manifest:
        print(f"  {Path(m['path']).name}  ←  {m['text']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
