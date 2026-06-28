"""Build a labelled speech dataset from a TTS provider.

:func:`synthesize_dataset` is the drop-in, *meaningful* replacement for
``selftest.make_toy_dataset``: instead of sine tones it renders karaoke prompts to
real speech, returning the identical manifest shape
``[{"path", "text", "duration_s"}, ...]`` that the engines and the benchmark
harness consume. Because the prompt IS the transcript, every clip is ground-truth
labelled — exactly what a fair WER measurement needs.
"""

from __future__ import annotations

from pathlib import Path

from talkteach.prompts import get_prompts

from .base import TTSProvider, wav_duration_s


def synthesize_dataset(
    provider: TTSProvider,
    dest_dir: str | Path,
    *,
    language: str | None = "en",
    prompts: list[str] | None = None,
    voices: list[str | None] | None = None,
    n: int | None = None,
    sample_rate: int = 16_000,
    prefix: str = "clip",
    start_index: int = 0,
) -> list[dict]:
    """Render prompts to WAVs in ``dest_dir`` and return a training manifest.

    Parameters
    ----------
    provider:
        Any :class:`~talkteach.tts.base.TTSProvider` (espeak, piper, …).
    prompts:
        Explicit sentences to speak. Defaults to the karaoke set for ``language``
        (``talkteach.prompts.get_prompts``). The benchmark uses this to hand a
        *disjoint* prompt list to the held-out eval set so it never overlaps train.
    voices:
        Voices to cycle through (round-robin per clip) for speaker variety; a list
        of one (or ``None``) uses the provider default.
    n:
        Cap the number of clips. ``start_index``/``prefix`` make filenames unique
        when generating train and eval sets into the same parent.
    """
    out = Path(dest_dir)
    out.mkdir(parents=True, exist_ok=True)
    sentences = list(prompts) if prompts is not None else get_prompts(language, n)
    if n is not None:
        sentences = sentences[:n]
    voice_cycle: list[str | None] = list(voices) if voices else [None]

    manifest: list[dict] = []
    for offset, text in enumerate(sentences):
        voice = voice_cycle[offset % len(voice_cycle)]
        path = out / f"{prefix}_{start_index + offset:03d}.wav"
        provider.synthesize(text, str(path), voice=voice, sample_rate=sample_rate)
        manifest.append(
            {"path": str(path), "text": text, "duration_s": round(wav_duration_s(str(path)), 3)}
        )
    return manifest
