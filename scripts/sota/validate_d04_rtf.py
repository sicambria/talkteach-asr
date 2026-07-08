#!/usr/bin/env python3
"""SOTA Domain D04: Inference Speed — Real-Time Factor"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from talkteach.sota.harness import SOTAHarness
from scripts.sota.common import build_base_parser, write_result


def main():
    domain = get_domain("d04_rtf")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    harness = SOTAHarness(engines=args.engines.split(","), seed=args.seed, data_root=args.data_root, baseline_only=args.baseline_only)
    result = harness.run_domain(domain)
    write_result({
        "domain_id": result.domain_id,
        "score_0_1000": result.score_0_1000,
        "band": result.band,
        "metrics": result.metrics,
        "confidence_95": {k: list(v) for k, v in result.confidence_95.items()},
        "baseline_ref": result.baseline_ref,
        "sota_ref": result.sota_ref,
    }, args.json)


if __name__ == "__main__":
    main()
