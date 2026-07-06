"""Decoding controls — beam size, hotword/prompt biasing, temperature fallback (#50).

Cheap accuracy wins that every pro decoder exposes (faster-whisper, NeMo): a wider
beam, an ``initial_prompt`` / hotword list to bias toward the user's vocabulary, and
a temperature fallback ladder so a low-confidence greedy decode retries hotter
instead of emitting garbage. :class:`DecodeOptions` is a pure, validated value
object; :meth:`to_faster_whisper_kwargs` maps it to the decode backend. The engine's
``transcribe`` takes an optional ``options`` — omitting it preserves today's
behaviour exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Whisper's canonical temperature-fallback ladder: start greedy (0.0), climb only
# when the decode looks unreliable (compression-ratio / logprob heuristics inside
# faster-whisper). Matches OpenAI's reference default.
DEFAULT_TEMPERATURE_LADDER: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


@dataclass(frozen=True)
class DecodeOptions:
    """Validated decoding knobs. Defaults reproduce the stock faster-whisper decode.

    Parameters
    ----------
    beam_size:
        Beam width (≥1). 1 = greedy. Higher trades speed for a bit of accuracy.
    initial_prompt:
        Free-text context prepended to bias the decode (names, topic, style).
    hotwords:
        Words/phrases to bias toward — e.g. the user's vocabulary. Joined into the
        backend's ``hotwords`` string.
    temperature:
        Fallback ladder. A single value disables fallback; the default ladder
        retries hotter when a window decodes unreliably.
    """

    beam_size: int = 5
    initial_prompt: str | None = None
    hotwords: tuple[str, ...] = field(default_factory=tuple)
    temperature: tuple[float, ...] = DEFAULT_TEMPERATURE_LADDER

    def __post_init__(self) -> None:
        if self.beam_size < 1:
            raise ValueError("beam_size must be >= 1")
        if not self.temperature:
            raise ValueError("temperature ladder must have at least one value")
        for t in self.temperature:
            if t < 0.0:
                raise ValueError("temperature values must be >= 0.0")

    @property
    def hotword_prompt(self) -> str | None:
        """Hotwords as one space-joined biasing string (or ``None``)."""
        return " ".join(w.strip() for w in self.hotwords if w.strip()) or None

    def to_faster_whisper_kwargs(self) -> dict:
        """Map to ``faster_whisper.WhisperModel.transcribe`` kwargs (pure).

        ``temperature`` is passed as a single float when the ladder has one entry
        (faster-whisper disables fallback for a scalar) and as a list otherwise.
        ``hotwords`` is only included when set, so older backend versions that lack
        the parameter still work with the default options.
        """
        kwargs: dict = {"beam_size": self.beam_size}
        if self.initial_prompt:
            kwargs["initial_prompt"] = self.initial_prompt
        hp = self.hotword_prompt
        if hp:
            kwargs["hotwords"] = hp
        kwargs["temperature"] = (
            self.temperature[0] if len(self.temperature) == 1 else list(self.temperature)
        )
        return kwargs
