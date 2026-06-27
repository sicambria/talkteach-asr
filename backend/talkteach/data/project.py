"""SQLite-backed persistence for a single TalkTeach project.

One ``ProjectDB`` wraps one SQLite database file living inside a project
folder. WAL journaling + autosave means a child's corrections are never lost,
even on an abrupt power cut.

Stdlib only.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

# Columns that ``update_run`` is permitted to touch. Anything else is rejected
# with ValueError, because column names cannot be parameterised and would
# otherwise be an SQL-injection vector.
_RUN_UPDATABLE_COLUMNS: frozenset[str] = frozenset(
    {"status", "best_val_wer", "checkpoint_path", "started_at", "finished_at"}
)


def _utcnow() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ProjectDB:
    """A thin, testable wrapper around one project's SQLite database."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def open(cls, db_path: str | Path) -> ProjectDB:
        """Open (or create) the project DB at ``db_path``.

        Enables WAL journaling and foreign keys, then applies ``schema.sql``
        idempotently so re-opening an existing DB is safe.
        """
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        conn.executescript(schema)
        conn.commit()
        return cls(conn)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ProjectDB:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- project -----------------------------------------------------------

    def init_project(
        self,
        name: str,
        language_code: str | None,
        *,
        created_at: str | None = None,
    ) -> int:
        """Create or update the single project row. Returns its id (always 1)."""
        now = created_at or _utcnow()
        existing = self.get_project()
        if existing is None:
            self._conn.execute(
                "INSERT INTO project (id, name, language_code, created_at, updated_at) "
                "VALUES (1, ?, ?, ?, ?)",
                (name, language_code, now, now),
            )
        else:
            self._conn.execute(
                "UPDATE project SET name = ?, language_code = ?, updated_at = ? WHERE id = 1",
                (name, language_code, now),
            )
        self._conn.commit()
        return 1

    def get_project(self) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM project WHERE id = 1").fetchone()
        return dict(row) if row is not None else None

    # -- clips -------------------------------------------------------------

    def add_clip(
        self,
        path: str,
        duration_s: float,
        is_good: bool,
        issues: list[str],
        transcript: str | None = None,
        *,
        created_at: str | None = None,
    ) -> int:
        """Insert one audio clip. Returns its new id."""
        now = created_at or _utcnow()
        cur = self._conn.execute(
            "INSERT INTO clip (path, duration_s, transcript, is_good, issues_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                path,
                float(duration_s),
                transcript,
                1 if is_good else 0,
                json.dumps(list(issues)),
                now,
            ),
        )
        self._conn.commit()
        assert cur.lastrowid is not None  # INSERT always sets a rowid
        return int(cur.lastrowid)

    def update_transcript(self, clip_id: int, transcript: str) -> None:
        self._conn.execute("UPDATE clip SET transcript = ? WHERE id = ?", (transcript, clip_id))
        self._conn.commit()

    def set_clip_good(self, clip_id: int, is_good: bool, issues: list[str]) -> None:
        self._conn.execute(
            "UPDATE clip SET is_good = ?, issues_json = ? WHERE id = ?",
            (1 if is_good else 0, json.dumps(list(issues)), clip_id),
        )
        self._conn.commit()

    def list_clips(self, only_good: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM clip"
        if only_good:
            sql += " WHERE is_good = 1"
        sql += " ORDER BY id"
        rows = self._conn.execute(sql).fetchall()
        return [self._clip_to_dict(r) for r in rows]

    def good_minutes(self) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(duration_s), 0.0) AS total FROM clip WHERE is_good = 1"
        ).fetchone()
        return float(row["total"]) / 60.0

    def total_minutes(self) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(duration_s), 0.0) AS total FROM clip"
        ).fetchone()
        return float(row["total"]) / 60.0

    # -- training runs -----------------------------------------------------

    def create_run(
        self,
        engine: str,
        base_checkpoint: str,
        plan_json: str,
        *,
        created_at: str | None = None,
    ) -> int:
        """Create a 'pending' training run. Returns its new id."""
        now = created_at or _utcnow()
        cur = self._conn.execute(
            "INSERT INTO training_run (status, engine, base_checkpoint, plan_json, created_at) "
            "VALUES ('pending', ?, ?, ?, ?)",
            (engine, base_checkpoint, plan_json, now),
        )
        self._conn.commit()
        assert cur.lastrowid is not None  # INSERT always sets a rowid
        return int(cur.lastrowid)

    def update_run(self, run_id: int, **fields: Any) -> None:
        """Update whitelisted columns of a training run.

        Raises ValueError if any field is not an updatable column, to avoid
        SQL injection through column names.
        """
        if not fields:
            return
        bad = set(fields) - _RUN_UPDATABLE_COLUMNS
        if bad:
            raise ValueError(
                f"Cannot update column(s) {sorted(bad)}; allowed: {sorted(_RUN_UPDATABLE_COLUMNS)}"
            )
        assignments = ", ".join(f"{col} = ?" for col in fields)
        params = list(fields.values())
        params.append(run_id)
        self._conn.execute(f"UPDATE training_run SET {assignments} WHERE id = ?", params)
        self._conn.commit()

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM training_run WHERE id = ?", (run_id,)).fetchone()
        return self._run_to_dict(row) if row is not None else None

    def list_runs(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM training_run ORDER BY id").fetchall()
        return [self._run_to_dict(r) for r in rows]

    # -- row conversion ----------------------------------------------------

    @staticmethod
    def _clip_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["is_good"] = bool(d["is_good"])
        d["issues"] = json.loads(d.pop("issues_json") or "[]")
        return d

    @staticmethod
    def _run_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        raw = d.pop("plan_json", None)
        d["plan"] = json.loads(raw) if raw else None
        return d
