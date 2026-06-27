"""Real-time-ish audio quality checks for recorded ASR-training clips.

A novice records short clips; we give them a thumbs-up / thumbs-down plus a
plain-language reason, and we count "minutes of GOOD audio" that feed the
director's sufficiency gate (see ``talkteach.director.types.DataProfile``).

All DSP here is pure numpy and deterministic. ``soundfile`` is an OPTIONAL
dependency, imported lazily inside :func:`analyze_file` so the rest of the
module works with numpy alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from talkteach.director.types import DataProfile

# ---------------------------------------------------------------------------
# Proposed default thresholds — calibrate against real recordings.
# These are deliberately conservative starting points, not tuned constants.
# ---------------------------------------------------------------------------

#: Log floor so 20*log10 never sees zero (about -120 dBFS in amplitude terms).
_DBFS_FLOOR = 1e-6

#: A sample at or above this absolute amplitude counts as "clipped".
CLIP_LEVEL = 0.99
#: If more than this fraction of samples clip, we flag "too loud / clipping".
CLIP_FRACTION_MAX = 0.005  # 0.5% of samples

#: RMS below this is judged "too quiet".
RMS_QUIET_DBFS = -40.0

#: Frame length (seconds) for the short-time RMS analysis.
FRAME_MS = 25.0
#: A frame whose RMS is below this counts as silence/background.
SILENCE_FRAME_DBFS = -45.0
#: If more than this fraction of frames are silent, we flag "mostly silence".
SILENCE_FRACTION_MAX = 0.8

#: Estimated SNR below this (dB) is judged "too noisy".
SNR_MIN_DB = 10.0

#: A clip shorter than this (seconds) is too short to be useful.
MIN_DURATION_S = 0.4


class Verdict(str, Enum):
    """Coarse quality verdict for a clip."""

    GOOD = "good"
    BAD = "bad"


# Plain-language issue strings (stable identifiers, shown to the user as-is).
ISSUE_TOO_QUIET = "too quiet"
ISSUE_TOO_LOUD = "too loud / clipping"
ISSUE_TOO_NOISY = "too noisy"
ISSUE_MOSTLY_SILENCE = "mostly silence"
ISSUE_TOO_SHORT = "too short"


@dataclass
class ClipQuality:
    """Outcome of analysing a single recorded clip."""

    duration_s: float
    ok: bool
    issues: list[str] = field(default_factory=list)
    peak_dbfs: float = float("-inf")
    rms_dbfs: float = float("-inf")
    est_snr_db: float = 0.0
    silence_fraction: float = 0.0

    @property
    def verdict(self) -> Verdict:
        return Verdict.GOOD if self.ok else Verdict.BAD


def _to_mono_float(samples: np.ndarray) -> np.ndarray:
    """Coerce arbitrary sample arrays to a 1-D float64 mono waveform."""
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim == 2:
        # Average across channels. soundfile gives (frames, channels).
        # Pick the smaller axis as the channel axis to be forgiving of layout.
        ch_axis = 1 if x.shape[1] <= x.shape[0] else 0
        x = x.mean(axis=ch_axis)
    elif x.ndim > 2:
        x = x.reshape(x.shape[0], -1).mean(axis=1)
    return np.ascontiguousarray(x.ravel())


def _amp_to_dbfs(amplitude: float) -> float:
    """Convert a linear amplitude (0..1) to dBFS with a safe floor."""
    return float(20.0 * np.log10(max(abs(amplitude), _DBFS_FLOOR)))


def _frame_rms(x: np.ndarray, frame_len: int) -> np.ndarray:
    """Non-overlapping per-frame RMS. Returns at least one frame."""
    n = x.size
    if frame_len <= 0 or n == 0:
        return np.array([0.0])
    if n < frame_len:
        # Shorter than one frame — treat the whole signal as a single frame.
        return np.array([float(np.sqrt(np.mean(x**2)))])
    n_frames = n // frame_len
    usable = n_frames * frame_len
    frames = x[:usable].reshape(n_frames, frame_len)
    return np.sqrt(np.mean(frames**2, axis=1))


def analyze_samples(samples: np.ndarray, sample_rate: int) -> ClipQuality:
    """Analyse a float waveform in [-1, 1] and return a :class:`ClipQuality`.

    Pure numpy and deterministic. ``samples`` may be 1-D mono or 2-D
    (channels averaged). ``sample_rate`` is in Hz.
    """
    x = _to_mono_float(samples)
    n = x.size
    sr = int(sample_rate) if sample_rate and sample_rate > 0 else 1
    duration_s = float(n / sr)

    issues: list[str] = []

    # Empty / degenerate input: nothing useful here.
    if n == 0:
        return ClipQuality(
            duration_s=0.0,
            ok=False,
            issues=[ISSUE_TOO_SHORT, ISSUE_MOSTLY_SILENCE],
            peak_dbfs=float("-inf"),
            rms_dbfs=float("-inf"),
            est_snr_db=0.0,
            silence_fraction=1.0,
        )

    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x**2)))
    peak_dbfs = _amp_to_dbfs(peak)
    rms_dbfs = _amp_to_dbfs(rms)

    # --- Clipping ---------------------------------------------------------
    clip_fraction = float(np.mean(np.abs(x) >= CLIP_LEVEL))
    if clip_fraction > CLIP_FRACTION_MAX:
        issues.append(ISSUE_TOO_LOUD)

    # --- Frame-level RMS for silence + SNR --------------------------------
    frame_len = max(1, int(round(sr * FRAME_MS / 1000.0)))
    frame_rms = _frame_rms(x, frame_len)
    frame_dbfs = 20.0 * np.log10(np.maximum(frame_rms, _DBFS_FLOOR))

    silent_mask = frame_dbfs < SILENCE_FRAME_DBFS
    speech_mask = ~silent_mask
    silence_fraction = float(np.mean(silent_mask))

    if silence_fraction > SILENCE_FRACTION_MAX:
        issues.append(ISSUE_MOSTLY_SILENCE)

    # --- Crude SNR estimate ----------------------------------------------
    # Speech-frame energy vs noise-frame energy. Robust to all-speech /
    # all-silence cases.
    speech_pow = float(np.mean(frame_rms[speech_mask] ** 2)) if speech_mask.any() else 0.0
    noise_pow = float(np.mean(frame_rms[silent_mask] ** 2)) if silent_mask.any() else 0.0

    if not speech_mask.any():
        # No speech detected at all — treat as no usable signal.
        est_snr_db = 0.0
    elif not silent_mask.any():
        # No noise floor frames — assume a clean signal (cap high).
        est_snr_db = 60.0
    else:
        est_snr_db = float(10.0 * np.log10(max(speech_pow, _DBFS_FLOOR) / max(noise_pow, _DBFS_FLOOR)))

    # Only flag noise when there is actually speech to judge.
    if speech_mask.any() and est_snr_db < SNR_MIN_DB:
        issues.append(ISSUE_TOO_NOISY)

    # --- Too quiet --------------------------------------------------------
    if rms_dbfs < RMS_QUIET_DBFS:
        if ISSUE_TOO_QUIET not in issues:
            issues.append(ISSUE_TOO_QUIET)

    # --- Duration sanity --------------------------------------------------
    if duration_s < MIN_DURATION_S:
        issues.append(ISSUE_TOO_SHORT)

    ok = len(issues) == 0 and duration_s >= MIN_DURATION_S

    return ClipQuality(
        duration_s=duration_s,
        ok=ok,
        issues=issues,
        peak_dbfs=peak_dbfs,
        rms_dbfs=rms_dbfs,
        est_snr_db=est_snr_db,
        silence_fraction=silence_fraction,
    )


def analyze_file(path: str, sample_rate: int | None = None) -> ClipQuality:
    """Load an audio file and analyse it.

    Requires the optional ``soundfile`` dependency. The file's own sample rate
    is always used (we cannot resample with numpy alone). ``sample_rate`` is
    accepted only for API symmetry / future resampling and is currently a
    no-op — passing it never changes the reported duration.
    """
    try:
        import soundfile as sf  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised only without sf
        raise ImportError(
            "Reading audio files needs the optional 'soundfile' dependency. "
            "Install the ML extras: pip install talkteach-backend[ml]"
        ) from exc

    data, file_sr = sf.read(path, dtype="float32", always_2d=False)
    # Always trust the file's rate; resampling is out of scope for numpy-only.
    return analyze_samples(data, int(file_sr))


def aggregate(clips: list[ClipQuality]) -> DataProfile:
    """Roll up per-clip results into a :class:`DataProfile` for the director."""
    total_seconds = sum(c.duration_s for c in clips)
    good_seconds = sum(c.duration_s for c in clips if c.ok)
    return DataProfile(
        good_minutes=good_seconds / 60.0,
        total_minutes=total_seconds / 60.0,
        clip_count=len(clips),
        distinct_speakers=1,  # diarization is out of scope for Phase 0
    )


__all__ = [
    "Verdict",
    "ClipQuality",
    "analyze_samples",
    "analyze_file",
    "aggregate",
    "ISSUE_TOO_QUIET",
    "ISSUE_TOO_LOUD",
    "ISSUE_TOO_NOISY",
    "ISSUE_MOSTLY_SILENCE",
    "ISSUE_TOO_SHORT",
]
