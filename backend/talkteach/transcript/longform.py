"""Long-form transcription — chunked, windowed, timestamped decoding (#49).

"Try it" decodes one short clip; a long file (a lecture, a video's audio) needs to
be split into overlapping windows, each decoded, then stitched back with absolute
timestamps. The **windowing and stitching are pure** (``plan_chunks`` /
``merge_segments``) and unit-tested without ML; ``transcribe_long`` is the thin
guarded wrapper that slices the audio and calls an engine's segment-returning
decode. Output feeds the subtitle writers (#48).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .subtitles import Segment

# Sensible defaults: 30 s windows (Whisper's native receptive field) with a 1 s
# overlap so a word straddling a boundary is captured in at least one window.
DEFAULT_WINDOW_S = 30.0
DEFAULT_OVERLAP_S = 1.0


@dataclass(frozen=True)
class Chunk:
    """A decode window: ``index`` (0-based), absolute ``start``/``end`` seconds."""

    index: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def plan_chunks(
    duration_s: float,
    *,
    window_s: float = DEFAULT_WINDOW_S,
    overlap_s: float = DEFAULT_OVERLAP_S,
) -> list[Chunk]:
    """Tile ``[0, duration_s]`` with overlapping windows (pure).

    Each window is ``window_s`` long and starts ``window_s - overlap_s`` after the
    previous one, so consecutive windows share an ``overlap_s`` tail/head. The last
    window is clamped to ``duration_s``. A file shorter than one window yields a
    single chunk. Raises ``ValueError`` on non-positive window or overlap ≥ window.
    """
    if window_s <= 0:
        raise ValueError("window_s must be positive")
    if overlap_s < 0 or overlap_s >= window_s:
        raise ValueError("overlap_s must be in [0, window_s)")
    if duration_s <= 0:
        return []
    if duration_s <= window_s:
        return [Chunk(0, 0.0, duration_s)]

    step = window_s - overlap_s
    chunks: list[Chunk] = []
    start = 0.0
    index = 0
    while start < duration_s:
        end = min(start + window_s, duration_s)
        chunks.append(Chunk(index, round(start, 6), round(end, 6)))
        if end >= duration_s:
            break
        start += step
        index += 1
    return chunks


def offset_segments(segments: list[Segment], by_s: float) -> list[Segment]:
    """Shift every segment's ``start``/``end`` by ``by_s`` (pure)."""
    return [
        Segment(start=float(s["start"]) + by_s, end=float(s["end"]) + by_s, text=s["text"])
        for s in segments
    ]


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def merge_segments(
    per_chunk: list[list[Segment]],
    *,
    overlap_s: float = DEFAULT_OVERLAP_S,
) -> list[Segment]:
    """Flatten already-offset per-chunk segments into one timeline, de-duping the
    overlap (pure).

    Segments live in absolute time. Because windows overlap, a segment near a
    boundary can be decoded in two adjacent chunks; we drop a later segment when it
    starts within ``overlap_s`` of an already-kept segment that has the same
    normalised text. The result is sorted by ``start``.
    """
    flat: list[Segment] = [s for chunk in per_chunk for s in chunk]
    flat.sort(key=lambda s: (float(s["start"]), float(s["end"])))
    kept: list[Segment] = []
    for seg in flat:
        text = _norm(seg["text"])
        if not text:
            continue
        dup = any(
            _norm(k["text"]) == text and abs(float(k["start"]) - float(seg["start"])) <= overlap_s
            for k in kept
        )
        if dup:
            continue
        kept.append(seg)
    return kept


def transcribe_long(
    engine,  # noqa: ANN001  (ASREngine; avoids importing the heavy base at module load)
    audio_path: str,
    *,
    model_dir: str | None = None,
    base_checkpoint: str | None = None,
    window_s: float = DEFAULT_WINDOW_S,
    overlap_s: float = DEFAULT_OVERLAP_S,
) -> list[Segment]:
    """Decode a long file window-by-window and stitch (guarded — needs soundfile).

    Reads the file's duration, plans overlapping windows, slices each to a temp WAV,
    asks the engine for that window's segments, offsets them to absolute time, and
    merges. The pure planning/merge live above; this shim only does the I/O + the
    guarded per-window decode.
    """
    import soundfile as sf  # guarded: audio I/O only when actually decoding

    info = sf.info(audio_path)
    duration = float(info.frames) / float(info.samplerate)
    chunks = plan_chunks(duration, window_s=window_s, overlap_s=overlap_s)
    if not chunks:
        return []

    audio, sr = sf.read(audio_path, dtype="float32", always_2d=False)
    if getattr(audio, "ndim", 1) == 2:
        audio = audio.mean(axis=1)

    import tempfile

    per_chunk: list[list[Segment]] = []
    with tempfile.TemporaryDirectory(prefix="talkteach_long_") as tmp:
        for ch in chunks:
            lo = int(ch.start * sr)
            hi = int(ch.end * sr)
            slice_path = os.path.join(tmp, f"chunk_{ch.index:04d}.wav")
            sf.write(slice_path, audio[lo:hi], int(sr))
            segs = engine.transcribe_segments(
                slice_path, model_dir=model_dir, base_checkpoint=base_checkpoint
            )
            per_chunk.append(offset_segments(segs, ch.start))
    return merge_segments(per_chunk, overlap_s=overlap_s)
