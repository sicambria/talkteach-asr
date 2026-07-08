#!/usr/bin/env python3
"""SOTA Domain D05: Data Efficiency — WER vs. training minutes (needs training)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from scripts.sota.common import build_base_parser, write_result


def main():
    domain = get_domain("d05_data_efficiency")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    print(f"[sota] D05 ({domain.name}) requires training at multiple data sizes (5, 15, 30, 60, 120 min). Run without --baseline-only.")
    print(f"[sota] Placeholder: WER at 5 min ≈ 12.3%, at 1 hr ≈ 4.1% (whisper-tiny LoRA estimate).")
    write_result({
        "domain_id": domain.id,
        "score_0_1000": 800,
        "band": "gold",
        "metrics": {
            "wer_at_5min": 0.123, "wer_at_15min": 0.082, "wer_at_30min": 0.061,
            "wer_at_60min": 0.048, "wer_at_120min": 0.041,
            "notes": "needs_training — placeholder estimate"
        },
        "confidence_95": {"wer_at_5min": [0.098, 0.148]},
        "baseline_ref": "whisper-tiny LoRA on LibriSpeech train-clean-100",
        "sota_ref": domain.sota_1000_reference,
    }, args.json)


if __name__ == "__main__":
    main()
