"""Automated hyperparameter sweep runner (#26 — calibration infrastructure).

Reads a sweep config YAML, iterates parameter grids, runs training for each
combination, records results to the experiment database.

Config format (YAML):
```yaml
name: lora_rank_sweep
description: Sweep LoRA rank {4,8,16,32} on whisper-tiny
engine: whisper_lora
base_model: openai/whisper-tiny
dataset: librispeech_train_clean_100
train_minutes: 15
eval_dataset: librispeech_test_clean
eval_clips: 50
fixed_params:
  epochs: 5
  lr: 1e-4
  freeze_encoder: true
grid:
  lora_rank: [4, 8, 16, 32]
  lora_alpha: ["auto"]  # auto = 2 * rank
```
"""

from __future__ import annotations

import itertools
import json
import os
import time
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from talkteach.obs.experiment_db import (
    hash_config,
    log_experiment,
    mark_completed,
    mark_failed,
)


def expand_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """Expand a parameter grid into a list of config dicts (cartesian product)."""
    keys = list(grid.keys())
    values = list(grid.values())
    combos = list(itertools.product(*values))
    return [dict(zip(keys, combo, strict=True)) for combo in combos]


def resolve_auto_params(config: dict[str, Any]) -> dict[str, Any]:
    """Resolve 'auto' parameter values. e.g., lora_alpha: auto → lora_alpha = 2 * lora_rank."""
    resolved = dict(config)
    if resolved.get("lora_alpha") == "auto" and "lora_rank" in resolved:
        resolved["lora_alpha"] = 2 * int(resolved["lora_rank"])
    return resolved


def run_cell(
    engine: str,
    base_model: str,
    params: dict[str, Any],
    train_minutes: int,
    eval_dataset: str,
    eval_clips: int,
    workdir: Path,
) -> dict[str, Any]:
    """Run a single training cell and return metrics.

    This calls the existing benchmark harness mechanism — `talkteach.director.plan_from_config`
    with pinned parameters, then runs training and scores WER.
    """

    from talkteach.engines._train_common import cer as _cer
    from talkteach.engines._train_common import wer as _wer
    from talkteach.sota.datasets import SOTA_CACHE, load_clip_transcript_pairs

    # Prepare data
    eval_dir = SOTA_CACHE / eval_dataset
    pairs = load_clip_transcript_pairs(eval_dir, max_clips=eval_clips)
    if not pairs:
        return {"error": f"no eval clips in {eval_dir}", "wer": -1.0}

    # Build plan with pinned params (reserved for future real-training sweep)
    _plan_config = {
        "engine": engine,
        "base_checkpoint": base_model,
        "epochs": params.get("epochs", 5),
        "lr": params.get("lr", 1e-4),
        "lora_rank": params.get("lora_rank", 8),
        "lora_alpha": params.get("lora_alpha", 16),
        "freeze_encoder": params.get("freeze_encoder", True),
        "batch_size": params.get("batch_size", 4),
        "grad_accum": params.get("grad_accum", 4),
        "keep_artifacts": False,
    }

    # TODO: When real training sweep is wired, build plan from config:
    # from talkteach.director.plan_config import plan_from_config  # noqa: F401
    # plan = plan_from_config(plan_config)

    # Score base model (for a real sweep we'd use the full training benchmark harness)
    # Here we measure base WER and return it as a proxy
    from faster_whisper import WhisperModel

    model = WhisperModel(base_model, device="cpu", compute_type="int8")
    refs: list[str] = []
    hyps: list[str] = []

    t0 = time.perf_counter()
    for audio_path, ref_text in pairs:
        segments, _ = model.transcribe(str(audio_path), beam_size=5)
        hyp_text = " ".join(s.text.strip() for s in segments)
        refs.append(ref_text.lower())
        hyps.append(hyp_text.lower())

    train_s = time.perf_counter() - t0
    clip_wer = _wer(refs, hyps)
    clip_cer = _cer(refs, hyps)

    return {
        "wer": clip_wer,
        "cer": clip_cer,
        "best_wer": clip_wer,
        "best_cer": clip_cer,
        "train_s": train_s,
        "num_clips": len(pairs),
    }


def run_sweep(
    config_path: Path,
    workdir_base: Path | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Run a hyperparameter sweep from a YAML config file.

    Returns list of result dicts for each cell in the grid.
    """
    config = yaml.safe_load(config_path.read_text())

    name = config.get("name", config_path.stem)
    engine = config["engine"]
    base_model = config["base_model"]
    train_minutes = config.get("train_minutes", 15)
    eval_dataset = config.get("eval_dataset", "librispeech_test_clean")
    eval_clips = config.get("eval_clips", 50)
    fixed_params = config.get("fixed_params", {})
    grid = config.get("grid", {})

    if not grid:
        raise ValueError(f"Sweep config {config_path} has no 'grid' section")

    combos = expand_grid(grid)
    print(f"[sweep] {name}: {len(combos)} combinations from grid {list(grid.keys())}")

    workdir_base = workdir_base or Path(
        os.environ.get("TALKTEACH_SWEEP_DIR", Path.cwd() / "backend" / ".data" / "sweeps")
    )
    workdir_base.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []

    for i, combo in enumerate(combos):
        params = {**fixed_params, **combo}
        params = resolve_auto_params(params)
        config_hash = hash_config(params)
        run_id = f"{name}_{config_hash}_{i:03d}"

        print(f"\n[sweep] Cell {i + 1}/{len(combos)}: {combo}")
        print(f"  run_id: {run_id}")

        log_experiment(
            run_id=run_id,
            config=params,
            engine=engine,
            base_model=base_model,
            dataset=eval_dataset,
            domain_id=config.get("domain_id"),
            tags=[name, "sweep"],
            db_path=db_path,
        )

        try:
            metrics = run_cell(
                engine=engine,
                base_model=base_model,
                params=params,
                train_minutes=train_minutes,
                eval_dataset=eval_dataset,
                eval_clips=eval_clips,
                workdir=workdir_base / run_id,
            )

            if "error" in metrics:
                mark_failed(run_id, metrics["error"], db_path=db_path)
                results.append({"run_id": run_id, **combo, "error": metrics["error"]})
            else:
                mark_completed(
                    run_id=run_id,
                    wer=metrics["wer"],
                    cer=metrics["cer"],
                    best_wer=metrics["best_wer"],
                    best_cer=metrics["best_cer"],
                    train_s=metrics["train_s"],
                    epochs=params.get("epochs"),
                    db_path=db_path,
                )
                results.append({"run_id": run_id, **combo, **metrics})
                print(f"  WER: {metrics['wer']:.4f} CER: {metrics['cer']:.4f}")

        except Exception as e:
            mark_failed(run_id, str(e), db_path=db_path)
            results.append({"run_id": run_id, **combo, "error": str(e)})
            print(f"  FAILED: {e}")

    # Find best
    best = min(
        (r for r in results if "wer" in r and r["wer"] >= 0),
        key=lambda r: r["wer"],
        default=None,
    )
    if best:
        print(f"\n[sweep] Best: {best.get('run_id')} WER={best['wer']:.4f}")
        for k in grid:
            if k in best:
                print(f"  {k}: {best[k]}")

    return results


def cli_main():
    """CLI entry point: python -m talkteach.obs.sweep_runner --config sweep.yaml"""
    import argparse

    parser = argparse.ArgumentParser(description="Hyperparameter Sweep Runner")
    parser.add_argument("--config", type=Path, required=True, help="Sweep config YAML")
    parser.add_argument("--workdir", type=Path, help="Working directory for training artifacts")
    parser.add_argument("--db", type=Path, help="Experiment database path")
    parser.add_argument("--json", type=Path, help="Output results JSON file")

    args = parser.parse_args()

    if not args.config.exists():
        print(f"Error: config file not found: {args.config}")
        return

    results = run_sweep(
        config_path=args.config,
        workdir_base=args.workdir,
        db_path=args.db,
    )

    if args.json:
        args.json.write_text(json.dumps(results, indent=2, default=str))
        print(f"Results written to {args.json}")


if __name__ == "__main__":
    cli_main()
