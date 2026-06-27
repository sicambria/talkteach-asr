"""Audio quality checks for TalkTeach recordings.

Pure-numpy, real-time-ish quality verdicts plus aggregation into the director's
:class:`~talkteach.director.types.DataProfile`.
"""

from __future__ import annotations

from talkteach.audio.quality import (
    ClipQuality,
    Verdict,
    aggregate,
    analyze_file,
    analyze_samples,
)

__all__ = [
    "ClipQuality",
    "Verdict",
    "aggregate",
    "analyze_file",
    "analyze_samples",
]
