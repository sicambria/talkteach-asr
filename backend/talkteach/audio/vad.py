"""Voice-activity detection: trim silence and auto-segment recordings (#11).

Uses **Silero VAD** (MIT, torch) when available to find speech regions; the
*segmentation* logic that turns raw speech timestamps into clean, padded,
merged training clips is pure Python and unit-tested without torch.

This closes part of the data-quality gap: the user records one long take, and we
split it into sentence-ish clips and drop the dead air automatically.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

TARGET_SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class Segment:
    """A speech region in seconds (start inclusive, end exclusive)."""

    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


def silero_available() -> bool:
    return importlib.util.find_spec("silero_vad") is not None or (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("torchaudio") is not None
    )


def merge_segments(
    segments: list[Segment],
    *,
    pad_s: float = 0.1,
    min_gap_s: float = 0.3,
    min_duration_s: float = 0.4,
    max_duration_s: float = 15.0,
) -> list[Segment]:
    """Clean raw VAD spans into usable clips (pure, unit-tested).

    - pads each span by ``pad_s`` (keeps onsets/offsets from being clipped),
    - merges spans separated by less than ``min_gap_s`` (don't cut mid-word),
    - drops spans shorter than ``min_duration_s`` (too short to train on),
    - splits spans longer than ``max_duration_s`` into even chunks (Whisper's
      30 s window; we stay well under for memory).
    """
    if not segments:
        return []
    ordered = sorted(segments, key=lambda s: s.start_s)
    merged: list[Segment] = [
        Segment(max(0.0, ordered[0].start_s - pad_s), ordered[0].end_s + pad_s)
    ]
    for seg in ordered[1:]:
        start, end = max(0.0, seg.start_s - pad_s), seg.end_s + pad_s
        last = merged[-1]
        if start - last.end_s < min_gap_s:
            merged[-1] = Segment(last.start_s, max(last.end_s, end))
        else:
            merged.append(Segment(start, end))

    out: list[Segment] = []
    for seg in merged:
        if seg.duration_s < min_duration_s:
            continue
        if seg.duration_s <= max_duration_s:
            out.append(seg)
            continue
        # Split an over-long span into even sub-clips ≤ max_duration_s.
        n = int(seg.duration_s // max_duration_s) + 1
        step = seg.duration_s / n
        for i in range(n):
            out.append(Segment(seg.start_s + i * step, seg.start_s + (i + 1) * step))
    return out


def detect_speech(samples, sample_rate: int = TARGET_SAMPLE_RATE) -> list[Segment]:  # noqa: ANN001
    """Run Silero VAD over a mono waveform → raw speech :class:`Segment`s.

    Raises ImportError (caught by callers) when Silero/torch aren't installed.
    Callers typically pass the result through :func:`merge_segments`.
    """
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad  # type: ignore

    model = load_silero_vad()
    tensor = torch.as_tensor(samples, dtype=torch.float32)
    spans = get_speech_timestamps(tensor, model, sampling_rate=sample_rate, return_seconds=True)
    return [Segment(float(s["start"]), float(s["end"])) for s in spans]
