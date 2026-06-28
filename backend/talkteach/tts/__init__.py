"""Text-to-speech providers for testing and benchmarking (not the product flow).

Pick a provider by name with :func:`get_tts_provider` and turn karaoke prompts into
a labelled dataset with :func:`talkteach.tts.dataset.synthesize_dataset`. New OSS
engines (gtts, coqui, …) plug in by adding a :class:`~talkteach.tts.base.TTSProvider`
subclass and one entry in :data:`_PROVIDERS`.
"""

from __future__ import annotations

from .base import TTSProvider, TTSUnavailableError
from .espeak import EspeakProvider
from .piper import PiperProvider

# Registry: name → zero-arg factory. Kept as factories (not instances) so importing
# this package never constructs a provider or touches an optional dependency.
_PROVIDERS: dict[str, type[TTSProvider]] = {
    "espeak": EspeakProvider,
    "piper": PiperProvider,
}


def available_providers() -> list[str]:
    """Names of all registered providers (whether or not their deps are present)."""
    return sorted(_PROVIDERS)


def get_tts_provider(name: str, **kwargs: object) -> TTSProvider:
    """Construct the provider registered under ``name`` (case-insensitive).

    Extra keyword args are forwarded to the provider constructor (e.g.
    ``get_tts_provider("piper", default_voice="en_US-amy-low")``). Raises
    ``KeyError`` with the known names if ``name`` is unregistered.
    """
    key = name.strip().lower()
    try:
        factory = _PROVIDERS[key]
    except KeyError as exc:
        raise KeyError(f"unknown TTS provider '{name}'; known: {available_providers()}") from exc
    return factory(**kwargs)  # type: ignore[arg-type]


__all__ = [
    "EspeakProvider",
    "PiperProvider",
    "TTSProvider",
    "TTSUnavailableError",
    "available_providers",
    "get_tts_provider",
]
