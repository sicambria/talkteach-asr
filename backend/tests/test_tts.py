"""Tests for the TTS providers and dataset builder (roadmap #1/#6).

Four tiers, by dependency:

* **Dep-light (always run):** the registry, availability reporting, and the
  stdlib resampler in ``tts.base`` — no binary, no model, no torch.
* **espeak (``-m espeak``):** real synthesis through the espeak-ng *binary*; skips
  cleanly when it isn't installed. This is the CI fast-path generator.
* **piper (``-m integration``):** real neural synthesis; needs the ``[tts]`` extra
  and downloads a small voice on first run, so it's opt-in like the other
  network/heavy paths.
* **pocket-tts (``-m integration``):** real neural synthesis + voice cloning; needs
  the ``[pocket-tts]`` extra. Downloads ~100M weights on first run.
"""

from __future__ import annotations

import importlib.util
import wave

import numpy as np
import pytest

from talkteach.audio.quality import Verdict, analyze_file
from talkteach.tts import (
    EspeakProvider,
    PiperProvider,
    PocketTTSProvider,
    available_providers,
    get_tts_provider,
)
from talkteach.tts.base import normalize_wav, wav_duration_s
from talkteach.tts.dataset import synthesize_dataset

_HAS_ESPEAK = EspeakProvider._binary() is not None
_HAS_PIPER = importlib.util.find_spec("piper") is not None
_HAS_POCKET_TTS = importlib.util.find_spec("pocket_tts") is not None
# These tests synthesize *and* run the audio-quality gate, which decodes via
# soundfile — an [ml] extra. The espeak marker means "binary + [ml]" (see
# pyproject markers); without soundfile the test would ImportError instead of
# skipping on a box that has the binary but not the ML extras.
_HAS_SOUNDFILE = importlib.util.find_spec("soundfile") is not None
_HAS_ESPEAK_ML = _HAS_ESPEAK and _HAS_SOUNDFILE


def _write_wav(path: str, freq: float, rate: int, seconds: float = 1.0, channels: int = 1) -> None:
    t = np.linspace(0, seconds, int(rate * seconds), endpoint=False)
    mono = (0.2 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    frames = np.repeat(mono, channels) if channels > 1 else mono
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(frames.tobytes())


# -- dep-light ---------------------------------------------------------------


def test_registry_lists_known_providers():
    assert set(available_providers()) >= {"espeak", "piper", "pocket-tts"}
    assert isinstance(get_tts_provider("espeak"), EspeakProvider)
    assert isinstance(get_tts_provider("piper"), PiperProvider)
    assert isinstance(get_tts_provider("pocket-tts"), PocketTTSProvider)


def test_unknown_provider_raises():
    with pytest.raises(KeyError):
        get_tts_provider("nope")


def test_availability_returns_tuple():
    ok, msg = get_tts_provider("espeak").is_available()
    assert isinstance(ok, bool) and isinstance(msg, str)


def test_normalize_wav_downsamples_to_16k_mono(tmp_path):
    src = str(tmp_path / "src.wav")
    dst = str(tmp_path / "dst.wav")
    _write_wav(src, freq=220, rate=22050, seconds=1.0, channels=2)
    normalize_wav(src, dst, target_rate=16_000)
    with wave.open(dst, "rb") as wf:
        assert wf.getframerate() == 16_000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
    assert wav_duration_s(dst) == pytest.approx(1.0, abs=0.05)


# -- espeak (real binary) ----------------------------------------------------


@pytest.mark.espeak
@pytest.mark.skipif(not _HAS_ESPEAK_ML, reason="needs espeak-ng binary + [ml] (soundfile)")
def test_espeak_synthesizes_good_clip(tmp_path):
    out = str(tmp_path / "hello.wav")
    get_tts_provider("espeak").synthesize("the cat sat on the warm mat", out)
    with wave.open(out, "rb") as wf:
        assert wf.getframerate() == 16_000 and wf.getnchannels() == 1
    # Real speech passes the same quality gate a real recording would.
    assert analyze_file(out).verdict is Verdict.GOOD


@pytest.mark.espeak
@pytest.mark.skipif(not _HAS_ESPEAK_ML, reason="needs espeak-ng binary + [ml] (soundfile)")
def test_synthesize_dataset_returns_manifest(tmp_path):
    mani = synthesize_dataset(get_tts_provider("espeak"), tmp_path, language="en", n=3)
    assert len(mani) == 3
    for item in mani:
        assert set(item) == {"path", "text", "duration_s"}
        assert item["duration_s"] > 0
        assert analyze_file(item["path"]).verdict is Verdict.GOOD


# -- piper (neural, downloads a voice) ---------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(not _HAS_PIPER, reason="piper-tts not installed ([tts] extra)")
def test_piper_synthesizes_good_clip(tmp_path):
    out = str(tmp_path / "hello.wav")
    provider = get_tts_provider("piper", download_dir=str(tmp_path / "voices"))
    provider.synthesize("look at the big blue sky today", out)
    with wave.open(out, "rb") as wf:
        assert wf.getframerate() == 16_000 and wf.getnchannels() == 1
    assert analyze_file(out).verdict is Verdict.GOOD


# -- pocket-tts (neural + voice cloning, downloads weights) ------------------


@pytest.mark.integration
@pytest.mark.skipif(not _HAS_POCKET_TTS, reason="pocket-tts not installed ([pocket-tts] extra)")
def test_pocket_tts_registered():
    """PocketTTSProvider is available in the registry and reports the right type."""
    provider = get_tts_provider("pocket-tts")
    assert isinstance(provider, PocketTTSProvider)


@pytest.mark.integration
@pytest.mark.skipif(not _HAS_POCKET_TTS, reason="pocket-tts not installed ([pocket-tts] extra)")
def test_pocket_tts_synthesizes_good_clip(tmp_path):
    """Real synthesis via Pocket TTS with a catalog voice."""
    out = str(tmp_path / "hello.wav")
    provider = get_tts_provider("pocket-tts", default_voice="alba", language="english")
    provider.synthesize("the cat sat on the warm mat", out)
    with wave.open(out, "rb") as wf:
        assert wf.getframerate() == 16_000 and wf.getnchannels() == 1
    assert analyze_file(out).verdict is Verdict.GOOD
