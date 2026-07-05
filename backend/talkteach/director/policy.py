"""The director's policy — the real IP.

Maps (HardwareProfile, DataProfile, LanguageProfile) → a fully-resolved
TrainingPlan and a SufficiencyResult, so the child never sees a hyperparameter.

IMPORTANT (per the design report, Part B.5): every threshold and hyperparameter
here is a *proposed design default* drawn from the LoRA/Whisper literature, NOT
empirically tuned for this app. They are the initial policy the director ships
with; calibrate against real hardware/datasets in Phase 0–1 and refine from
telemetry. Each decision appends a human-readable line to `plan.rationale` so
"Grown-up mode" can show exactly why a choice was made.
"""

from __future__ import annotations

from .types import (
    Compute,
    DataProfile,
    EngineKind,
    GateStatus,
    HardwareProfile,
    LanguageProfile,
    Precision,
    SufficiencyResult,
    TrainingPlan,
)

# --- Tunable policy constants (proposed defaults; calibrate in Phase 0–1) ------
DEFAULT_SEED = 1234
DEFAULT_GRAD_CLIP = 1.0
MIN_TARGET_MINUTES = 20.0  # floor for the sufficiency gate
GOOD_FRACTION_FLOOR = 0.6  # if >40% of audio is poor, warn loudly

# VRAM tiers (GiB) → model size choices. From B.5.
_TIER_PARAKEET = 16.0
_TIER_WHISPER_SMALL = 6.0


def adaptive_target(lang: LanguageProfile) -> float:
    """Heuristic data-sufficiency target (minutes) by language difficulty (#35).

    Replaces the one-size 20–30 min floor: a language Whisper already knows well
    needs less new data to adapt; a language outside Whisper's set (we'd train a
    CTC head from a self-supervised base) needs more. Auto-detect leans easy
    (Whisper figures out the language). All values stay at/above the
    :data:`MIN_TARGET_MINUTES` floor and remain *proposed defaults* to calibrate
    (report B.5); a future version can learn this from telemetry.
    """
    if lang.auto_detect or lang.is_whisper_supported:
        return max(MIN_TARGET_MINUTES, 25.0)
    # Outside Whisper's set → adapting a base model needs noticeably more audio.
    return max(MIN_TARGET_MINUTES, 45.0)


# --- augmentation policy (#46) ------------------------------------------------
# Proposed thresholds (calibrate in Phase 0–1). Augmentation multiplies effective
# data, so it earns its cost most on tiny sets and is dialled back as data grows.
_AUG_TINY_MINUTES = 10.0  # below this: augment aggressively
_AUG_SMALL_MINUTES = 25.0  # below this: augment moderately


def augmentation_for(data: DataProfile):  # noqa: ANN201  (return type imported lazily)
    """Decide the augmentation recipe for this dataset (#46).

    The single biggest small-data accuracy win, so the director **auto-enables** it
    for tiny sets and tapers it off as ``good_minutes`` grows — the user never
    configures it. Returns a framework-free
    :class:`~talkteach.audio.augment.AugmentationConfig`. Thresholds are proposed
    defaults to calibrate (report B.5).
    """
    from talkteach.audio.augment import AugmentationConfig

    minutes = data.good_minutes
    if minutes >= _AUG_SMALL_MINUTES:
        return AugmentationConfig(
            enabled=False,
            reason=f"{minutes:.0f} min is plenty — augmentation off to avoid distorting good data",
        )
    if minutes >= _AUG_TINY_MINUTES:
        return AugmentationConfig(
            enabled=True,
            speed_factors=(0.95, 1.0, 1.05),
            pitch_semitones=(-1.0, 0.0, 1.0),
            noise_snr_db=20.0,
            spec_time_masks=1,
            spec_time_width=10,
            spec_freq_masks=1,
            spec_freq_width=8,
            reason=f"{minutes:.0f} min is a bit small — moderate augmentation to stretch it",
            labels=("speed", "pitch", "noise", "spec_augment"),
        )
    return AugmentationConfig(
        enabled=True,
        speed_factors=(0.9, 0.95, 1.0, 1.05, 1.1),
        pitch_semitones=(-2.0, -1.0, 0.0, 1.0, 2.0),
        noise_snr_db=15.0,
        spec_time_masks=2,
        spec_time_width=12,
        spec_freq_masks=2,
        spec_freq_width=10,
        reason=f"only {minutes:.0f} min — aggressive augmentation to multiply tiny data",
        labels=("speed", "pitch", "noise", "spec_augment"),
    )


def sufficiency(data: DataProfile, target_minutes: float = 30.0) -> SufficiencyResult:
    """Drive the friendly meter and the Teach! gate.

    The gate stays BLOCKED until there are enough *good* minutes. Messages tell
    the novice exactly what is missing, in plain language.
    """
    target = max(MIN_TARGET_MINUTES, target_minutes)
    messages: list[str] = []
    status = GateStatus.READY if data.good_minutes >= target else GateStatus.BLOCKED

    if status is GateStatus.BLOCKED:
        need = target - data.good_minutes
        messages.append(
            f"Add about {need:.0f} more minute(s) of clear talking "
            f"({data.good_minutes:.0f} of {target:.0f} so far)."
        )
    if data.total_minutes > 0 and data.good_fraction < GOOD_FRACTION_FLOOR:
        messages.append(
            "A lot of the sound was too quiet, too loud, or too noisy — "
            "try recording somewhere calm and close to the mic."
        )
    if not messages:
        messages.append("Looks great — ready to teach!")
    return SufficiencyResult(
        status=status,
        good_minutes=round(data.good_minutes, 1),
        target_minutes=target,
        messages=messages,
    )


def _choose_engine_and_model(
    hw: HardwareProfile, lang: LanguageProfile, data: DataProfile, rationale: list[str]
) -> tuple[EngineKind, str, Precision]:
    """Pick engine + base checkpoint + precision from hardware and language."""
    # Languages Whisper doesn't cover fine-tune better from a self-supervised
    # multilingual base — but only once there's enough data to train a CTC head.
    if not lang.is_whisper_supported and data.good_minutes >= MIN_TARGET_MINUTES:
        rationale.append(
            f"Language '{lang.code}' isn't in Whisper's set → using wav2vec2/XLS-R "
            "(self-supervised multilingual base) which adapts better to new languages."
        )
        prec = Precision.FP16 if hw.compute is Compute.CUDA else Precision.INT8
        return EngineKind.WAV2VEC2_CTC, "facebook/wav2vec2-xls-r-300m", prec

    if hw.compute is Compute.CUDA and hw.vram_gib >= _TIER_PARAKEET:
        rationale.append(
            f"{hw.vram_gib:.0f} GiB VRAM ≥ {_TIER_PARAKEET:.0f} → Whisper-medium LoRA "
            "in fp16 (plenty of headroom)."
        )
        return EngineKind.WHISPER_LORA, "openai/whisper-medium", Precision.FP16

    if hw.compute in (Compute.CUDA, Compute.MPS) and hw.vram_gib >= _TIER_WHISPER_SMALL:
        rationale.append(
            f"{hw.vram_gib:.0f} GiB accelerator memory → Whisper-small LoRA in fp16 "
            "(fast, low-VRAM, hard to diverge)."
        )
        return EngineKind.WHISPER_LORA, "openai/whisper-small", Precision.FP16

    rationale.append(
        "No usable GPU → Whisper-tiny LoRA in int8 on CPU (slow but safe). "
        "Offer one-tap cloud for a real GPU."
    )
    return EngineKind.WHISPER_LORA, "openai/whisper-tiny", Precision.INT8


def _choose_batch(hw: HardwareProfile, rationale: list[str]) -> tuple[int, int]:
    """Pick (batch_size, grad_accum) targeting a stable effective batch of ~16."""
    target_effective = 16
    if hw.compute is Compute.CUDA and hw.vram_gib >= _TIER_PARAKEET:
        bs = 8
    elif hw.has_gpu and hw.vram_gib >= _TIER_WHISPER_SMALL:
        bs = 4
    else:
        bs = 1
    accum = max(1, round(target_effective / bs))
    rationale.append(
        f"Batch {bs} × grad-accum {accum} → effective batch {bs * accum} "
        "(stable updates within the memory budget)."
    )
    return bs, accum


def _choose_schedule(
    data: DataProfile, rationale: list[str]
) -> tuple[int, float, float, int, bool]:
    """From dataset minutes pick (epochs, lr, warmup_ratio, patience, freeze_encoder)."""
    minutes = data.good_minutes
    if minutes < 30:
        epochs, lr, freeze = 12, 1e-4, True
        rationale.append(
            f"Only {minutes:.0f} min of data → 12 epochs, freeze the encoder and "
            "train just the head + LoRA so it can't overfit."
        )
    elif minutes < 120:
        epochs, lr, freeze = 8, 1e-4, False
        rationale.append(f"{minutes:.0f} min → 8 epochs, full LoRA, LR 1e-4 cosine.")
    else:
        epochs, lr, freeze = 5, 8e-5, False
        rationale.append(f"{minutes:.0f} min (plenty) → 5 epochs, lower LR 8e-5 for stability.")
    warmup_ratio = 0.1
    patience = 3  # eval rounds of no val-WER improvement → early stop
    return epochs, lr, warmup_ratio, patience, freeze


def build_plan(hw: HardwareProfile, data: DataProfile, lang: LanguageProfile) -> TrainingPlan:
    """Combine all three probes into one zero-config TrainingPlan."""
    rationale: list[str] = []
    engine, base, precision = _choose_engine_and_model(hw, lang, data, rationale)
    batch_size, grad_accum = _choose_batch(hw, rationale)
    epochs, lr, warmup, patience, freeze = _choose_schedule(data, rationale)

    # LoRA defaults from B.5: rank 8–16, alpha = 2×rank. Smaller rank on tiny data.
    lora_rank = 8 if data.good_minutes < 30 else 16
    lora_alpha = lora_rank * 2
    rationale.append(f"LoRA rank {lora_rank}, alpha {lora_alpha}.")
    rationale.append(
        f"Safety rails: fixed seed {DEFAULT_SEED}, grad-clip {DEFAULT_GRAD_CLIP}, "
        f"NaN-guard with rollback, early-stop patience {patience}."
    )

    return TrainingPlan(
        engine=engine,
        base_checkpoint=base,
        compute=hw.compute,
        precision=precision,
        batch_size=batch_size,
        grad_accum=grad_accum,
        learning_rate=lr,
        epochs=epochs,
        warmup_ratio=warmup,
        early_stop_patience=patience,
        lora_rank=lora_rank,
        lora_alpha=lora_alpha,
        freeze_encoder=freeze,
        seed=DEFAULT_SEED,
        grad_clip=DEFAULT_GRAD_CLIP,
        rationale=rationale,
    )
