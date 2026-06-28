"""Real wav2vec2 CTC fine-tuning — the wav2vec2 counterpart to ``_whisper_train``.

Same two-layer split and dependency philosophy: the engine-agnostic pure helpers
(WER/CER, smartness, checkpoint discovery, NaN guard, simulate dispatch) come from
:mod:`_train_common`; everything heavy (torch/transformers) is imported inside the
functions so this module costs nothing to import without the ``[ml]`` extra.

wav2vec2 is a CTC model, not a seq2seq one, so it has its own dataset/collator/
metrics: audio → ``input_values`` (no mel front-end), transcripts tokenised by the
CTC character tokenizer, predictions decoded by argmax. We fine-tune the base
end-to-end with the feature *encoder* frozen (the standard low-data recipe); the
plan's LoRA fields are Whisper-specific and intentionally unused here.
"""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

from talkteach.director.types import TrainingPlan

from ._train_common import (
    NanRollbackGuard,
    cer,
    find_latest_checkpoint,
    smartness_from_wer,
    wer,
)

if TYPE_CHECKING:
    from .base import ProgressCallback, ShouldStop, TrainProgress

log = logging.getLogger("talkteach.train")

TARGET_SAMPLE_RATE = 16_000
# Characters a default English CTC tokenizer (e.g. wav2vec2-base-960h) knows.
_CTC_KEEP = re.compile(r"[^A-Z' ]+")


def normalize_for_ctc(text: str) -> str:
    """Fold text into the base CTC tokenizer's charset (uppercase A–Z, apostrophe).

    English wav2vec2 CTC vocabularies have no digits/punctuation/lowercase; mapping
    out-of-vocab characters to nothing (rather than ``<unk>``) keeps labels clean so
    the loss and WER reflect the words, not tokenizer artefacts.
    """
    return _CTC_KEEP.sub("", text.upper()).strip()


def build_training_arguments(plan: TrainingPlan, workdir: str):  # noqa: ANN201
    """Construct ``TrainingArguments`` from the plan (needs transformers).

    Mirrors the Whisper arg policy (fixed seed + grad clip safety rails, no
    telemetry, per-epoch eval/save with best-model restore) and handles the
    ``evaluation_strategy`` → ``eval_strategy`` rename across versions.
    """
    from transformers import TrainingArguments

    kwargs = {
        "output_dir": workdir,
        "per_device_train_batch_size": plan.batch_size,
        "per_device_eval_batch_size": max(1, plan.batch_size),
        "gradient_accumulation_steps": plan.grad_accum,
        "learning_rate": plan.learning_rate,
        "num_train_epochs": plan.epochs,
        "warmup_ratio": plan.warmup_ratio,
        "max_grad_norm": plan.grad_clip,  # safety rail #3
        "seed": plan.seed,  # safety rail #3
        "fp16": plan.precision.value == "fp16",
        "bf16": plan.precision.value == "bf16",
        "logging_steps": 10,
        "save_total_limit": 2,
        "load_best_model_at_end": True,
        "metric_for_best_model": "wer",
        "greater_is_better": False,
        "report_to": [],  # no telemetry (project/docs/DECISIONS.md D-008)
    }
    for strat_key in ("eval_strategy", "evaluation_strategy"):
        try:
            return TrainingArguments(**kwargs, **{strat_key: "epoch"}, save_strategy="epoch")
        except TypeError:
            continue
    kwargs["load_best_model_at_end"] = False
    return TrainingArguments(**kwargs)


def _build_dataset(manifest: list[dict], processor):  # noqa: ANN001, ANN202
    """Turn the manifest into a 🤗 Dataset of (input_values, labels) for CTC."""
    import soundfile as sf
    from datasets import Dataset

    rows = []
    for item in manifest:
        path, text = item.get("path", ""), item.get("text", "")
        if not os.path.isfile(path):
            continue
        audio, sr = sf.read(path, dtype="float32", always_2d=False)
        if getattr(audio, "ndim", 1) == 2:
            audio = audio.mean(axis=1)
        if int(sr) != TARGET_SAMPLE_RATE:
            import librosa

            audio = librosa.resample(audio, orig_sr=int(sr), target_sr=TARGET_SAMPLE_RATE)
        input_values = processor(audio, sampling_rate=TARGET_SAMPLE_RATE).input_values[0]
        # Tokenize the (CTC-normalised) transcript directly; the deprecated
        # as_target_processor() context manager clashes with default kwargs.
        labels = processor.tokenizer(normalize_for_ctc(text)).input_ids
        rows.append({"input_values": input_values, "labels": labels})
    if not rows:
        raise RuntimeError("No loadable training clips after decoding the manifest.")
    return Dataset.from_list(rows)


def _make_collator(processor):  # noqa: ANN001, ANN201
    """Pad input_values + label ids separately; mask label pad with -100."""

    class DataCollatorCTCWithPadding:
        def __call__(self, features: list[dict]) -> dict:
            input_features = [{"input_values": f["input_values"]} for f in features]
            batch = processor.feature_extractor.pad(input_features, return_tensors="pt")
            label_features = [{"input_ids": f["labels"]} for f in features]
            labels_batch = processor.tokenizer.pad(label_features, return_tensors="pt")
            labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
            batch["labels"] = labels
            return batch

    return DataCollatorCTCWithPadding()


def _make_compute_metrics(processor):  # noqa: ANN001, ANN201
    """Build the ``compute_metrics`` fn that reports measured WER/CER for CTC (#2)."""

    def compute_metrics(pred) -> dict:  # noqa: ANN001
        import numpy as np

        pred_logits = pred.predictions
        pred_ids = np.argmax(pred_logits, axis=-1)
        label_ids = pred.label_ids
        label_ids = np.where(label_ids == -100, processor.tokenizer.pad_token_id, label_ids)
        hyps = processor.batch_decode(pred_ids)
        refs = processor.batch_decode(label_ids, group_tokens=False)
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
    """The real wav2vec2 CTC ``Trainer`` loop with measured WER and safety rails."""
    from transformers import Trainer, TrainerCallback, Wav2Vec2ForCTC, Wav2Vec2Processor

    from .base import TrainProgress

    os.makedirs(workdir, exist_ok=True)
    guard = NanRollbackGuard()

    def emit(p: TrainProgress) -> None:
        if progress is not None:
            progress(p)

    emit(TrainProgress(0, plan.epochs, 0.0, None, "Getting the computer ready to learn…"))

    processor = Wav2Vec2Processor.from_pretrained(plan.base_checkpoint)
    dataset = _build_dataset(manifest, processor)
    split = dataset.train_test_split(test_size=max(1, len(dataset) // 10), seed=plan.seed)

    model = Wav2Vec2ForCTC.from_pretrained(
        plan.base_checkpoint,
        ctc_loss_reduction="mean",
        # Zero out non-finite CTC losses (a short clip whose frame count is < its
        # label length yields inf → nan otherwise). Essential for short TTS clips.
        ctc_zero_infinity=True,
        pad_token_id=processor.tokenizer.pad_token_id,
    )
    # SpecAugment time/feature masking destabilises (NaN) on the short clips this
    # app trains on; disable it for fine-tuning. The feature encoder is frozen as
    # the standard low-data recipe.
    model.config.apply_spec_augment = False
    model.freeze_feature_encoder()

    args = build_training_arguments(plan, workdir)
    total_epochs = plan.epochs

    class _BridgeCallback(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kw):  # noqa: ANN001
            logs = logs or {}
            loss = logs.get("loss")
            if loss is not None and guard.should_rollback(float(loss)):
                control.should_training_stop = True
                emit(
                    TrainProgress(
                        int(state.epoch or 0),
                        total_epochs,
                        min(1.0, (state.epoch or 0) / total_epochs),
                        None,
                        "Training wobbled (NaN) — rolled back to the last good point.",
                        failed=True,
                    )
                )
            return control

        def on_epoch_end(self, args, state, control, **kw):  # noqa: ANN001
            ep = int(state.epoch or 0)
            emit(
                TrainProgress(
                    ep,
                    total_epochs,
                    min(1.0, ep / total_epochs),
                    None,
                    f"Learning… epoch {ep} of {total_epochs}",
                )
            )
            return control

        def on_evaluate(self, args, state, control, metrics=None, **kw):  # noqa: ANN001
            w = (metrics or {}).get("eval_wer")
            if w is not None:
                ep = int(state.epoch or 0)
                emit(
                    TrainProgress(
                        ep,
                        total_epochs,
                        min(1.0, ep / total_epochs),
                        smartness_from_wer(float(w)),
                        "Checking how smart it got…",
                    )
                )
            return control

        def on_save(self, args, state, control, **kw):  # noqa: ANN001
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
        "data_collator": _make_collator(processor),
        "compute_metrics": _make_compute_metrics(processor),
        "callbacks": [_BridgeCallback()],
    }
    # transformers renamed `tokenizer` → `processing_class` (5.x).
    try:
        trainer = Trainer(processing_class=processor, **trainer_kwargs)
    except TypeError:
        trainer = Trainer(tokenizer=processor.feature_extractor, **trainer_kwargs)

    trainer.train(resume_from_checkpoint=find_latest_checkpoint(workdir))
    trainer.save_model(workdir)
    processor.save_pretrained(workdir)

    final_wer = float(trainer.evaluate().get("eval_wer", 1.0))
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


def transcribe(audio_path: str, model_dir: str) -> str:
    """Greedy-decode one clip with a fine-tuned wav2vec2 CTC model in ``model_dir``."""
    import soundfile as sf
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    processor = Wav2Vec2Processor.from_pretrained(model_dir)
    model = Wav2Vec2ForCTC.from_pretrained(model_dir)
    model.eval()
    audio, sr = sf.read(audio_path, dtype="float32", always_2d=False)
    if getattr(audio, "ndim", 1) == 2:
        audio = audio.mean(axis=1)
    if int(sr) != TARGET_SAMPLE_RATE:
        import librosa

        audio = librosa.resample(audio, orig_sr=int(sr), target_sr=TARGET_SAMPLE_RATE)
    inputs = processor(audio, sampling_rate=TARGET_SAMPLE_RATE, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values).logits
    pred_ids = torch.argmax(logits, dim=-1)
    return processor.batch_decode(pred_ids)[0]
