"""Whisper + LoRA engine adapter (the director's default engine).

Why Whisper+LoRA is the default: multilingual coverage (~99 languages), strong
small/medium checkpoints, and LoRA/PEFT fine-tuning that fits in modest VRAM —
ideal for a family laptop. See ``director/policy.py`` for the selection logic.

Dependency philosophy
---------------------
Every heavy import (torch / transformers / peft / faster_whisper / ctranslate2)
is **function-local and guarded**. This module imports fine with none of them
installed. Real work that needs a missing dep raises
:class:`~talkteach.engines.base.EngineUnavailableError` with a child-app-friendly
message instead of crashing.

Simulation mode
---------------
:meth:`WhisperLoRAEngine.train` ships a real, dependency-light *simulation* that
runs whenever torch is unavailable (and currently always, see the phase-1 TODO).
It walks the plan's epochs, streams a rising "smartness" curve through the
progress callback, honours cooperative cancellation, and writes one JSON
checkpoint per epoch to ``workdir``. This lets the FastAPI ``/train`` endpoint and
the whole UI be exercised end-to-end on a GPU-less machine. Checkpoints carry a
``"mode": "SIMULATION"`` marker so nothing downstream mistakes them for a real
fine-tune.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from typing import Optional

from .base import (
    ASREngine,
    EngineUnavailableError,
    ExportResult,
    ProgressCallback,
    ShouldStop,
    TrainProgress,
)
from talkteach.director.types import TrainingPlan

# Required to run a *real* LoRA fine-tune. faster_whisper is needed only for
# "Try it" inference, so it is tracked separately from the training trio.
_TRAIN_DEPS = ("torch", "transformers", "peft")
_TRANSCRIBE_DEP = "faster_whisper"
_EXPORT_DEP = "ctranslate2"

_INSTALL_HINT = "install talkteach-backend[ml] to train"


def _missing(modules: tuple[str, ...]) -> list[str]:
    """Return the subset of ``modules`` that are NOT importable.

    Uses ``importlib.util.find_spec`` so we never actually import (and pay the
    cost of / risk a side effect from) a heavy ML package just to test for it.
    """
    missing: list[str] = []
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


class WhisperLoRAEngine(ASREngine):
    """Whisper-with-LoRA adapter. See module docstring for the dep policy."""

    def name(self) -> str:
        return "Whisper + LoRA"

    def is_available(self) -> tuple[bool, str]:
        """True only when the training trio (torch/transformers/peft) is present.

        faster_whisper (for "Try it") is reported in the message when missing but
        does not by itself gate training, since the message reads "...to train".
        """
        missing_train = _missing(_TRAIN_DEPS)
        if missing_train:
            mods = ", ".join(missing_train)
            extra = ""
            if not _has(_TRANSCRIBE_DEP):
                extra = f" ({_TRANSCRIBE_DEP} is also needed for 'Try it')"
            return False, f"missing {mods}: {_INSTALL_HINT}{extra}"
        return True, ""

    # -- Teach! ---------------------------------------------------------------

    def train(
        self,
        plan: TrainingPlan,
        manifest: list[dict],
        workdir: str,
        progress: Optional[ProgressCallback] = None,
        should_stop: Optional[ShouldStop] = None,
    ) -> TrainProgress:
        """Run the teaching job (real loop in phase 1; simulation today).

        Currently always falls through to :meth:`_simulate_train` so the app is
        fully exercisable without a GPU. When torch is available we still
        simulate, but the structured outline below is where the real loop lands.
        """
        if _has("torch"):
            # TODO(phase-1): real PEFT/LoRA Seq2SeqTrainer loop. Outline:
            #   1. Resolve device/precision from plan.compute / plan.precision.
            #   2. WhisperProcessor.from_pretrained(plan.base_checkpoint); build a
            #      torch Dataset over `manifest` (load wav -> log-mel features via
            #      processor.feature_extractor; tokenize `text` -> labels).
            #   3. WhisperForConditionalGeneration.from_pretrained(...); wrap with
            #      peft.LoraConfig(r=plan.lora_rank, lora_alpha=plan.lora_alpha,
            #      target_modules=["q_proj","v_proj"], ...) -> get_peft_model.
            #      Optionally freeze the encoder when plan.freeze_encoder.
            #   4. DataCollatorSpeechSeq2SeqWithPadding (pad input_features +
            #      labels, replace pad token id with -100).
            #   5. Seq2SeqTrainingArguments built from the plan:
            #         per_device_train_batch_size = plan.batch_size,
            #         gradient_accumulation_steps = plan.grad_accum,
            #         learning_rate = plan.learning_rate,
            #         num_train_epochs = plan.epochs,
            #         warmup_ratio = plan.warmup_ratio,
            #         max_grad_norm = plan.grad_clip, seed = plan.seed,
            #         fp16/bf16 from plan.precision, output_dir = workdir,
            #         load_best_model_at_end=True + EarlyStoppingCallback(
            #             plan.early_stop_patience).
            #   6. compute_metrics -> jiwer.wer; report smartness = 1 - WER.
            #   7. A TrainerCallback bridges HF logs -> TrainProgress(progress=...)
            #      and polls should_stop() to set control.should_training_stop.
            #   8. trainer.train(resume_from_checkpoint=<latest in workdir>).
            # Until that lands, fall through to the simulation so nothing breaks:
            pass
        return self._simulate_train(plan, manifest, workdir, progress, should_stop)

    def _simulate_train(
        self,
        plan: TrainingPlan,
        manifest: list[dict],
        workdir: str,
        progress: Optional[ProgressCallback],
        should_stop: Optional[ShouldStop],
    ) -> TrainProgress:
        """Dependency-free stand-in for a real fine-tune.

        Emits a monotonically rising ``fraction`` and a synthetic rising
        ``smartness`` curve, respects ``should_stop``, and writes one
        SIMULATION-marked JSON checkpoint per epoch so resume is demonstrable.
        """
        os.makedirs(workdir, exist_ok=True)
        total = max(1, int(plan.epochs))

        # Checkpoint-and-resume (demonstration): continue past any epochs already
        # checkpointed in this workdir from a previous (interrupted) run.
        start_epoch = self._latest_checkpoint_epoch(workdir) + 1

        if start_epoch > total:
            # Nothing left to do — already finished in a prior run.
            final = TrainProgress(
                epoch=total,
                total_epochs=total,
                fraction=1.0,
                smartness=self._synthetic_smartness(total, total),
                message="Already taught! (resumed, nothing left to learn) [SIMULATION]",
                done=True,
            )
            if progress is not None:
                progress(final)
            return final

        last = TrainProgress(
            epoch=start_epoch - 1,
            total_epochs=total,
            fraction=(start_epoch - 1) / total,
            smartness=None,
            message="Getting ready... [SIMULATION]",
        )

        for epoch in range(start_epoch, total + 1):
            # Check cancellation at the TOP of the epoch, before advancing the
            # meter — so an always-True should_stop returns with fraction < 1.0.
            if should_stop is not None and should_stop():
                cancelled = TrainProgress(
                    epoch=epoch - 1,
                    total_epochs=total,
                    fraction=(epoch - 1) / total,
                    smartness=last.smartness,
                    message="Stopped by the grown-up. Progress was saved. [SIMULATION]",
                    done=False,
                )
                if progress is not None:
                    progress(cancelled)
                return cancelled

            # Pretend to do an epoch of work. Tiny sleep keeps it cheap in tests
            # while still being a real, observable step.
            time.sleep(0.0)

            fraction = epoch / total  # last epoch -> exactly 1.0
            smartness = self._synthetic_smartness(epoch, total)
            self._write_checkpoint(workdir, plan, epoch, total, smartness, len(manifest))

            last = TrainProgress(
                epoch=epoch,
                total_epochs=total,
                fraction=fraction,
                smartness=smartness,
                message=f"Learning... epoch {epoch} of {total} [SIMULATION]",
                done=(epoch == total),
            )
            if progress is not None:
                progress(last)

        # Guarantee the returned object reports completion at fraction 1.0.
        last.fraction = 1.0
        last.done = True
        last.message = "All done — your computer got smarter! [SIMULATION]"
        return last

    @staticmethod
    def _synthetic_smartness(epoch: int, total: int) -> float:
        """A plausible rising "smartness" (= 1 - WER) curve in [0, 1].

        Diminishing-returns shape that climbs toward ~0.92 but never hits 1.0.
        """
        progress = epoch / max(1, total)
        return round(0.92 * (1.0 - (1.0 - progress) ** 2), 4)

    @staticmethod
    def _checkpoint_path(workdir: str, epoch: int) -> str:
        return os.path.join(workdir, f"checkpoint_epoch_{epoch}.json")

    def _write_checkpoint(
        self,
        workdir: str,
        plan: TrainingPlan,
        epoch: int,
        total: int,
        smartness: float,
        num_examples: int,
    ) -> None:
        payload = {
            "mode": "SIMULATION",
            "marker": "SIMULATION",
            "engine": self.name(),
            "base_checkpoint": plan.base_checkpoint,
            "epoch": epoch,
            "total_epochs": total,
            "smartness": smartness,
            "num_examples": num_examples,
            "effective_batch": plan.effective_batch,
            "seed": plan.seed,
        }
        with open(self._checkpoint_path(workdir, epoch), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

    @staticmethod
    def _latest_checkpoint_epoch(workdir: str) -> int:
        """Highest epoch number with a checkpoint in ``workdir`` (0 if none)."""
        if not os.path.isdir(workdir):
            return 0
        best = 0
        for name in os.listdir(workdir):
            if name.startswith("checkpoint_epoch_") and name.endswith(".json"):
                stem = name[len("checkpoint_epoch_") : -len(".json")]
                if stem.isdigit():
                    best = max(best, int(stem))
        return best

    # -- Try it ---------------------------------------------------------------

    def transcribe(self, audio_path: str, model_dir: str | None = None) -> str:
        """Transcribe one clip with faster-whisper (real inference).

        Raises :class:`EngineUnavailableError` if faster_whisper is not installed.
        """
        if not _has(_TRANSCRIBE_DEP):
            raise EngineUnavailableError(
                f"'Try it' needs the {_TRANSCRIBE_DEP} package — "
                f"ask a grown-up to {_INSTALL_HINT}."
            )
        from faster_whisper import WhisperModel  # type: ignore

        # model_dir, when given, is a CTranslate2 export of the fine-tuned model;
        # otherwise fall back to the base checkpoint name.
        model_id = model_dir or "small"
        model = WhisperModel(model_id, device="auto", compute_type="default")
        segments, _info = model.transcribe(audio_path)
        return " ".join(seg.text.strip() for seg in segments).strip()

    # -- Use on my computer ---------------------------------------------------

    def export(self, model_dir: str, out_dir: str, fmt: str = "ctranslate2") -> ExportResult:
        """Package ``model_dir`` into a portable runtime format.

        Real CTranslate2 conversion when the dep is present; otherwise writes a
        small JSON manifest describing what *would* be exported and returns an
        :class:`ExportResult` whose ``notes`` explain which dep is missing.
        """
        os.makedirs(out_dir, exist_ok=True)

        if fmt == "ctranslate2" and _has(_EXPORT_DEP):
            from ctranslate2.converters import TransformersConverter  # type: ignore

            converter = TransformersConverter(model_dir)
            converter.convert(out_dir, quantization="int8", force=True)
            return ExportResult(
                format="ctranslate2",
                path=out_dir,
                notes="Converted to CTranslate2 (int8). Copy this folder to use offline.",
            )

        # Dry-run placeholder so the "Use on my computer" flow is exercisable.
        manifest_path = os.path.join(out_dir, "export_manifest.json")
        needed = _EXPORT_DEP if fmt == "ctranslate2" else f"a converter for '{fmt}'"
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
                "Wrote a manifest describing what would be produced; "
                "install talkteach-backend[export] to do it for real."
            ),
        )
