#!/usr/bin/env python3
"""SOTA Domain D05: Data Efficiency — WER after fine-tuning on bounded data slices.

Anchors base (pre-finetune) WER on disjoint test-clean, fine-tunes whisper-tiny on
5/15/30 min slices of train-clean-100, and reports WER-at-5-min — OR abstains with
the base→trained numbers if no slice improves (the likely case for in-domain
LibriSpeech, per INS-001 and D03). Bounded (≤30 min) → flagged partial.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from talkteach.sota.harness import SOTAHarness

from scripts.sota.common import build_base_parser, write_domain_result


def main():
    domain = get_domain("d05_data_efficiency")
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
