"""Tests for the P2/P3 pure helpers: active-learning ranking (#32) and the
adaptive data-sufficiency target (#35). No ML deps."""

from __future__ import annotations

from talkteach.director import adaptive_target, probe_language, rank_clips

# --- adaptive target (#35) ----------------------------------------------------


def test_adaptive_target_easier_for_whisper_languages():
    en = probe_language("en")  # Whisper-supported
    xx = probe_language("zz")  # outside Whisper's set
    assert adaptive_target(en) < adaptive_target(xx)
    assert adaptive_target(en) >= 20.0  # never below the floor


def test_adaptive_target_autodetect_is_easy():
    auto = probe_language(None)  # "let it figure out"
    assert adaptive_target(auto) == adaptive_target(probe_language("en"))


# --- active learning (#32) ----------------------------------------------------


def test_rank_clips_prioritises_unlabelled_then_issues():
    clips = [
        {"id": 1, "transcript": "all good here", "issues": [], "duration_s": 3.0},
        {"id": 2, "transcript": "", "issues": [], "duration_s": 3.0},  # no words
        {"id": 3, "transcript": "ok", "issues": ["too quiet"], "duration_s": 3.0},
    ]
    ranked = rank_clips(clips)
    assert ranked[0].clip_id == 2  # unlabelled is most worth fixing
    assert ranked[1].clip_id == 3  # then the flagged one
    assert ranked[-1].clip_id == 1  # the clean, labelled clip is last


def test_rank_clips_top_k_and_confidence():
    clips = [
        {"id": 1, "transcript": "x", "confidence": 0.95, "duration_s": 3.0},
        {"id": 2, "transcript": "x", "confidence": 0.10, "duration_s": 3.0},
    ]
    top = rank_clips(clips, top_k=1)
    assert len(top) == 1 and top[0].clip_id == 2  # least confident first


def test_rank_clips_empty():
    assert rank_clips([]) == []
