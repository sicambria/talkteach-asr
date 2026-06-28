"""End-to-end benchmark tests — the proof that WER means something here.

Two tiers, deliberately split (see project/docs/BENCHMARKING.md):

* **measurement-is-real (``-m espeak``, the CI fast-path):** NO training. Transcribe
  clean TTS speech with a base model → low WER; transcribe *tones* labelled with the
  same sentences → high WER. This proves the measurement *discriminates* real speech
  from noise — which the old sine-tone fixtures never did — and is fast/robust
  because it doesn't depend on a tiny fine-tune actually lowering WER.
* **training-improves (``-m integration``, opt-in):** run the real benchmark
  (TTS → fine-tune → score on a shared eval set) and assert a sane, *loose* bound.
  Heavier (downloads a model, trains on CPU); not part of the default suite.

Everything skips cleanly when its dependency (espeak-ng binary / piper / [ml]) is
absent, so the default ``pytest -q`` is unaffected.
"""

from __future__ import annotations

import importlib.util
import os
import wave

import numpy as np
import pytest

from talkteach.engines._train_common import wer
from talkteach.tts import EspeakProvider
from talkteach.tts.dataset import synthesize_dataset

_HAS_ESPEAK = EspeakProvider._binary() is not None
_HAS_PIPER = importlib.util.find_spec("piper") is not None
_HAS_FW = importlib.util.find_spec("faster_whisper") is not None
_HAS_ML = all(importlib.util.find_spec(m) is not None for m in ("torch", "transformers", "peft"))
# The `integration` tier downloads a model + trains, so it stays opt-in like
# test_integration_train (set TALKTEACH_RUN_INTEGRATION=1). The `espeak` fast-path
# is gated only on its binary so the CI `pytest -m espeak` job runs it.
_RUN = os.environ.get("TALKTEACH_RUN_INTEGRATION") == "1"

_SENTENCES = ["the cat sat on the mat", "look at the blue sky today"]

# Calibrated on piper + whisper-tiny (measured ~0.04 clean WER — large headroom).
# espeak is robotic formant synthesis, so its clean WER through the weak whisper-tiny
# may be higher; the espeak check therefore uses a looser absolute bound and leans on
# the *gap* (speech ≪ tones) as the real discriminator, not a knife-edge threshold.
_CLEAN_WER_MAX = 0.5  # piper / benchmark cells
_ESPEAK_CLEAN_WER_MAX = 0.7  # robotic voice + tiny model → looser
_TONE_WER_MIN = 0.8
_MIN_GAP = 0.3  # tones must be at least this much worse than clean speech


def _write_tone_wav(path: str, freq: float, seconds: float = 2.0, sr: int = 16000) -> None:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    pcm = (0.2 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


_FW_MODEL = []  # one-element cache so we load whisper-tiny once per session


def _base_transcribe(path: str) -> str:
    from faster_whisper import WhisperModel

    if not _FW_MODEL:
        _FW_MODEL.append(WhisperModel("tiny", device="cpu", compute_type="int8"))
    segments, _ = _FW_MODEL[0].transcribe(path)
    return " ".join(seg.text.strip() for seg in segments).strip()


def _check_discriminates(provider, tmp_path, clean_max: float = _CLEAN_WER_MAX) -> None:
    clean = synthesize_dataset(provider, tmp_path / "clean", prompts=_SENTENCES, prefix="clean")
    tones_dir = tmp_path / "tones"
    tones_dir.mkdir()
    tone_manifest = []
    for i, text in enumerate(_SENTENCES):
        p = str(tones_dir / f"tone_{i}.wav")
        _write_tone_wav(p, freq=200 + 60 * i)
        tone_manifest.append({"path": p, "text": text})

    clean_wer = wer(_SENTENCES, [_base_transcribe(m["path"]) for m in clean])
    tone_wer = wer(_SENTENCES, [_base_transcribe(m["path"]) for m in tone_manifest])

    assert clean_wer <= clean_max, f"clean speech WER too high: {clean_wer}"
    assert tone_wer >= _TONE_WER_MIN, f"tone WER too low (tones shouldn't transcribe): {tone_wer}"
    # The gap is the real signal: real speech transcribes, tones don't.
    assert tone_wer - clean_wer >= _MIN_GAP, (
        f"measurement failed to discriminate speech ({clean_wer}) from tones ({tone_wer})"
    )


# -- measurement-is-real (CI fast-path) --------------------------------------


@pytest.mark.espeak
@pytest.mark.skipif(not (_HAS_ESPEAK and _HAS_FW), reason="needs espeak-ng binary + faster-whisper")
def test_measurement_discriminates_speech_from_tones_espeak(tmp_path):
    from talkteach.tts import get_tts_provider

    _check_discriminates(get_tts_provider("espeak"), tmp_path, clean_max=_ESPEAK_CLEAN_WER_MAX)


@pytest.mark.integration
@pytest.mark.skipif(
    not (_RUN and _HAS_PIPER and _HAS_FW),
    reason="set TALKTEACH_RUN_INTEGRATION=1 + piper + faster-whisper",
)
def test_measurement_discriminates_speech_from_tones_piper(tmp_path):
    from talkteach.tts import get_tts_provider

    _check_discriminates(get_tts_provider("piper", download_dir=str(tmp_path / "voices")), tmp_path)


# -- training-improves (opt-in) ----------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    not (_RUN and _HAS_PIPER and _HAS_ML),
    reason="set TALKTEACH_RUN_INTEGRATION=1 + piper + [ml] for a real fine-tune",
)
def test_benchmark_trains_and_scores_real(tmp_path, monkeypatch):
    """Run the real benchmark end-to-end on piper speech; assert a sane WER bound."""
    # The suite forces simulation (conftest); clear it so training is real here.
    monkeypatch.delenv("TALKTEACH_FORCE_SIMULATION", raising=False)
    from talkteach.benchmark import run_benchmark

    config = {
        "name": "test",
        "language": "en",
        "train_clips": 5,
        "eval_clips": 3,
        "tts": [
            {
                "provider": "piper",
                "voice": "en_US-lessac-low",
                "download_dir": str(tmp_path / "voices"),
            }
        ],
        "engines": [
            {
                "name": "whisper",
                "plan": {
                    "engine": "whisper_lora",
                    "base_checkpoint": "openai/whisper-tiny",
                    "compute": "cpu",
                    "precision": "fp32",
                    "epochs": 1,
                    "batch_size": 2,
                    "learning_rate": 1e-3,
                    "lora_rank": 4,
                },
            }
        ],
    }
    report = run_benchmark(config, tmp_path / "run")
    ok = [c for c in report.cells if c.status == "ok"]
    assert ok, f"no cell completed: {[(c.engine, c.status, c.detail) for c in report.cells]}"
    cell = ok[0]
    # Clean synthetic speech through whisper-tiny → low WER on the shared eval set.
    assert cell.wer is not None and cell.wer <= _CLEAN_WER_MAX
    assert cell.smartness is not None and 0.0 <= cell.smartness <= 1.0
    assert cell.train_seconds is not None and cell.train_seconds > 0
    assert cell.train_good_fraction == 1.0  # piper clips pass the quality gate
