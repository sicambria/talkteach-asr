"""wav2vec2 / XLS-R CTC engine adapter — low-resource languages (roadmap #26).

**Tier C scaffold** (DECISIONS.md D-001). The director already *selects* this
engine for languages outside Whisper's set once there's enough data
(``director/policy.py``); this adapter is where the self-supervised XLS-R base +
a CTC head fine-tune will live. Until built it reports itself unavailable with a
friendly message so the app gracefully falls back to Whisper-LoRA. See
docs/ENGINES.md.
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

_HINT = "the wav2vec2/XLS-R CTC engine is planned for Phase 2 (install talkteach-backend[ml])"


class Wav2Vec2CTCEngine(ASREngine):
    def name(self) -> str:
        return "wav2vec2 / XLS-R (CTC)"

    def is_available(self) -> tuple[bool, str]:
        if importlib.util.find_spec("transformers") is None:
            return False, _HINT
        return False, "transformers found, but the CTC adapter is not built yet (Phase 2)."

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

    def export(self, model_dir: str, out_dir: str, fmt: str = "ctranslate2") -> ExportResult:
        raise EngineUnavailableError(_HINT)
