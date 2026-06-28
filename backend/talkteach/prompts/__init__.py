"""Karaoke prompt sets — sentences for a child to read aloud (roadmap #21).

Giving a child a sentence to read ("karaoke") is the fastest way to collect
clean, *labelled* audio: the prompt IS the transcript, so Screen 2 has a ground
truth to check against. We ship a small, CC0 / public-domain starter set per
language here; the full product seeds these from the Common Voice CC0 sentence
corpus (see project/docs/PROMPTS.md). All sentences here are short, kid-friendly, and
phonetically varied.
"""

from __future__ import annotations

# CC0 (public-domain dedication) — original, intentionally simple sentences.
PROMPT_SETS: dict[str, list[str]] = {
    "en": [
        "The cat sat on the warm mat.",
        "I like to run and jump and play.",
        "Look at the big blue sky today.",
        "My dog can catch a little ball.",
        "We eat red apples after lunch.",
        "The moon is bright and round at night.",
        "Please pass me the green cup.",
        "Birds sing a happy song each morning.",
        "She drew a yellow sun and a tree.",
        "Let us read a fun story now.",
        "The train goes fast down the track.",
        "I can count to ten very fast.",
    ],
    "es": [
        "El gato está en la alfombra.",
        "Me gusta correr y saltar.",
        "Mira el cielo azul de hoy.",
        "Mi perro atrapa la pelota.",
        "Comemos manzanas rojas al mediodía.",
        "La luna brilla por la noche.",
    ],
    "de": [
        "Die Katze sitzt auf der Matte.",
        "Ich laufe und springe gern.",
        "Schau dir den blauen Himmel an.",
        "Mein Hund fängt den kleinen Ball.",
        "Wir essen mittags rote Äpfel.",
        "Der Mond scheint hell in der Nacht.",
    ],
}

# When a language has no set yet, fall back to English so the flow never blocks.
_FALLBACK = "en"


def get_prompts(language: str | None = None, n: int | None = None) -> list[str]:
    """Return up to ``n`` karaoke sentences for ``language`` (English fallback)."""
    code = (language or _FALLBACK).strip().lower()[:2]
    sentences = PROMPT_SETS.get(code) or PROMPT_SETS[_FALLBACK]
    return sentences[:n] if n else list(sentences)


def available_languages() -> list[str]:
    return sorted(PROMPT_SETS)
