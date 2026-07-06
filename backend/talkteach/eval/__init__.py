"""Evaluation beyond one WER number — per-utterance metrics + an error report (#52).

jiwer-only (no torch), so it runs in the dep-light test job. Powers active learning
(#32: which clips are worst) and Advanced mode insight. See
project/docs/COMPETITIVE_GAPS.md #52.
"""

from __future__ import annotations

from .report import (
    UtteranceScore,
    error_report,
    normalized_vs_raw,
    per_utterance_wer,
)

__all__ = [
    "UtteranceScore",
    "error_report",
    "normalized_vs_raw",
    "per_utterance_wer",
]
