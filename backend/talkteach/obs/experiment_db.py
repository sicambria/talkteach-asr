"""SQLite-backed experiment registry — track, query, and compare runs.

Extends obs/experiment.py (per-run metrics.jsonl) with a cross-run database.
Each experiment is a row with config hash, metrics, git commit, and timestamp.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(
    os.environ.get(
        "TALKTEACH_EXPERIMENT_DB", os.path.expanduser("~/.cache/talkteach/experiments.db")
    )
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL UNIQUE,
    config_hash TEXT NOT NULL,
    config      TEXT NOT NULL,          -- JSON of hyperparameters
    git_commit  TEXT NOT NULL,
    engine      TEXT NOT NULL,
    base_model  TEXT NOT NULL,
    dataset     TEXT NOT NULL,
    domain_id   TEXT,                   -- SOTA domain if applicable
    wer         REAL,
    cer         REAL,
    best_wer    REAL,
    best_cer    REAL,
    train_s     REAL,
    epochs      INTEGER,
    status      TEXT NOT NULL DEFAULT 'running',  -- running | completed | failed | cancelled
    notes       TEXT,
    started_at  TEXT NOT NULL,
    completed_at TEXT,
    tags        TEXT                    -- JSON array of tags for filtering
);

CREATE INDEX IF NOT EXISTS idx_experiments_run_id ON experiments(run_id);
CREATE INDEX IF NOT EXISTS idx_experiments_engine ON experiments(engine);
CREATE INDEX IF NOT EXISTS idx_experiments_wer ON experiments(wer);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiments_tags ON experiments(tags);
"""


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a connection to the experiment database (creates it if needed)."""
    db_path = db_path or DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def hash_config(config: dict[str, Any]) -> str:
    """Deterministic hash of a config dict for deduplication."""
    serialized = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def get_git_commit() -> str:
    """Current git HEAD short SHA."""
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def log_experiment(
    run_id: str,
    config: dict[str, Any],
    engine: str = "",
    base_model: str = "",
    dataset: str = "",
    domain_id: str | None = None,
    status: str = "running",
    tags: list[str] | None = None,
    db_path: Path | None = None,
) -> int | None:
    """Create a new experiment row. Returns the row ID."""
    conn = get_db(db_path)
    config_hash = hash_config(config)
    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        """INSERT OR REPLACE INTO experiments
           (run_id, config_hash, config, git_commit, engine, base_model, dataset,
            domain_id, status, started_at, tags)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            config_hash,
            json.dumps(config, sort_keys=True, default=str),
            get_git_commit(),
            engine,
            base_model,
            dataset,
            domain_id,
            status,
            now,
            json.dumps(tags or []),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def update_metrics(
    run_id: str,
    wer: float | None = None,
    cer: float | None = None,
    best_wer: float | None = None,
    best_cer: float | None = None,
    train_s: float | None = None,
    epochs: int | None = None,
    db_path: Path | None = None,
) -> None:
    """Update metrics for an existing experiment."""
    conn = get_db(db_path)
    updates: list[str] = []
    params: list[Any] = []

    for col, val in [
        ("wer", wer),
        ("cer", cer),
        ("best_wer", best_wer),
        ("best_cer", best_cer),
        ("train_s", train_s),
        ("epochs", epochs),
    ]:
        if val is not None:
            updates.append(f"{col} = ?")
            params.append(val)

    if not updates:
        return

    params.append(run_id)
    conn.execute(
        f"UPDATE experiments SET {', '.join(updates)} WHERE run_id = ?",
        params,
    )
    conn.commit()


def mark_completed(
    run_id: str,
    wer: float | None = None,
    cer: float | None = None,
    best_wer: float | None = None,
    best_cer: float | None = None,
    train_s: float | None = None,
    epochs: int | None = None,
    notes: str = "",
    db_path: Path | None = None,
) -> None:
    """Mark an experiment as completed with final metrics."""
    update_metrics(
        run_id,
        wer=wer,
        cer=cer,
        best_wer=best_wer,
        best_cer=best_cer,
        train_s=train_s,
        epochs=epochs,
        db_path=db_path,
    )
    conn = get_db(db_path)
    conn.execute(
        """UPDATE experiments SET status = 'completed', completed_at = ?, notes = ?
           WHERE run_id = ?""",
        (datetime.now(timezone.utc).isoformat(), notes, run_id),
    )
    conn.commit()


def mark_failed(run_id: str, error: str, db_path: Path | None = None) -> None:
    """Mark an experiment as failed."""
    conn = get_db(db_path)
    conn.execute(
        """UPDATE experiments SET status = 'failed', completed_at = ?, notes = ?
           WHERE run_id = ?""",
        (datetime.now(timezone.utc).isoformat(), error, run_id),
    )
    conn.commit()


def query_recent(
    limit: int = 10,
    engine: str | None = None,
    status: str | None = None,
    domain_id: str | None = None,
    tag: str | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Query recent experiments with optional filters."""
    conn = get_db(db_path)
    query = "SELECT * FROM experiments WHERE 1=1"
    params: list[Any] = []

    if engine:
        query += " AND engine = ?"
        params.append(engine)
    if status:
        query += " AND status = ?"
        params.append(status)
    if domain_id:
        query += " AND domain_id = ?"
        params.append(domain_id)
    if tag:
        query += " AND tags LIKE ?"
        params.append(f'%"{tag}"%')

    query += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def best_by_domain(
    domain_id: str,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Get the best experiment result for a given SOTA domain."""
    conn = get_db(db_path)
    row = conn.execute(
        """SELECT * FROM experiments
           WHERE domain_id = ? AND status = 'completed' AND best_wer IS NOT NULL
           ORDER BY best_wer ASC LIMIT 1""",
        (domain_id,),
    ).fetchone()
    return dict(row) if row else None


def compare_runs(
    run_id_a: str,
    run_id_b: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Compare two runs: which is better, and by how much."""
    conn = get_db(db_path)
    a = conn.execute("SELECT * FROM experiments WHERE run_id = ?", (run_id_a,)).fetchone()
    b = conn.execute("SELECT * FROM experiments WHERE run_id = ?", (run_id_b,)).fetchone()

    if not a or not b:
        return {"error": "one or both run_ids not found"}

    a_wer = _safe_wer(a)
    b_wer = _safe_wer(b)

    return {
        "run_a": run_id_a,
        "wer_a": a_wer,
        "run_b": run_id_b,
        "wer_b": b_wer,
        "delta_wer": a_wer - b_wer if a_wer != float("inf") and b_wer != float("inf") else None,
        "winner": run_id_a if a_wer < b_wer else run_id_b,
    }


def _safe_wer(row: sqlite3.Row | dict[str, Any]) -> float:
    """Extract WER from a row, handling None and treating 0.0 as valid."""
    for key in ("best_wer", "wer"):
        v = row[key]
        if v is not None:
            return float(v)
    return float("inf")


def regression_check(
    domain_id: str,
    current_wer: float,
    tolerance: float = 0.01,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Check if current WER is a regression vs. best known for this domain."""
    best = best_by_domain(domain_id, db_path)
    if not best:
        return {"regression": False, "reason": "no prior baseline"}

    prev_best = _safe_wer(best)
    if prev_best == float("inf"):
        return {"regression": False, "reason": "no prior WER"}

    delta = current_wer - prev_best
    return {
        "regression": delta > tolerance,
        "current_wer": current_wer,
        "prior_best": float(prev_best),
        "delta": delta,
        "tolerance": tolerance,
    }


def export_json(
    output_path: Path | None = None, db_path: Path | None = None
) -> list[dict[str, Any]]:
    """Export all experiments as JSON."""
    conn = get_db(db_path)
    rows = conn.execute("SELECT * FROM experiments ORDER BY started_at DESC").fetchall()
    data = [dict(r) for r in rows]
    if output_path:
        output_path.write_text(json.dumps(data, indent=2, default=str))
    return data


def cli_main():
    """CLI entry point: python -m talkteach.obs.experiment_db --recent 10"""
    import argparse

    parser = argparse.ArgumentParser(description="Experiment Registry CLI")
    parser.add_argument("--recent", type=int, default=10, help="Show recent N experiments")
    parser.add_argument("--engine", help="Filter by engine")
    parser.add_argument("--status", help="Filter by status")
    parser.add_argument("--domain", help="Filter by domain_id")
    parser.add_argument("--best", help="Show best for a domain")
    parser.add_argument("--compare", nargs=2, metavar=("RUN_A", "RUN_B"), help="Compare two runs")
    parser.add_argument("--export", type=Path, help="Export to JSON file")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Database path")

    args = parser.parse_args()

    if args.compare:
        result = compare_runs(args.compare[0], args.compare[1], db_path=args.db)
        print(json.dumps(result, indent=2, default=str))
    elif args.export:
        data = export_json(args.export, db_path=args.db)
        print(f"Exported {len(data)} experiments to {args.export}")
    elif args.best:
        best = best_by_domain(args.best, db_path=args.db)
        if best:
            print(json.dumps(best, indent=2, default=str))
        else:
            print(f"No completed experiments for domain {args.best}")
    else:
        rows = query_recent(
            limit=args.recent,
            engine=args.engine,
            status=args.status,
            domain_id=args.domain,
            db_path=args.db,
        )
        if not rows:
            print("No experiments found.")
            return
        print(f"{'RUN_ID':<20} {'WER':>8} {'CER':>8} {'ENGINE':<16} {'STATUS':<10} {'STARTED'}")
        print("-" * 80)
        for r in rows:
            wer_str = f"{r['wer']:.4f}" if r["wer"] else "—"
            cer_str = f"{r['cer']:.4f}" if r["cer"] else "—"
            print(
                f"{r['run_id']:<20} {wer_str:>8} {cer_str:>8} "
                f"{r['engine']:<16} {r['status']:<10} {r['started_at'][:19]}"
            )


if __name__ == "__main__":
    cli_main()
