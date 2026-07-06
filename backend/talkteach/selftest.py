"""First-run self-test: a tiny toy dataset so "Teach!" is verifiable (#22).

On first launch the app can seed a handful of short, synthetic spoken-tone clips
(paired with karaoke prompts as transcripts) so a curious user can prove the
whole Record → Check → Teach → Try loop end-to-end in ~2 minutes without
recording anything. The clips are synthetic tones — enough to exercise the
pipeline and the *simulation*; a real fine-tune wants real speech.

Pure stdlib + numpy (numpy is a base dep). No ML deps required.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from .prompts import get_prompts


def make_toy_dataset(
    dest_dir: str | Path, *, language: str | None = "en", clips: int = 8
) -> list[dict]:
    """Write ``clips`` short WAVs into ``dest_dir``; return a manifest.

    Each clip is a distinct, clean tone (so the quality checker passes it) paired
    with a karaoke sentence as its transcript. Returns
    ``[{"path", "text", "duration_s"}, ...]``.
    """
    out = Path(dest_dir)
    out.mkdir(parents=True, exist_ok=True)
    sentences = get_prompts(language)
    sr = 16_000
    seconds = 2.0
    manifest: list[dict] = []
    for i in range(clips):
        text = sentences[i % len(sentences)]
        freq = 180.0 + 25.0 * (i % 8)  # vary pitch so clips aren't identical
        t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
        sig = 0.2 * np.sin(2 * np.pi * freq * t) + 0.01 * np.sin(2 * np.pi * 55 * t)
        pcm = (sig * 32767).astype(np.int16)
        path = out / f"toy_{i:02d}.wav"
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())
        manifest.append({"path": str(path), "text": text, "duration_s": seconds})
    return manifest
