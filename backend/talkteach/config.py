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

# --- Upload safety (security #7/#9) -------------------------------------------
# Reject oversized/empty uploads early, and never trust a client-supplied
# filename as a path component (path-traversal). See project/docs/DECISIONS.md D-004.
MAX_UPLOAD_BYTES = int(os.environ.get("TALKTEACH_MAX_UPLOAD_MB", "100")) * 1024 * 1024

# Extensions we recognise as audio. A client name is used ONLY to recover a
# validated extension for the *generated* storage name — never as a path.
ALLOWED_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {"wav", "webm", "weba", "ogg", "oga", "opus", "mp3", "m4a", "mp4", "flac", "aac"}
)
# Content-type prefixes we accept. Browser MediaRecorder blobs are audio/* (and
# occasionally video/webm for an audio-only webm container), so both are allowed.
ALLOWED_AUDIO_CONTENT_PREFIXES: tuple[str, ...] = ("audio/", "video/webm")


def ensure_dirs() -> None:
    DEFAULT_PROJECT_DIR.mkdir(parents=True, exist_ok=True)
