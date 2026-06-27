"""Tests for the TalkTeach data-persistence layer (stdlib + tmp_path only)."""

from __future__ import annotations

import json

import pytest

from talkteach.data.project import ProjectDB


def test_init_and_get_project(tmp_path):
    db_path = tmp_path / "project.db"
    with ProjectDB.open(db_path) as db:
        assert db.get_project() is None
        pid = db.init_project("Mama's voice", "hu")
        assert pid == 1

        proj = db.get_project()
        assert proj is not None
        assert proj["id"] == 1
        assert proj["name"] == "Mama's voice"
        assert proj["language_code"] == "hu"
        assert proj["created_at"]
        assert proj["updated_at"]

        # init_project on an existing DB updates the single row, not inserts.
        db.init_project("Papa's voice", None)
        proj2 = db.get_project()
        assert proj2["id"] == 1
        assert proj2["name"] == "Papa's voice"
        assert proj2["language_code"] is None


def test_clips_filtering_and_minutes(tmp_path):
    with ProjectDB.open(tmp_path / "p.db") as db:
        db.init_project("v", "en")

        good_id = db.add_clip("a.wav", 60.0, True, [], transcript="hello")
        bad_id = db.add_clip("b.wav", 30.0, False, ["too_loud", "clipping"])

        assert good_id != bad_id

        all_clips = db.list_clips()
        assert len(all_clips) == 2

        good_only = db.list_clips(only_good=True)
        assert len(good_only) == 1
        assert good_only[0]["path"] == "a.wav"
        assert good_only[0]["is_good"] is True
        assert good_only[0]["issues"] == []
        assert good_only[0]["transcript"] == "hello"

        # bad clip parses its issues list back into a Python list.
        bad = next(c for c in all_clips if c["id"] == bad_id)
        assert bad["is_good"] is False
        assert bad["issues"] == ["too_loud", "clipping"]

        # 60s good of 90s total.
        assert db.good_minutes() == pytest.approx(1.0)
        assert db.total_minutes() == pytest.approx(1.5)


def test_empty_minutes(tmp_path):
    with ProjectDB.open(tmp_path / "p.db") as db:
        db.init_project("v", None)
        assert db.good_minutes() == 0.0
        assert db.total_minutes() == 0.0


def test_update_transcript_and_set_clip_good(tmp_path):
    with ProjectDB.open(tmp_path / "p.db") as db:
        db.init_project("v", None)
        cid = db.add_clip("a.wav", 10.0, True, [])

        db.update_transcript(cid, "the quick brown fox")
        clip = db.list_clips()[0]
        assert clip["transcript"] == "the quick brown fox"

        db.set_clip_good(cid, False, ["noisy"])
        clip = db.list_clips()[0]
        assert clip["is_good"] is False
        assert clip["issues"] == ["noisy"]

        db.set_clip_good(cid, True, [])
        clip = db.list_clips()[0]
        assert clip["is_good"] is True
        assert clip["issues"] == []


def test_runs_lifecycle_and_update_whitelist(tmp_path):
    with ProjectDB.open(tmp_path / "p.db") as db:
        db.init_project("v", None)

        plan = json.dumps({"lr": 1e-4, "epochs": 3})
        run_id = db.create_run("whisper", "base.en", plan)

        run = db.get_run(run_id)
        assert run["status"] == "pending"
        assert run["engine"] == "whisper"
        assert run["base_checkpoint"] == "base.en"
        assert run["plan"] == {"lr": 1e-4, "epochs": 3}
        assert run["best_val_wer"] is None

        db.update_run(
            run_id,
            status="done",
            best_val_wer=0.12,
            checkpoint_path="ckpt/best.pt",
            started_at="2026-06-28T00:00:00+00:00",
            finished_at="2026-06-28T01:00:00+00:00",
        )
        run = db.get_run(run_id)
        assert run["status"] == "done"
        assert run["best_val_wer"] == pytest.approx(0.12)
        assert run["checkpoint_path"] == "ckpt/best.pt"

        assert len(db.list_runs()) == 1

        # Unknown column is rejected (SQL-injection guard).
        with pytest.raises(ValueError):
            db.update_run(run_id, id=999)
        with pytest.raises(ValueError):
            db.update_run(run_id, engine="evil")

        # No-op update is harmless.
        db.update_run(run_id)

    assert db.get_run is not None  # sanity: object still referenceable


def test_get_missing_run(tmp_path):
    with ProjectDB.open(tmp_path / "p.db") as db:
        db.init_project("v", None)
        assert db.get_run(12345) is None


def test_persistence_across_reopen(tmp_path):
    db_path = tmp_path / "persist.db"

    with ProjectDB.open(db_path) as db:
        db.init_project("durable", "de")
        db.add_clip("a.wav", 120.0, True, [], transcript="bleibt")
        db.create_run("whisper", "small", json.dumps({"k": 1}))

    # Reopen the same path: data must still be there (WAL durability).
    with ProjectDB.open(db_path) as db:
        proj = db.get_project()
        assert proj["name"] == "durable"
        assert proj["language_code"] == "de"

        clips = db.list_clips()
        assert len(clips) == 1
        assert clips[0]["transcript"] == "bleibt"
        assert db.total_minutes() == pytest.approx(2.0)

        runs = db.list_runs()
        assert len(runs) == 1
        assert runs[0]["plan"] == {"k": 1}
