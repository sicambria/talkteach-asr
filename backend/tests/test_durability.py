"""Job durability + observability tests (roadmap #40, #41, #17).

These prove that an orphaned 'running' run is reconciled on startup, that
training resumes from the latest checkpoint, and that the help-bundle export is
local + redacted (no secrets leak).
"""

from __future__ import annotations

import os
import tempfile
import zipfile

from talkteach import config
from talkteach.app import _reconcile_interrupted_runs
from talkteach.data.project import ProjectDB
from talkteach.engines._whisper_train import find_latest_checkpoint
from talkteach.obs.logging import export_help_bundle


def test_reconcile_marks_orphaned_running_as_interrupted(tmp_path):
    db = ProjectDB.open(str(tmp_path / "p.db"))
    db.init_project("t", None)
    rid = db.create_run(engine="whisper_lora", base_checkpoint="x", plan_json="{}")
    db.update_run(rid, status="running")  # simulate a crash mid-run

    n = _reconcile_interrupted_runs(db)
    assert n == 1
    assert db.get_run(rid)["status"] == "interrupted"
    db.close()


def test_reconcile_leaves_finished_runs_alone(tmp_path):
    db = ProjectDB.open(str(tmp_path / "p.db"))
    db.init_project("t", None)
    rid = db.create_run(engine="whisper_lora", base_checkpoint="x", plan_json="{}")
    db.update_run(rid, status="done")
    assert _reconcile_interrupted_runs(db) == 0
    assert db.get_run(rid)["status"] == "done"
    db.close()


def test_resume_finds_latest_checkpoint(tmp_path):
    # #17: a closed/crashed run resumes from the newest checkpoint dir.
    for step in (10, 50, 30):
        (tmp_path / f"checkpoint-{step}").mkdir()
    assert find_latest_checkpoint(str(tmp_path)).endswith("checkpoint-50")


def test_help_bundle_is_local_and_redacts_secrets(tmp_path, monkeypatch):
    # A secret-looking env var must be redacted in the exported bundle (#41/D-008).
    monkeypatch.setenv("TALKTEACH_HF_TOKEN", "super-secret-value")
    monkeypatch.setenv("TALKTEACH_PORT", "8756")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "talkteach.jsonl").write_text('{"msg":"hello"}\n', encoding="utf-8")

    out = export_help_bundle(str(tmp_path))
    assert os.path.isfile(out)
    with zipfile.ZipFile(out) as zf:
        report = zf.read("report.json").decode()
        assert "super-secret-value" not in report  # redacted
        assert "<redacted>" in report
        assert "8756" in report  # non-secret env kept
        assert "logs/talkteach.jsonl" in zf.namelist()


def test_clean_default_db_starts_with_no_runs():
    os.environ["TALKTEACH_DATA"] = tempfile.mkdtemp(prefix="talkteach-dur-")
    import importlib

    importlib.reload(config)
    db = ProjectDB.open(config.DEFAULT_DB_PATH)
    assert db.list_runs() == []
    db.close()
