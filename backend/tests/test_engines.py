"""Tests for the engine adapter layer.

These run with NO heavy ML deps installed (torch/transformers/peft/faster-whisper
are not in the test environment). They prove:
  * the package import-guards correctly (importing it here can't fail),
  * is_available() reports the missing deps by name,
  * the dependency-free simulation train drives the UI contract end-to-end,
  * cooperative cancellation actually stops the run,
  * inference raises a friendly error when its dep is absent,
  * the engine registry maps/rejects EngineKinds as designed.
"""

from __future__ import annotations

import os

import pytest

# Importing all of this with zero ML deps is itself the first assertion.
from talkteach.engines import get_engine
from talkteach.engines.base import (
    ASREngine,
    EngineUnavailableError,
    ExportResult,
    TrainProgress,
)
from talkteach.engines.whisper_lora import WhisperLoRAEngine
from talkteach.director.types import Compute, EngineKind, Precision, TrainingPlan


def _make_plan(epochs: int = 3) -> TrainingPlan:
    """Construct a TrainingPlan directly with all required fields."""
    return TrainingPlan(
        engine=EngineKind.WHISPER_LORA,
        base_checkpoint="openai/whisper-small",
        compute=Compute.CPU,
        precision=Precision.FP32,
        batch_size=2,
        grad_accum=1,
        learning_rate=1e-4,
        epochs=epochs,
        warmup_ratio=0.1,
        early_stop_patience=2,
        lora_rank=8,
        lora_alpha=16,
        freeze_encoder=True,
        seed=1234,
        grad_clip=1.0,
        rationale=["test plan"],
    )


def test_engine_instantiates_and_is_asreengine():
    eng = WhisperLoRAEngine()
    assert isinstance(eng, ASREngine)
    assert isinstance(eng.name(), str) and eng.name()


def test_is_available_reports_missing_module():
    ok, msg = WhisperLoRAEngine().is_available()
    assert ok is False
    # The message must name a specific missing training dep.
    assert any(mod in msg for mod in ("torch", "transformers", "peft"))


def test_simulation_train_drives_progress_to_completion(tmp_path):
    eng = WhisperLoRAEngine()
    plan = _make_plan(epochs=3)
    manifest = [{"path": "a.wav", "text": "hello"}]
    seen: list[TrainProgress] = []

    final = eng.train(plan, manifest, str(tmp_path), progress=seen.append)

    # Callback was actually called.
    assert seen, "progress callback was never invoked"

    # Fractions are non-decreasing and reach ~1.0.
    fractions = [p.fraction for p in seen]
    assert all(b >= a - 1e-9 for a, b in zip(fractions, fractions[1:]))
    assert fractions[-1] == pytest.approx(1.0)

    # Final state: returned object AND last callback both report done at 1.0.
    assert final.done is True
    assert final.failed is False
    assert final.fraction == pytest.approx(1.0)
    assert seen[-1].done is True
    assert seen[-1].fraction == pytest.approx(1.0)

    # Smartness rose and is a fraction in [0, 1].
    assert final.smartness is not None and 0.0 <= final.smartness <= 1.0

    # A checkpoint file exists in the workdir, marked SIMULATION.
    ckpts = [f for f in os.listdir(tmp_path) if f.startswith("checkpoint_epoch_")]
    assert ckpts, "no checkpoint written"
    with open(tmp_path / ckpts[0], encoding="utf-8") as fh:
        assert "SIMULATION" in fh.read()


def test_should_stop_cancels_early(tmp_path):
    eng = WhisperLoRAEngine()
    plan = _make_plan(epochs=5)
    manifest = [{"path": "a.wav", "text": "hello"}]
    seen: list[TrainProgress] = []

    final = eng.train(
        plan,
        manifest,
        str(tmp_path),
        progress=seen.append,
        should_stop=lambda: True,  # cancel immediately
    )

    assert final.fraction < 1.0
    assert final.done is False
    assert "stop" in final.message.lower() or "cancel" in final.message.lower()


def test_transcribe_without_faster_whisper_raises():
    with pytest.raises(EngineUnavailableError):
        WhisperLoRAEngine().transcribe("a.wav")


def test_export_dry_run_writes_manifest(tmp_path):
    result = WhisperLoRAEngine().export(str(tmp_path / "model"), str(tmp_path / "out"))
    assert isinstance(result, ExportResult)
    # No ctranslate2 installed -> dry-run manifest fallback.
    assert result.format == "manifest"
    assert os.path.exists(result.path)


def test_get_engine_whisper_returns_adapter():
    assert isinstance(get_engine(EngineKind.WHISPER_LORA), WhisperLoRAEngine)


def test_get_engine_nemo_not_implemented():
    with pytest.raises(NotImplementedError):
        get_engine(EngineKind.NEMO_RNNT)
