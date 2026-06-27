#!/usr/bin/env python3
"""Freeze the Python backend into a Tauri **sidecar** binary (roadmap #15/#16).

Tauri's `externalBin` expects an executable named with the Rust target triple,
e.g. `binaries/talkteach-backend-x86_64-unknown-linux-gnu`. This script uses
PyInstaller to produce that single-file binary so the desktop app can spawn the
backend with zero install on the user's machine (DECISIONS.md D-001 Tier C: the
script is real; running it needs the [ml] toolchain + PyInstaller on each target
OS, so it's part of the release pipeline, not the sandbox).

Usage:
    uv pip install -e 'backend[ml,export]' pyinstaller
    python scripts/build_sidecar.py            # detects the host triple

The desktop build (`npm run tauri build`) then bundles the binary automatically.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENTRY = REPO / "scripts" / "_sidecar_entry.py"
OUT_DIR = REPO / "src-tauri" / "binaries"


def host_target_triple() -> str:
    """Best-effort Rust target triple for the host (override with --triple)."""
    out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=False)
    for line in out.stdout.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("Could not detect the host target triple; pass --triple.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--triple", help="Rust target triple (default: host)")
    args = ap.parse_args()
    triple = args.triple or host_target_triple()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = f"talkteach-backend-{triple}"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(OUT_DIR),
        "--collect-all",
        "talkteach",
        str(ENTRY),
    ]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
