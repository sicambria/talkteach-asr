#!/usr/bin/env python3
"""SOTA Domain D05: Data Efficiency — WER vs. training minutes (needs a training run)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from scripts.sota.common import build_base_parser, write_abstention


def main():
    domain = get_domain("d05_data_efficiency")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    print(f"[sota] D05 ({domain.name}) is NOT measured — no fabricated estimate is emitted.")
    print("[sota] Requires training at multiple data sizes (5/15/30/60/120 min) on train-clean-100.")
    write_abstention(
        domain,
        requires="training runs at 5/15/30/60/120 min of LibriSpeech train-clean-100 "
        "to trace the WER-vs-data curve (extract the cached tar first)",
        json_path=args.json,
    )


if __name__ == "__main__":
    main()
