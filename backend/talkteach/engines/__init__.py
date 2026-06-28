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

    :attr:`EngineKind.WHISPER_LORA` is fully implemented (Phase 0/1). The
    NeMo-RNNT and Wav2Vec2-CTC adapters are **Phase 2 scaffolds** that satisfy the
    :class:`ASREngine` contract but report themselves unavailable (their heavy
    methods raise :class:`EngineUnavailableError`). The app's training loop checks
    ``is_available()`` and gracefully falls back to Whisper-LoRA, so a
    director-selected-but-unbuilt engine never dead-ends a child's flow.
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
