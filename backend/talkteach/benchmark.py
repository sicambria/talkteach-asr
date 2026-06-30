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
import os
import random
import shutil
import sys
import time
from collections.abc import Callable
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
    # Fairness bracket: engines only ever play head-to-heads (and share a podium)
    # against others in the SAME category, so a 39M CPU model is never ranked
    # against a 1.1B GPU model. "default" = one pool (the back-compat behaviour for
    # configs that don't tag categories). See benchmarks/full.yaml + BENCHMARKING.md.
    category: str = "default"
    language: str | None = None  # the language this cell was spoken/scored in
    voice: str | None = None  # the TTS voice this cell was spoken with (for breakdowns)
    wer: float | None = None
    cer: float | None = None
    smartness: float | None = None
    train_seconds: float | None = None
    eval_clips: int = 0
    train_good_fraction: float | None = None
    # WER of the *untrained* base model on the same eval clips, and how much the
    # fine-tune improved it (base_wer - wer; positive = training helped). None when
    # the engine can't score an arbitrary base (e.g. NeMo) or the pass failed.
    base_wer: float | None = None
    delta_wer: float | None = None
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
    # The shared, held-out eval sentences, index-aligned to every cell's
    # ``per_clip_wer`` — so the best/worst-clip view can show the prompt text.
    # For a multi-language run this holds the *primary* language's prompts;
    # ``eval_prompts_by_lang`` has the per-language sets a cell is actually scored on.
    eval_prompts: list[str] = field(default_factory=list)
    eval_prompts_by_lang: dict[str, list[str]] = field(default_factory=dict)

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


def run_benchmark(
    config: dict[str, Any],
    workroot: str | Path,
    *,
    on_cell: Callable[[CellResult], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> BenchmarkReport:
    """Execute the full TTS×ASR matrix described by ``config``.

    See ``benchmarks/quick.yaml`` for the schema. ``workroot`` is a scratch dir for
    generated audio and per-cell training checkpoints. Providers/engines whose deps
    are missing are recorded as ``skipped`` (never crash the whole run).

    ``on_cell`` (optional) is invoked with each :class:`CellResult` right after it is
    appended — the API uses it to stream partial progress. ``should_stop`` (optional)
    is polled between cells and forwarded into training so a long cell cancels promptly.
    """
    stop = should_stop or (lambda: False)

    def _emit(cell: CellResult, report: BenchmarkReport) -> None:
        report.cells.append(cell)
        if on_cell is not None:
            on_cell(cell)

    name = config.get("name", "benchmark")
    # `languages` (plural) is the new multi-language axis; `language` stays as the
    # single-language default for back-compat.
    languages = [str(x) for x in (config.get("languages") or [config.get("language", "en")])]
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

    primary = languages[0]
    primary_train, primary_eval = _split_prompts(primary, n_train, n_eval)
    report = BenchmarkReport(
        name=name,
        language=",".join(languages),
        train_clips=len(primary_train),
        eval_clips=len(primary_eval),
        eval_prompts=list(primary_eval),
    )

    for lang in languages:
        if stop():
            break
        train_prompts, eval_prompts = _split_prompts(lang, n_train, n_eval)
        report.eval_prompts_by_lang[lang] = list(eval_prompts)

        for tts_spec in tts_specs:
            if stop():
                break
            tts_name = tts_spec["provider"]
            # Resolve the voice for THIS language: espeak speaks any language by its
            # code; piper needs a language-specific model (others self-skip cleanly).
            voice = _resolve_voice(tts_name, lang, tts_spec.get("voice"))
            if voice is None:
                for eng_spec in engine_specs:
                    _emit(
                        CellResult(
                            tts_name,
                            eng_spec.get("name", "?"),
                            "skipped",
                            f"{tts_name} has no voice for '{lang}'",
                            category=eng_spec.get("category", "default"),
                            language=lang,
                        ),
                        report,
                    )
                continue

            kwargs = {k: v for k, v in tts_spec.items() if k not in ("provider", "voice")}
            try:
                provider = get_tts_provider(tts_name, **kwargs)
            except KeyError as exc:
                _emit(
                    CellResult(tts_name, "-", "error", str(exc), language=lang, voice=voice), report
                )
                continue
            ok, msg = provider.is_available()
            if not ok:
                for eng_spec in engine_specs:
                    _emit(
                        CellResult(
                            tts_name,
                            eng_spec.get("name", "?"),
                            "skipped",
                            f"TTS: {msg}",
                            category=eng_spec.get("category", "default"),
                            language=lang,
                            voice=voice,
                        ),
                        report,
                    )
                continue

            tts_dir = root / lang / tts_name
            train_mani = synthesize_dataset(
                provider,
                tts_dir / "train",
                prompts=train_prompts,
                voices=[voice],
                sample_rate=sample_rate,
                prefix="train",
            )
            eval_mani = synthesize_dataset(
                provider,
                tts_dir / "eval",
                prompts=eval_prompts,
                voices=[voice],
                sample_rate=sample_rate,
                prefix="eval",
            )
            train_gf = _good_fraction(train_mani)
            refs = [m["text"] for m in eval_mani]

            for eng_spec in engine_specs:
                if stop():
                    break
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
                    category=eng_spec.get("category", "default"),
                    language=lang,
                    voice=voice,
                    should_stop=stop,
                )
                _emit(cell, report)
                # Release model/tensor memory before the next cell so a multi-engine
                # matrix doesn't accumulate several models in RAM at once.
                _free_memory()
                # Bound disk: drop the (potentially multi-GB) checkpoint now that the
                # cell is scored, unless the caller explicitly wants to keep artifacts.
                if not keep_artifacts:
                    shutil.rmtree(run_dir, ignore_errors=True)

    return report


# Known piper voices per language (16 kHz "low" where possible). Languages absent
# here self-skip for piper rather than trying to download a voice that may not exist;
# espeak still covers them. Extend as voices are verified.
_PIPER_VOICES: dict[str, str] = {"en": "en_US-lessac-low"}


def _resolve_voice(provider: str, language: str, configured_voice: str | None) -> str | None:
    """Pick the TTS voice for ``(provider, language)``.

    espeak speaks any language by passing the language code as the voice; piper needs
    a language-specific model (only the ones in ``_PIPER_VOICES`` are run). Returns
    ``None`` when the provider can't speak the language, so the caller skips the cell.
    """
    p = provider.strip().lower()
    if "espeak" in p:
        return language
    if p == "piper":
        return _PIPER_VOICES.get(language)
    return configured_voice  # unknown provider: trust the configured voice


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
    category: str = "default",
    language: str | None = None,
    voice: str | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> CellResult:
    try:
        plan = plan_from_config(plan_cfg)
        engine = get_engine(plan.engine)
    except (KeyError, NotImplementedError) as exc:
        return CellResult(
            tts_name, eng_name, "error", str(exc), category=category, language=language, voice=voice
        )

    available, msg = engine.is_available()
    if not available:
        return CellResult(
            tts_name,
            eng_name,
            "skipped",
            f"engine: {msg}",
            category=category,
            language=language,
            voice=voice,
        )

    workdir.mkdir(parents=True, exist_ok=True)
    try:
        # Delta vs base: score the *untrained* base on the eval clips first (best
        # effort — None if the engine can't load an arbitrary base, e.g. NeMo).
        base_wer = _base_wer(engine, plan.base_checkpoint, eval_mani, refs)
        t0 = time.perf_counter()
        engine.train(plan, train_mani, str(workdir), should_stop=should_stop)
        train_seconds = time.perf_counter() - t0
        hyps = [engine.transcribe(m["path"], model_dir=str(workdir)) for m in eval_mani]
    except Exception as exc:  # noqa: BLE001 - one bad cell shouldn't kill the matrix
        return CellResult(
            tts_name,
            eng_name,
            "error",
            f"{type(exc).__name__}: {exc}",
            category=category,
            language=language,
            voice=voice,
        )

    wer_v = wer(refs, hyps)
    per_clip = [round(wer([r], [h]), 4) for r, h in zip(refs, hyps, strict=False)]
    delta = None if base_wer is None else round(base_wer - wer_v, 4)
    return CellResult(
        tts=tts_name,
        engine=eng_name,
        status="ok",
        category=category,
        language=language,
        voice=voice,
        wer=round(wer_v, 4),
        cer=round(cer(refs, hyps), 4),
        smartness=round(smartness_from_wer(wer_v), 4),
        train_seconds=round(train_seconds, 2),
        eval_clips=len(eval_mani),
        train_good_fraction=round(train_good_fraction, 3),
        base_wer=None if base_wer is None else round(base_wer, 4),
        delta_wer=delta,
        per_clip_wer=per_clip,
    )


def _base_wer(
    engine: Any, base_checkpoint: str, eval_mani: list[dict], refs: list[str]
) -> float | None:
    """WER of the untrained ``base_checkpoint`` on the eval clips, or None if the
    engine can't score a bare base (it raises) — never fails the cell over it."""
    # Under forced simulation the trained side is a stub, so a real base pass would
    # be both meaningless and slow (it loads the actual model); skip it.
    if os.environ.get("TALKTEACH_FORCE_SIMULATION") == "1":
        return None
    try:
        base_hyps = [
            engine.transcribe(m["path"], base_checkpoint=base_checkpoint) for m in eval_mani
        ]
    except Exception:  # noqa: BLE001 - delta is a nicety; absence is fine
        return None
    return wer(refs, base_hyps)


def format_table(report: BenchmarkReport) -> str:
    """Render the report as a plain-text table (the human-facing matrix)."""
    header = f"Benchmark '{report.name}'  lang={report.language}  "
    header += f"train={report.train_clips} eval={report.eval_clips} clips"
    cols = [
        "Lang",
        "TTS",
        "Engine",
        "Bracket",
        "Status",
        "WER",
        "CER",
        "Smartness",
        "Train(s)",
        "Detail",
    ]
    rows = [cols]
    for c in report.cells:
        rows.append(
            [
                c.language or "-",
                c.tts,
                c.engine,
                c.category,
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
    category: str
    elo: int
    wins: int
    losses: int
    ties: int
    win_rate: float | None  # decided matches only; None if it played none
    mean_wer: float | None
    mean_cer: float | None
    mean_train_seconds: float | None
    cells: int  # number of (TTS) conditions it completed
    mean_delta_wer: float | None = None  # avg WER drop vs untrained base (None if unknown)
    medal: str | None = None  # "gold" | "silver" | "bronze" | None (top-N podium)


def _clip_matches(report: BenchmarkReport, eps: float = 1e-9) -> list[tuple[str, str, float]]:
    """Per-(category, language, TTS, clip) head-to-head outcomes: (engineA, engineB, scoreA).

    Within each (category, language, TTS) condition every pair of completed engines is
    compared on each shared eval clip; the lower WER wins (0.5 on a tie). Engines that
    appear under several conditions (more voices, more languages) play more matches —
    more signal. Grouping includes the **category** so a small CPU model is never
    matched against a large GPU one (fairness brackets), and the language so clips from
    different languages (which have different prompts) are never wrongly compared.
    """
    matches: list[tuple[str, str, float]] = []
    by_cond: dict[tuple[str, str | None, str], list[CellResult]] = {}
    for c in report.cells:
        if c.status == "ok" and c.per_clip_wer:
            by_cond.setdefault((c.category, c.language, c.tts), []).append(c)
    for cells in by_cond.values():
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


def scoreboard(report: BenchmarkReport, *, medals: int = 3) -> list[EngineScore]:
    """Aggregate the matrix into a per-engine leaderboard, sorted best-first.

    Ranking is **per fairness bracket** (``CellResult.category``): engines are sorted
    and awarded medals only against others in the same category, so each bracket gets
    its own podium and a small CPU model never loses a medal to a large GPU one. The
    returned list is flat (back-compat) but ordered bracket-by-bracket, each bracket
    internally sorted by ELO desc then mean WER asc. Use :func:`scoreboard_brackets`
    for the grouped view. A config with no categories is one ``"default"`` bracket,
    so the order and medals match the pre-bracket behaviour exactly.
    """
    rows = _engine_scores(report)
    # Preserve the order categories first appear in the matrix (config order), then
    # rank within each bracket and hand out that bracket's medals independently.
    cat_order: list[str] = []
    for c in report.cells:
        if c.status == "ok" and c.category not in cat_order:
            cat_order.append(c.category)
    ordered: list[EngineScore] = []
    for cat in cat_order:
        bracket = [r for r in rows if r.category == cat]
        bracket.sort(key=lambda r: (-r.elo, r.mean_wer if r.mean_wer is not None else 1e9))
        assign_medals(bracket, n=medals)
        ordered.extend(bracket)
    return ordered


def _engine_scores(report: BenchmarkReport) -> list[EngineScore]:
    """One unranked :class:`EngineScore` per engine (ELO + aggregated metrics)."""
    elo = compute_elo(report)
    cat_of = {c.engine: c.category for c in report.cells if c.status == "ok"}
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
                category=cat_of.get(e, "default"),
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
                mean_delta_wer=_mean([c.delta_wer for c in cells if c.delta_wer is not None]),
            )
        )
    return rows


def scoreboard_brackets(report: BenchmarkReport, *, medals: int = 3) -> list[dict[str, Any]]:
    """The leaderboard split into fairness brackets: ``[{category, board}, …]``.

    Each ``board`` is the ranked, medal-assigned :class:`EngineScore` list for that
    category. Brackets are ordered by first appearance in the matrix (config order).
    This is what the in-app Arena renders as one podium per bracket.
    """
    flat = scoreboard(report, medals=medals)
    out: list[dict[str, Any]] = []
    seen: dict[str, list[EngineScore]] = {}
    for r in flat:
        if r.category not in seen:
            seen[r.category] = []
            out.append({"category": r.category, "board": seen[r.category]})
        seen[r.category].append(r)
    return out


_MEDALS = ("gold", "silver", "bronze")
_MEDAL_EMOJI = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}


def assign_medals(board: list[EngineScore], n: int = 3) -> None:
    """Award gold/silver/bronze to the top ``n`` engines of ``board``.

    Tie-aware (standard *competition ranking*): an engine's rank is the number of
    strictly-better engines, so engines sharing an ELO share a medal and the next
    *distinct* ELO takes the medal below. Two engines tied at the top both get gold,
    silver is skipped, and the third (if any) gets bronze. With fewer than three
    distinct ELOs the lower medals simply go unassigned (a 2-engine matrix never
    reaches bronze). ``n`` caps how many medal ranks are handed out.
    """
    cap = min(n, len(_MEDALS))
    for row in board:
        rank = sum(1 for r in board if r.elo > row.elo)  # 0=gold, 1=silver, 2=bronze
        row.medal = _MEDALS[rank] if rank < cap else None


# =============================================================================
# Detail views — richer breakdowns over the matrix (consumed by the report and
# the in-app "Arena" scoreboard). All are pure functions over a (possibly partial)
# BenchmarkReport, so they work on a live run as cells stream in.
# =============================================================================


def head_to_head(report: BenchmarkReport) -> dict[str, dict[str, int]]:
    """Engine × engine win grid: ``grid[a][b]`` = clips where ``a`` beat ``b``.

    Built from the same per-(TTS, clip) head-to-heads that feed ELO, so it never
    double-counts or disagrees with the leaderboard. Ties add to neither side.
    """
    engines = sorted({c.engine for c in report.cells if c.status == "ok" and c.per_clip_wer})
    grid: dict[str, dict[str, int]] = {a: {b: 0 for b in engines if b != a} for a in engines}
    for a, b, s in _clip_matches(report):
        if s == 1.0:
            grid[a][b] += 1
        elif s == 0.0:
            grid[b][a] += 1
    return grid


def per_engine_clip_extremes(report: BenchmarkReport) -> dict[str, dict[str, Any]]:
    """For each engine, its easiest and hardest eval clip (lowest/highest WER).

    Returns ``{engine: {"best": {...}, "worst": {...}}}`` where each entry carries
    the clip's ``prompt`` text, ``wer``, ``tts`` and ``voice`` — so the UI can show
    "nailed this / struggled here". Engines with no scored clips are omitted.
    """
    out: dict[str, dict[str, Any]] = {}
    for e in sorted({c.engine for c in report.cells if c.status == "ok"}):
        scored: list[dict[str, Any]] = []
        for c in report.cells:
            if c.status != "ok" or c.engine != e:
                continue
            # Prompts differ per language, so look up this cell's set.
            prompts = report.eval_prompts_by_lang.get(c.language or "") or report.eval_prompts
            for i, w in enumerate(c.per_clip_wer):
                scored.append(
                    {
                        "prompt": prompts[i] if i < len(prompts) else f"clip {i + 1}",
                        "wer": w,
                        "tts": c.tts,
                        "voice": c.voice,
                        "language": c.language,
                    }
                )
        if scored:
            out[e] = {
                "best": min(scored, key=lambda d: d["wer"]),
                "worst": max(scored, key=lambda d: d["wer"]),
            }
    return out


def per_engine_conditions(report: BenchmarkReport) -> dict[str, list[dict[str, Any]]]:
    """Per-engine breakdown by condition (language × TTS voice): cells completed.

    ``{engine: [{language, tts, voice, wer, cer, train_seconds, delta_wer}, …]}`` —
    surfaces which language/voice each engine handled best/worst without re-deriving.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for c in report.cells:
        if c.status != "ok":
            continue
        out.setdefault(c.engine, []).append(
            {
                "language": c.language,
                "tts": c.tts,
                "voice": c.voice,
                "wer": c.wer,
                "cer": c.cer,
                "train_seconds": c.train_seconds,
                "delta_wer": c.delta_wer,
            }
        )
    return out


def scoreboard_payload(report: BenchmarkReport, *, medals: int = 3) -> dict[str, Any]:
    """One JSON-serializable bundle: leaderboard + matrix + all detail views.

    This is the single source the HTTP API returns and the renderers consume, so
    the CLI report and the in-app Arena always show identical numbers.
    """
    board = scoreboard(report, medals=medals)
    brackets = [
        {"category": b["category"], "board": [asdict(r) for r in b["board"]]}
        for b in scoreboard_brackets(report, medals=medals)
    ]
    return {
        "meta": {
            "name": report.name,
            "language": report.language,
            "train_clips": report.train_clips,
            "eval_clips": report.eval_clips,
        },
        # Flat board (back-compat) plus the same rows grouped into fairness brackets;
        # the Arena renders one podium per bracket from `brackets`.
        "scoreboard": [asdict(r) for r in board],
        "brackets": brackets,
        "matrix": [asdict(c) for c in report.cells],
        "head_to_head": head_to_head(report),
        "clip_extremes": per_engine_clip_extremes(report),
        "per_voice": per_engine_conditions(report),
        "eval_prompts": list(report.eval_prompts),
        "eval_prompts_by_lang": {k: list(v) for k, v in report.eval_prompts_by_lang.items()},
    }


def format_scoreboard(report: BenchmarkReport, *, medals: int = 3) -> str:
    """Plain-text leaderboard (ranked by ELO, with raw WER/CER/time alongside).

    One sub-table per fairness bracket; the bracket header is omitted when the whole
    run is the single ``"default"`` bracket (the back-compat layout).
    """
    brackets = scoreboard_brackets(report, medals=medals)
    if not brackets:
        return "Scoreboard: no completed engine cells."
    single_default = len(brackets) == 1 and brackets[0]["category"] == "default"
    cols = ["#", "", "Engine", "ELO", "W-L-T", "Win%", "MeanWER", "MeanCER", "Train(s)", "Conds"]
    out = ["SCOREBOARD (ranked by ELO; WER is the ground truth)", ""]
    for bracket in brackets:
        if not single_default:
            out += [f"— bracket: {bracket['category']} —"]
        rows = [cols]
        for i, r in enumerate(bracket["board"], 1):
            rows.append(
                [
                    str(i),
                    _MEDAL_EMOJI.get(r.medal or "", ""),
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
        widths = [max(len(r[i]) for r in rows) for i in range(len(cols))]
        for ri, row in enumerate(rows):
            out.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
            if ri == 0:
                out.append("  ".join("-" * widths[i] for i in range(len(cols))))
        out.append("")
    return "\n".join(out).rstrip()


def report_markdown(
    report: BenchmarkReport, *, generated_at: str | None = None, medals: int = 3
) -> str:
    """Full Markdown report: scoreboard + matrix + detail views + methodology."""
    brackets = scoreboard_brackets(report, medals=medals)
    single_default = len(brackets) == 1 and brackets and brackets[0]["category"] == "default"
    lines = [
        f"# TTS × ASR benchmark report — `{report.name}`",
        "",
        f"- Language: `{report.language}`",
        f"- Train clips: {report.train_clips} · Eval clips (shared, held-out): {report.eval_clips}",
    ]
    if generated_at:
        lines.append(f"- Generated: {generated_at}")
    lines += ["", "## Scoreboard (ranked by ELO)", ""]
    if not single_default:
        lines.append(
            "Ranked within **fairness brackets** — engines only compete against others "
            "in the same category (size / compute class), so comparisons stay apples-to-apples."
        )
        lines.append("")
    for bracket in brackets:
        if not single_default:
            lines += [f"### Bracket: `{bracket['category']}`", ""]
        lines += [
            "| # | | Engine | ELO | W-L-T | Win% | Mean WER | Mean CER | Δ vs base "
            "| Mean train(s) | Conditions |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(bracket["board"], 1):
            win = "—" if r.win_rate is None else f"{r.win_rate * 100:.0f}%"
            mwer = "—" if r.mean_wer is None else f"{r.mean_wer:.3f}"
            mcer = "—" if r.mean_cer is None else f"{r.mean_cer:.3f}"
            mtr = "—" if r.mean_train_seconds is None else f"{r.mean_train_seconds:.1f}"
            delta = "—" if r.mean_delta_wer is None else f"{r.mean_delta_wer:+.3f}"
            medal = _MEDAL_EMOJI.get(r.medal or "", "")
            lines.append(
                f"| {i} | {medal} | {r.engine} | **{r.elo}** | {r.wins}-{r.losses}-{r.ties} | "
                f"{win} | {mwer} | {mcer} | {delta} | {mtr} | {r.cells} |"
            )
        lines.append("")
    lines += ["## Full matrix (per TTS × engine cell)", ""]
    lines += ["```", format_table(report), "```", ""]
    lines += _detail_markdown(report)
    lines += [
        "## How to read this",
        "",
        "- **WER / CER** (lower is better) on the shared, held-out eval set are the "
        "ground-truth metrics. **Train(s)** is wall-clock fine-tune time.",
        "- **Δ vs base** is the mean WER drop from the *untrained* base checkpoint to the "
        "fine-tune (positive = training helped); `—` when the base wasn't scorable.",
        "- **ELO** is a leaderboard layer: each engine plays one match per (TTS, clip) "
        "and wins the clips it transcribes with lower WER. It aggregates across voices "
        "and clip difficulty into one number; with few clips treat it as indicative.",
        "- 🥇🥈🥉 mark the top engines by ELO (ties share a medal). Engines compared on "
        "**WER/CER/train-time**, not a single export format. See `project/docs/BENCHMARKING.md`.",
        "",
    ]
    return "\n".join(lines)


def _detail_markdown(report: BenchmarkReport) -> list[str]:
    """The four detail sections: best/worst clip, head-to-head, per-voice, delta."""
    lines: list[str] = []

    extremes = per_engine_clip_extremes(report)
    if extremes:
        lines += ["## Easiest & hardest clip (per engine)", ""]
        lines += ["| Engine | Best clip (WER) | Hardest clip (WER) |", "|---|---|---|"]
        for eng, ex in extremes.items():
            b, w = ex["best"], ex["worst"]
            lines.append(
                f"| {eng} | “{b['prompt']}” ({b['wer']:.3f}, {b['tts']}) "
                f"| “{w['prompt']}” ({w['wer']:.3f}, {w['tts']}) |"
            )
        lines.append("")

    grid = head_to_head(report)
    if len(grid) >= 2:
        opponents = sorted(grid)
        lines += ["## Head-to-head (clips won, row vs column)", ""]
        lines.append("| | " + " | ".join(opponents) + " |")
        lines.append("|---|" + "---|" * len(opponents))
        for a in opponents:
            cells = " | ".join("·" if a == b else str(grid[a].get(b, 0)) for b in opponents)
            lines.append(f"| **{a}** | {cells} |")
        lines.append("")

    by_voice = per_engine_conditions(report)
    if by_voice:
        lines += ["## Per-voice breakdown", ""]
        lines += [
            "| Engine | Lang | TTS | Voice | WER | CER | Δ vs base | Train(s) |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for eng, conds in by_voice.items():
            for c in conds:
                lang = c["language"] or "—"
                voice = c["voice"] or "—"
                wer_s = "—" if c["wer"] is None else f"{c['wer']:.3f}"
                cer_s = "—" if c["cer"] is None else f"{c['cer']:.3f}"
                d_s = "—" if c["delta_wer"] is None else f"{c['delta_wer']:+.3f}"
                tr_s = "—" if c["train_seconds"] is None else f"{c['train_seconds']:.1f}"
                lines.append(
                    f"| {eng} | {lang} | {c['tts']} | {voice} | {wer_s} | {cer_s} "
                    f"| {d_s} | {tr_s} |"
                )
        lines.append("")

    return lines


def write_report(report: BenchmarkReport, out_path: str | Path) -> None:
    Path(out_path).write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def write_markdown(
    report: BenchmarkReport,
    out_path: str | Path,
    *,
    generated_at: str | None = None,
    medals: int = 3,
) -> None:
    Path(out_path).write_text(
        report_markdown(report, generated_at=generated_at, medals=medals), encoding="utf-8"
    )
