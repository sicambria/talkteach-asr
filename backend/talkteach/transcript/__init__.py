"""Transcript post-processing: subtitles, long-form chunking, decoding controls,
and punctuation restoration — the competitive-parity batch #48–#51.

Every module here is **torch-free at import time** (pure string/number logic on a
list of ``{"start", "end", "text"}`` segments); any heavy decode is a thin guarded
wrapper over an engine's ``transcribe``. See project/docs/DECISIONS.md D-002 for the
pure-helper split and project/docs/COMPETITIVE_GAPS.md for why these are parity gaps.
"""

from __future__ import annotations

from .decode import DecodeOptions
from .longform import Chunk, merge_segments, plan_chunks
from .punctuate import restore
from .subtitles import Segment, segments_to_srt, segments_to_text, segments_to_vtt

__all__ = [
    "Chunk",
    "DecodeOptions",
    "Segment",
    "merge_segments",
    "plan_chunks",
    "restore",
    "segments_to_srt",
    "segments_to_text",
    "segments_to_vtt",
]
