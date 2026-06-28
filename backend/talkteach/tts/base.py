"""TTS provider contract — synthetic *speech* for testing and benchmarking.

The app collects real recorded speech in production. For automated end-to-end
testing and for the engine benchmark (``scripts/benchmark.py``) we need audio with
a *known* transcript and real phonetic content — so word-error-rate actually means
something. The old fixtures used sine *tones* (see ``selftest.make_toy_dataset``):
they exercise the plumbing but a tone has no words, so any WER measured on them is
noise. A ``TTSProvider`` fixes that by turning a karaoke prompt into intelligible
speech whose ground-truth transcript is the prompt itself.

Design mirrors :mod:`talkteach.engines.base`: this module is import-light (no heavy
deps at import time), each provider guards its own optional dependency, and a
provider that can't run reports it via :meth:`TTSProvider.is_available` rather than
crashing. Providers always emit 16 kHz mono PCM WAV — the format Whisper, the CTC
engines, and :mod:`talkteach.audio.quality` all expect.
"""

from __future__ import annotations

import abc
import wave

# audioop is stdlib on the supported Pythons (3.10–3.12) and gives clean rate
# conversion with no extra dependency. It is slated for removal in 3.13; the
# numpy fallback below keeps resampling working if/when it disappears.
try:  # pragma: no cover - exercised by whichever branch the runtime has
    import audioop  # type: ignore

    _HAS_AUDIOOP = True
except ImportError:  # pragma: no cover
    _HAS_AUDIOOP = False

TARGET_SAMPLE_RATE = 16_000


class TTSUnavailableError(RuntimeError):
    """Raised when a provider is asked to synthesize without its dependency.

    The message names the missing piece (a system binary or a pip extra) and how
    to get it, so the benchmark harness and tests can surface a clear hint instead
    of a raw traceback.
    """


class TTSProvider(abc.ABC):
    """Abstract adapter every text-to-speech backend implements.

    Subclasses own all optional-dependency imports (a system binary for espeak, the
    ``piper-tts`` package for piper) and isolate them so this package imports with
    none of them present.
    """

    @abc.abstractmethod
    def name(self) -> str:
        """Stable, human-readable provider name (used in benchmark reports)."""

    @abc.abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """Report whether this provider can synthesize *right now*.

        Returns ``(True, "")`` when its dependency is present, else ``(False, msg)``
        where ``msg`` names what to install.
        """

    @abc.abstractmethod
    def synthesize(
        self,
        text: str,
        out_path: str,
        *,
        voice: str | None = None,
        sample_rate: int = TARGET_SAMPLE_RATE,
    ) -> None:
        """Render ``text`` to a 16 kHz mono WAV at ``out_path``.

        ``voice`` selects a provider-specific voice (e.g. an espeak language code or
        a piper voice name); ``None`` uses the provider default. Raises
        :class:`TTSUnavailableError` if the provider's dependency is missing.
        """


def normalize_wav(src: str, dst: str, target_rate: int = TARGET_SAMPLE_RATE) -> None:
    """Rewrite WAV ``src`` as 16-bit **mono** PCM at ``target_rate`` into ``dst``.

    TTS backends emit at their own rate (espeak ~22 kHz, piper 16/22 kHz) and
    sometimes stereo. The whole pipeline downstream assumes 16 kHz mono, so every
    provider funnels its raw output through here for one canonical format.
    """
    with wave.open(src, "rb") as w:
        n_channels = w.getnchannels()
        sample_width = w.getsampwidth()
        frame_rate = w.getframerate()
        frames = w.readframes(w.getnframes())

    frames, sample_width = _to_int16(frames, sample_width)
    frames = _to_mono(frames, n_channels)
    if frame_rate != target_rate:
        frames = _resample(frames, frame_rate, target_rate)

    with wave.open(dst, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(target_rate)
        w.writeframes(frames)


def wav_duration_s(path: str) -> float:
    """Duration of a WAV file in seconds (used to build manifest entries)."""
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        return w.getnframes() / float(rate) if rate else 0.0


# -- internal helpers ---------------------------------------------------------


def _to_int16(frames: bytes, sample_width: int) -> tuple[bytes, int]:
    if sample_width == 2:
        return frames, 2
    if _HAS_AUDIOOP:
        return audioop.lin2lin(frames, sample_width, 2), 2
    # numpy fallback: reinterpret + scale to int16.
    import numpy as np

    dtype = {1: np.uint8, 4: np.int32}.get(sample_width)
    if dtype is None:
        raise ValueError(f"unsupported sample width: {sample_width}")
    arr = np.frombuffer(frames, dtype=dtype).astype(np.float64)
    # 8-bit PCM is unsigned (centred at 128); 32-bit is signed full-scale.
    arr = (arr - 128.0) / 128.0 if sample_width == 1 else arr / 2_147_483_648.0
    return (arr * 32767.0).astype(np.int16).tobytes(), 2


def _to_mono(frames: bytes, n_channels: int) -> bytes:
    if n_channels == 1:
        return frames
    if _HAS_AUDIOOP:
        return audioop.tomono(frames, 2, 0.5, 0.5)
    import numpy as np

    arr = np.frombuffer(frames, dtype=np.int16).reshape(-1, n_channels)
    return arr.mean(axis=1).astype(np.int16).tobytes()


def _resample(frames: bytes, in_rate: int, out_rate: int) -> bytes:
    if _HAS_AUDIOOP:
        converted, _ = audioop.ratecv(frames, 2, 1, in_rate, out_rate, None)
        return converted
    # numpy linear-interpolation fallback (adequate for ASR benchmarking).
    import numpy as np

    src = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
    if src.size == 0:
        return frames
    n_out = max(1, round(src.size * out_rate / in_rate))
    xp = np.linspace(0.0, 1.0, num=src.size, endpoint=False)
    x = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x, xp, src).astype(np.int16).tobytes()
