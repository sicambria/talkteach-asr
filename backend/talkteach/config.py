"""Backend configuration. Local-first, offline by default (see report B.7)."""

from __future__ import annotations

import os
from pathlib import Path

# Where project folders (one SQLite DB + audio each) live. Local-only.
DATA_ROOT = Path(os.environ.get("TALKTEACH_DATA", Path.home() / ".talkteach")).expanduser()

# The single active project DB for this Phase-0 single-project server.
DEFAULT_PROJECT_DIR = DATA_ROOT / "default"
DEFAULT_DB_PATH = DEFAULT_PROJECT_DIR / "project.db"

# Job server bind. The Tauri shell spawns this as a local sidecar.
HOST = os.environ.get("TALKTEACH_HOST", "127.0.0.1")
PORT = int(os.environ.get("TALKTEACH_PORT", "8756"))

# Sufficiency gate target (minutes of *good* audio) before "Teach!" unlocks.
TARGET_GOOD_MINUTES = float(os.environ.get("TALKTEACH_TARGET_MINUTES", "30"))


def ensure_dirs() -> None:
    DEFAULT_PROJECT_DIR.mkdir(parents=True, exist_ok=True)
