"""Batch A parity tests (no ML deps): subtitles (#48), long-form chunking (#49),
decoding controls (#50), punctuation restoration (#51). All pure — run in the
dep-light default job.
"""

from __future__ import annotations

import pytest

from talkteach.transcript import (
    DecodeOptions,
    merge_segments,
    plan_chunks,
    restore,
    segments_to_srt,
    segments_to_text,
    segments_to_vtt,
)
from talkteach.transcript.longform import offset_segments

# --- #48 subtitles ------------------------------------------------------------


def _segs():
    return [
        {"start": 0.0, "end": 1.5, "text": "hello there"},
        {"start": 1.5, "end": 3.25, "text": "general kenobi"},
    ]


def test_srt_format_and_numbering():
    srt = segments_to_srt(_segs())
    lines = srt.splitlines()
    assert lines[0] == "1"
    assert lines[1] == "00:00:00,000 --> 00:00:01,500"
    assert lines[2] == "hello there"
    assert lines[3] == ""
    assert lines[4] == "2"
    assert lines[5] == "00:00:01,500 --> 00:00:03,250"  # comma millis, 250 ms


def test_vtt_header_and_dot_millis():
    vtt = segments_to_vtt(_segs())
    assert vtt.startswith("WEBVTT\n")
    assert "00:00:01.500 --> 00:00:03.250" in vtt  # dot, not comma


def test_subtitles_skip_empty_and_handle_hours():
    segs = [
        {"start": 0.0, "end": 1.0, "text": "   "},  # dropped
        {"start": 3661.0, "end": 3662.0, "text": "over an hour"},
    ]
    srt = segments_to_srt(segs)
    assert srt.splitlines()[0] == "1"  # numbering starts at the first non-empty cue
    assert "01:01:01,000" in srt


def test_segments_to_text_plain_and_timestamped():
    assert segments_to_text(_segs()) == "hello there\ngeneral kenobi\n"
    ts = segments_to_text(_segs(), timestamps=True)
    assert ts.startswith("[00:00:00] hello there")


def test_empty_segments_are_safe():
    assert segments_to_srt([]) == ""
    assert segments_to_vtt([]) == "WEBVTT\n"


# --- #49 long-form chunking ---------------------------------------------------


def test_plan_chunks_short_file_single_window():
    chunks = plan_chunks(5.0, window_s=30.0, overlap_s=1.0)
    assert len(chunks) == 1
    assert (chunks[0].start, chunks[0].end) == (0.0, 5.0)


def test_plan_chunks_tiles_with_overlap():
    chunks = plan_chunks(70.0, window_s=30.0, overlap_s=1.0)
    # step = 29 s: [0,30], [29,59], [58,70]
    assert [(c.start, c.end) for c in chunks] == [(0.0, 30.0), (29.0, 59.0), (58.0, 70.0)]
    # consecutive windows overlap by exactly overlap_s
    assert chunks[0].end - chunks[1].start == pytest.approx(1.0)


def test_plan_chunks_validates():
    assert plan_chunks(0.0) == []
    with pytest.raises(ValueError):
        plan_chunks(10.0, window_s=0.0)
    with pytest.raises(ValueError):
        plan_chunks(10.0, window_s=5.0, overlap_s=5.0)


def test_offset_and_merge_dedup_overlap():
    # Same word decoded in two overlapping windows near the boundary → kept once.
    chunk_a = [{"start": 28.5, "end": 29.5, "text": "boundary"}]
    chunk_b = offset_segments([{"start": 0.0, "end": 1.0, "text": "boundary"}], 29.0)
    merged = merge_segments([chunk_a, chunk_b], overlap_s=1.0)
    assert len(merged) == 1
    assert merged[0]["text"] == "boundary"


def test_merge_keeps_distinct_and_sorts():
    merged = merge_segments(
        [
            [{"start": 2.0, "end": 3.0, "text": "second"}],
            [{"start": 0.0, "end": 1.0, "text": "first"}],
        ]
    )
    assert [s["text"] for s in merged] == ["first", "second"]


# --- #50 decoding controls ----------------------------------------------------


def test_decode_options_defaults_reproduce_stock():
    opt = DecodeOptions()
    kw = opt.to_faster_whisper_kwargs()
    assert kw["beam_size"] == 5
    assert kw["temperature"] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]  # fallback ladder
    assert "hotwords" not in kw  # absent by default → works on older backends
    assert "initial_prompt" not in kw


def test_decode_options_hotwords_and_prompt():
    opt = DecodeOptions(
        beam_size=1, initial_prompt="a story", hotwords=("dinosaur", "  "), temperature=(0.0,)
    )
    kw = opt.to_faster_whisper_kwargs()
    assert kw["beam_size"] == 1
    assert kw["initial_prompt"] == "a story"
    assert kw["hotwords"] == "dinosaur"  # blank hotword stripped
    assert kw["temperature"] == 0.0  # single value → scalar (fallback disabled)


def test_decode_options_validation():
    with pytest.raises(ValueError):
        DecodeOptions(beam_size=0)
    with pytest.raises(ValueError):
        DecodeOptions(temperature=())
    with pytest.raises(ValueError):
        DecodeOptions(temperature=(-0.1,))


# --- #51 punctuation restoration ----------------------------------------------


def test_restore_capitalizes_and_terminates():
    assert restore("hello world") == "Hello world."


def test_restore_multi_sentence_and_pronoun_i():
    assert restore("i went home. then i slept") == "I went home. Then I slept."


def test_restore_preserves_existing_terminal():
    assert restore("are you there?") == "Are you there?"


def test_restore_empty():
    assert restore("   ") == ""
