#!/usr/bin/env python3
"""SOTA Domain D09: Augmentation Efficacy — SpecAugment + noise (needs a training run)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from scripts.sota.common import build_base_parser, write_abstention


def main():
    domain = get_domain("d09_augmentation")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    print(f"[sota] D09 ({domain.name}) is NOT measured — no fabricated estimate is emitted.")
    print("[sota] Requires paired training runs (with/without augmentation) — and the")
    print("[sota] augmentation collator is still unwired (see wiring debt E07-E10 in OVERALL.md).")
    write_abstention(
        domain,
        requires="paired with/without-augmentation training runs on train-clean-100; "
        "also blocked on the unwired augmentation collator (OVERALL.md wiring debt)",
        json_path=args.json,
    )


if __name__ == "__main__":
    main()
