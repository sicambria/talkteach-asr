"""NeMo / Parakeet RNN-T engine adapter — streaming / edge target (roadmap #25).

**Tier C scaffold** (DECISIONS.md D-001): implements the :class:`ASREngine`
contract and reports itself unavailable with a friendly, actionable message until
the NeMo backend is wired up. The director may select streaming/edge deployment;
this is where a FastConformer-Transducer (Parakeet) fine-tune + ONNX/sherpa
export will live. See docs/ENGINES.md for the build plan.

Keeping it as a real adapter (rather than a bare ``NotImplementedError``) means
the registry, the app's graceful-fallback, and Grown-up mode all treat it
uniformly: ``is_available()`` explains what's missing; the heavy work raises
:class:`EngineUnavailableError` so the flow degrades to Whisper-LoRA instead of
crashing.
"""

from __future__ import annotations

import importlib.util

from talkteach.director.types import TrainingPlan

from .base import (
    ASREngine,
    EngineUnavailableError,
    ExportResult,
    ProgressCallback,
    ShouldStop,
    TrainProgress,
)

_BACKEND = "nemo_toolkit"
_HINT = "the NeMo engine is planned for Phase 2 (install talkteach-backend[nemo])"


class NeMoRNNTEngine(ASREngine):
    def name(self) -> str:
        return "NeMo Parakeet (RNN-T)"

    def is_available(self) -> tuple[bool, str]:
        if importlib.util.find_spec(_BACKEND) is None:
            return False, _HINT
        # Backend present but the adapter itself is still a scaffold.
        return False, "NeMo backend found, but the TalkTeach adapter is not built yet (Phase 2)."

    def train(
        self,
        plan: TrainingPlan,
        manifest: list[dict],
        workdir: str,
        progress: ProgressCallback | None = None,
        should_stop: ShouldStop | None = None,
    ) -> TrainProgress:
        raise EngineUnavailableError(_HINT)

    def transcribe(self, audio_path: str, model_dir: str | None = None) -> str:
        raise EngineUnavailableError(_HINT)

    def export(self, model_dir: str, out_dir: str, fmt: str = "onnx") -> ExportResult:
        raise EngineUnavailableError(_HINT)
