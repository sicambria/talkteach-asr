#!/usr/bin/env python3
"""Director calibration harness (roadmap #6) — Tier C scaffold.

Every threshold in `director/policy.py` and `audio/quality.py` is a *proposed
default* (report B.5), not empirically tuned. This harness sweeps a constant over
a labelled dataset and reports the metric so a human can pick a calibrated value,
then records the result. See project/docs/CALIBRATION.md for the full protocol.

It is a scaffold: the sweep loop and reporting are real, but running a meaningful
sweep needs labelled audio + the `[ml]` extras, so it's part of the calibration
workflow, not the sandbox.

    python scripts/calibrate.py --constant SNR_MIN_DB --values 6,8,10,12 --data ./labelled
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


def sweep(constant: str, values: list[float], data_dir: str) -> list[dict]:
    """Evaluate `constant` at each value against the labelled dataset.

    SCAFFOLD: returns a results skeleton. A real implementation re-runs the
    relevant check / training plan with the candidate value and measures the
    target metric (e.g. fraction of human-good clips the quality checker agrees
    with, or held-out WER for a policy hyperparameter).
    """
    results = []
    for v in values:
        results.append(
            {
                "constant": constant,
                "value": v,
                "metric": None,  # ← filled by a real evaluation against data_dir
                "note": "scaffold — wire the real evaluator (see project/docs/CALIBRATION.md)",
            }
        )
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--constant", required=True, help="e.g. SNR_MIN_DB, MIN_TARGET_MINUTES")
    ap.add_argument("--values", required=True, help="comma-separated candidate values")
    ap.add_argument("--data", required=True, help="labelled dataset dir")
    ap.add_argument("--out", default="calibration_results.json")
    args = ap.parse_args()
    values = [float(x) for x in args.values.split(",")]
    results = sweep(args.constant, values, args.data)
    Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} sweep rows → {args.out}")
    print("NOTE: scaffold — fill in the real evaluator before trusting the numbers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
