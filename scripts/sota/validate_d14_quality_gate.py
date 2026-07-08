#!/usr/bin/env python3
"""SOTA Domain D14: Data Quality Gate — ROC-AUC vs human labels (needs labelled data)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from scripts.sota.common import build_base_parser, write_abstention


def main():
    domain = get_domain("d14_quality_gate")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    print(f"[sota] D14 ({domain.name}) is NOT measured — no fabricated estimate is emitted.")
    print("[sota] Requires a hand-labelled GOOD/BAD quality dataset at")
    print("[sota] ~/.cache/talkteach/sota/labelled_quality_set/ to score the gate against.")
    write_abstention(
        domain,
        requires="hand-labelled GOOD/BAD quality dataset (human labels) to compute ROC-AUC "
        "of the SNR/clipping/silence gate",
        json_path=args.json,
    )


if __name__ == "__main__":
    main()
