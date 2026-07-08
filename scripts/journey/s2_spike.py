"""Stage 2 spike: LoRA fine-tune whisper-tiny on LibriSpeech, evaluate on test-clean.

Fast spike to validate whether LoRA fine-tuning helps on in-domain data.
If successful, scale to whisper-small with more data/epochs.
"""
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from talkteach.data.import_manifest import import_librispeech
from talkteach.director.plan_config import plan_from_config
from talkteach.engines._whisper_train import run_real_training
from talkteach.engines.base import TrainProgress
from talkteach.sota.scoring import wer, cer, score_against_bands
from talkteach.sota.datasets import load_clip_transcript_pairs
from faster_whisper import WhisperModel
from talkteach.director.types import TrainingPlan as TP


def progress_cb(p: TrainProgress) -> None:
    pct = int(p.fraction * 100)
    msg = (p.message or "")[:80]
    sys.stderr.write(f"\r[{pct:3d}%] {msg}\n" if "Epoch" in msg else f"\r[{pct:3d}%] {msg}")
    sys.stderr.flush()


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path,
                   default=Path.home() / ".cache/talkteach/sota/LibriSpeech/train-clean-100")
    p.add_argument("--eval-dir", type=Path,
                   default=Path.home() / ".cache/talkteach/sota/librispeech_test_clean")
    p.add_argument("--workdir", type=Path, default=Path("/tmp/talkteach-s2"))
    p.add_argument("--minutes", type=float, default=30)
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--model", choices=["tiny", "small"], default="tiny")
    p.add_argument("--skip-train", action="store_true")
    args = p.parse_args()

    model_id = f"openai/whisper-{args.model}"
    if args.skip_train:
        workdir = str(args.workdir)
    else:
        workdir = str(args.workdir / f"whisper-{args.model}-{args.minutes}min")

    # Build manifest
    full = import_librispeech(str(args.data_dir))
    target_s = args.minutes * 60.0
    acc, manifest = 0.0, []
    for m in full:
        manifest.append(m)
        acc += m.get("duration_s", 1.0)
        if acc >= target_s:
            break
    train_dur = sum(m.get("duration_s", 0) for m in manifest) / 60.0
    n_manifest = len(manifest)

    plan = plan_from_config({
        "engine": "whisper_lora",
        "base_checkpoint": model_id,
        "compute": "cpu", "precision": "fp32",
        "batch_size": 1, "grad_accum": 16,
        "learning_rate": 1e-4, "epochs": args.epochs,
        "warmup_ratio": 0.1, "early_stop_patience": 3,
        "lora_rank": 8, "freeze_encoder": True,
        "rationale": ["journey-s2-spike"],
    })

    print(f"TRAINING: {model_id} | {n_manifest} clips ({train_dur:.1f} min) | {args.epochs} epoch(s)")
    print(f"  batch_size={plan.batch_size} grad_accum={plan.grad_accum} lr={plan.learning_rate}")
    print(f"  lora_rank={plan.lora_rank} freeze_encoder={plan.freeze_encoder}")
    print()

    t0 = time.time()
    if not args.skip_train:
        result = run_real_training(plan, manifest, workdir, progress=progress_cb, should_stop=None, language="en")
        elapsed = time.time() - t0
        print(f"\nTraining: {elapsed/60:.1f} min | smartness={result.smartness}")
    else:
        elapsed = 0
        print(f"Skip training, evaluating existing model at {workdir}")

    # Evaluate
    print("\nEvaluating on test-clean...")
    eval_pairs = load_clip_transcript_pairs(args.eval_dir, max_clips=100)

    # Baseline
    fw_model = args.model.replace("_", "-")
    base_model = WhisperModel(fw_model, device="cpu", compute_type="int8")
    base_refs, base_hyps = [], []
    for ap, ref in eval_pairs:
        segs, _ = base_model.transcribe(str(ap), beam_size=5)
        base_hyps.append(" ".join(s.text.strip() for s in segs))
        base_refs.append(ref)
    base_wer = wer(base_refs, base_hyps)

    # Fine-tuned
    from talkteach.engines._whisper_train import transcribe_with_transformers
    ft_refs, ft_hyps = [], []
    for ap, ref in eval_pairs:
        hyp = transcribe_with_transformers(str(ap), workdir, "en")
        ft_hyps.append(hyp)
        ft_refs.append(ref)
    ft_wer = wer(ft_refs, ft_hyps)

    rel = (base_wer - ft_wer) / base_wer * 100 if base_wer > 0 else 0
    bands = [(1000, 0.01), (950, 0.015), (900, 0.02), (800, 0.03), (700, 0.05), (600, 0.08)]
    b_score, b_band = score_against_bands(base_wer, bands, False)
    f_score, f_band = score_against_bands(ft_wer, bands, False)

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"  {args.model:6s} baseline:   WER={base_wer:.4f} ({base_wer*100:.2f}%) Band={b_band} Score={b_score}")
    print(f"  {args.model:6s} fine-tuned: WER={ft_wer:.4f} ({ft_wer*100:.2f}%) Band={f_band} Score={f_score}")
    print(f"  Relative change: {rel:+.1f}% ({abs(ft_wer-base_wer)*100:+.2f}pp)")

    results = dict(
        experiment="s2_spike", model=args.model, training_minutes=args.minutes,
        epochs=args.epochs, elapsed_min=elapsed/60,
        baseline_wer=base_wer, finetuned_wer=ft_wer,
        relative_change_pct=rel, abs_change_pp=(ft_wer-base_wer)*100,
        baseline_score=b_score, finetuned_score=f_score,
        baseline_band=b_band, finetuned_band=f_band,
        eval_clips=len(eval_pairs),
    )
    rp = (args.workdir if args.skip_train else args.workdir / f"whisper-{args.model}-{args.minutes}min") / f"results-{args.model}-{args.minutes}min.json"
    json.dump(results, rp.open("w"), indent=2)
    print(f"  Results: {rp}")

if __name__ == "__main__":
    sys.exit(main())
