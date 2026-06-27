"""Tests for talkteach.audio.quality — pytest + numpy only (no soundfile).

Run from the backend/ directory; pyproject sets pythonpath=["."].
"""

from __future__ import annotations

import numpy as np
import pytest

from talkteach.audio.quality import (
    ISSUE_MOSTLY_SILENCE,
    ISSUE_TOO_LOUD,
    ISSUE_TOO_QUIET,
    ClipQuality,
    Verdict,
    aggregate,
    analyze_samples,
)

SR = 16_000


def _sine(freq_hz: float, duration_s: float, amplitude: float, sr: int = SR) -> np.ndarray:
    t = np.arange(int(sr * duration_s)) / sr
    return (amplitude * np.sin(2.0 * np.pi * freq_hz * t)).astype(np.float64)


def test_clipped_sine_flags_too_loud():
    # Amplitude 1.5 then hard-clipped to [-1, 1] -> long flat tops at +/-1.
    raw = _sine(220.0, 1.0, amplitude=1.5)
    clipped = np.clip(raw, -1.0, 1.0)
    q = analyze_samples(clipped, SR)
    assert ISSUE_TOO_LOUD in q.issues
    assert q.ok is False
    assert q.verdict is Verdict.BAD


def test_very_quiet_sine_flags_too_quiet():
    quiet = _sine(220.0, 1.0, amplitude=0.001)
    q = analyze_samples(quiet, SR)
    assert ISSUE_TOO_QUIET in q.issues
    assert q.ok is False


def test_pure_silence_flags_mostly_silence():
    zeros = np.zeros(int(SR * 1.0), dtype=np.float64)
    q = analyze_samples(zeros, SR)
    assert ISSUE_MOSTLY_SILENCE in q.issues
    assert q.ok is False
    assert q.silence_fraction > 0.8


def test_near_silence_flags_mostly_silence():
    near = _sine(220.0, 1.0, amplitude=1e-5)
    q = analyze_samples(near, SR)
    assert ISSUE_MOSTLY_SILENCE in q.issues
    assert q.ok is False


def test_clean_moderate_sine_is_ok():
    # Healthy level (~ -12 dBFS), light broadband noise -> clean SNR.
    rng = np.random.default_rng(0)
    signal = _sine(220.0, 2.0, amplitude=0.25)
    noise = rng.normal(0.0, 0.002, size=signal.shape)
    clip = signal + noise
    q = analyze_samples(clip, SR)
    assert q.ok is True, f"expected ok, got issues={q.issues}"
    assert q.issues == []
    assert q.verdict is Verdict.GOOD
    assert q.rms_dbfs > -40.0
    assert q.est_snr_db >= 10.0


def test_too_short_clip_not_ok():
    short = _sine(220.0, 0.1, amplitude=0.25)
    q = analyze_samples(short, SR)
    assert q.ok is False


def test_sub_frame_clip_does_not_crash():
    # 300 samples @ 16kHz is shorter than one 25ms (400-sample) frame.
    tiny = _sine(220.0, 300 / SR, amplitude=0.25)
    assert tiny.size < 400
    q = analyze_samples(tiny, SR)  # must not raise
    assert q.ok is False


def test_stereo_input_is_averaged():
    mono = _sine(220.0, 1.0, amplitude=0.25)
    stereo = np.stack([mono, mono], axis=1)  # (frames, 2)
    q = analyze_samples(stereo, SR)
    assert q.ok is True
    assert q.duration_s == pytest.approx(1.0, abs=0.01)


def test_empty_input_is_handled():
    q = analyze_samples(np.array([], dtype=np.float64), SR)
    assert q.ok is False
    assert q.duration_s == 0.0


def test_aggregate_math():
    clips = [
        ClipQuality(duration_s=60.0, ok=True),  # 1.0 good min
        ClipQuality(duration_s=30.0, ok=True),  # 0.5 good min
        ClipQuality(duration_s=120.0, ok=False),  # 2.0 total, not good
    ]
    profile = aggregate(clips)
    assert profile.clip_count == 3
    assert profile.good_minutes == pytest.approx(1.5)
    assert profile.total_minutes == pytest.approx(3.5)
    assert profile.distinct_speakers == 1
    assert profile.good_fraction == pytest.approx(1.5 / 3.5)


def test_aggregate_empty():
    profile = aggregate([])
    assert profile.clip_count == 0
    assert profile.good_minutes == 0.0
    assert profile.total_minutes == 0.0
