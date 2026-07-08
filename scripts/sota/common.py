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


def write_domain_result(result: Any, json_path: Path | None) -> None:
    """Serialize a harness SOTAResult uniformly (domain_name, num_samples, notes).

    Thin-wrapper validation scripts share this so every domain's JSON carries the
    same fields — including ``num_samples`` and error ``notes`` that ad-hoc payloads
    used to drop, which then rendered as "Samples: 0" / blank notes on the board.
    """
    write_result(
        {
            "domain_id": result.domain_id,
            "domain_name": result.domain_name,
            "score_0_1000": result.score_0_1000,
            "band": result.band,
            "metrics": result.metrics,
            "confidence_95": {k: list(v) for k, v in result.confidence_95.items()},
            "baseline_ref": result.baseline_ref,
            "sota_ref": result.sota_ref,
            "num_samples": result.num_samples,
            "engine_used": result.engine_used,
            "notes": result.notes,
        },
        json_path,
    )


def write_abstention(domain: Any, requires: str, json_path: Path | None) -> None:
    """Emit an honest abstention for a domain this harness cannot self-measure.

    Score 0 (band ``human_needed``) so the result is counted as *unmeasured* by
    ``aggregate_headline`` (measured == score > 0) and can never contribute a
    fabricated grade to the scoreboard. Carries no invented metric values —
    only a status describing what real measurement would require.
    """
    write_result(
        {
            "domain_id": domain.id,
            "score_0_1000": 0,
            "band": "human_needed",
            "metrics": {"status": "not measured", "requires": requires},
            "confidence_95": {},
            "baseline_ref": "",
            "sota_ref": domain.sota_1000_reference,
        },
        json_path,
    )
