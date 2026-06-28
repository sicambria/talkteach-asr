"""Pure (no-ML) tests for the benchmark scoreboard + ELO leaderboard.

These build a fabricated ``BenchmarkReport`` with hand-set per-clip WERs, so the
ranking logic is exercised in the fast suite with no model download or training.
"""

from __future__ import annotations

import json

from talkteach.benchmark import (
    BenchmarkReport,
    CellResult,
    assign_medals,
    compute_elo,
    format_scoreboard,
    head_to_head,
    per_engine_clip_extremes,
    per_engine_conditions,
    report_markdown,
    scoreboard,
    scoreboard_payload,
)

_PROMPTS = ["alpha one", "beta two", "gamma three", "delta four"]


def _report() -> BenchmarkReport:
    # One TTS condition, two engines on the SAME 4 eval clips. "good" wins 3 of 4
    # clips (lower WER); "bad" wins 1. Ties impossible here.
    good = CellResult(
        tts="piper",
        engine="good",
        status="ok",
        voice="en_US-lessac-low",
        wer=0.15,
        cer=0.05,
        smartness=0.85,
        train_seconds=5.0,
        eval_clips=4,
        base_wer=0.40,
        delta_wer=0.25,
        per_clip_wer=[0.0, 0.1, 0.2, 0.5],
    )
    bad = CellResult(
        tts="piper",
        engine="bad",
        status="ok",
        voice="en_US-lessac-low",
        wer=0.45,
        cer=0.2,
        smartness=0.55,
        train_seconds=3.0,
        eval_clips=4,
        base_wer=0.50,
        delta_wer=0.05,
        per_clip_wer=[0.3, 0.4, 0.6, 0.4],  # only beats "good" on the last clip
    )
    return BenchmarkReport(
        name="t",
        language="en",
        train_clips=6,
        eval_clips=4,
        cells=[good, bad],
        eval_prompts=_PROMPTS,
    )


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


# -- medals -------------------------------------------------------------------


def test_medals_gold_then_silver():
    board = scoreboard(_report())
    assert board[0].engine == "good" and board[0].medal == "gold"
    assert board[1].engine == "bad" and board[1].medal == "silver"
    # Only two engines → bronze is never reached.
    assert all(r.medal != "bronze" for r in board)


def test_medals_tie_shares_and_skips():
    # Three engines, two tied at the top ELO → both gold, silver skipped, bronze next.
    rows = [
        _score("a", elo=1200),
        _score("b", elo=1200),
        _score("c", elo=900),
    ]
    assign_medals(rows)
    medals = {r.engine: r.medal for r in rows}
    assert medals == {"a": "gold", "b": "gold", "c": "bronze"}


def test_medals_count_caps_podium():
    rows = [_score("a", elo=1300), _score("b", elo=1200), _score("c", elo=1100)]
    assign_medals(rows, n=1)
    assert [r.medal for r in rows] == ["gold", None, None]


def test_format_scoreboard_shows_medal_emoji():
    assert "🥇" in format_scoreboard(_report())


# -- detail views -------------------------------------------------------------


def test_head_to_head_grid_sums_to_wins():
    grid = head_to_head(_report())
    # "good" beat "bad" on 3 clips; "bad" beat "good" on 1.
    assert grid["good"]["bad"] == 3
    assert grid["bad"]["good"] == 1


def test_clip_extremes_pick_best_and_worst_prompts():
    ex = per_engine_clip_extremes(_report())
    # good's per-clip WERs are [0.0, 0.1, 0.2, 0.5] over _PROMPTS.
    assert ex["good"]["best"]["prompt"] == "alpha one" and ex["good"]["best"]["wer"] == 0.0
    assert ex["good"]["worst"]["prompt"] == "delta four" and ex["good"]["worst"]["wer"] == 0.5
    assert ex["good"]["best"]["tts"] == "piper"


def test_per_engine_conditions_carries_voice_and_delta():
    conds = per_engine_conditions(_report())
    row = conds["good"][0]
    assert row["voice"] == "en_US-lessac-low"
    assert row["delta_wer"] == 0.25


def test_mean_delta_wer_aggregated_on_scoreboard():
    board = scoreboard(_report())
    good = next(r for r in board if r.engine == "good")
    assert good.mean_delta_wer == 0.25


# -- payload + markdown detail sections ---------------------------------------


def test_scoreboard_payload_shape():
    p = scoreboard_payload(_report())
    assert set(p) == {
        "meta",
        "scoreboard",
        "matrix",
        "head_to_head",
        "clip_extremes",
        "per_voice",
        "eval_prompts",
        "eval_prompts_by_lang",
    }
    assert p["scoreboard"][0]["medal"] == "gold"
    assert p["meta"]["eval_clips"] == 4
    assert p["eval_prompts"] == _PROMPTS
    # Must be JSON-serializable (it crosses the HTTP boundary verbatim).
    json.dumps(p)


def test_markdown_has_detail_sections():
    md = report_markdown(_report())
    assert "## Easiest & hardest clip (per engine)" in md
    assert "## Head-to-head (clips won, row vs column)" in md
    assert "## Per-voice breakdown" in md
    assert "Δ vs base" in md and "🥇" in md


def test_multilang_groups_and_uses_each_languages_prompts():
    # Two languages, each with its own eval prompts; the same engine pair runs in both.
    # Head-to-heads must stay within a language, and clip extremes must show the
    # language-correct sentence (never English for a Hungarian cell).
    def cell(engine, lang, wers):
        return CellResult(
            tts="espeak",
            engine=engine,
            status="ok",
            language=lang,
            voice=lang,
            wer=sum(wers) / len(wers),
            cer=0.05,
            per_clip_wer=wers,
        )

    rep = BenchmarkReport(
        name="ml",
        language="en,hu",
        train_clips=2,
        eval_clips=2,
        cells=[
            cell("whisper", "en", [0.0, 0.1]),
            cell("wav2vec2", "en", [0.3, 0.4]),
            cell("whisper", "hu", [0.1, 0.2]),
            cell("wav2vec2", "hu", [0.5, 0.5]),
        ],
        eval_prompts=["the cat", "blue sky"],
        eval_prompts_by_lang={
            "en": ["the cat", "blue sky"],
            "hu": ["a macska", "kék ég"],
        },
    )
    # whisper beats wav2vec2 on all 4 clips (2 en + 2 hu) → 4-0.
    grid = head_to_head(rep)
    assert grid["whisper"]["wav2vec2"] == 4 and grid["wav2vec2"]["whisper"] == 0
    # Hungarian clip extremes show Hungarian text, not the English fallback.
    ex = per_engine_clip_extremes(rep)
    hu_prompts = {"a macska", "kék ég"}
    whisper_hu = [s for c in [ex["whisper"]] for s in (c["best"], c["worst"])]
    assert any(e["prompt"] in hu_prompts for e in whisper_hu)
    # Per-voice rows carry the language.
    conds = per_engine_conditions(rep)
    assert {r["language"] for r in conds["whisper"]} == {"en", "hu"}


def _score(engine: str, *, elo: int):
    """A bare EngineScore for medal-logic tests (only engine+elo matter)."""
    from talkteach.benchmark import EngineScore

    return EngineScore(
        engine=engine,
        elo=elo,
        wins=0,
        losses=0,
        ties=0,
        win_rate=None,
        mean_wer=None,
        mean_cer=None,
        mean_train_seconds=None,
        cells=1,
    )
