"""Shared, framework-free data model for the TalkTeach director.

These dataclasses are the contract between the hardware/data/language probes,
the policy that combines them, the engines, and the FastAPI layer. They contain
no heavy dependencies (no torch/transformers) so they import anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Compute(str, Enum):
    """The kind of accelerator the director decided to target."""

    CUDA = "cuda"
    MPS = "mps"  # Apple Silicon
    CPU = "cpu"


class Precision(str, Enum):
    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"


class EngineKind(str, Enum):
    """Which training engine adapter the director selected."""

    WHISPER_LORA = "whisper_lora"  # default, multilingual, low-VRAM
    NEMO_RNNT = "nemo_rnnt"  # streaming / edge (Parakeet/FastConformer)
    WAV2VEC2_CTC = "wav2vec2_ctc"  # low-resource / unseen languages


@dataclass(frozen=True)
class HardwareProfile:
    """Result of the hardware probe. All sizes in GiB."""

    compute: Compute
    gpu_name: str | None
    vram_gib: float
    ram_gib: float
    cpu_cores: int
    free_disk_gib: float

    @property
    def has_gpu(self) -> bool:
        return self.compute in (Compute.CUDA, Compute.MPS)


@dataclass(frozen=True)
class DataProfile:
    """Result of the data probe — what the user has actually recorded."""

    good_minutes: float  # minutes of audio that passed quality checks
    total_minutes: float  # all recorded audio, good or not
    clip_count: int
    distinct_speakers: int = 1

    @property
    def good_fraction(self) -> float:
        if self.total_minutes <= 0:
            return 0.0
        return self.good_minutes / self.total_minutes


@dataclass(frozen=True)
class LanguageProfile:
    """Result of the language probe."""

    code: str | None  # ISO 639-1/3, or None for "let it figure out"
    is_whisper_supported: bool  # in Whisper's ~99-language set
    auto_detect: bool = False


@dataclass(frozen=True)
class TrainingPlan:
    """The fully-resolved, zero-config plan the director hands to an engine.

    Every field here is a decision the user never had to make. This object is
    what makes the "Teach!" button a single tap.
    """

    engine: EngineKind
    base_checkpoint: str
    compute: Compute
    precision: Precision
    batch_size: int
    grad_accum: int
    learning_rate: float
    epochs: int
    warmup_ratio: float
    early_stop_patience: int  # in eval rounds
    lora_rank: int
    lora_alpha: int
    freeze_encoder: bool
    seed: int
    grad_clip: float
    # Human-readable trace of *why* each choice was made — surfaced in Grown-up mode.
    rationale: list[str] = field(default_factory=list)

    @property
    def effective_batch(self) -> int:
        return self.batch_size * self.grad_accum


class GateStatus(str, Enum):
    BLOCKED = "blocked"  # not enough good data — "Teach!" stays asleep
    READY = "ready"


@dataclass(frozen=True)
class SufficiencyResult:
    """Drives the friendly meter ("12 of 30 minutes") and the Teach! gate."""

    status: GateStatus
    good_minutes: float
    target_minutes: float
    messages: list[str] = field(default_factory=list)

    @property
    def fraction(self) -> float:
        if self.target_minutes <= 0:
            return 1.0
        return min(1.0, self.good_minutes / self.target_minutes)
