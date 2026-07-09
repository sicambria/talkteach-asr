"""Tests for talkteach.audio.quality — pytest + numpy only (no soundfile).

Run from the backend/ directory; pyproject sets pythonpath=["."].
"""

from __future__ import annotations

import numpy as np
import pytest

from talkteach.audio.augment import mix_noise
from talkteach.audio.quality import (
    ISSUE_MOSTLY_SILENCE,
    ISSUE_TOO_LOUD,
    ISSUE_TOO_NOISY,
    ISSUE_TOO_QUIET,
    SNR_MIN_DB,
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


# ── INS-002: SNR estimator no longer saturates on broadband noise ──────────────
# The gate used to fall back to a 60 dB ceiling whenever a clip had no silence
# frames — which is exactly what full-clip broadband noise produces — so it gave
# its BEST score to its WORST inputs (speech buried in noise), accepting them for
# training. The spectral noise-floor estimate must instead track true SNR.
# Thresholds below were set from the *measured* fixed behaviour (seed=0), not
# predicted, and left with margin.


def _structured_base(duration_s: float = 2.0) -> np.ndarray:
    """A continuous two-tone signal with no sub-−45 dBFS frames (forces the
    spectral branch), normalised to a healthy ~0.4 peak level."""
    base = _sine(220.0, duration_s, 0.25) + 0.5 * _sine(440.0, duration_s, 0.25)
    return base / np.max(np.abs(base)) * 0.4


def test_snr_sweep_is_monotonic_and_tracks_true_snr():
    # Additive broadband noise at known SNRs: est_snr_db must increase with true
    # SNR and stay close to it (spectral estimate ≈ 10*log10(SNR_linear+1)).
    base = _structured_base()
    rng = np.random.default_rng(0)
    true_snrs = [3.0, 8.0, 10.0, 15.0, 20.0]
    ests = []
    for s in true_snrs:
        noise = rng.standard_normal(base.shape[0]).astype(np.float64)
        q = analyze_samples(mix_noise(base, noise, s), SR)
        ests.append(q.est_snr_db)
        # No silence frames — this exercises the spectral branch, not temporal.
        assert q.silence_fraction == 0.0
    # Strictly monotonic in true SNR (no ceiling saturation).
    assert ests == sorted(ests)
    assert all(b - a > 0.5 for a, b in zip(ests, ests[1:], strict=False))
    # Tracks the true value within a small margin (measured: 5.4/9.2/11.0/15.9/20.6).
    for s, est in zip(true_snrs, ests, strict=True):
        assert abs(est - s) < 2.5, f"true {s} dB -> est {est:.2f} dB drifted too far"


def test_snr_gate_crosses_near_true_10db():
    # The whole point: the noise gate (SNR_MIN_DB) must become meaningful again —
    # buried-in-noise clips (≤8 dB) rejected, acceptable clips (≥10 dB) pass.
    base = _structured_base()
    rng = np.random.default_rng(0)
    verdicts = {}
    for s in [3.0, 8.0, 10.0, 15.0, 20.0]:
        noise = rng.standard_normal(base.shape[0]).astype(np.float64)
        q = analyze_samples(mix_noise(base, noise, s), SR)
        verdicts[s] = q
    # Below the gate → flagged noisy and rejected.
    assert verdicts[3.0].est_snr_db < SNR_MIN_DB
    assert ISSUE_TOO_NOISY in verdicts[3.0].issues and verdicts[3.0].ok is False
    assert verdicts[8.0].est_snr_db < SNR_MIN_DB and verdicts[8.0].ok is False
    # At/above the gate → accepted.
    assert verdicts[10.0].est_snr_db >= SNR_MIN_DB and verdicts[10.0].ok is True
    assert verdicts[20.0].ok is True


def test_clean_continuous_signal_is_not_false_rejected():
    # A clean continuous tone (no silence frames) must still score high and pass —
    # the fix must not flip clean audio to "too noisy". (Measured: 60 dB.)
    q = analyze_samples(_structured_base(), SR)
    assert q.est_snr_db >= 40.0
    assert ISSUE_TOO_NOISY not in q.issues
    assert q.ok is True


def test_pure_broadband_noise_is_rejected():
    # The exact defect input: continuous broadband noise, no silence frames. Used
    # to score 60 dB (GOOD); must now score low and be rejected.
    rng = np.random.default_rng(0)
    noise = (rng.standard_normal(int(SR * 2.0)) * 0.1).astype(np.float64)
    q = analyze_samples(noise, SR)
    assert q.silence_fraction == 0.0  # broadband noise defeats the silence heuristic
    assert q.est_snr_db < SNR_MIN_DB
    assert ISSUE_TOO_NOISY in q.issues and q.ok is False


def test_spectral_snr_safe_on_sub_two_frame_input():
    # <2 frames cannot establish a spectral noise floor -> 0.0, no crash. A tiny
    # continuous clip reaches the spectral branch (no silence frames).
    tiny = _sine(220.0, 300 / SR, amplitude=0.25)
    assert tiny.size < 2 * 400
    q = analyze_samples(tiny, SR)  # must not raise
    assert q.est_snr_db == 0.0
