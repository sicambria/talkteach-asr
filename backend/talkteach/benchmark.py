"""TTS × ASR benchmark — compare ASR engines on real synthetic speech, for real.

This is the payoff of the TTS providers and ``plan_from_config``: a single,
config-driven run that generates labelled speech with one or more TTS engines,
trains each ASR engine on it, and measures word/character error rate on a **shared,
held-out** eval set — so the numbers across engines are actually comparable.

Methodology (why each piece matters):

* **Real speech, known transcript.** Prompts are spoken by a :class:`TTSProvider`;
  the prompt IS the ground truth. WER therefore measures recognition, not (as with
  the old sine-tone fixtures) noise.
* **Disjoint, shared eval set.** Train and eval prompts never overlap, and *every*
  engine is scored on the *same* eval clips — not each engine's own internal split,
  which would vary per run and make cells incomparable.
* **Quality gate.** Generated clips are run through :func:`audio.quality.analyze_file`
  (the same gate real recordings face); the good-fraction is reported so a bad TTS
  voice can't silently poison the comparison.
* **Pinned hyperparameters.** Each cell's plan comes from
  :func:`director.plan_config.plan_from_config`, not the director's hardware
  heuristics, so a comparison holds everything fixed except the engine.

Comparable metrics are **WER / CER / train-time** (export formats differ per engine,
so a single portable artifact is not the comparison axis — see project/docs/ENGINES.md).

Run it via ``scripts/benchmark.py`` (a thin CLI over :func:`run_benchmark`).
"""

from __future__ import annotations

import contextlib
import gc
import json
import random
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from talkteach.audio.quality import Verdict, analyze_file
from talkteach.director.plan_config import plan_from_config
from talkteach.engines import get_engine
from talkteach.engines._train_common import cer, smartness_from_wer, wer
from talkteach.prompts import get_prompts
from talkteach.tts import get_tts_provider
from talkteach.tts.dataset import synthesize_dataset


@dataclass
class CellResult:
    """One (TTS provider, ASR engine) cell of the comparison matrix."""

    tts: str
    engine: str
    status: str  # "ok" | "skipped" | "error"
    detail: str = ""
    wer: float | None = None
    cer: float | None = None
    smartness: float | None = None
    train_seconds: float | None = None
    eval_clips: int = 0
    train_good_fraction: float | None = None
    # Per-eval-clip WER, aligned to the shared eval set — the input to the ELO
    # head-to-head (engine A beats B on a clip if its WER there is lower).
    per_clip_wer: list[float] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    name: str
    language: str
    train_clips: int
    eval_clips: int
    cells: list[CellResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _split_prompts(language: str | None, n_train: int, n_eval: int) -> tuple[list[str], list[str]]:
    """Return (train_prompts, eval_prompts) that DO NOT overlap.

    Pulls from the karaoke set and partitions it. If the set is too small for a
    fully disjoint split, the eval set wraps onto leftover prompts and the caller
    is warned via the returned counts (eval may be shorter than requested).
    """
    prompts = get_prompts(language)
    train = prompts[:n_train]
    rest = prompts[n_train:]
    # If the set is too small, use whatever is left (still disjoint from train)
    # rather than leaking train sentences into eval.
    eval_set = rest if len(rest) < n_eval else rest[:n_eval]
    return train, eval_set


def _good_fraction(manifest: list[dict]) -> float:
    if not manifest:
        return 0.0
    good = sum(1 for m in manifest if analyze_file(m["path"]).verdict is Verdict.GOOD)
    return good / len(manifest)


def run_benchmark(config: dict[str, Any], workroot: str | Path) -> BenchmarkReport:
    """Execute the full TTS×ASR matrix described by ``config``.

    See ``benchmarks/quick.yaml`` for the schema. ``workroot`` is a scratch dir for
    generated audio and per-cell training checkpoints. Providers/engines whose deps
    are missing are recorded as ``skipped`` (never crash the whole run).
    """
    name = config.get("name", "benchmark")
    language = config.get("language", "en")
    n_train = int(config.get("train_clips", 6))
    n_eval = int(config.get("eval_clips", 4))
    sample_rate = int(config.get("sample_rate", 16_000))
    tts_specs = config.get("tts") or [{"provider": "piper"}]
    engine_specs = config.get("engines") or [{"name": "whisper", "plan": {}}]
    # A trained model (esp. wav2vec2, ~GBs) is only needed while its cell is being
    # scored. Delete it afterwards by default so an N-cell matrix needs disk for ONE
    # model at a time, not N — see project/docs/LEARNINGS.md (RCA: disk-quota wedge).
    keep_artifacts = bool(config.get("keep_artifacts", False))

    root = Path(workroot)
    root.mkdir(parents=True, exist_ok=True)
    train_prompts, eval_prompts = _split_prompts(language, n_train, n_eval)

    report = BenchmarkReport(
        name=name, language=language, train_clips=len(train_prompts), eval_clips=len(eval_prompts)
    )

    for tts_spec in tts_specs:
        tts_name = tts_spec["provider"]
        voice = tts_spec.get("voice")
        kwargs = {k: v for k, v in tts_spec.items() if k not in ("provider", "voice")}
        try:
            provider = get_tts_provider(tts_name, **kwargs)
        except KeyError as exc:
            report.cells.append(CellResult(tts_name, "-", "error", str(exc)))
            continue
        ok, msg = provider.is_available()
        if not ok:
            for eng_spec in engine_specs:
                report.cells.append(
                    CellResult(tts_name, eng_spec.get("name", "?"), "skipped", f"TTS: {msg}")
                )
            continue

        tts_dir = root / tts_name
        voices = [voice] if voice else None
        train_mani = synthesize_dataset(
            provider,
            tts_dir / "train",
            prompts=train_prompts,
            voices=voices,
            sample_rate=sample_rate,
            prefix="train",
        )
        eval_mani = synthesize_dataset(
            provider,
            tts_dir / "eval",
            prompts=eval_prompts,
            voices=voices,
            sample_rate=sample_rate,
            prefix="eval",
        )
        train_gf = _good_fraction(train_mani)
        refs = [m["text"] for m in eval_mani]

        for eng_spec in engine_specs:
            eng_name = eng_spec.get("name", eng_spec.get("plan", {}).get("engine", "?"))
            run_dir = tts_dir / f"run_{eng_name}"
            cell = _run_cell(
                tts_name,
                eng_name,
                eng_spec.get("plan", {}),
                train_mani,
                eval_mani,
                refs,
                workdir=run_dir,
                train_good_fraction=train_gf,
            )
            report.cells.append(cell)
            # Release model/tensor memory before the next cell so a multi-engine
            # matrix doesn't accumulate several models in RAM at once.
            _free_memory()
            # Bound disk: drop the (potentially multi-GB) checkpoint now that the
            # cell is scored, unless the caller explicitly wants to keep artifacts.
            if not keep_artifacts:
                shutil.rmtree(run_dir, ignore_errors=True)

    return report


def _free_memory() -> None:
    """Best-effort release of model memory between cells (gc + torch cache)."""
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is not None:  # only if an engine actually imported it
        with contextlib.suppress(Exception):  # cache clear is best-effort
            torch.cuda.empty_cache()


def _run_cell(
    tts_name: str,
    eng_name: str,
    plan_cfg: dict[str, Any],
    train_mani: list[dict],
    eval_mani: list[dict],
    refs: list[str],
    *,
    workdir: Path,
    train_good_fraction: float,
) -> CellResult:
    try:
        plan = plan_from_config(plan_cfg)
        engine = get_engine(plan.engine)
    except (KeyError, NotImplementedError) as exc:
        return CellResult(tts_name, eng_name, "error", str(exc))

    available, msg = engine.is_available()
    if not available:
        return CellResult(tts_name, eng_name, "skipped", f"engine: {msg}")

    workdir.mkdir(parents=True, exist_ok=True)
    try:
        t0 = time.perf_counter()
        engine.train(plan, train_mani, str(workdir))
        train_seconds = time.perf_counter() - t0
        hyps = [engine.transcribe(m["path"], model_dir=str(workdir)) for m in eval_mani]
    except Exception as exc:  # noqa: BLE001 - one bad cell shouldn't kill the matrix
        return CellResult(tts_name, eng_name, "error", f"{type(exc).__name__}: {exc}")

    wer_v = wer(refs, hyps)
    per_clip = [round(wer([r], [h]), 4) for r, h in zip(refs, hyps, strict=False)]
    return CellResult(
        tts=tts_name,
        engine=eng_name,
        status="ok",
        wer=round(wer_v, 4),
        cer=round(cer(refs, hyps), 4),
        smartness=round(smartness_from_wer(wer_v), 4),
        train_seconds=round(train_seconds, 2),
        eval_clips=len(eval_mani),
        train_good_fraction=round(train_good_fraction, 3),
        per_clip_wer=per_clip,
    )


def format_table(report: BenchmarkReport) -> str:
    """Render the report as a plain-text table (the human-facing matrix)."""
    header = f"Benchmark '{report.name}'  lang={report.language}  "
    header += f"train={report.train_clips} eval={report.eval_clips} clips"
    cols = ["TTS", "Engine", "Status", "WER", "CER", "Smartness", "Train(s)", "Detail"]
    rows = [cols]
    for c in report.cells:
        rows.append(
            [
                c.tts,
                c.engine,
                c.status,
                "" if c.wer is None else f"{c.wer:.3f}",
                "" if c.cer is None else f"{c.cer:.3f}",
                "" if c.smartness is None else f"{c.smartness:.3f}",
                "" if c.train_seconds is None else f"{c.train_seconds:.1f}",
                c.detail[:48],
            ]
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(cols))]
    lines = [header, ""]
    for ri, row in enumerate(rows):
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
        if ri == 0:
            lines.append("  ".join("-" * widths[i] for i in range(len(cols))))
    return "\n".join(lines)


# =============================================================================
# ELO leaderboard — a single comparable number across all TTS×clip conditions.
#
# WER on the shared eval set is the *ground truth*; ELO is a presentation layer on
# top of it (LLM arenas use ELO because they have NO ground-truth metric — we do).
# Its value here: one familiar leaderboard number that aggregates across voices and
# clip difficulty without a few brutal clips dominating a mean, and that fits the
# matrix naturally — each engine plays a "match" per (TTS, clip), winning the clips
# it transcribes better. With few clips it is indicative; raw WER stays the truth.
# =============================================================================


@dataclass
class EngineScore:
    """Aggregated leaderboard row for one engine across all conditions it ran."""

    engine: str
    elo: int
    wins: int
    losses: int
    ties: int
    win_rate: float | None  # decided matches only; None if it played none
    mean_wer: float | None
    mean_cer: float | None
    mean_train_seconds: float | None
    cells: int  # number of (TTS) conditions it completed


def _clip_matches(report: BenchmarkReport, eps: float = 1e-9) -> list[tuple[str, str, float]]:
    """Per-(TTS, clip) head-to-head outcomes: (engineA, engineB, scoreA∈{1,.5,0}).

    Within each TTS condition every pair of completed engines is compared on each
    shared eval clip; the lower WER wins (0.5 on a tie). Engines that appear under
    several TTS providers therefore play more matches — more conditions, more signal.
    """
    matches: list[tuple[str, str, float]] = []
    by_tts: dict[str, list[CellResult]] = {}
    for c in report.cells:
        if c.status == "ok" and c.per_clip_wer:
            by_tts.setdefault(c.tts, []).append(c)
    for cells in by_tts.values():
        if len(cells) < 2:
            continue  # need ≥2 engines on the same clips to have a match
        n = min(len(c.per_clip_wer) for c in cells)
        for i in range(n):
            for a in range(len(cells)):
                for b in range(a + 1, len(cells)):
                    wa, wb = cells[a].per_clip_wer[i], cells[b].per_clip_wer[i]
                    score = 0.5 if abs(wa - wb) <= eps else (1.0 if wa < wb else 0.0)
                    matches.append((cells[a].engine, cells[b].engine, score))
    return matches


def compute_elo(
    report: BenchmarkReport,
    *,
    base: float = 1000.0,
    k: float = 24.0,
    passes: int = 80,
    seed: int = 1234,
) -> dict[str, dict[str, float]]:
    """ELO rating + win/loss/tie per engine from per-clip head-to-heads.

    Iterates the match list over several shuffled passes (fixed seed) so the rating
    is stable and not biased by match order. Returns
    ``{engine: {"elo", "wins", "losses", "ties"}}``.
    """
    engines = sorted({c.engine for c in report.cells if c.status == "ok" and c.per_clip_wer})
    stats = {e: {"elo": base, "wins": 0.0, "losses": 0.0, "ties": 0.0} for e in engines}
    matches = _clip_matches(report)

    # Win/loss/tie counted once over the real match set (not per shuffled pass).
    for a, b, s in matches:
        if s == 1.0:
            stats[a]["wins"] += 1
            stats[b]["losses"] += 1
        elif s == 0.0:
            stats[a]["losses"] += 1
            stats[b]["wins"] += 1
        else:
            stats[a]["ties"] += 1
            stats[b]["ties"] += 1

    rng = random.Random(seed)
    for _ in range(passes):
        order = matches[:]
        rng.shuffle(order)
        for a, b, s in order:
            ea = 1.0 / (1.0 + 10 ** ((stats[b]["elo"] - stats[a]["elo"]) / 400.0))
            stats[a]["elo"] += k * (s - ea)
            stats[b]["elo"] += k * ((1.0 - s) - (1.0 - ea))
    return stats


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def scoreboard(report: BenchmarkReport) -> list[EngineScore]:
    """Aggregate the matrix into a per-engine leaderboard, sorted best-first.

    Sort key: ELO desc, then mean WER asc (the objective tie-breaker).
    """
    elo = compute_elo(report)
    rows: list[EngineScore] = []
    engines = sorted({c.engine for c in report.cells if c.status == "ok"})
    for e in engines:
        cells = [c for c in report.cells if c.status == "ok" and c.engine == e]
        st = elo.get(e, {"elo": 1000.0, "wins": 0.0, "losses": 0.0, "ties": 0.0})
        wins, losses, ties = int(st["wins"]), int(st["losses"]), int(st["ties"])
        decided = wins + losses
        rows.append(
            EngineScore(
                engine=e,
                elo=round(st["elo"]),
                wins=wins,
                losses=losses,
                ties=ties,
                win_rate=round(wins / decided, 3) if decided else None,
                mean_wer=_mean([c.wer for c in cells if c.wer is not None]),
                mean_cer=_mean([c.cer for c in cells if c.cer is not None]),
                mean_train_seconds=_mean(
                    [c.train_seconds for c in cells if c.train_seconds is not None]
                ),
                cells=len(cells),
            )
        )
    rows.sort(key=lambda r: (-r.elo, r.mean_wer if r.mean_wer is not None else 1e9))
    return rows


def format_scoreboard(report: BenchmarkReport) -> str:
    """Plain-text leaderboard (ranked by ELO, with raw WER/CER/time alongside)."""
    board = scoreboard(report)
    cols = ["#", "Engine", "ELO", "W-L-T", "Win%", "MeanWER", "MeanCER", "Train(s)", "Conds"]
    rows = [cols]
    for i, r in enumerate(board, 1):
        rows.append(
            [
                str(i),
                r.engine,
                str(r.elo),
                f"{r.wins}-{r.losses}-{r.ties}",
                "—" if r.win_rate is None else f"{r.win_rate * 100:.0f}%",
                "—" if r.mean_wer is None else f"{r.mean_wer:.3f}",
                "—" if r.mean_cer is None else f"{r.mean_cer:.3f}",
                "—" if r.mean_train_seconds is None else f"{r.mean_train_seconds:.1f}",
                str(r.cells),
            ]
        )
    if len(rows) == 1:
        return "Scoreboard: no completed engine cells."
    widths = [max(len(r[i]) for r in rows) for i in range(len(cols))]
    out = ["SCOREBOARD (ranked by ELO; WER is the ground truth)", ""]
    for ri, row in enumerate(rows):
        out.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
        if ri == 0:
            out.append("  ".join("-" * widths[i] for i in range(len(cols))))
    return "\n".join(out)


def report_markdown(report: BenchmarkReport, *, generated_at: str | None = None) -> str:
    """Full Markdown report: scoreboard + matrix + methodology (the recorded artifact)."""
    board = scoreboard(report)
    lines = [
        f"# TTS × ASR benchmark report — `{report.name}`",
        "",
        f"- Language: `{report.language}`",
        f"- Train clips: {report.train_clips} · Eval clips (shared, held-out): {report.eval_clips}",
    ]
    if generated_at:
        lines.append(f"- Generated: {generated_at}")
    lines += [
        "",
        "## Scoreboard (ranked by ELO)",
        "",
        "| # | Engine | ELO | W-L-T | Win% | Mean WER | Mean CER | Mean train(s) | Conditions |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(board, 1):
        win = "—" if r.win_rate is None else f"{r.win_rate * 100:.0f}%"
        mwer = "—" if r.mean_wer is None else f"{r.mean_wer:.3f}"
        mcer = "—" if r.mean_cer is None else f"{r.mean_cer:.3f}"
        mtr = "—" if r.mean_train_seconds is None else f"{r.mean_train_seconds:.1f}"
        lines.append(
            f"| {i} | {r.engine} | **{r.elo}** | {r.wins}-{r.losses}-{r.ties} | "
            f"{win} | {mwer} | {mcer} | {mtr} | {r.cells} |"
        )
    lines += ["", "## Full matrix (per TTS × engine cell)", ""]
    lines += ["```", format_table(report), "```", ""]
    lines += [
        "## How to read this",
        "",
        "- **WER / CER** (lower is better) on the shared, held-out eval set are the "
        "ground-truth metrics. **Train(s)** is wall-clock fine-tune time.",
        "- **ELO** is a leaderboard layer: each engine plays one match per (TTS, clip) "
        "and wins the clips it transcribes with lower WER. It aggregates across voices "
        "and clip difficulty into one number; with few clips treat it as indicative.",
        "- Engines compared on **WER/CER/train-time**, not a single export format "
        "(formats differ per engine). See `project/docs/BENCHMARKING.md`.",
        "",
    ]
    return "\n".join(lines)


def write_report(report: BenchmarkReport, out_path: str | Path) -> None:
    Path(out_path).write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def write_markdown(
    report: BenchmarkReport, out_path: str | Path, *, generated_at: str | None = None
) -> None:
    Path(out_path).write_text(report_markdown(report, generated_at=generated_at), encoding="utf-8")
