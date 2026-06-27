"""Tests for the director — the zero-config policy that is the app's real IP.

These cover the decision boundaries (engine/model/precision/batch/schedule) and
the sufficiency gate, all pure-logic and GPU-free.
"""

from __future__ import annotations

from talkteach.director import (
    Compute,
    DataProfile,
    EngineKind,
    GateStatus,
    HardwareProfile,
    Precision,
    build_plan,
    probe_language,
    sufficiency,
)


def hw(compute=Compute.CPU, vram=0.0, ram=16.0, cores=8, disk=100.0, name=None):
    return HardwareProfile(
        compute=compute,
        gpu_name=name,
        vram_gib=vram,
        ram_gib=ram,
        cpu_cores=cores,
        free_disk_gib=disk,
    )


def data(good=40.0, total=50.0, clips=60):
    return DataProfile(good_minutes=good, total_minutes=total, clip_count=clips)


# --- engine / model selection by hardware ------------------------------------


def test_big_gpu_picks_whisper_medium_fp16():
    plan = build_plan(hw(Compute.CUDA, vram=24, name="RTX 4090"), data(), probe_language("en"))
    assert plan.engine is EngineKind.WHISPER_LORA
    assert plan.base_checkpoint == "openai/whisper-medium"
    assert plan.precision is Precision.FP16
    assert plan.batch_size == 8


def test_mid_gpu_picks_whisper_small():
    plan = build_plan(hw(Compute.CUDA, vram=8, name="RTX 3070"), data(), probe_language("en"))
    assert plan.base_checkpoint == "openai/whisper-small"
    assert plan.precision is Precision.FP16


def test_cpu_only_picks_tiny_int8():
    plan = build_plan(hw(Compute.CPU), data(), probe_language("en"))
    assert plan.base_checkpoint == "openai/whisper-tiny"
    assert plan.precision is Precision.INT8
    assert plan.compute is Compute.CPU
    assert plan.batch_size == 1


def test_unsupported_language_with_enough_data_switches_to_wav2vec2():
    # A language outside Whisper's set, with enough data → XLS-R/wav2vec2.
    plan = build_plan(hw(Compute.CUDA, vram=12), data(good=40), probe_language("xx"))
    assert plan.engine is EngineKind.WAV2VEC2_CTC
    assert "wav2vec2" in plan.base_checkpoint


def test_unsupported_language_with_tiny_data_stays_whisper():
    # Too little data to train a CTC head from scratch → stick with Whisper.
    plan = build_plan(hw(Compute.CUDA, vram=12), data(good=10, total=12), probe_language("xx"))
    assert plan.engine is EngineKind.WHISPER_LORA


# --- schedule by data size ----------------------------------------------------


def test_tiny_data_freezes_encoder_and_more_epochs():
    plan = build_plan(hw(Compute.CUDA, vram=12), data(good=15, total=18), probe_language("en"))
    assert plan.freeze_encoder is True
    assert plan.epochs == 12
    assert plan.lora_rank == 8


def test_large_data_lower_lr_no_freeze():
    plan = build_plan(hw(Compute.CUDA, vram=24), data(good=300, total=320), probe_language("en"))
    assert plan.freeze_encoder is False
    assert plan.epochs == 5
    assert plan.learning_rate == 8e-5
    assert plan.lora_rank == 16


def test_effective_batch_is_stable():
    plan = build_plan(hw(Compute.CUDA, vram=24), data(), probe_language("en"))
    assert plan.effective_batch == plan.batch_size * plan.grad_accum
    assert 12 <= plan.effective_batch <= 24


def test_plan_always_has_rationale_and_safety():
    plan = build_plan(hw(Compute.CPU), data(), probe_language(None))
    assert plan.rationale, "every decision must be explainable in Grown-up mode"
    assert plan.seed == 1234
    assert plan.grad_clip == 1.0


# --- language probe -----------------------------------------------------------


def test_language_probe_none_is_autodetect():
    lp = probe_language(None)
    assert lp.auto_detect is True
    assert lp.is_whisper_supported is True


def test_language_probe_known_and_unknown():
    assert probe_language("EN").is_whisper_supported is True
    assert probe_language("en").code == "en"
    assert probe_language("zz").is_whisper_supported is False


# --- sufficiency gate ---------------------------------------------------------


def test_sufficiency_blocks_when_too_little():
    profile = DataProfile(good_minutes=12, total_minutes=15, clip_count=20)
    res = sufficiency(profile, target_minutes=30)
    assert res.status is GateStatus.BLOCKED
    assert res.fraction < 1.0
    assert any("more minute" in m for m in res.messages)


def test_sufficiency_ready_when_enough():
    profile = DataProfile(good_minutes=35, total_minutes=40, clip_count=60)
    res = sufficiency(profile, target_minutes=30)
    assert res.status is GateStatus.READY
    assert res.fraction == 1.0


def test_sufficiency_warns_on_poor_quality_fraction():
    # Lots of audio but most of it bad.
    profile = DataProfile(good_minutes=31, total_minutes=100, clip_count=120)
    res = sufficiency(profile, target_minutes=30)
    assert res.status is GateStatus.READY  # enough good minutes...
    assert any("quiet" in m or "noisy" in m for m in res.messages)  # ...but warned


def test_sufficiency_target_has_floor():
    profile = DataProfile(good_minutes=21, total_minutes=22, clip_count=30)
    res = sufficiency(profile, target_minutes=5)
    assert res.target_minutes >= 20.0  # MIN_TARGET_MINUTES floor
