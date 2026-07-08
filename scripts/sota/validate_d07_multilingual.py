#!/usr/bin/env python3
"""SOTA Domain D07: Multilingual Coverage — languages < 15% WER on FLEURS.

The B-001 loader fix unblocks *loading* FLEURS, but the metric counts languages,
and DATASET_SPECS["fleurs"] is configured for a single config (en_us). A real
measurement needs a multi-language FLEURS sweep, so this abstains rather than
report a one-language count.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from scripts.sota.common import build_base_parser, write_abstention


def main():
    domain = get_domain("d07_multilingual")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    print(f"[sota] D07 ({domain.name}) is NOT measured — no fabricated estimate is emitted.")
    print("[sota] B-001 loader fix enables FLEURS loading, but the metric counts languages;")
    print("[sota] a multi-language FLEURS sweep (many configs) is required.")
    write_abstention(
        domain,
        requires="multi-language FLEURS sweep (add configs beyond en_us to "
        "DATASET_SPECS['fleurs'] and a measure_multilingual loop) to count languages < 15% WER",
        json_path=args.json,
    )


if __name__ == "__main__":
    main()
