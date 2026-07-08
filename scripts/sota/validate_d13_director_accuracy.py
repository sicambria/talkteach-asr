#!/usr/bin/env python3
"""SOTA Domain D13: Director Auto-Selection — vs oracle (needs an exhaustive sweep)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from scripts.sota.common import build_base_parser, write_abstention


def main():
    domain = get_domain("d13_director_accuracy")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    print(f"[sota] D13 ({domain.name}) is NOT measured — no fabricated estimate is emitted.")
    print("[sota] Requires training every config across (hw, data, lang) scenarios to build the")
    print("[sota] oracle, then comparing the director's pick against it.")
    write_abstention(
        domain,
        requires="exhaustive training sweep over (hardware, data, language) scenarios to "
        "build the WER-minimizing oracle, then director-vs-oracle comparison",
        json_path=args.json,
    )


if __name__ == "__main__":
    main()
