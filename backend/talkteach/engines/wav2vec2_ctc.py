"""wav2vec2 / XLS-R CTC engine adapter — low-resource languages (roadmap #26).

A **real** CTC fine-tune (Tier B), not a scaffold. The director selects this engine
for languages outside Whisper's set once there's enough data (``director/policy.py``),
and the benchmark (``talkteach.benchmark``) compares it head-to-head with Whisper-LoRA
on the same TTS speech.

Dependency philosophy matches :mod:`whisper_lora`: every heavy import (torch /
transformers / datasets / soundfile) is function-local, so this module imports with
none of them present. Real work that needs a missing dep raises
:class:`EngineUnavailableError`. The real loop lives in :mod:`_wav2vec2_train` (kept
separate so its dataset/collator/metrics stay torch-free at import); when deps or
real audio are absent, training falls back to the shared dependency-free simulation
(:func:`_train_common.simulate_training`). Export targets ONNX (via 🤗 optimum) for
sherpa-onnx streaming/edge use. See project/docs/ENGINES.md and BENCHMARKING.md.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os

from talkteach.director.types import TrainingPlan

from .base import (
    ASREngine,
    EngineUnavailableError,
    ExportResult,
    ProgressCallback,
    ShouldStop,
    TrainProgress,
)

# torch+transformers are enough to train a CTC head; datasets/soundfile travel with
# them in the [ml] extra. faster paths/inference reuse transformers directly.
_TRAIN_DEPS = ("torch", "transformers")
_EXPORT_DEP = "optimum"
_INSTALL_HINT = "install talkteach-backend[ml] to train"


def _missing(modules: tuple[str, ...]) -> list[str]:
    missing = []
    for mod in modules:
        try:
            found = importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(mod)
    return missing


def _has(module: str) -> bool:
    return not _missing((module,))


class Wav2Vec2CTCEngine(ASREngine):
    """wav2vec2 CTC adapter. See module docstring for the dependency policy."""

    def name(self) -> str:
        return "wav2vec2 / XLS-R (CTC)"

    def is_available(self) -> tuple[bool, str]:
        missing = _missing(_TRAIN_DEPS)
        if missing:
            return False, f"missing {', '.join(missing)}: {_INSTALL_HINT}"
        return True, ""

    def train(
        self,
        plan: TrainingPlan,
        manifest: list[dict],
        workdir: str,
        progress: ProgressCallback | None = None,
        should_stop: ShouldStop | None = None,
    ) -> TrainProgress:
        """Run the real CTC ``Trainer`` loop, or the dependency-free simulation.

        Same dispatch as Whisper (D-012): real when deps are present, the run isn't
        force-simulated, and at least one manifest clip exists on disk; otherwise
        simulate so the app stays exercisable on a GPU-less machine.
        """
        from . import _train_common as common
        from . import _wav2vec2_train as w2v

        has_deps = not _missing(_TRAIN_DEPS)
        simulate, reason = common.should_simulate(manifest, has_train_deps=has_deps)
        if simulate:
            if reason:
                logging.getLogger("talkteach.train").info("Simulating training: %s", reason)
            return common.simulate_training(
                plan, manifest, workdir, progress, should_stop, engine_label="wav2vec2"
            )
        return w2v.run_real_training(plan, manifest, workdir, progress, should_stop)

    def transcribe(
        self, audio_path: str, model_dir: str | None = None, base_checkpoint: str | None = None
    ) -> str:
        """Greedy-decode one clip with the fine-tuned CTC model in ``model_dir``.

        With no trained ``model_dir`` but a ``base_checkpoint`` (benchmark delta
        pass), score the untrained base model named by the HF id instead.
        """
        if _missing(_TRAIN_DEPS):
            raise EngineUnavailableError(f"'Try it' needs torch + transformers — {_INSTALL_HINT}.")
        from . import _wav2vec2_train as w2v

        if model_dir and os.path.isfile(os.path.join(model_dir, "config.json")):
            return w2v.transcribe(audio_path, model_dir)
        if not model_dir and base_checkpoint:
            return w2v.transcribe(audio_path, base_checkpoint)
        raise EngineUnavailableError(
            "wav2vec2 transcribe needs a trained model_dir (run train first)."
        )

    def export(self, model_dir: str, out_dir: str, fmt: str = "onnx") -> ExportResult:
        """Export the fine-tuned CTC model to ONNX (sherpa-onnx streaming/edge).

        ONNX is the natural portable target for a CTC model; CTranslate2 (Whisper's
        default) does not cover wav2vec2. When optimum is missing we write a manifest
        describing what *would* be produced so the flow never dead-ends.
        """
        os.makedirs(out_dir, exist_ok=True)
        # Only convert a real trained model; a simulation run dir (JSON checkpoints
        # only) falls through to the dry-run manifest.
        real_model = os.path.isfile(os.path.join(model_dir, "config.json"))
        if real_model and fmt in ("onnx", "ort") and _has(_EXPORT_DEP) and _has("transformers"):
            from optimum.exporters.onnx import main_export  # type: ignore

            main_export(model_dir, output=out_dir, task="automatic-speech-recognition")
            return ExportResult(
                format="onnx",
                path=out_dir,
                notes="Exported to ONNX. Run with sherpa-onnx for streaming/edge use.",
            )

        manifest_path = os.path.join(out_dir, "export_manifest.json")
        needed = _EXPORT_DEP if fmt in ("onnx", "ort") else f"a converter for '{fmt}'"
        manifest = {
            "would_export": {"source_model_dir": model_dir, "format": fmt},
            "status": "dry-run",
            "missing_dependency": needed,
            "how_to_fix": "install talkteach-backend[export]",
        }
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        return ExportResult(
            format="manifest",
            path=manifest_path,
            notes=(
                f"Dry run: real export to '{fmt}' needs {needed}. "
                "Wrote a manifest; install talkteach-backend[export] to do it for real."
            ),
        )
