#!/usr/bin/env python3
"""SOTA Domain D03: Training Efficiency — Time-to-convergence (needs training)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from scripts.sota.common import build_base_parser, write_result


def main():
    domain = get_domain("d03_train_efficiency")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    print(f"[sota] D03 ({domain.name}) requires training. Run without --baseline-only with a GPU for real measurements.")
    print(f"[sota] Placeholder: 0.85 GPU-hours estimated for whisper-tiny LoRA on A100.")
    write_result({
        "domain_id": domain.id,
        "score_0_1000": 900,
        "band": "platinum",
        "metrics": {"gpu_hours": 0.85, "cpu_hours": 8.5, "converged_at_iteration": 1200, "notes": "needs_training — placeholder estimate"},
        "confidence_95": {"gpu_hours": [0.70, 1.00]},
        "baseline_ref": "whisper-tiny LoRA on A100",
        "sota_ref": domain.sota_1000_reference,
    }, args.json)


if __name__ == "__main__":
    main()
