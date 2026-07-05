"""Data augmentation — SpecAugment, speed/pitch perturbation, noise mixing (#46).

The single biggest accuracy win on a small kid dataset (NeMo, SpeechBrain both lean
on it). Every function here is **pure numpy** — deterministic given a seed, no torch,
no audio I/O — so it is unit-tested directly and can run inside the training collator
or a preprocessing pass. The director decides *whether* to augment via
:func:`talkteach.director.policy.augmentation_for` (auto-enabled for tiny data);
:class:`AugmentationConfig` is the framework-free knob it returns.

Waveforms are 1-D float32 arrays at 16 kHz (the canonical form, DECISIONS.md D-010);
SpecAugment operates on a 2-D ``[n_mels, n_frames]`` feature array.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TARGET_SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class AugmentationConfig:
    """Which augmentations to apply, and how hard. Framework-free (director output).

    ``enabled`` is the master switch. ``speed_factors`` are multipliers cycled per
    example (1.0 = identity). ``noise_snr_db`` mixes noise at that SNR when a noise
    bank is available. ``spec_*`` drive SpecAugment masking.
    """

    enabled: bool = False
    speed_factors: tuple[float, ...] = (1.0,)
    pitch_semitones: tuple[float, ...] = (0.0,)
    noise_snr_db: float | None = None
    spec_time_masks: int = 0
    spec_time_width: int = 0
    spec_freq_masks: int = 0
    spec_freq_width: int = 0
    reason: str = ""

    labels: tuple[str, ...] = field(default_factory=tuple)


# --- waveform augmentations ---------------------------------------------------


def perturb_speed(samples: np.ndarray, factor: float) -> np.ndarray:
    """Resample-based speed perturbation (changes speed *and* pitch), the classic
    SpeedPerturb. ``factor`` > 1 speeds up (shortens); < 1 slows down. ``1.0`` is a
    no-op. Length scales by ``1/factor``.
    """
    if factor <= 0:
        raise ValueError("speed factor must be positive")
    if factor == 1.0 or samples.size == 0:
        return samples.astype("float32", copy=False)
    n_out = max(1, int(round(samples.shape[0] / factor)))
    xp = np.linspace(0.0, 1.0, num=samples.shape[0], endpoint=False)
    x = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x, xp, samples).astype("float32")


def perturb_pitch(
    samples: np.ndarray, n_semitones: float, sample_rate: int = TARGET_SAMPLE_RATE
) -> np.ndarray:
    """Approximate pitch shift that **preserves duration** (resample up/down, then
    back to the original length). Crude vs a phase vocoder, but a real, cheap,
    dependency-free augmentation. ``0`` semitones is a no-op.
    """
    _ = sample_rate  # kept for API symmetry / future high-quality path
    if n_semitones == 0.0 or samples.size == 0:
        return samples.astype("float32", copy=False)
    ratio = 2.0 ** (n_semitones / 12.0)
    shifted = perturb_speed(samples, ratio)  # changes pitch + length
    # Stretch back to the original length so only pitch changed.
    xp = np.linspace(0.0, 1.0, num=shifted.shape[0], endpoint=False)
    x = np.linspace(0.0, 1.0, num=samples.shape[0], endpoint=False)
    return np.interp(x, xp, shifted).astype("float32")


def mix_noise(samples: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """Mix ``noise`` into ``samples`` at a target signal-to-noise ratio (dB).

    Noise is tiled/truncated to the signal length and scaled so the resulting SNR
    equals ``snr_db``. A silent signal or silent noise returns the signal unchanged.
    """
    if samples.size == 0 or noise.size == 0:
        return samples.astype("float32", copy=False)
    sig = samples.astype("float32")
    # Tile / truncate noise to match length.
    if noise.shape[0] < sig.shape[0]:
        reps = int(np.ceil(sig.shape[0] / noise.shape[0]))
        noise = np.tile(noise, reps)
    noise = noise[: sig.shape[0]].astype("float32")

    sig_rms = float(np.sqrt(np.mean(sig**2)))
    noise_rms = float(np.sqrt(np.mean(noise**2)))
    if sig_rms == 0.0 or noise_rms == 0.0:
        return sig
    target_noise_rms = sig_rms / (10.0 ** (snr_db / 20.0))
    scaled = noise * (target_noise_rms / noise_rms)
    return (sig + scaled).astype("float32")


# --- feature augmentation -----------------------------------------------------


def spec_augment(
    spec: np.ndarray,
    *,
    num_time_masks: int = 2,
    time_mask_width: int = 10,
    num_freq_masks: int = 2,
    freq_mask_width: int = 10,
    mask_value: float | None = None,
    seed: int | None = None,
) -> np.ndarray:
    """SpecAugment time/frequency masking on a ``[n_mels, n_frames]`` spectrogram.

    Returns a masked copy (input is not mutated). Masked cells are set to
    ``mask_value`` (defaults to the spectrogram mean, the standard choice). A fixed
    ``seed`` makes the masking deterministic for tests/reproducibility.
    """
    if spec.ndim != 2:
        raise ValueError("spec_augment expects a 2-D [n_mels, n_frames] array")
    out = spec.astype("float32", copy=True)
    n_mels, n_frames = out.shape
    fill = float(spec.mean()) if mask_value is None else float(mask_value)
    rng = np.random.default_rng(seed)

    for _ in range(num_time_masks):
        w = int(rng.integers(0, max(1, min(time_mask_width, n_frames)) + 1))
        if w == 0 or w >= n_frames:
            continue
        start = int(rng.integers(0, n_frames - w + 1))
        out[:, start : start + w] = fill

    for _ in range(num_freq_masks):
        w = int(rng.integers(0, max(1, min(freq_mask_width, n_mels)) + 1))
        if w == 0 or w >= n_mels:
            continue
        start = int(rng.integers(0, n_mels - w + 1))
        out[start : start + w, :] = fill

    return out
