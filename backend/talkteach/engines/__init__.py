"""TalkTeach engine adapters — the only place heavy ML libraries are touched.

This package imports cleanly with NO ML frameworks installed: the contract
(:mod:`~talkteach.engines.base`) and the registry below are dependency-light, and
each adapter guards its heavy imports behind function-local try/except. Use
:func:`get_engine` to obtain the adapter for a director-selected
:class:`~talkteach.director.types.EngineKind`.
"""

from __future__ import annotations

from talkteach.director.types import EngineKind

from .base import (
    ASREngine,
    EngineUnavailableError,
    ExportResult,
    ProgressCallback,
    ShouldStop,
    TrainProgress,
)
from .whisper_lora import WhisperLoRAEngine

__all__ = [
    "ASREngine",
    "EngineUnavailableError",
    "ExportResult",
    "ProgressCallback",
    "ShouldStop",
    "TrainProgress",
    "WhisperLoRAEngine",
    "get_engine",
]


def get_engine(kind: EngineKind) -> ASREngine:
    """Return the engine adapter for ``kind``.

    :attr:`EngineKind.WHISPER_LORA` and :attr:`EngineKind.WAV2VEC2_CTC` are **real**
    fine-tune engines (Tier A/B) and are compared head-to-head by the benchmark.
    :attr:`EngineKind.NEMO_RNNT` is a **real but GPU/opt-in** path: it needs
    ``nemo_toolkit`` + CUDA and self-reports unavailable otherwise, so the app's
    training loop falls back to Whisper-LoRA and a child's flow never dead-ends.
    See project/docs/BENCHMARKING.md for the engine tiering.
    """
    if kind == EngineKind.WHISPER_LORA:
        return WhisperLoRAEngine()
    if kind == EngineKind.NEMO_RNNT:
        from .nemo_rnnt import NeMoRNNTEngine

        return NeMoRNNTEngine()
    if kind == EngineKind.WAV2VEC2_CTC:
        from .wav2vec2_ctc import Wav2Vec2CTCEngine

        return Wav2Vec2CTCEngine()
    raise NotImplementedError(f"Unknown engine kind: {kind!r}")
