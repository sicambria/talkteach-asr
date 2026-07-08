"""Stage 2 journey script: LoRA fine-tune whisper-small on LibriSpeech, evaluate on test-clean.

Usage:
    PYTHONPATH=backend:. python scripts/journey/s2_finetune_whisper_small.py [--data-dir DIR] [--minutes N]
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
from talkteach.engines import get_engine
from talkteach.engines.base import TrainProgress
from talkteach.engines._whisper_train import run_real_training
from talkteach.director.types import DataProfile, EngineKind
from talkteach.sota.scoring import wer, cer
from talkteach.sota.datasets import load_clip_transcript_pairs
from faster_whisper import WhisperModel


def progress_cb(p: TrainProgress) -> None:
    pct = int(p.fraction * 100)
    msg = p.message[:80] if p.message else ""
    sys.stderr.write(f"\r[{pct:3d}%] {msg}")
    sys.stderr.flush()


def main():
    import argparse
    p = argparse.ArgumentParser(description="Stage 2: Fine-tune whisper-small on LibriSpeech")
    p.add_argument("--data-dir", type=Path,
                   default=Path.home() / ".cache/talkteach/sota/librispeech_train_clean_100/LibriSpeech/train-clean-100")
    p.add_argument("--eval-dir", type=Path,
                   default=Path.home() / ".cache/talkteach/sota/librispeech_test_clean")
    p.add_argument("--workdir", type=Path, default=Path("/tmp/talkteach-s2-finetune"))
    p.add_argument("--minutes", type=float, default=30, help="Approx minutes of training data to use")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--skip-train", action="store_true", help="Skip training, only evaluate")
    args = p.parse_args()

    # ── Build training manifest ──
    if not args.skip_train:
        train_root = args.data_dir
        if not train_root.exists():
            print(f"ERROR: Training data not found at {train_root}")
            print("  Run: PYTHONPATH=backend:. python -c 'from talkteach.sota.datasets import download; download(\"librispeech_train_clean_100\", Path.home()/ \".cache/talkteach/sota\")'")
            return 1

        print(f"Building manifest from {train_root}...")
        full_manifest = import_librispeech(str(train_root))
        total_dur = sum(m.get("duration_s", 0) for m in full_manifest) / 60.0
        print(f"  Total: {len(full_manifest)} clips, {total_dur:.0f} min")

        # Take a prefix of clips up to --minutes
        target_s = args.minutes * 60.0
        acc = 0.0
        manifest = []
        for m in full_manifest:
            manifest.append(m)
            acc += m.get("duration_s", 1.0)
            if acc >= target_s:
                break

        train_dur = sum(m.get("duration_s", 0) for m in manifest) / 60.0
        print(f"  Subset: {len(manifest)} clips, {train_dur:.0f} min")
    else:
        manifest = []

    # ── Build training plan ──
    plan = plan_from_config({
        "engine": "whisper_lora",
        "base_checkpoint": "openai/whisper-small",
        "compute": "cpu",
        "precision": "fp32",
        "batch_size": 1,
        "grad_accum": 16,
        "learning_rate": 1e-4,
        "epochs": args.epochs,
        "warmup_ratio": 0.1,
        "early_stop_patience": 3,
        "lora_rank": 8,
        "freeze_encoder": True,
        "rationale": ["journey-stage-2: LoRA fine-tune whisper-small on LibriSpeech subset"],
    })
    print(f"\nTraining plan:")
    for f in ["base_checkpoint", "lora_rank", "lora_alpha", "epochs", "batch_size",
              "grad_accum", "learning_rate", "freeze_encoder"]:
        print(f"  {f}: {getattr(plan, f)}")
    print()

    # ── Train ──
    workdir = str(args.workdir)
    if not args.skip_train:
        print(f"Training to {workdir}...")
        t0 = time.time()
        result = run_real_training(
            plan, manifest, workdir,
            progress=progress_cb, should_stop=None, language="en"
        )
        elapsed = time.time() - t0
        print(f"\nTraining done in {elapsed/60:.1f} min")
        print(f"  Smartness: {result.smartness}")
        print(f"  Message: {result.message}")
    else:
        print("Skipping training (--skip-train)")

    # ── Evaluate on test-clean ──
    print(f"\nEvaluating on test-clean ({args.eval_dir})...")
    eval_pairs = load_clip_transcript_pairs(args.eval_dir, max_clips=100)

    # Baseline (pretrained whisper-small via faster-whisper)
    print("  Running baseline (pretrained whisper-small)...")
    base_model = WhisperModel("small", device="cpu", compute_type="int8")
    base_refs, base_hyps = [], []
    for ap, ref in eval_pairs:
        segs, _ = base_model.transcribe(str(ap), beam_size=5)
        hyp = " ".join(s.text.strip() for s in segs)
        base_refs.append(ref)
        base_hyps.append(hyp)
    base_wer = wer(base_refs, base_hyps)
    base_cer = cer(base_refs, base_hyps)

    # Fine-tuned (load from workdir)
    print("  Running fine-tuned model...")
    from talkteach.engines._whisper_train import transcribe_with_transformers

    ft_refs, ft_hyps = [], []
    ft_times = []
    for ap, ref in eval_pairs:
        t0 = time.time()
        hyp = transcribe_with_transformers(str(ap), workdir, "openai/whisper-small", "en")
        ft_times.append(time.time() - t0)
        ft_refs.append(ref)
        ft_hyps.append(hyp)

    ft_wer = wer(ft_refs, ft_hyps)
    ft_cer = cer(ft_refs, ft_hyps)

    # ── Report ──
    rel_change = (base_wer - ft_wer) / base_wer * 100 if base_wer > 0 else 0
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"  Baseline (pretrained whisper-small): WER={base_wer:.4f} ({base_wer*100:.2f}%) CER={base_cer:.4f}")
    print(f"  Fine-tuned (whisper-small + LoRA):   WER={ft_wer:.4f} ({ft_wer*100:.2f}%) CER={ft_cer:.4f}")
    print(f"  Relative change: {rel_change:+.1f}%")
    print(f"  Avg decode time: {sum(ft_times)/len(ft_times):.2f}s/clip")

    # Score against D01 bands
    from talkteach.sota.scoring import score_against_bands
    bands = [(1000, 0.010), (950, 0.015), (900, 0.020), (800, 0.030), (700, 0.050), (600, 0.080)]
    base_score, base_band = score_against_bands(base_wer, bands, higher_is_better=False)
    ft_score, ft_band = score_against_bands(ft_wer, bands, higher_is_better=False)
    print(f"  Baseline score: {base_score} ({base_band})")
    print(f"  Fine-tuned score: {ft_score} ({ft_band})")

    # Write results
    results = {
        "experiment": "s2_finetune_whisper_small",
        "training_minutes": args.minutes,
        "epochs": args.epochs,
        "baseline_wer": base_wer,
        "baseline_cer": base_cer,
        "baseline_score": base_score,
        "baseline_band": base_band,
        "finetuned_wer": ft_wer,
        "finetuned_cer": ft_cer,
        "finetuned_score": ft_score,
        "finetuned_band": ft_band,
        "relative_change_pct": rel_change,
        "eval_clips": len(eval_pairs),
    }
    result_path = args.workdir / "results.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(results, result_path.open("w"), indent=2)
    print(f"\nResults saved to {result_path}")

    return 0 if not args.skip_train else 0


if __name__ == "__main__":
    sys.exit(main())
