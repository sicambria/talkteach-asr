"""Real Whisper + LoRA fine-tuning — the parts that make training *real* (#1–3).

This module is split into two layers on purpose (see project/docs/DECISIONS.md D-002):

* **Pure helpers** (top of file) — derive ``Seq2SeqTrainingArguments`` kwargs from
  a :class:`TrainingPlan`, compute WER/CER, map WER → "smartness", run the
  NaN-guard rollback policy, and find the latest resumable checkpoint. These touch
  NO heavy framework (jiwer is light and torch-free) and are unit-tested directly
  with synthetic data — no GPU, no network, no model download.
* **Guarded real-training functions** (bottom) — build the dataset/collator,
  wrap the model with PEFT/LoRA, wire a progress+cancel+NaN-guard callback, and
  drive ``Seq2SeqTrainer.train``. Every torch/transformers/peft import is
  function-local so importing this module costs nothing on a plain laptop.

The simulation lives in :mod:`talkteach.engines.whisper_lora`; this module is the
real path it dispatches to.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from talkteach.director.types import Precision, TrainingPlan

# Engine-agnostic pure helpers live in `_train_common` (shared with the wav2vec2-CTC
# engine); re-exported here so existing call sites/tests using `wt.wer`,
# `wt.should_simulate`, etc. keep working unchanged.
from ._train_common import (
    NanRollbackGuard,
    cer,
    find_latest_checkpoint,
    should_simulate,  # noqa: F401  (re-exported for whisper_lora/tests)
    smartness_from_wer,
    wer,
)

if TYPE_CHECKING:
    from .base import ProgressCallback, ShouldStop, TrainProgress

log = logging.getLogger("talkteach.train")

# Whisper's mel feature extractor always produces 16 kHz, 80-bin log-mel input.
TARGET_SAMPLE_RATE = 16_000


# =============================================================================
# Whisper-specific pure helper — unit-tested without torch (DECISIONS.md D-002).
# The engine-agnostic helpers (should_simulate/wer/cer/…) are imported above from
# `_train_common`.
# =============================================================================


def training_arguments_kwargs(plan: TrainingPlan, workdir: str) -> dict[str, Any]:
    """Map a :class:`TrainingPlan` → ``Seq2SeqTrainingArguments`` kwargs (pure).

    Encodes the safety rails (#3): a fixed ``seed`` and gradient clipping via
    ``max_grad_norm``. Precision flags come straight from the plan. ``report_to``
    is empty so training never phones home (privacy promise, D-008). The
    eval/save *strategy* keys are added by :func:`build_training_arguments`
    because their name changed across transformers versions.
    """
    return {
        "output_dir": workdir,
        "per_device_train_batch_size": plan.batch_size,
        "per_device_eval_batch_size": max(1, plan.batch_size),
        "gradient_accumulation_steps": plan.grad_accum,
        "learning_rate": plan.learning_rate,
        "num_train_epochs": plan.epochs,
        "warmup_ratio": plan.warmup_ratio,
        "max_grad_norm": plan.grad_clip,  # gradient clipping — safety rail #3
        "seed": plan.seed,  # fixed seed — safety rail #3 (reproducibility)
        "fp16": plan.precision is Precision.FP16,
        "bf16": plan.precision is Precision.BF16,
        "predict_with_generate": True,
        "generation_max_length": 225,
        "logging_steps": 10,
        "save_total_limit": 2,
        "load_best_model_at_end": True,
        "metric_for_best_model": "wer",
        "greater_is_better": False,  # lower WER is better
        "report_to": [],  # no telemetry (project/docs/DECISIONS.md D-008)
        "remove_unused_columns": False,  # Whisper passes a feature dict, not columns
    }


# =============================================================================
# Guarded real-training path — all heavy imports are function-local
# =============================================================================


def build_training_arguments(plan: TrainingPlan, workdir: str):  # noqa: ANN201
    """Construct ``Seq2SeqTrainingArguments`` from the plan (needs transformers).

    Handles the ``evaluation_strategy`` → ``eval_strategy`` rename across
    transformers versions so the same code works on 4.40+ and newer.
    """
    from transformers import Seq2SeqTrainingArguments

    kwargs = training_arguments_kwargs(plan, workdir)
    # Eval + save once per epoch, matched so load_best_model_at_end works.
    for strat_key in ("eval_strategy", "evaluation_strategy"):
        try:
            return Seq2SeqTrainingArguments(**kwargs, **{strat_key: "epoch"}, save_strategy="epoch")
        except TypeError:
            continue
    # Last resort: no per-epoch eval (older/newer arg surface) — still trains.
    kwargs["load_best_model_at_end"] = False
    return Seq2SeqTrainingArguments(**kwargs)


def _build_dataset(manifest: list[dict], processor, language: str | None):  # noqa: ANN001
    """Turn the manifest into a 🤗 Dataset of (input_features, labels)."""
    import soundfile as sf
    from datasets import Dataset

    def _resample(samples, sr: int):  # noqa: ANN001
        if sr == TARGET_SAMPLE_RATE:
            return samples
        import numpy as np

        # Linear resample — adequate for 16 kHz target; librosa is optional.
        duration = samples.shape[0] / sr
        n_target = int(round(duration * TARGET_SAMPLE_RATE))
        if n_target <= 1:
            return samples
        xp = np.linspace(0.0, 1.0, num=samples.shape[0], endpoint=False)
        x = np.linspace(0.0, 1.0, num=n_target, endpoint=False)
        return np.interp(x, xp, samples).astype("float32")

    rows = []
    for item in manifest:
        path, text = item.get("path", ""), item.get("text", "")
        if not os.path.isfile(path):
            continue
        audio, sr = sf.read(path, dtype="float32", always_2d=False)
        if getattr(audio, "ndim", 1) == 2:  # stereo → mono
            audio = audio.mean(axis=1)
        audio = _resample(audio, int(sr))
        feats = processor.feature_extractor(audio, sampling_rate=TARGET_SAMPLE_RATE).input_features[
            0
        ]
        labels = processor.tokenizer(text).input_ids
        rows.append({"input_features": feats, "labels": labels})
    if not rows:
        raise RuntimeError("No loadable training clips after decoding the manifest.")
    return Dataset.from_list(rows)


def _make_collator(processor):  # noqa: ANN001, ANN201
    """Pad input features + label ids; mask pad tokens with -100."""
    import torch

    class DataCollatorSpeechSeq2SeqWithPadding:
        def __call__(self, features: list[dict]) -> dict:
            input_features = [{"input_features": f["input_features"]} for f in features]
            batch = processor.feature_extractor.pad(input_features, return_tensors="pt")
            label_features = [{"input_ids": f["labels"]} for f in features]
            labels_batch = processor.tokenizer.pad(label_features, return_tensors="pt")
            labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
            # Strip a leading forced BOS the tokenizer may have added.
            if (labels[:, 0] == processor.tokenizer.bos_token_id).all().cpu().item():
                labels = labels[:, 1:]
            batch["labels"] = labels
            return batch

        _ = torch  # keep the guarded import referenced

    return DataCollatorSpeechSeq2SeqWithPadding()


def _make_compute_metrics(processor):  # noqa: ANN001, ANN201
    """Build the ``compute_metrics`` fn that reports measured WER/CER (#2)."""

    def compute_metrics(pred) -> dict:  # noqa: ANN001
        import numpy as np

        pred_ids = pred.predictions
        label_ids = pred.label_ids
        label_ids = np.where(label_ids == -100, processor.tokenizer.pad_token_id, label_ids)
        hyps = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        refs = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)
        return {"wer": wer(refs, hyps), "cer": cer(refs, hyps)}

    return compute_metrics


def run_real_training(
    plan: TrainingPlan,
    manifest: list[dict],
    workdir: str,
    progress: ProgressCallback | None,
    should_stop: ShouldStop | None,
    language: str | None = None,
) -> TrainProgress:
    """The real PEFT/LoRA ``Seq2SeqTrainer`` loop (#1) with measured WER (#2) and
    the safety rails wired in (#3). All heavy imports are local to this call.
    """
    from peft import LoraConfig, get_peft_model
    from transformers import (
        Seq2SeqTrainer,
        TrainerCallback,
        WhisperForConditionalGeneration,
        WhisperProcessor,
    )

    from talkteach.obs import experiment as exp

    from .base import TrainProgress

    os.makedirs(workdir, exist_ok=True)
    guard = NanRollbackGuard()

    def emit(p: TrainProgress) -> None:
        if progress is not None:
            progress(p)

    emit(
        TrainProgress(
            epoch=0,
            total_epochs=plan.epochs,
            fraction=0.0,
            smartness=None,
            message="Getting the computer ready to learn…",
        )
    )

    processor = WhisperProcessor.from_pretrained(
        plan.base_checkpoint, language=language, task="transcribe"
    )
    dataset = _build_dataset(manifest, processor, language)
    # A small held-out split for genuine WER (#2). At least one eval example.
    split = dataset.train_test_split(test_size=max(1, len(dataset) // 10), seed=plan.seed)

    model = WhisperForConditionalGeneration.from_pretrained(plan.base_checkpoint)
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []
    if plan.freeze_encoder:
        model.freeze_encoder()
    lora = LoraConfig(
        r=plan.lora_rank,
        lora_alpha=plan.lora_alpha,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
    )
    model = get_peft_model(model, lora)

    args = build_training_arguments(plan, workdir)
    collator = _make_collator(processor)
    compute_metrics = _make_compute_metrics(processor)

    total_epochs = plan.epochs

    class _BridgeCallback(TrainerCallback):
        """Bridge HF training state → TrainProgress, honour cancel + NaN-guard."""

        def on_log(self, args, state, control, logs=None, **kw):  # noqa: ANN001
            logs = logs or {}
            loss = logs.get("loss")
            if loss is not None:
                # Local-only loss curve for Grown-up mode (#53; no telemetry, D-008).
                exp.log_metrics(
                    workdir,
                    step=int(state.global_step or 0),
                    epoch=float(state.epoch or 0),
                    loss=float(loss),
                )
            if loss is not None and guard.should_rollback(float(loss)):
                # Diverged into NaN/inf → stop now; best checkpoint is restored
                # by load_best_model_at_end / resume on next run (safety rail #3).
                control.should_training_stop = True
                emit(
                    TrainProgress(
                        epoch=int(state.epoch or 0),
                        total_epochs=total_epochs,
                        fraction=min(1.0, (state.epoch or 0) / total_epochs),
                        smartness=None,
                        message="Training wobbled (NaN) — rolled back to the last good point.",
                        failed=True,
                    )
                )
            return control

        def on_epoch_end(self, args, state, control, **kw):  # noqa: ANN001
            frac = min(1.0, (state.epoch or 0) / total_epochs)
            emit(
                TrainProgress(
                    epoch=int(state.epoch or 0),
                    total_epochs=total_epochs,
                    fraction=frac,
                    smartness=None,
                    message=f"Learning… epoch {int(state.epoch or 0)} of {total_epochs}",
                )
            )
            return control

        def on_evaluate(self, args, state, control, metrics=None, **kw):  # noqa: ANN001
            metrics = metrics or {}
            w = metrics.get("eval_wer")
            if w is not None:
                exp.log_metrics(
                    workdir,
                    epoch=float(state.epoch or 0),
                    wer=float(w),
                    cer=float(metrics.get("eval_cer", float("nan"))),
                )
                emit(
                    TrainProgress(
                        epoch=int(state.epoch or 0),
                        total_epochs=total_epochs,
                        fraction=min(1.0, (state.epoch or 0) / total_epochs),
                        smartness=smartness_from_wer(float(w)),
                        message="Checking how smart it got…",
                    )
                )
            return control

        def on_save(self, args, state, control, **kw):  # noqa: ANN001
            # Remember the freshly-written checkpoint as the last known-good state
            # so the NaN guard can name it if the run later diverges.
            latest = find_latest_checkpoint(workdir)
            if latest:
                guard.observe_good_checkpoint(latest)
            return control

        def on_step_end(self, args, state, control, **kw):  # noqa: ANN001
            if should_stop is not None and should_stop():
                control.should_training_stop = True
            return control

    trainer_kwargs = {
        "model": model,
        "args": args,
        "train_dataset": split["train"],
        "eval_dataset": split["test"],
        "data_collator": collator,
        "compute_metrics": compute_metrics,
        "callbacks": [_BridgeCallback()],
    }
    # transformers renamed `tokenizer` → `processing_class` (5.x). Pass whichever
    # the installed version accepts so we work across 4.40+ and 5.x.
    try:
        trainer = Seq2SeqTrainer(processing_class=processor, **trainer_kwargs)
    except TypeError:
        trainer = Seq2SeqTrainer(tokenizer=processor.feature_extractor, **trainer_kwargs)

    resume = find_latest_checkpoint(workdir)
    trainer.train(resume_from_checkpoint=resume)

    # Save the adapter + processor so export (#4) can merge + convert it.
    trainer.save_model(workdir)
    processor.save_pretrained(workdir)

    final_metrics = trainer.evaluate()
    final_wer = float(final_metrics.get("eval_wer", 1.0))
    cancelled = should_stop is not None and should_stop()
    return TrainProgress(
        epoch=total_epochs,
        total_epochs=total_epochs,
        fraction=1.0 if not cancelled else min(1.0, trainer.state.epoch / total_epochs),
        smartness=smartness_from_wer(final_wer),
        message=(
            "Stopped by the grown-up. Progress was saved."
            if cancelled
            else "All done — your computer really got smarter!"
        ),
        done=not cancelled,
        failed=guard.tripped,
    )


def transcribe_with_transformers(
    audio_path: str, model_dir: str, language: str | None = None
) -> str:
    """Decode one clip with a trained Whisper model in ``model_dir`` (no CT2 export).

    Loads the processor saved alongside the run; if ``model_dir`` is a LoRA adapter,
    loads the base and merges the adapter in (so ``generate`` works), else loads the
    full model directly. Used by the benchmark to score a freshly fine-tuned model.
    """
    import json as _json

    import soundfile as sf
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    processor = WhisperProcessor.from_pretrained(model_dir)
    adapter_cfg = os.path.join(model_dir, "adapter_config.json")
    if os.path.isfile(adapter_cfg):
        from peft import PeftModel

        with open(adapter_cfg, encoding="utf-8") as fh:
            base_id = _json.load(fh).get("base_model_name_or_path", "openai/whisper-tiny")
        base = WhisperForConditionalGeneration.from_pretrained(base_id)
        model = PeftModel.from_pretrained(base, model_dir).merge_and_unload()
    else:
        model = WhisperForConditionalGeneration.from_pretrained(model_dir)
    model.eval()

    audio, sr = sf.read(audio_path, dtype="float32", always_2d=False)
    if getattr(audio, "ndim", 1) == 2:
        audio = audio.mean(axis=1)
    if int(sr) != TARGET_SAMPLE_RATE:
        import librosa

        audio = librosa.resample(audio, orig_sr=int(sr), target_sr=TARGET_SAMPLE_RATE)
    feats = processor.feature_extractor(
        audio, sampling_rate=TARGET_SAMPLE_RATE, return_tensors="pt"
    ).input_features
    with torch.no_grad():
        generated = model.generate(feats)
    return processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
