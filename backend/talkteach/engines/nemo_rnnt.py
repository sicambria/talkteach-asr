"""NeMo / Parakeet RNN-T engine adapter — streaming / edge target (roadmap #25).

A **real but GPU/opt-in** engine. Unlike Whisper-LoRA and wav2vec2-CTC (which run a
real fine-tune on CPU and in CI), NVIDIA NeMo's training stack is PyTorch-Lightning /
CUDA-centric and heavy to install, so this engine is honest about its ceiling:
``is_available()`` returns True only when ``nemo_toolkit`` is importable **and** a
CUDA device is present. Everywhere else it reports what's missing and the app falls
back to Whisper-LoRA — and the benchmark records the cell as ``skipped`` rather than
failing. It is therefore never part of the default or CI test path (see
project/docs/BENCHMARKING.md and DECISIONS.md D-001).

The training/transcribe code below follows NeMo's standard manifest + Lightning
recipe. It is validated on a provisioned GPU box, not in this repo's CI; treat it as
the real path you opt into with ``backend[nemo]`` + a GPU.
"""

from __future__ import annotations

import importlib.util
import json
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

_HINT = "the NeMo engine needs a GPU + talkteach-backend[nemo] (nemo_toolkit)"


def _nemo_importable() -> bool:
    # nemo_toolkit installs as the importable package `nemo`.
    return importlib.util.find_spec("nemo") is not None


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # pragma: no cover - torch absent or broken
        return False


class NeMoRNNTEngine(ASREngine):
    def name(self) -> str:
        return "NeMo Parakeet (RNN-T)"

    def is_available(self) -> tuple[bool, str]:
        if not _nemo_importable():
            return False, _HINT
        if not _cuda_available():
            return False, "NeMo is installed but no CUDA GPU was found — NeMo training is GPU-only."
        return True, ""

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _write_manifest(manifest: list[dict], path: str) -> int:
        """Write a NeMo-format JSONL manifest; return the count of usable rows."""
        import soundfile as sf

        n = 0
        with open(path, "w", encoding="utf-8") as fh:
            for item in manifest:
                audio_path, text = item.get("path", ""), item.get("text", "")
                if not os.path.isfile(audio_path):
                    continue
                duration = item.get("duration_s")
                if duration is None:
                    info = sf.info(audio_path)
                    duration = info.frames / float(info.samplerate)
                fh.write(
                    json.dumps(
                        {
                            "audio_filepath": audio_path,
                            "text": text,
                            "duration": float(duration),
                        }
                    )
                    + "\n"
                )
                n += 1
        return n

    # -- Teach! ---------------------------------------------------------------

    def train(
        self,
        plan: TrainingPlan,
        manifest: list[dict],
        workdir: str,
        progress: ProgressCallback | None = None,
        should_stop: ShouldStop | None = None,
    ) -> TrainProgress:
        available, msg = self.is_available()
        if not available:
            raise EngineUnavailableError(msg)

        import nemo.collections.asr as nemo_asr  # type: ignore
        import pytorch_lightning as pl  # type: ignore

        os.makedirs(workdir, exist_ok=True)
        train_mani = os.path.join(workdir, "train_manifest.jsonl")
        if self._write_manifest(manifest, train_mani) == 0:
            raise RuntimeError("No loadable training clips after decoding the manifest.")

        if progress is not None:
            progress(TrainProgress(0, plan.epochs, 0.0, None, "Loading the NeMo model…"))

        model = nemo_asr.models.ASRModel.from_pretrained(plan.base_checkpoint)
        model.setup_training_data(
            train_data_config={
                "manifest_filepath": train_mani,
                "sample_rate": 16_000,
                "batch_size": plan.batch_size,
                "shuffle": True,
            }
        )
        trainer = pl.Trainer(
            max_epochs=plan.epochs,
            accelerator="gpu",
            devices=1,
            gradient_clip_val=plan.grad_clip,  # safety rail #3
            enable_checkpointing=True,
            default_root_dir=workdir,
            logger=False,
            enable_progress_bar=False,
        )
        model.set_trainer(trainer)
        trainer.fit(model)
        out = os.path.join(workdir, "model.nemo")
        model.save_to(out)

        # Measure WER on the same clips (a real held-out split needs the standard
        # NeMo eval loop; for the benchmark, WER is computed by the harness on the
        # shared eval set via transcribe()).
        return TrainProgress(
            epoch=plan.epochs,
            total_epochs=plan.epochs,
            fraction=1.0,
            smartness=None,
            message="All done — NeMo model trained.",
            done=True,
        )

    # -- Try it ---------------------------------------------------------------

    def transcribe(self, audio_path: str, model_dir: str | None = None) -> str:
        available, msg = self.is_available()
        if not available:
            raise EngineUnavailableError(msg)
        import nemo.collections.asr as nemo_asr  # type: ignore

        if not model_dir:
            raise EngineUnavailableError("NeMo transcribe needs a trained model_dir.")
        nemo_file = (
            model_dir if model_dir.endswith(".nemo") else os.path.join(model_dir, "model.nemo")
        )
        model = nemo_asr.models.ASRModel.restore_from(nemo_file)
        hyps = model.transcribe([audio_path])
        # NeMo returns a list of strings (or Hypothesis objects on newer versions).
        first = hyps[0]
        return getattr(first, "text", first)

    # -- Use on my computer ---------------------------------------------------

    def export(self, model_dir: str, out_dir: str, fmt: str = "onnx") -> ExportResult:
        available, msg = self.is_available()
        if not available:
            raise EngineUnavailableError(msg)
        import nemo.collections.asr as nemo_asr  # type: ignore

        os.makedirs(out_dir, exist_ok=True)
        nemo_file = (
            model_dir if model_dir.endswith(".nemo") else os.path.join(model_dir, "model.nemo")
        )
        model = nemo_asr.models.ASRModel.restore_from(nemo_file)
        out = os.path.join(out_dir, "model.onnx")
        model.export(out)
        return ExportResult(
            format="onnx",
            path=out,
            notes="Exported NeMo model to ONNX. Run with sherpa-onnx for streaming/edge use.",
        )
