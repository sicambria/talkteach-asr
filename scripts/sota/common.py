"""Shared utilities for SOTA validation scripts.

Each validate_dXX.py script imports from here and from talkteach.sota.
Output schema:
    {domain_id, score_0_1000, band, metrics:{}, confidence_95:{}, timestamp, git_commit}
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SOTA_RESULT_SCHEMA = {
    "domain_id": str,
    "score_0_1000": int,
    "band": str,
    "metrics": dict,
    "confidence_95": dict,
    "baseline_ref": str,
    "sota_ref": str,
    "timestamp": str,
    "git_commit": str,
}


def get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def build_base_parser(domain_id: str, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--baseline-only", action="store_true", help="Measure base (untrained) model only, skip training")
    p.add_argument("--engines", default="whisper-tiny", help="Comma-separated engine filter")
    p.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    p.add_argument("--json", type=Path, help="Output JSON result file")
    p.add_argument("--data-root", type=Path, default=Path(os.environ.get("TALKTEACH_DATA_ROOT", REPO_ROOT / "backend" / ".data")))
    return p


def write_result(result: dict[str, Any], json_path: Path | None) -> None:
    result.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    result.setdefault("git_commit", get_git_commit())
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps(result, indent=2, default=str))
