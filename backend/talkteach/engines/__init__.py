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

    Only :attr:`EngineKind.WHISPER_LORA` is wired up (Phase 0/1). The NeMo-RNNT
    and Wav2Vec2-CTC adapters are Phase 2 and raise :class:`NotImplementedError`
    with a clear message so callers fail loudly rather than silently.
    """
    if kind == EngineKind.WHISPER_LORA:
        return WhisperLoRAEngine()
    raise NotImplementedError(
        f"The '{kind.value}' engine is planned for Phase 2 and is not available yet. "
        "Phase 0/1 ships the Whisper+LoRA engine."
    )
