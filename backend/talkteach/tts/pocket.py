"""pocket-tts provider — high-quality neural TTS with voice cloning, runs on CPU.

`Pocket TTS <https://github.com/kyutai-labs/pocket-tts>`_ is a 100M-parameter neural
text-to-speech model from Kyutai. It runs faster than real-time on a laptop CPU
(~6x on an M4 MacBook Air) with ~200 ms to first audio chunk.

Unique to this provider: **voice cloning**. Instead of picking a fixed voice name,
you can point ``voice`` at any WAV file and Pocket TTS will generate speech that
sounds like the speaker in that recording — from as little as 20 seconds of audio.

Depends on the ``pocket-tts`` pip package (the ``[pocket-tts]`` extra), which brings
``torch>=2.5`` (CPU variant) and model weights downloaded on first use from Hugging
Face. Model and voice states are cached after loading so repeated calls are fast.
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import scipy.io.wavfile

from talkteach import config

from .base import TARGET_SAMPLE_RATE, TTSProvider, TTSUnavailableError, normalize_wav

_INSTALL_HINT = (
    "pocket-tts is not installed — install it with: uv pip install talkteach-backend[pocket-tts]"
)

# Default voice for each language Pocket TTS supports. Languages not in this
# dict fall through to the configured ``default_voice`` (which must be a
# provider-catalog name or a WAV path).
_POCKET_VOICES: dict[str, str] = {
    "en": "alba",
    "fr": "estelle",
    "de": "juergen",
    "pt": "rafael",
    "it": "giovanni",
    "es": "lola",
}

# Map TalkTeach language codes to Pocket TTS language config names.
_POCKET_LANGUAGES: dict[str, str] = {
    "en": "english",
    "fr": "french_24l",
    "de": "german_24l",
    "pt": "portuguese",
    "it": "italian",
    "es": "spanish_24l",
}

# File extensions recognised as voice-cloning samples.
_CLONE_EXTENSIONS: frozenset[str] = frozenset({".wav", ".mp3", ".flac", ".ogg", ".m4a"})


class PocketTTSProvider(TTSProvider):
    """Synthesize speech with Kyutai's Pocket TTS (CPU, voice cloning).

    ``voice`` can be:

    * A catalog name (e.g. ``"alba"``, ``"estelle"``, ``"juergen"``) — uses a
      predefined voice. See the full list in the project README.
    * A WAV/MP3 file path — **voice cloning**: generates speech in that voice.
    * A ``.safetensors`` path — a previously exported voice state for fast loading.

    The first call to :meth:`synthesize` loads the model (~100M weights, ~18 s on
    first run for download + load). Subsequent calls reuse the cached model. Voice
    states are also cached once loaded.
    """

    def __init__(
        self,
        *,
        default_voice: str | None = None,
        language: str = "english",
        quantize: bool = False,
        download_dir: str | None = None,
    ) -> None:
        self.default_voice = default_voice
        self.language = language
        self.quantize = quantize
        self.download_dir = (
            Path(download_dir) if download_dir else (config.DATA_ROOT / "pocket_tts")
        )
        self._model: Any = None
        self._voice_cache: dict[str, Any] = {}

    def name(self) -> str:
        return "pocket-tts"

    def is_available(self) -> tuple[bool, str]:
        if importlib.util.find_spec("pocket_tts") is None:
            return False, _INSTALL_HINT
        return True, ""

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        if importlib.util.find_spec("pocket_tts") is None:
            raise TTSUnavailableError(_INSTALL_HINT)
        from pocket_tts import TTSModel

        self._model = TTSModel.load_model(
            language=self.language,
            quantize=self.quantize,
        )
        return self._model

    def _ensure_voice(self, voice: str | None) -> Any:
        name = voice or self.default_voice or _POCKET_VOICES.get("en", "alba")
        if name is None:
            raise TTSUnavailableError(
                "no voice specified and no default configured — "
                "pass a voice name, WAV path, or safetensors path"
            )

        if name in self._voice_cache:
            return self._voice_cache[name]

        model = self._ensure_model()
        state = model.get_state_for_audio_prompt(name)  # type: ignore[attr-defined]
        self._voice_cache[name] = state
        return state

    def _resolve_voice(self, language: str | None) -> str | None:
        lang = (language or "en").strip().lower()
        return _POCKET_VOICES.get(lang)

    def synthesize(
        self,
        text: str,
        out_path: str,
        *,
        voice: str | None = None,
        sample_rate: int = TARGET_SAMPLE_RATE,
    ) -> None:
        model = self._ensure_model()
        voice_state = self._ensure_voice(voice)

        audio = model.generate_audio(voice_state, text)  # type: ignore[attr-defined]

        # Convert float32 [-1, 1] to int16 PCM for WAV write; normalize_wav
        # expects the stdlib wave module which only handles integer formats.
        samples = (audio.numpy() * 32767.0).clip(-32768, 32767).astype(np.int16)

        with tempfile.TemporaryDirectory() as td:
            raw = f"{td}/raw.wav"
            scipy.io.wavfile.write(raw, model.sample_rate, samples)  # type: ignore[attr-defined]
            normalize_wav(raw, out_path, sample_rate)
