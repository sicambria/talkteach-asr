"""Subtitle / caption output — SRT, VTT, and timestamped plain text (#48).

"Subtitle this video" is a top real-world ASR use case the product did not serve
(see project/docs/FORMATS.md). This module is pure formatting over a list of
timestamped segments — no ML, no I/O — so it is unit-tested directly. The segments
come from the engine's segment-returning decode (see
``whisper_lora.transcribe_segments``) or the long-form chunker (#49).
"""

from __future__ import annotations

from typing import TypedDict


class Segment(TypedDict):
    """One decoded span: ``start``/``end`` in seconds, ``text`` the words."""

    start: float
    end: float
    text: str


def _fmt_timestamp(seconds: float, *, sep: str) -> str:
    """Format ``seconds`` as ``HH:MM:SS<sep>mmm`` (``sep`` = ``,`` SRT / ``.`` VTT).

    Negative inputs clamp to zero so a rounding underflow never emits ``-0:00``.
    """
    if seconds < 0 or seconds != seconds:  # negative or NaN
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"


def _clean(text: str) -> str:
    return " ".join(text.split())


def segments_to_srt(segments: list[Segment]) -> str:
    """Render segments as SubRip (``.srt``): 1-based cue numbers, ``,`` millis.

    Empty-text segments are dropped (a silent gap is not a caption). Returns a
    trailing-newline-terminated string, or ``""`` when nothing is captionable.
    """
    lines: list[str] = []
    cue = 0
    for seg in segments:
        text = _clean(seg["text"])
        if not text:
            continue
        cue += 1
        start = _fmt_timestamp(float(seg["start"]), sep=",")
        end = _fmt_timestamp(float(seg["end"]), sep=",")
        lines.append(str(cue))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")  # blank line between cues
    return "\n".join(lines) + ("\n" if lines else "")


def segments_to_vtt(segments: list[Segment]) -> str:
    """Render segments as WebVTT (``.vtt``): ``WEBVTT`` header, ``.`` millis."""
    lines: list[str] = ["WEBVTT", ""]
    wrote = False
    for seg in segments:
        text = _clean(seg["text"])
        if not text:
            continue
        wrote = True
        start = _fmt_timestamp(float(seg["start"]), sep=".")
        end = _fmt_timestamp(float(seg["end"]), sep=".")
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    if not wrote:
        return "WEBVTT\n"
    return "\n".join(lines) + "\n"


def segments_to_text(segments: list[Segment], *, timestamps: bool = False) -> str:
    """Plain-text transcript. With ``timestamps`` prefix each line ``[MM:SS] ``."""
    out: list[str] = []
    for seg in segments:
        text = _clean(seg["text"])
        if not text:
            continue
        if timestamps:
            ts = _fmt_timestamp(float(seg["start"]), sep=".")[:-4]  # HH:MM:SS
            out.append(f"[{ts}] {text}")
        else:
            out.append(text)
    return "\n".join(out) + ("\n" if out else "")
