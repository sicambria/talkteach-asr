"""SOTA benchmark framework — measure TalkTeach against real-world ASR standards.

15 domains across accuracy, efficiency, robustness, portability, and automation.
Each scored 0-1000 against real-world SOTA=1000 anchors.

Public API:
    from talkteach.sota import harness, datasets, scoring, domains, report
    harness.SOTAHarness    — one harness to run all domains
    datasets.download      — download benchmark datasets (LibriSpeech, Common Voice, ...)
    scoring.wer, .cer, .rtf, .confidence_interval  — shared measurement functions
    domains.ALL_DOMAINS    — list of 15 Domain dataclasses
    report.generate        — produce SCOREBOARD.md and JSON
"""

from talkteach.sota.domains import ALL_DOMAINS, Band, Domain  # noqa: F401

__all__ = ["ALL_DOMAINS", "Band", "Domain"]
