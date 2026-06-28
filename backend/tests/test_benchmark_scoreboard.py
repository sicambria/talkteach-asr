"""Pure (no-ML) tests for the benchmark scoreboard + ELO leaderboard.

These build a fabricated ``BenchmarkReport`` with hand-set per-clip WERs, so the
ranking logic is exercised in the fast suite with no model download or training.
"""

from __future__ import annotations

from talkteach.benchmark import (
    BenchmarkReport,
    CellResult,
    compute_elo,
    format_scoreboard,
    report_markdown,
    scoreboard,
)


def _report() -> BenchmarkReport:
    # One TTS condition, two engines on the SAME 4 eval clips. "good" wins 3 of 4
    # clips (lower WER); "bad" wins 1. Ties impossible here.
    good = CellResult(
        tts="piper",
        engine="good",
        status="ok",
        wer=0.15,
        cer=0.05,
        smartness=0.85,
        train_seconds=5.0,
        eval_clips=4,
        per_clip_wer=[0.0, 0.1, 0.2, 0.5],
    )
    bad = CellResult(
        tts="piper",
        engine="bad",
        status="ok",
        wer=0.45,
        cer=0.2,
        smartness=0.55,
        train_seconds=3.0,
        eval_clips=4,
        per_clip_wer=[0.3, 0.4, 0.6, 0.4],  # only beats "good" on the last clip
    )
    return BenchmarkReport(name="t", language="en", train_clips=6, eval_clips=4, cells=[good, bad])


def test_elo_counts_head_to_head_wins():
    stats = compute_elo(_report())
    # 4 clips, one pair → 4 matches. good wins 3, loses 1; bad mirrors.
    assert stats["good"]["wins"] == 3 and stats["good"]["losses"] == 1
    assert stats["bad"]["wins"] == 1 and stats["bad"]["losses"] == 3
    # The better engine earns the higher rating.
    assert stats["good"]["elo"] > stats["bad"]["elo"]


def test_scoreboard_ranks_better_engine_first():
    board = scoreboard(_report())
    assert [r.engine for r in board] == ["good", "bad"]
    top = board[0]
    assert top.engine == "good"
    assert top.win_rate == 0.75  # 3 of 4 decided matches
    assert top.mean_wer == 0.15 and top.cells == 1
    assert board[0].elo >= board[1].elo


def test_scoreboard_handles_single_engine_no_matches():
    solo = CellResult(
        tts="piper",
        engine="only",
        status="ok",
        wer=0.2,
        cer=0.1,
        smartness=0.8,
        train_seconds=1.0,
        eval_clips=2,
        per_clip_wer=[0.1, 0.3],
    )
    rep = BenchmarkReport(name="t", language="en", train_clips=2, eval_clips=2, cells=[solo])
    board = scoreboard(rep)
    assert len(board) == 1
    assert board[0].elo == 1000  # no opponents → stays at base
    assert board[0].win_rate is None


def test_format_and_markdown_mention_engines():
    rep = _report()
    text = format_scoreboard(rep)
    assert "good" in text and "bad" in text and "ELO" in text
    md = report_markdown(rep, generated_at="2026-06-28 12:00:00 UTC")
    assert "# TTS × ASR benchmark report" in md
    assert "## Scoreboard (ranked by ELO)" in md
    assert "good" in md and "2026-06-28" in md
