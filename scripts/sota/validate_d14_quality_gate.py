#!/usr/bin/env python3
"""SOTA Domain D14: Data Quality Gate — gate score vs *measured* downstream WER.

Not scored against human GOOD/BAD labels (none exist); instead the gate's SNR
score is correlated with the per-clip WER it is meant to predict. Scope-partial
(SNR component only) → flagged and excluded from the headline.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from talkteach.sota.harness import SOTAHarness

from scripts.sota.common import build_base_parser, write_domain_result


def main():
    domain = get_domain("d14_quality_gate")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    harness = SOTAHarness(
        engines=args.engines.split(","),
        seed=args.seed,
        data_root=args.data_root,
        baseline_only=args.baseline_only,
    )
    result = harness.run_domain(domain)
    write_domain_result(result, args.json)


if __name__ == "__main__":
    main()
