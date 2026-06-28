"""Build a *pinned* TrainingPlan from explicit config — for reproducible experiments.

In the product, :func:`talkteach.director.policy.build_plan` derives every
hyperparameter from the detected hardware/data/language so the child never sees a
knob. That is exactly wrong for a benchmark: to compare engines fairly you must
hold the hyperparameters fixed and known. :func:`plan_from_config` is the
experiment-only counterpart — it takes a plain dict (typically one cell of a
``benchmarks/*.yaml``) and returns a fully-specified :class:`TrainingPlan`,
bypassing the director's heuristics. Anything omitted falls back to a safe,
CPU-friendly default (with seed/grad-clip taken from the shipping policy), so a
partial config still produces a valid plan.

The product flow and the zero-config "Teach!" button do not use this module.
"""

from __future__ import annotations

from typing import Any

from . import policy
from .types import Compute, EngineKind, Precision, TrainingPlan

# Safe defaults: a tiny Whisper LoRA fit that runs on CPU. Chosen so an empty
# config still yields a runnable plan; benchmarks override what they care about.
_DEFAULTS: dict[str, Any] = {
    "engine": EngineKind.WHISPER_LORA,
    "base_checkpoint": "openai/whisper-tiny",
    "compute": Compute.CPU,
    "precision": Precision.FP32,
    "batch_size": 2,
    "grad_accum": 1,
    "learning_rate": 1e-4,
    "epochs": 3,
    "warmup_ratio": 0.1,
    "early_stop_patience": 3,  # no policy constant; matches the value the policy uses
    "lora_rank": 8,
    "freeze_encoder": True,
    "seed": policy.DEFAULT_SEED,
    "grad_clip": policy.DEFAULT_GRAD_CLIP,
}


def plan_from_config(cfg: dict[str, Any] | None = None) -> TrainingPlan:
    """Return a pinned :class:`TrainingPlan` from ``cfg`` (missing keys → defaults).

    Enum-typed fields accept their string value (e.g. ``engine: "whisper_lora"``,
    ``compute: "cpu"``, ``precision: "fp32"``) since the enums are ``str``-backed.
    ``lora_alpha`` defaults to ``2 * lora_rank`` when not given (the policy's ratio).
    Unknown keys raise ``KeyError`` so a typo in a benchmark config fails loudly.
    """
    cfg = dict(cfg or {})
    known = set(_DEFAULTS) | {"lora_alpha", "rationale"}
    unknown = set(cfg) - known
    if unknown:
        raise KeyError(f"unknown plan config keys: {sorted(unknown)}; known: {sorted(known)}")

    def pick(key: str) -> Any:
        return cfg.get(key, _DEFAULTS[key])

    lora_rank = int(pick("lora_rank"))
    return TrainingPlan(
        engine=EngineKind(pick("engine")),
        base_checkpoint=str(pick("base_checkpoint")),
        compute=Compute(pick("compute")),
        precision=Precision(pick("precision")),
        batch_size=int(pick("batch_size")),
        grad_accum=int(pick("grad_accum")),
        learning_rate=float(pick("learning_rate")),
        epochs=int(pick("epochs")),
        warmup_ratio=float(pick("warmup_ratio")),
        early_stop_patience=int(pick("early_stop_patience")),
        lora_rank=lora_rank,
        lora_alpha=int(cfg.get("lora_alpha", lora_rank * 2)),
        freeze_encoder=bool(pick("freeze_encoder")),
        seed=int(pick("seed")),
        grad_clip=float(pick("grad_clip")),
        rationale=list(cfg.get("rationale", ["pinned by plan_from_config (benchmark)"])),
    )
