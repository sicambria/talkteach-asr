#!/usr/bin/env python3
"""SOTA Domain D02: ASR Accuracy — Spontaneous Speech — WER on Common Voice en.

The B-001 torchcodec fix lets HF audio columns decode without torchcodec, but
Common Voice 17 additionally fails to resolve data files under `datasets` v5
(EmptyDatasetError / gated access) in this environment. When the dataset can't be
loaded we abstain with a clear reason rather than emit a bare "error".
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from talkteach.sota.domains import get_domain
from talkteach.sota.harness import SOTAHarness
from scripts.sota.common import build_base_parser, write_abstention, write_domain_result


def main():
    domain = get_domain("d02_wer_spontaneous")
    parser = build_base_parser(domain.id, domain.description)
    args = parser.parse_args()
    harness = SOTAHarness(
        engines=args.engines.split(","),
        seed=args.seed,
        data_root=args.data_root,
        baseline_only=args.baseline_only,
    )
    result = harness.run_domain(domain)
    if result.band == "error" or (result.score_0_1000 == 0 and not result.metrics):
        print(f"[sota] D02 could not load Common Voice: {result.notes}")
        write_abstention(
            domain,
            requires="a working Common Voice 17 loader (fails with EmptyDatasetError under "
            "HF datasets v5 / gated access here) or local CV clips at the SOTA cache",
            json_path=args.json,
        )
    else:
        write_domain_result(result, args.json)


if __name__ == "__main__":
    main()
