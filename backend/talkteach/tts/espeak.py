"""espeak-ng TTS provider — formant-synthesis speech via a system binary.

espeak-ng is a tiny, ubiquitous open-source speech synthesizer. The voice is
robotic, but it is **phonetically correct**, so a model's word-error-rate on it is
meaningful — and unlike the neural piper voice it needs no model download, which
makes it the right generator for the CI fast-path.

It is the one provider that depends on a *system binary* rather than a pip package:
install ``espeak-ng`` (e.g. ``apt-get install espeak-ng``, ``brew install
espeak-ng``). When the binary is absent :meth:`is_available` says so and tests
skip cleanly.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from .base import TARGET_SAMPLE_RATE, TTSProvider, TTSUnavailableError, normalize_wav

# Prefer espeak-ng; fall back to the older `espeak` if that's all that's present.
_BINARIES = ("espeak-ng", "espeak")
_INSTALL_HINT = (
    "the espeak-ng binary was not found on PATH — install it "
    "(Debian/Ubuntu: `apt-get install espeak-ng`, macOS: `brew install espeak-ng`)"
)


class EspeakProvider(TTSProvider):
    """Synthesize speech by shelling out to the espeak-ng binary.

    ``voice`` is an espeak voice/language code (e.g. ``"en"``, ``"en-us"``,
    ``"es"``, ``"de"``). ``words_per_minute`` controls speaking rate.
    """

    def __init__(self, *, default_voice: str = "en", words_per_minute: int = 160) -> None:
        self.default_voice = default_voice
        self.words_per_minute = words_per_minute

    def name(self) -> str:
        return "espeak-ng"

    @staticmethod
    def _binary() -> str | None:
        for candidate in _BINARIES:
            path = shutil.which(candidate)
            if path:
                return path
        return None

    def is_available(self) -> tuple[bool, str]:
        return (True, "") if self._binary() else (False, _INSTALL_HINT)

    def synthesize(
        self,
        text: str,
        out_path: str,
        *,
        voice: str | None = None,
        sample_rate: int = TARGET_SAMPLE_RATE,
    ) -> None:
        binary = self._binary()
        if binary is None:
            raise TTSUnavailableError(_INSTALL_HINT)
        voice = voice or self.default_voice
        # espeak writes a WAV at its own (≈22 kHz) rate; render to a temp file then
        # normalize to canonical 16 kHz mono. `-w` writes a file instead of playing.
        with tempfile.TemporaryDirectory() as td:
            raw = os.path.join(td, "raw.wav")
            cmd = [binary, "-v", voice, "-s", str(self.words_per_minute), "-w", raw, text]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:  # pragma: no cover - rare
                raise TTSUnavailableError(
                    f"espeak-ng failed for voice '{voice}': {exc.stderr or exc}"
                ) from exc
            normalize_wav(raw, out_path, sample_rate)
