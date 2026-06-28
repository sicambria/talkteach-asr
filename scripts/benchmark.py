#!/usr/bin/env python3
"""CLI for the TTS × ASR benchmark (roadmap #6 / #1–5).

Generate real synthetic speech with one or more TTS engines, train each ASR engine
on it, and report WER/CER/train-time on a shared held-out eval set. The heavy lifting
lives in :mod:`talkteach.benchmark`; this is a thin, dependency-light CLI.

    # needs the [ml] + [tts] extras and (for espeak cells) the espeak-ng binary
    python scripts/benchmark.py --config benchmarks/quick.yaml
    python scripts/benchmark.py --config benchmarks/quick.yaml --out results/quick.json
    python scripts/benchmark.py --config benchmarks/quick.yaml --train-clips 4 --eval-clips 3

See project/docs/BENCHMARKING.md for the config schema and methodology.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


def _load_config(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    if path.endswith((".yaml", ".yml")):
        import yaml  # PyYAML ships with the backend deps

        return yaml.safe_load(text)
    return json.loads(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--config", required=True, help="benchmark config (.yaml/.yml/.json)"
    )
    ap.add_argument(
        "--out", default=None, help="write JSON results here (default: under --workdir)"
    )
    ap.add_argument(
        "--report",
        default=None,
        help="write the Markdown scoreboard report here (default: under --workdir)",
    )
    ap.add_argument(
        "--workdir",
        default=None,
        help="scratch dir for audio + checkpoints (default: temp)",
    )
    ap.add_argument(
        "--train-clips", type=int, default=None, help="override config train_clips"
    )
    ap.add_argument(
        "--eval-clips", type=int, default=None, help="override config eval_clips"
    )
    ap.add_argument(
        "--medals",
        type=int,
        default=None,
        help="how many top engines get medals (default 3)",
    )
    args = ap.parse_args(argv)

    from talkteach.benchmark import (
        format_scoreboard,
        format_table,
        run_benchmark,
        write_markdown,
        write_report,
    )

    config = _load_config(args.config)
    if args.train_clips is not None:
        config["train_clips"] = args.train_clips
    if args.eval_clips is not None:
        config["eval_clips"] = args.eval_clips
    if args.medals is not None:
        config["medals"] = args.medals
    medals = int(config.get("medals", 3))

    workdir = args.workdir or tempfile.mkdtemp(prefix="talkteach-bench-")
    report = run_benchmark(config, workdir)

    # Present: the full matrix, then the medal-ranked ELO scoreboard.
    print(format_table(report))
    print("\n" + format_scoreboard(report, medals=medals))

    # Record: JSON results + a Markdown report (the durable artifact).
    out = args.out or str(Path(workdir) / "results.json")
    write_report(report, out)
    md = args.report or str(Path(workdir) / "REPORT.md")
    Path(md).parent.mkdir(parents=True, exist_ok=True)
    write_markdown(
        report, md, generated_at=time.strftime("%Y-%m-%d %H:%M:%S %Z"), medals=medals
    )
    print(f"\nWrote JSON results → {out}\nWrote Markdown report → {md}")

    # Non-zero exit if every cell failed/skipped, so CI can catch a dead config.
    if report.cells and all(c.status != "ok" for c in report.cells):
        print(
            "WARNING: no cell completed successfully (deps/binaries missing?)",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
