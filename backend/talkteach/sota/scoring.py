"""Shared scoring functions for SOTA benchmarks.

All heavy imports are function-local (D-002). Pure Python until measurement time.
"""

from __future__ import annotations

import math
import time
from collections.abc import Sequence
from pathlib import Path


def wer(references: list[str], hypotheses: list[str]) -> float:
    """Word Error Rate via jiwer. Returns 0.0–1.0."""
    from jiwer import process_words

    output = process_words(references, hypotheses)
    return output.wer


def cer(references: list[str], hypotheses: list[str]) -> float:
    """Character Error Rate via jiwer. Returns 0.0–1.0."""
    from jiwer import cer as _cer

    return _cer(references, hypotheses)


def rtf(total_audio_seconds: float, total_decode_seconds: float) -> float:
    """Real-Time Factor. decode_time / audio_duration."""
    if total_audio_seconds <= 0:
        return float("inf")
    return total_decode_seconds / total_audio_seconds


def confidence_interval(
    values: Sequence[float],
    n_bootstrap: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap 95% confidence interval for the mean."""
    import random

    import numpy as np

    rng = random.Random(seed)
    arr = np.array(values, dtype=np.float64)
    n = len(arr)
    if n < 3:
        m = float(np.mean(arr))
        return (m, m)

    means = np.empty(n_bootstrap, dtype=np.float64)
    for i in range(n_bootstrap):
        sample = arr[rng.choices(range(n), k=n)]
        means[i] = float(np.mean(sample))

    lo = float(np.percentile(means, 100 * alpha / 2))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return (lo, hi)


def cohens_d(group_a: Sequence[float], group_b: Sequence[float]) -> float:
    """Cohen's d effect size between two groups."""
    import numpy as np

    a = np.array(group_a, dtype=np.float64)
    b = np.array(group_b, dtype=np.float64)
    diff = np.mean(a) - np.mean(b)
    pooled_std = math.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2)
    if pooled_std == 0:
        return 0.0
    return float(diff / pooled_std)


def precision_at_k(
    references: Sequence[Sequence[str]],
    hypotheses: Sequence[Sequence[str]],
    k: int = 5,
) -> float:
    """Precision@k for top-k hotword accuracy."""
    hits = 0
    total = 0
    for ref_tokens, hyp_tokens in zip(references, hypotheses, strict=False):
        ref_set = set(ref_tokens)
        top_k = set(hyp_tokens[:k])
        hits += len(ref_set & top_k)
        total += min(len(ref_set), k)
    return hits / total if total > 0 else 0.0


def demographic_equity_gini(per_group_metrics: dict[str, float]) -> float:
    """Gini coefficient of per-demographic-group metrics. 0 = perfect equity."""
    import numpy as np

    values = sorted(per_group_metrics.values())
    n = len(values)
    if n < 2 or sum(values) == 0:
        return 0.0
    arr = np.array(values, dtype=np.float64)
    index = np.arange(1, n + 1, dtype=np.float64)
    return float((2 * np.sum(index * arr)) / (n * np.sum(arr)) - (n + 1) / n)


def measure_rtf_single(
    audio_path: Path,
    engine_name: str = "whisper-tiny",
) -> dict[str, float]:
    """Measure RTF for a single audio file using faster-whisper."""
    import soundfile as sf
    from faster_whisper import WhisperModel

    audio, sr = sf.read(str(audio_path))
    duration = len(audio) / sr

    model = WhisperModel(engine_name, device="cpu", compute_type="int8")
    t0 = time.perf_counter()
    segments, _ = model.transcribe(audio)
    # exhaust generator
    for _ in segments:
        pass
    decode_time = time.perf_counter() - t0
    return {"duration_s": duration, "decode_s": decode_time, "rtf": rtf(duration, decode_time)}


def score_against_bands(
    value: float,
    bands: list[tuple[int, float]],
    higher_is_better: bool = False,
) -> tuple[int, str]:
    """Map a metric value to a SOTA score and band name.

    bands: list of (score, threshold) sorted descending by score.
    For higher_is_better=True: value >= threshold to achieve that score.
    For higher_is_better=False: value <= threshold to achieve that score.
    Returns (score, band_label).
    """
    BAND_NAMES = {
        1000: "platinum",
        950: "diamond",
        900: "platinum",
        800: "gold",
        700: "silver",
        600: "bronze",
        500: "bronze",
    }

    for score, threshold in sorted(bands, reverse=True):
        if higher_is_better:
            if value >= threshold:
                return score, BAND_NAMES.get(score, "bronze")
        else:
            if value <= threshold:
                return score, BAND_NAMES.get(score, "bronze")

    # Below the lowest band
    lowest = min(s[0] for s in bands) if bands else 600
    return max(0, lowest - 100), "bronze"


def aggregate_wer(
    wer_per_clip: list[float],
    durations: list[float] | None = None,
) -> tuple[float, float]:
    """Aggregate per-clip WER. Returns (mean, duration_weighted_mean)."""
    import numpy as np

    arr = np.array(wer_per_clip)
    mean = float(np.mean(arr))
    if durations and len(durations) == len(wer_per_clip):
        d = np.array(durations)
        total = float(np.sum(d))
        if total > 0:
            weighted = float(np.sum(arr * d) / total)
            return mean, weighted
    return mean, mean
