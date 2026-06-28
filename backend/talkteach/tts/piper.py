"""piper TTS provider — neural, natural-sounding speech (offline).

`piper <https://github.com/OHF-Voice/piper1-gpl>`_ is a fast, local neural TTS.
Its voices sound far more like real speech than espeak's formant synthesis, so it
is the higher-fidelity end of the benchmark: if an engine does well on espeak but
poorly on piper (or vice-versa) that difference is itself a finding.

Depends on the ``piper-tts`` pip package (the ``[tts]`` extra) plus a voice model
(an ONNX file). Voices are downloaded on first use into a cache dir and reused.
The default ``en_US-lessac-low`` voice is 16 kHz native (no resample) and small
(~few MB). piper bundles its own espeak-ng phonemizer, so no system binary is
needed for piper itself.
"""

from __future__ import annotations

import importlib.util
import tempfile
import wave
from pathlib import Path

from talkteach import config

from .base import TARGET_SAMPLE_RATE, TTSProvider, TTSUnavailableError, normalize_wav

# "low" voices synthesize at 16 kHz — our canonical rate — so they need no
# resampling and download fast, which is what we want for tests/benchmarks.
_DEFAULT_VOICE = "en_US-lessac-low"
_INSTALL_HINT = "piper is not installed — install talkteach-backend[tts]"


class PiperProvider(TTSProvider):
    """Synthesize speech with a piper neural voice.

    ``voice`` is a piper voice name like ``"en_US-lessac-low"`` or
    ``"en_US-amy-low"``; it is downloaded on demand. ``download_dir`` overrides
    where voice models are cached (defaults under the app data root).
    """

    def __init__(
        self, *, default_voice: str = _DEFAULT_VOICE, download_dir: str | None = None
    ) -> None:
        self.default_voice = default_voice
        self.download_dir = (
            Path(download_dir) if download_dir else (config.DATA_ROOT / "piper_voices")
        )
        # Cache loaded PiperVoice objects so repeated synth calls don't reload ONNX.
        self._loaded: dict[str, object] = {}

    def name(self) -> str:
        return "piper"

    def is_available(self) -> tuple[bool, str]:
        if importlib.util.find_spec("piper") is None:
            return False, _INSTALL_HINT
        return True, ""

    def _voice(self, name: str):  # noqa: ANN202 - returns a piper.PiperVoice
        if name in self._loaded:
            return self._loaded[name]
        if importlib.util.find_spec("piper") is None:
            raise TTSUnavailableError(_INSTALL_HINT)
        from piper import PiperVoice  # type: ignore
        from piper.download_voices import download_voice  # type: ignore

        self.download_dir.mkdir(parents=True, exist_ok=True)
        model = self.download_dir / f"{name}.onnx"
        if not model.exists():
            # download_voice fetches `<name>.onnx` and `<name>.onnx.json`.
            download_voice(name, self.download_dir)
        voice = PiperVoice.load(model)
        self._loaded[name] = voice
        return voice

    def synthesize(
        self,
        text: str,
        out_path: str,
        *,
        voice: str | None = None,
        sample_rate: int = TARGET_SAMPLE_RATE,
    ) -> None:
        name = voice or self.default_voice
        piper_voice = self._voice(name)
        # piper writes at the model's native rate; render to a temp WAV then
        # normalize to canonical 16 kHz mono (a no-op for *-low voices).
        with tempfile.TemporaryDirectory() as td:
            raw = f"{td}/raw.wav"
            with wave.open(raw, "wb") as wf:
                piper_voice.synthesize_wav(text, wf)  # type: ignore[attr-defined]
            normalize_wav(raw, out_path, sample_rate)
