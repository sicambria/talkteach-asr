"""Opt-in end-to-end test of the REAL Whisper-LoRA fine-tune (roadmap #1–5).

This is deliberately NOT part of the fast suite: it downloads ``whisper-tiny``
(~150 MB) and runs a genuine 1-epoch LoRA fit on a few synthetic clips on CPU.
Run it explicitly on a provisioned machine:

    TALKTEACH_RUN_INTEGRATION=1 .venv/bin/python -m pytest -m integration -q

It is the proof that the Tier-B training/eval/export code paths actually work
(DECISIONS.md D-002); CI and the sandbox skip it.
"""

from __future__ import annotations

import importlib.util
import os
import wave

import numpy as np
import pytest

pytestmark = pytest.mark.integration

_RUN = os.environ.get("TALKTEACH_RUN_INTEGRATION") == "1"
_HAS_DEPS = all(
    importlib.util.find_spec(m) is not None
    for m in ("torch", "transformers", "peft", "datasets", "jiwer", "soundfile")
)

skip = pytest.mark.skipif(
    not (_RUN and _HAS_DEPS),
    reason="set TALKTEACH_RUN_INTEGRATION=1 and install [ml] to run the real fine-tune",
)


def _write_tone_wav(path: str, freq: float, seconds: float = 1.0, sr: int = 16000) -> None:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    pcm = (0.2 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


@skip
def test_real_finetune_runs_and_reports_measured_smartness(tmp_path):
    from talkteach.director.types import Compute, EngineKind, Precision, TrainingPlan
    from talkteach.engines import _whisper_train as wt

    # A handful of real (synthetic) clips so the loop has something to fit.
    manifest = []
    for i in range(6):
        p = str(tmp_path / f"clip_{i}.wav")
        _write_tone_wav(p, freq=180 + 30 * i)
        manifest.append({"path": p, "text": f"sound number {i}"})

    plan = TrainingPlan(
        engine=EngineKind.WHISPER_LORA,
        base_checkpoint="openai/whisper-tiny",
        compute=Compute.CPU,
        precision=Precision.FP32,  # CPU: no fp16
        batch_size=2,
        grad_accum=1,
        learning_rate=1e-3,
        epochs=1,
        warmup_ratio=0.0,
        early_stop_patience=1,
        lora_rank=4,
        lora_alpha=8,
        freeze_encoder=True,
        seed=1234,
        grad_clip=1.0,
        rationale=[],
    )

    seen = []
    final = wt.run_real_training(
        plan, manifest, str(tmp_path / "run"), progress=seen.append, should_stop=None
    )

    # The run completed and reported a measured (not synthetic) smartness in range.
    assert final.done is True
    assert final.smartness is not None and 0.0 <= final.smartness <= 1.0
    # A real HF checkpoint or saved adapter exists (resume + export depend on it).
    out = tmp_path / "run"
    assert any(out.iterdir()), "training produced no artifacts"
