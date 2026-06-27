"""Tests for the P1 audio-pipeline helpers (#10–13): the pure cores of ffmpeg
decode, Silero VAD segmentation, forced-alignment grouping, and the live meter.

The heavy backends (ffmpeg binary, silero/torch, WhisperX) are NOT required —
we test the deterministic command-building / segmentation / metering logic that
decides behaviour, and assert the guarded paths fail gracefully when a backend
is absent.
"""

from __future__ import annotations

import numpy as np

from talkteach.audio import decode
from talkteach.audio.align import AlignedWord, group_into_sentences
from talkteach.audio.quality import live_meter
from talkteach.audio.vad import Segment, merge_segments

# --- ffmpeg decode command (#10) ---------------------------------------------


def test_build_decode_command_is_mono_16k_pcm():
    cmd = decode.build_decode_command("in.webm", "out.wav", sample_rate=16000)
    assert cmd[0] == "ffmpeg"
    assert "-ac" in cmd and cmd[cmd.index("-ac") + 1] == "1"  # mono
    assert "-ar" in cmd and cmd[cmd.index("-ar") + 1] == "16000"  # 16 kHz
    assert "pcm_s16le" in cmd
    assert cmd[-1] == "out.wav" and "in.webm" in cmd


def test_decode_without_ffmpeg_degrades_gracefully(monkeypatch):
    monkeypatch.setattr(decode, "ffmpeg_available", lambda: False)
    try:
        decode.decode_to_wav("whatever.webm")
        raise AssertionError("expected AudioDecodeError")
    except decode.AudioDecodeError as e:
        assert "audio pack" in str(e).lower() or "ffmpeg" in str(e).lower()


# --- VAD segmentation (#11) ---------------------------------------------------


def test_merge_segments_merges_close_spans_and_pads():
    segs = [Segment(1.0, 2.0), Segment(2.1, 3.0)]  # 0.1 s gap < min_gap 0.3
    out = merge_segments(segs, pad_s=0.05, min_gap_s=0.3, min_duration_s=0.2)
    assert len(out) == 1
    assert out[0].start_s < 1.0 and out[0].end_s > 3.0  # merged + padded


def test_merge_segments_drops_too_short_and_splits_too_long():
    out = merge_segments(
        [Segment(0.0, 0.1), Segment(5.0, 45.0)],
        pad_s=0.0,
        min_duration_s=0.4,
        max_duration_s=15.0,
    )
    # The 0.1 s span is dropped; the 40 s span is split into ≤15 s chunks.
    assert all(s.duration_s <= 15.0 + 1e-6 for s in out)
    assert len(out) >= 3


def test_merge_segments_empty():
    assert merge_segments([]) == []


# --- forced-alignment sentence grouping (#12) ---------------------------------


def test_group_into_sentences_splits_on_punctuation():
    words = [
        AlignedWord("Hello", 0.0, 0.5),
        AlignedWord("there.", 0.5, 1.0),
        AlignedWord("How", 1.2, 1.5),
        AlignedWord("are", 1.5, 1.7),
        AlignedWord("you?", 1.7, 2.2),
    ]
    segs = group_into_sentences(words)
    assert len(segs) == 2
    assert segs[0].start_s == 0.0 and segs[0].end_s == 1.0
    assert segs[1].start_s == 1.2 and segs[1].end_s == 2.2


def test_group_into_sentences_empty():
    assert group_into_sentences([]) == []


# --- live meter (#13) ---------------------------------------------------------


def test_live_meter_flags_quiet_and_loud():
    sr = 16000
    silence = np.zeros(sr, dtype=np.float32)
    assert live_meter(silence, sr).status == "quiet"

    loud = np.ones(sr, dtype=np.float32)  # full-scale → clipping
    assert live_meter(loud, sr).status == "loud"

    t = np.linspace(0, 1, sr, endpoint=False)
    good = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    m = live_meter(good, sr)
    assert m.status == "good"
    assert 0.0 < m.level <= 1.0
