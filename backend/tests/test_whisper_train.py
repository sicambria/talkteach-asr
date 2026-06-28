"""Unit tests for the *pure* parts of the real Whisper-LoRA training path.

These cover the logic most likely to harbour bugs — plan → training-args mapping,
WER/CER, the smartness mapping, the simulate/real dispatch policy, checkpoint
discovery, and the NaN-rollback guard — with NO torch/transformers/network/GPU.
The end-to-end fine-tune itself is covered by the opt-in `integration` marker
(see project/docs/DECISIONS.md D-002 and tests/test_integration_train.py).

jiwer is light (no torch); the two WER/CER tests skip cleanly if it's absent.
"""

from __future__ import annotations

import importlib.util

import pytest

from talkteach.director.types import Compute, EngineKind, Precision, TrainingPlan
from talkteach.engines import _whisper_train as wt

_HAS_JIWER = importlib.util.find_spec("jiwer") is not None


def _plan(**overrides) -> TrainingPlan:
    base = {
        "engine": EngineKind.WHISPER_LORA,
        "base_checkpoint": "openai/whisper-tiny",
        "compute": Compute.CPU,
        "precision": Precision.FP16,
        "batch_size": 4,
        "grad_accum": 4,
        "learning_rate": 1e-4,
        "epochs": 8,
        "warmup_ratio": 0.1,
        "early_stop_patience": 3,
        "lora_rank": 8,
        "lora_alpha": 16,
        "freeze_encoder": True,
        "seed": 1234,
        "grad_clip": 1.0,
        "rationale": [],
    }
    base.update(overrides)
    return TrainingPlan(**base)


# --- training_arguments_kwargs: the plan → HF args contract -------------------


def test_training_args_map_plan_faithfully():
    kw = wt.training_arguments_kwargs(_plan(), "/tmp/run")
    assert kw["per_device_train_batch_size"] == 4
    assert kw["gradient_accumulation_steps"] == 4
    assert kw["learning_rate"] == 1e-4
    assert kw["num_train_epochs"] == 8
    assert kw["warmup_ratio"] == 0.1
    assert kw["output_dir"] == "/tmp/run"


def test_training_args_encode_safety_rails():
    # Safety rail #3: fixed seed + gradient clipping must flow into the args.
    kw = wt.training_arguments_kwargs(_plan(seed=777, grad_clip=0.5), "/tmp/run")
    assert kw["seed"] == 777
    assert kw["max_grad_norm"] == 0.5
    # Lower WER is better, and we never phone home while training.
    assert kw["greater_is_better"] is False
    assert kw["metric_for_best_model"] == "wer"
    assert kw["report_to"] == []


def test_training_args_precision_flags():
    assert wt.training_arguments_kwargs(_plan(precision=Precision.FP16), "x")["fp16"] is True
    assert wt.training_arguments_kwargs(_plan(precision=Precision.FP16), "x")["bf16"] is False
    bf = wt.training_arguments_kwargs(_plan(precision=Precision.BF16), "x")
    assert bf["bf16"] is True and bf["fp16"] is False
    int8 = wt.training_arguments_kwargs(_plan(precision=Precision.INT8), "x")
    assert int8["fp16"] is False and int8["bf16"] is False


# --- simulate/real dispatch (D-012) -------------------------------------------


def test_should_simulate_when_deps_missing():
    sim, reason = wt.should_simulate([{"path": __file__}], has_train_deps=False)
    assert sim is True and "deps" in reason


def test_should_simulate_when_no_clip_exists(monkeypatch):
    monkeypatch.delenv("TALKTEACH_FORCE_SIMULATION", raising=False)
    sim, reason = wt.should_simulate(
        [{"path": "/does/not/exist.wav", "text": "hi"}], has_train_deps=True
    )
    assert sim is True and "disk" in reason


def test_should_simulate_force_env(monkeypatch):
    monkeypatch.setenv("TALKTEACH_FORCE_SIMULATION", "1")
    sim, reason = wt.should_simulate([{"path": __file__}], has_train_deps=True)
    assert sim is True and "FORCE" in reason


def test_should_run_real_when_clip_exists(monkeypatch):
    # Clear the suite-wide force-simulation pin (conftest) for this one case.
    monkeypatch.delenv("TALKTEACH_FORCE_SIMULATION", raising=False)
    # An existing file (this test module) + deps present → real path.
    sim, reason = wt.should_simulate([{"path": __file__, "text": "x"}], has_train_deps=True)
    assert sim is False and reason == ""


# --- smartness mapping (#2) ---------------------------------------------------


def test_smartness_from_wer_clamps_and_inverts():
    assert wt.smartness_from_wer(0.0) == 1.0
    assert wt.smartness_from_wer(1.0) == 0.0
    assert wt.smartness_from_wer(0.25) == pytest.approx(0.75)
    # WER can exceed 1.0 (more errors than words) → smartness floored at 0.
    assert wt.smartness_from_wer(1.7) == 0.0


# --- checkpoint discovery (#1/#17) --------------------------------------------


def test_find_latest_checkpoint_picks_highest_step(tmp_path):
    for step in (5, 40, 12):
        (tmp_path / f"checkpoint-{step}").mkdir()
    (tmp_path / "checkpoint-notanumber").mkdir()
    latest = wt.find_latest_checkpoint(str(tmp_path))
    assert latest is not None and latest.endswith("checkpoint-40")


def test_find_latest_checkpoint_none_when_empty(tmp_path):
    assert wt.find_latest_checkpoint(str(tmp_path)) is None
    assert wt.find_latest_checkpoint(str(tmp_path / "missing")) is None


# --- NaN-rollback guard (safety rail #3) --------------------------------------


def test_nan_guard_trips_on_non_finite():
    g = wt.NanRollbackGuard()
    g.observe_good_checkpoint("/runs/checkpoint-10")
    assert g.should_rollback(0.42) is False
    assert g.tripped is False
    assert g.should_rollback(float("nan")) is True
    assert g.tripped is True
    assert g.last_good_checkpoint == "/runs/checkpoint-10"


def test_nan_guard_detects_inf():
    g = wt.NanRollbackGuard()
    assert g.is_finite(1.0) is True
    assert g.is_finite(float("inf")) is False
    assert g.should_rollback(float("inf")) is True


# --- WER / CER (#2) -----------------------------------------------------------


@pytest.mark.skipif(not _HAS_JIWER, reason="jiwer not installed")
def test_wer_perfect_and_imperfect():
    assert wt.wer(["the cat sat"], ["the cat sat"]) == pytest.approx(0.0)
    # One substitution out of three words → 1/3.
    assert wt.wer(["the cat sat"], ["the dog sat"]) == pytest.approx(1 / 3)
    # Normalisation: case + whitespace differences don't count as errors.
    assert wt.wer(["The  Cat"], ["the cat"]) == pytest.approx(0.0)


@pytest.mark.skipif(not _HAS_JIWER, reason="jiwer not installed")
def test_cer_and_empty_reference_guard():
    assert wt.cer(["abc"], ["abc"]) == pytest.approx(0.0)
    # Empty reference set → defined as fully wrong rather than raising.
    assert wt.wer([""], ["something"]) == 1.0
    assert wt.cer([""], ["x"]) == 1.0
