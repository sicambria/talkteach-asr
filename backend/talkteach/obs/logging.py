"""Structured (JSON-lines) local logging + help-bundle export (roadmap #41).

Stdlib only. JSON lines are greppable and machine-readable for support without
pulling in a logging framework. Everything stays under the project dir; nothing
is sent anywhere (project/docs/DECISIONS.md D-008).
"""

from __future__ import annotations

import datetime
import io
import json
import logging
import os
import platform
import sys
import zipfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False

# Environment variables that may carry secrets/PII — redacted from help bundles.
_REDACT_HINTS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "AUTH", "HF_TOKEN")


class _JsonFormatter(logging.Formatter):
    """Render a log record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.datetime.fromtimestamp(
                record.created, datetime.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def log_path(project_dir: str | Path) -> Path:
    return Path(project_dir) / "logs" / "talkteach.jsonl"


def configure_logging(project_dir: str | Path, *, level: int = logging.INFO) -> None:
    """Attach a rotating JSON file handler (+ console) to the ``talkteach`` logger.

    Idempotent: safe to call on every server start.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    path = log_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("talkteach")
    root.setLevel(level)
    file_handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(_JsonFormatter())
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(file_handler)
    root.addHandler(console)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"talkteach.{name}")


def _redacted_env() -> dict[str, str]:
    """The TALKTEACH_* env, with anything secret-looking redacted."""
    out = {}
    for key, value in os.environ.items():
        if not key.startswith("TALKTEACH_"):
            continue
        out[key] = "<redacted>" if any(h in key.upper() for h in _REDACT_HINTS) else value
    return out


def _versions() -> dict[str, str | bool]:
    """A few facts that help debugging, no PII."""
    import importlib.util

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": importlib.util.find_spec("torch") is not None,
        "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
        "ffmpeg_on_path": bool(__import__("shutil").which("ffmpeg")),
    }


def export_help_bundle(project_dir: str | Path, out_path: str | Path | None = None) -> str:
    """Zip logs + a redacted environment/versions report into a help bundle (#41).

    Returns the path to the zip. Nothing leaves the machine — the user shares it
    deliberately. PII-bearing env vars are redacted; only log files and a small
    system report are included.
    """
    project = Path(project_dir)
    out = Path(out_path) if out_path else project / "help_bundle.zip"
    report = {
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "versions": _versions(),
        "env": _redacted_env(),
    }
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.json", json.dumps(report, indent=2))
        log_dir = project / "logs"
        if log_dir.is_dir():
            for f in sorted(log_dir.glob("talkteach.jsonl*")):
                zf.write(f, arcname=f"logs/{f.name}")
    return str(out)


def help_bundle_bytes(project_dir: str | Path) -> bytes:
    """In-memory help bundle (for serving as an HTTP download)."""
    buf = io.BytesIO()
    report = {
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "versions": _versions(),
        "env": _redacted_env(),
    }
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report.json", json.dumps(report, indent=2))
        log_dir = Path(project_dir) / "logs"
        if log_dir.is_dir():
            for f in sorted(log_dir.glob("talkteach.jsonl*")):
                zf.write(f, arcname=f"logs/{f.name}")
    return buf.getvalue()
