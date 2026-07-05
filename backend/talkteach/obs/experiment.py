"""Local experiment metrics — on-device loss/WER curves, no telemetry (#53).

Grown-up mode wants TensorBoard-style curves without any of the data leaving the
machine (honours project/docs/DECISIONS.md D-008: off-by-default, local-only). This
is a tiny append-only JSONL log written into the training ``workdir`` plus pure
readers over it — no torch, no network, no third-party tracker. The training loop
appends a point per evaluation; the UI reads the curve back for a chart.

Format: one JSON object per line in ``<workdir>/metrics.jsonl``, e.g.
``{"step": 1, "epoch": 1.0, "loss": 0.9, "wer": 0.4, "t": 1719000000.0}``.
"""

from __future__ import annotations

import json
import os
import time

METRICS_FILENAME = "metrics.jsonl"


def metrics_path(workdir: str) -> str:
    return os.path.join(workdir, METRICS_FILENAME)


def log_metrics(workdir: str, *, at: float | None = None, **values: float) -> None:
    """Append one metrics point to ``<workdir>/metrics.jsonl`` (creates the file).

    ``values`` are arbitrary numeric metrics (loss, wer, cer, epoch, step, …).
    ``at`` is an optional wall-clock timestamp (defaults to now) so callers in a
    deterministic context can pin it. Non-finite values are dropped so the log stays
    chartable.
    """
    os.makedirs(workdir, exist_ok=True)
    point: dict[str, float] = {"t": time.time() if at is None else at}
    for key, val in values.items():
        fval = float(val)
        if fval == fval and fval not in (float("inf"), float("-inf")):  # finite only
            point[key] = fval
    with open(metrics_path(workdir), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(point) + "\n")


def read_curve(workdir: str) -> list[dict]:
    """Read all logged points back in order (``[]`` if none logged yet).

    Malformed lines are skipped rather than raising, so a half-flushed log from an
    interrupted run still renders.
    """
    path = metrics_path(workdir)
    if not os.path.isfile(path):
        return []
    points: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                points.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return points


def summarize(workdir: str) -> dict:
    """Summary stats for Grown-up mode: point count, best WER, latest loss/epoch."""
    curve = read_curve(workdir)
    wers = [p["wer"] for p in curve if "wer" in p]
    losses = [p["loss"] for p in curve if "loss" in p]
    return {
        "points": len(curve),
        "best_wer": min(wers) if wers else None,
        "final_wer": wers[-1] if wers else None,
        "final_loss": losses[-1] if losses else None,
        "final_epoch": curve[-1].get("epoch") if curve else None,
    }
