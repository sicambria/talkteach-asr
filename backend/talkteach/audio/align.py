"""Forced alignment — split a long recording into sentence clips (#12).

When a child reads a paragraph in one take, forced alignment maps each word to a
timestamp so we can cut clean per-sentence training clips on Screen 2. This is a
**Tier C scaffold** (see project/docs/ROADMAP_STATUS.md): the adapter boundary and the
pure sentence-grouping logic are here and tested; the heavy aligner backends
(NeMo Forced Aligner / WhisperX) are wired behind guarded imports and documented
in project/docs/ALIGNMENT.md.

The pure part — turning word-level (word, start, end) timings + a target
transcript into sentence-bounded :class:`talkteach.audio.vad.Segment` cuts — is
the bit that actually decides clip boundaries, so it lives here and is unit
testable without any aligner installed.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass

from .vad import Segment

# Sentence-ending punctuation we split on when grouping aligned words.
_SENTENCE_END = re.compile(r"[.!?]+$")


@dataclass(frozen=True)
class AlignedWord:
    word: str
    start_s: float
    end_s: float


def aligner_available() -> bool:
    """True if a supported forced-aligner backend is importable."""
    return any(
        importlib.util.find_spec(m) is not None
        for m in ("whisperx", "nemo_forced_aligner", "ctc_forced_aligner")
    )


def group_into_sentences(words: list[AlignedWord]) -> list[Segment]:
    """Group word timings into sentence-bounded clips (pure, unit-tested).

    A new clip starts after any word whose text ends in sentence punctuation.
    Empty input → no segments. This is the boundary logic Screen 2 uses to slice
    a long take into clips the child can review one at a time.
    """
    segments: list[Segment] = []
    if not words:
        return segments
    start = words[0].start_s
    for i, w in enumerate(words):
        is_last = i == len(words) - 1
        if _SENTENCE_END.search(w.word.strip()) or is_last:
            segments.append(Segment(start, w.end_s))
            if not is_last:
                start = words[i + 1].start_s
    return segments


def align(audio_path: str, transcript: str, language: str | None = None) -> list[AlignedWord]:
    """Force-align ``transcript`` to ``audio_path`` → word timings (Tier C).

    Raises ImportError when no aligner backend is installed; callers fall back to
    VAD-only segmentation. See project/docs/ALIGNMENT.md for the backend wiring plan.
    """
    raise ImportError(
        "Forced alignment needs a backend (WhisperX or NeMo Forced Aligner). "
        "See project/docs/ALIGNMENT.md. Falling back to VAD segmentation for now."
    )
