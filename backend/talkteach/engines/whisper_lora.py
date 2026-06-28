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

Real vs. simulation
-------------------
:meth:`WhisperLoRAEngine.train` runs the **real** PEFT/LoRA ``Seq2SeqTrainer``
loop (in :mod:`talkteach.engines._whisper_train`) when the training deps are
installed and the manifest points at real audio on disk; otherwise it falls back
to a dependency-light *simulation* (see :meth:`_simulate_train` and the dispatch
in :meth:`train`; the policy is :func:`_whisper_train.should_simulate`, recorded
in project/docs/DECISIONS.md D-012). The simulation walks the plan's epochs, streams a rising
"smartness" curve, honours cooperative cancellation, and writes one JSON
checkpoint per epoch — enough to exercise the FastAPI ``/train`` endpoint and the
whole UI on a GPU-less machine. Its checkpoints carry a ``"mode": "SIMULATION"``
marker so nothing downstream mistakes them for a real fine-tune.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time

from talkteach.director.types import TrainingPlan

from .base import (
    ASREngine,
    EngineUnavailableError,
    ExportResult,
    ProgressCallback,
    ShouldStop,
    TrainProgress,
)

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


def _is_trained_hf_dir(model_dir: str) -> bool:
    """True if ``model_dir`` holds a trained HF model/adapter (not a CT2 export).

    A CTranslate2 export is distinguished by its ``model.bin``; a trained run dir has
    a PEFT ``adapter_config.json`` or HF weights. This routes a freshly fine-tuned
    model to the transformers ``generate`` path instead of faster-whisper.
    """
    if os.path.isfile(os.path.join(model_dir, "model.bin")):
        return False  # CTranslate2 export → faster-whisper handles it
    return any(
        os.path.isfile(os.path.join(model_dir, name))
        for name in ("adapter_config.json", "model.safetensors", "pytorch_model.bin")
    )


def _has_real_model(model_dir: str) -> bool:
    """True if ``model_dir`` holds a real model to export (not a simulation run).

    The simulation writes only ``checkpoint_epoch_*.json`` markers — there's nothing
    to convert — so export should fall back to a dry-run manifest rather than handing
    a fake directory to a real converter (which fails confusingly).
    """
    return any(
        os.path.isfile(os.path.join(model_dir, name))
        for name in ("adapter_config.json", "config.json", "model.safetensors", "pytorch_model.bin")
    )


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
        progress: ProgressCallback | None = None,
        should_stop: ShouldStop | None = None,
    ) -> TrainProgress:
        """Run the teaching job: the real PEFT/LoRA loop, or the simulation.

        Dispatch (see project/docs/DECISIONS.md D-012): the real ``Seq2SeqTrainer`` loop runs
        when the training deps are present, the run isn't force-simulated, and at
        least one manifest clip exists on disk. Otherwise we fall back to the
        dependency-free simulation so the whole app stays exercisable on a
        GPU-less machine with seed/fake data. The real loop lives in
        :mod:`talkteach.engines._whisper_train` (kept separate so its pure helpers
        are unit-tested without torch).
        """
        from . import _whisper_train as wt

        has_deps = not _missing(_TRAIN_DEPS)
        simulate, reason = wt.should_simulate(manifest, has_train_deps=has_deps)
        if simulate:
            if reason:
                # Visible in logs / Grown-up mode; never crashes the child's flow.
                import logging

                logging.getLogger("talkteach.train").info("Simulating training: %s", reason)
            return self._simulate_train(plan, manifest, workdir, progress, should_stop)

        return wt.run_real_training(plan, manifest, workdir, progress, should_stop)

    def _simulate_train(
        self,
        plan: TrainingPlan,
        manifest: list[dict],
        workdir: str,
        progress: ProgressCallback | None,
        should_stop: ShouldStop | None,
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
        """Transcribe one clip — fast CTranslate2 path, or a trained-adapter path.

        Two cases:

        * ``model_dir`` is a **trained run dir** (a LoRA adapter or full HF model
          saved by training, no CTranslate2 ``model.bin``): load it with
          transformers (merging the adapter) and ``generate`` — this is how the
          benchmark scores a freshly fine-tuned model without an export step.
        * Otherwise (a CTranslate2 export dir, or ``None``): use faster-whisper, the
          fast offline "Try it" path the product ships.
        """
        if model_dir and _is_trained_hf_dir(model_dir):
            if _missing(_TRAIN_DEPS):
                raise EngineUnavailableError(
                    f"scoring a trained model needs torch + transformers — {_INSTALL_HINT}."
                )
            from . import _whisper_train as wt

            return wt.transcribe_with_transformers(audio_path, model_dir)

        if not _has(_TRANSCRIBE_DEP):
            raise EngineUnavailableError(
                f"'Try it' needs the {_TRANSCRIBE_DEP} package — ask a grown-up to {_INSTALL_HINT}."
            )
        from faster_whisper import WhisperModel  # type: ignore

        # model_dir, when given, is a CTranslate2 export of the fine-tuned model;
        # otherwise fall back to the base checkpoint name.
        model_id = model_dir or "small"
        model = WhisperModel(model_id, device="auto", compute_type="default")
        segments, _info = model.transcribe(audio_path)
        return " ".join(seg.text.strip() for seg in segments).strip()

    # -- Use on my computer ---------------------------------------------------

    @staticmethod
    def _resolve_full_model(model_dir: str) -> str:
        """Return a directory holding a *full* HF model to convert.

        Real training saves a PEFT/LoRA *adapter* (plus the processor) to the run
        dir. CTranslate2/ONNX need a full model, so if we find an adapter we load
        the base, merge the adapter in, and save the merged model to
        ``<model_dir>/_merged``. A plain full model is returned unchanged. Needs
        torch/transformers/peft; callers guard on availability.
        """
        adapter_cfg = os.path.join(model_dir, "adapter_config.json")
        if not os.path.isfile(adapter_cfg):
            return model_dir  # already a full model (or a dry-run placeholder)

        import json as _json

        from peft import PeftModel  # type: ignore
        from transformers import WhisperForConditionalGeneration, WhisperProcessor  # type: ignore

        with open(adapter_cfg, encoding="utf-8") as fh:
            base_id = _json.load(fh).get("base_model_name_or_path", "openai/whisper-small")
        base = WhisperForConditionalGeneration.from_pretrained(base_id)
        merged = PeftModel.from_pretrained(base, model_dir).merge_and_unload()
        merged_dir = os.path.join(model_dir, "_merged")
        os.makedirs(merged_dir, exist_ok=True)
        merged.save_pretrained(merged_dir)
        # Bring the processor/tokenizer along so the converter has everything.
        try:
            WhisperProcessor.from_pretrained(model_dir).save_pretrained(merged_dir)
        except Exception:
            WhisperProcessor.from_pretrained(base_id).save_pretrained(merged_dir)
        return merged_dir

    def export(self, model_dir: str, out_dir: str, fmt: str = "ctranslate2") -> ExportResult:
        """Package ``model_dir`` into a portable, offline runtime format (#4).

        For a LoRA-trained run, the adapter is first merged into the base model
        (:meth:`_resolve_full_model`). The default ``ctranslate2`` target gives
        the fastest CPU inference and pairs with the faster-whisper "Try it" path;
        ``onnx`` is the streaming/edge target via sherpa-onnx (Phase 2 scaffold,
        project/docs/DECISIONS.md D-006). When the needed dep is missing we write a manifest
        describing what *would* be produced so the flow never dead-ends.
        """
        os.makedirs(out_dir, exist_ok=True)

        real_model = _has_real_model(model_dir)
        ct2_ready = _has(_EXPORT_DEP) and _has("transformers")
        if real_model and fmt in ("ctranslate2", "ct2") and ct2_ready:
            from ctranslate2.converters import TransformersConverter  # type: ignore

            source = self._resolve_full_model(model_dir)
            TransformersConverter(source).convert(out_dir, quantization="int8", force=True)
            return ExportResult(
                format="ctranslate2",
                path=out_dir,
                notes="Converted to CTranslate2 (int8). Copy this folder to use offline.",
            )

        if real_model and fmt == "onnx" and _has("optimum") and _has("transformers"):
            # sherpa-onnx consumes ONNX exported via 🤗 optimum. Scaffolded path:
            # merge LoRA, then `optimum.exporters.onnx` the Whisper model.
            from optimum.exporters.onnx import main_export  # type: ignore

            source = self._resolve_full_model(model_dir)
            main_export(source, output=out_dir, task="automatic-speech-recognition")
            return ExportResult(
                format="onnx",
                path=out_dir,
                notes="Exported to ONNX. Run with sherpa-onnx for streaming/edge use.",
            )

        # Dry-run placeholder so the "Use on my computer" flow is exercisable —
        # taken when the export dep is missing OR there's no real model to convert
        # (e.g. a simulation run).
        manifest_path = os.path.join(out_dir, "export_manifest.json")
        if not real_model:
            needed = "a real trained model (this run dir holds only a simulation checkpoint)"
        else:
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
