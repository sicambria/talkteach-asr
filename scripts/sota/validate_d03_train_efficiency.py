#!/usr/bin/env python3
"""SOTA Domain D03: Training Efficiency — Time-to-convergence (needs a training run)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from scripts.sota.common import build_base_parser, write_abstention


def main():
    domain = get_domain("d03_train_efficiency")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    print(f"[sota] D03 ({domain.name}) is NOT measured — no fabricated estimate is emitted.")
    print("[sota] Requires a real training run (GPU) to time convergence on train-clean-100.")
    write_abstention(
        domain,
        requires="GPU training run measuring time-to-convergence on LibriSpeech "
        "train-clean-100 (extract the cached tar first)",
        json_path=args.json,
    )


if __name__ == "__main__":
    main()
