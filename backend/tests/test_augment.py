"""Data-augmentation tests (#46): pure-numpy waveform + SpecAugment ops and the
director's auto-enable policy. No torch."""

from __future__ import annotations

import numpy as np
import pytest

from talkteach.audio.augment import (
    AugmentationConfig,
    mix_noise,
    perturb_pitch,
    perturb_speed,
    spec_augment,
)
from talkteach.director import augmentation_for
from talkteach.director.types import DataProfile


def _tone(seconds=1.0, rate=16000, freq=220.0):
    t = np.arange(int(seconds * rate)) / rate
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype("float32")


def test_perturb_speed_changes_length():
    x = _tone(1.0)
    faster = perturb_speed(x, 2.0)
    slower = perturb_speed(x, 0.5)
    assert faster.shape[0] == x.shape[0] // 2
    assert slower.shape[0] == x.shape[0] * 2
    assert perturb_speed(x, 1.0).shape == x.shape  # identity
    assert faster.dtype == np.float32


def test_perturb_speed_rejects_nonpositive():
    with pytest.raises(ValueError):
        perturb_speed(_tone(), 0.0)


def test_perturb_pitch_noop_is_pure():
    x = _tone(1.0)
    assert np.allclose(perturb_pitch(x, 0.0), x)  # 0 semitones needs no dep, returns input


def test_perturb_pitch_actually_shifts_the_dominant_frequency():
    # Measure the PROPERTY: +4 semitones must move 220 Hz → ~277 Hz (220·2^(4/12)),
    # duration preserved. Needs librosa (guarded [ml] path); skip in the dep-light job.
    pytest.importorskip("librosa")

    def dom_hz(sig, sr=16000):
        spectrum = np.abs(np.fft.rfft(sig))
        return np.fft.rfftfreq(len(sig), 1 / sr)[np.argmax(spectrum)]

    x = _tone(1.0, freq=220.0)
    shifted = perturb_pitch(x, 4.0)
    assert shifted.shape == x.shape  # duration preserved
    assert dom_hz(shifted) == pytest.approx(277.0, abs=5.0)  # pitch really moved


def test_mix_noise_hits_target_snr():
    sig = _tone(1.0, freq=200.0)
    rng = np.random.default_rng(0)
    noise = rng.standard_normal(sig.shape[0]).astype("float32")
    mixed = mix_noise(sig, noise, snr_db=10.0)
    added = mixed - sig
    sig_rms = np.sqrt(np.mean(sig**2))
    noise_rms = np.sqrt(np.mean(added**2))
    measured_snr = 20 * np.log10(sig_rms / noise_rms)
    assert measured_snr == pytest.approx(10.0, abs=0.5)


def test_mix_noise_tiles_short_noise():
    sig = _tone(1.0)
    short = _tone(0.1)  # shorter than signal → must be tiled, not crash
    out = mix_noise(sig, short, snr_db=20.0)
    assert out.shape == sig.shape


def test_spec_augment_masks_and_is_deterministic():
    spec = np.ones((80, 100), dtype="float32")
    kw = {
        "num_time_masks": 2,
        "time_mask_width": 10,
        "num_freq_masks": 2,
        "mask_value": 0.0,
        "seed": 7,
    }
    a = spec_augment(spec, **kw)
    b = spec_augment(spec, **kw)
    assert np.array_equal(a, b)  # same seed → same masks
    assert (a != spec).any()  # something got masked
    assert not np.shares_memory(a, spec)  # input untouched


def test_spec_augment_requires_2d():
    with pytest.raises(ValueError):
        spec_augment(np.ones(10, dtype="float32"))


# --- director auto-enable policy ----------------------------------------------


def _data(good_minutes):
    return DataProfile(good_minutes=good_minutes, total_minutes=good_minutes, clip_count=10)


def test_augmentation_off_when_plenty_of_data():
    cfg = augmentation_for(_data(40.0))
    assert isinstance(cfg, AugmentationConfig)
    assert cfg.enabled is False


def test_augmentation_moderate_and_aggressive_scale_with_scarcity():
    moderate = augmentation_for(_data(15.0))
    aggressive = augmentation_for(_data(3.0))
    assert moderate.enabled and aggressive.enabled
    # Aggressive stretches tiny data harder: more speed variants + louder noise.
    assert len(aggressive.speed_factors) > len(moderate.speed_factors)
    assert aggressive.noise_snr_db < moderate.noise_snr_db
    assert "spec_augment" in aggressive.labels
