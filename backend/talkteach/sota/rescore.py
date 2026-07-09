"""Rescore the SOTA scoreboard from a banked ``SCOREBOARD.json``.

Re-applies the *current* scoring policy — band thresholds (``domains.py``) plus
the small-n headline gate (``scoring.aggregate_headline``) — to already-measured
raw metrics, and regenerates ``SCOREBOARD.md``/``.json``. Runs in seconds with no
GPU, network, or re-measurement.

Use it after changing scoring policy or a domain definition. It **preserves the
``generated`` stamp** (the measurement time): rescoring re-presents existing
measurements, it does not create new ones. A fresh measurement (``run_all``) is
what advances the stamp.

Heavy imports stay function-local elsewhere; this module is pure-Python glue.

Usage:
    python -m talkteach.sota.rescore
    python -m talkteach.sota.rescore --in <SCOREBOARD.json> --out <output-dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from talkteach.sota.domains import Domain, get_domain
from talkteach.sota.harness import Scoreboard, SOTAResult
from talkteach.sota.report import generate
from talkteach.sota.scoring import aggregate_headline, score_against_bands


def _rederive_score(result: SOTAResult, domain: Domain | None) -> tuple[int, str]:
    """Re-derive (score, band) from raw metrics + the domain's bands.

    Idempotent — proves the stored score is reproducible from the raw metric,
    and applies any band-threshold change. Falls back to the stored score/band
    for unmeasured domains (no usable metric value).
    """
    # An explicit abstention is a policy decision the measure made at measurement
    # time (it determined no valid band exists — e.g. a degenerate gate estimate).
    # Rescore must NOT second-guess it by scoring a raw metric the measure
    # deliberately declined to score, which would fabricate a band. Preserve it.
    if result.band == "human_needed" or result.metrics.get("degenerate"):
        return 0, "human_needed"
    if domain is None or not domain.bands:
        return result.score_0_1000, result.band
    primary = domain.metric
    value: float | None = None
    for key, v in result.metrics.items():
        if (primary in key or key == primary) and isinstance(v, (int, float)) and v >= 0:
            value = float(v)
            break
    if value is None:
        return result.score_0_1000, result.band
    band_tuples = [(b.score, b.threshold) for b in domain.bands]
    return score_against_bands(value, band_tuples, domain.higher_is_better)


def rescore_scoreboard(data: dict[str, Any]) -> Scoreboard:
    """Rebuild a Scoreboard from a SCOREBOARD.json dict, applying current policy."""
    results: list[SOTAResult] = []
    for d in data.get("domains", []):
        ci: dict[str, tuple[float, float]] = {}
        for k, v in (d.get("confidence_95") or {}).items():
            if isinstance(v, list) and len(v) == 2:
                ci[k] = (float(v[0]), float(v[1]))
        domain = get_domain(d.get("domain_id", ""))
        metrics = d.get("metrics", {}) or {}
        # Derive display fields from single sources when the stored JSON omits them:
        # the domain name from the definition, the sample count from the metrics
        # (num_clips/num_speakers) — so measured domains never render "Samples: 0".
        num_samples = int(d.get("num_samples", 0) or 0)
        if not num_samples:
            num_samples = int(metrics.get("num_clips", metrics.get("num_speakers", 0)) or 0)
        r = SOTAResult(
            domain_id=d.get("domain_id", ""),
            domain_name=d.get("domain_name") or (domain.name if domain else ""),
            score_0_1000=int(d.get("score_0_1000", 0) or 0),
            band=d.get("band", "unmeasured"),
            metrics=metrics,
            confidence_95=ci,
            baseline_ref=d.get("baseline_ref", ""),
            # Refresh the anchor from the (possibly corrected) domain definition
            # so anchor-hygiene fixes propagate without hand-editing the JSON.
            sota_ref=(domain.sota_1000_reference if domain else d.get("sota_ref", "")),
            num_samples=num_samples,
            engine_used=d.get("engine_used", ""),
            notes=d.get("notes", ""),
        )
        r.score_0_1000, r.band = _rederive_score(r, domain)
        results.append(r)

    headline = aggregate_headline(results)  # also sets r.directional / .directional_reason
    return Scoreboard(
        domains=results,
        overall_mean=headline["overall_mean"],
        overall_band=headline["overall_band"],
        generated=data.get("generated", ""),  # preserve measurement time
        num_total=headline["num_total"],
        num_measured=headline["num_measured"],
        num_eligible=headline["num_eligible"],
        num_directional=headline["num_directional"],
        num_unmeasured=headline["num_unmeasured"],
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Rescore the SOTA scoreboard from banked JSON.")
    p.add_argument(
        "--in",
        dest="inp",
        type=Path,
        default=Path("docs/sota-benchmarks/SCOREBOARD.json"),
        help="Input SCOREBOARD.json (default: docs/sota-benchmarks/SCOREBOARD.json)",
    )
    p.add_argument(
        "--out",
        dest="out",
        type=Path,
        default=Path("docs/sota-benchmarks"),
        help="Output directory (default: docs/sota-benchmarks)",
    )
    args = p.parse_args(argv)

    data = json.loads(args.inp.read_text())
    sb = rescore_scoreboard(data)
    generate(sb, args.out)
    print(
        f"Rescored {sb.num_total} domains → headline {sb.overall_mean:.0f}/1000 "
        f"({sb.overall_band}); {sb.num_eligible} adequately powered, "
        f"{sb.num_directional} directional, {sb.num_unmeasured} unmeasured/blocked. "
        f"Stamp preserved: {sb.generated}"
    )


if __name__ == "__main__":
    main()
