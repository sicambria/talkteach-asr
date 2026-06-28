-- TalkTeach project database schema.
--
-- One SQLite DB per project folder. A "project" is one thing the child is
-- teaching the computer (a voice / a language). It owns recorded audio clips
-- (with transcripts and quality flags) and training runs.
--
-- This script is applied idempotently on every ProjectDB.open() via
-- executescript(), so every statement is guarded with IF NOT EXISTS.

-- Single-row table describing the project itself. We pin id = 1 so there is
-- only ever one project per database (see init_project()).
CREATE TABLE IF NOT EXISTS project (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    name          TEXT    NOT NULL,
    language_code TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

-- One audio example.
CREATE TABLE IF NOT EXISTS clip (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT    NOT NULL,
    duration_s  REAL    NOT NULL DEFAULT 0.0,
    transcript  TEXT,
    is_good     INTEGER NOT NULL DEFAULT 1 CHECK (is_good IN (0, 1)),
    issues_json TEXT    NOT NULL DEFAULT '[]',
    created_at  TEXT    NOT NULL
);

-- One training run (the director's TrainingPlan, plus lifecycle state).
CREATE TABLE IF NOT EXISTS training_run (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 'interrupted' = was 'running' when the app crashed/closed; reconciled on
    -- startup (roadmap #40) so the UI can offer to resume from the checkpoint.
    status          TEXT    NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'running', 'done', 'failed',
                                              'cancelled', 'interrupted')),
    engine          TEXT    NOT NULL,
    base_checkpoint TEXT    NOT NULL,
    plan_json       TEXT    NOT NULL DEFAULT '{}',
    best_val_wer    REAL,
    checkpoint_path TEXT,
    started_at      TEXT,
    finished_at     TEXT,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clip_is_good     ON clip (is_good);
CREATE INDEX IF NOT EXISTS idx_clip_created_at  ON clip (created_at);
CREATE INDEX IF NOT EXISTS idx_run_status       ON training_run (status);
CREATE INDEX IF NOT EXISTS idx_run_created_at   ON training_run (created_at);
