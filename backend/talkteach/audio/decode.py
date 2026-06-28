"""Decode + resample arbitrary audio to 16 kHz mono via bundled ffmpeg (#10/#20).

Browser ``MediaRecorder`` emits webm/opus; users also drag in mp3/m4a/ogg. The
training and quality pipelines want 16 kHz mono PCM WAV. ffmpeg (LGPL build,
invoked as a subprocess — see project/docs/THIRD_PARTY.md) is the one canonical converter
shared by uploads and recordings (project/docs/DECISIONS.md D-010).

ffmpeg is an external binary, not a Python package, so we never import it; we
shell out and degrade gracefully when it's absent. The command-building and
availability logic is pure and unit-tested; the actual subprocess run is the only
side-effecting part.
"""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

TARGET_SAMPLE_RATE = 16_000


class AudioDecodeError(RuntimeError):
    """ffmpeg is missing or failed. Message is written for a grown-up to act on."""


def ffmpeg_available() -> bool:
    """True if an ``ffmpeg`` binary is on PATH (or bundled next to us)."""
    return shutil.which("ffmpeg") is not None


def build_decode_command(src: str, dst: str, sample_rate: int = TARGET_SAMPLE_RATE) -> list[str]:
    """Build the ffmpeg argv to decode ``src`` → mono ``sample_rate`` PCM16 WAV.

    Pure (no I/O) so it's unit-testable. ``-y`` overwrites, ``-ac 1`` downmixes to
    mono, ``-ar`` resamples, ``-f wav`` + ``pcm_s16le`` forces a stdlib-readable
    WAV.
    """
    return [
        "ffmpeg",
        "-y",
        "-i",
        src,
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "wav",
        "-acodec",
        "pcm_s16le",
        dst,
    ]


def decode_to_wav(
    src_path: str, dst_path: str | None = None, sample_rate: int = TARGET_SAMPLE_RATE
) -> str:
    """Decode any ffmpeg-readable file to a 16 kHz mono WAV; return its path.

    Raises :class:`AudioDecodeError` if ffmpeg is unavailable or the decode fails.
    """
    if not ffmpeg_available():
        raise AudioDecodeError(
            "We can't read this kind of sound file yet — the audio pack (ffmpeg) "
            "isn't installed. Ask a grown-up to install it."
        )
    dst = dst_path or str(Path(src_path).with_suffix(".16k.wav"))
    cmd = build_decode_command(src_path, dst, sample_rate)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise AudioDecodeError(f"Couldn't convert the recording: {exc}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
        raise AudioDecodeError(f"Couldn't convert the recording: {tail[0]}")
    return dst


def decode_to_samples(src_path: str, sample_rate: int = TARGET_SAMPLE_RATE):  # noqa: ANN201
    """Decode to a float32 mono numpy array in [-1, 1] plus the sample rate."""
    import numpy as np

    wav_path = decode_to_wav(src_path, sample_rate=sample_rate)
    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    return arr, sr
