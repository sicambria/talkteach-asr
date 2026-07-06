"""Punctuation + capitalization restoration (#51).

ASR often emits lowercase, punctuation-free text; readable output needs sentence
capitalization and terminal punctuation. This module ships a **rule-based**
``restore`` that is always available (no deps) and deterministic — a real perceived-
quality win for free. A heavier neural restorer (e.g. a ``deepmultilingualpunctuation``
model) is a documented future *guarded* path; the rule-based function is the floor
the product can always rely on, and the only part with unit tests.

Scope: light, language-agnostic-ish rules tuned for English speech. It does
NOT do inverse text normalization (spoken→written numbers); that is tracked
separately under #51's ITN note in project/docs/COMPETITIVE_GAPS.md.
"""

from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"([.!?])")
# Standalone lowercase "i" → "I" (English), but not inside a word.
_LONE_I = re.compile(r"\bi\b")


def _capitalize_first_alpha(text: str) -> str:
    """Upper-case the first alphabetic character, leaving leading punctuation."""
    for idx, ch in enumerate(text):
        if ch.isalpha():
            return text[:idx] + ch.upper() + text[idx + 1 :]
    return text


def restore(text: str, *, add_terminal: bool = True) -> str:
    """Restore basic capitalization + terminal punctuation (pure, rule-based).

    - collapses whitespace,
    - capitalizes the first letter of each sentence (split on ``. ! ?``),
    - upper-cases the standalone pronoun ``i`` → ``I``,
    - appends a period if ``add_terminal`` and the text lacks terminal punctuation.

    Returns ``""`` for empty/whitespace input.
    """
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""

    cleaned = _LONE_I.sub("I", cleaned)

    # Re-capitalize after every sentence terminator. Split keeps the delimiters.
    parts = _SENTENCE_SPLIT.split(cleaned)
    rebuilt: list[str] = []
    capitalize_next = True
    for part in parts:
        if part in (".", "!", "?"):
            rebuilt.append(part)
            capitalize_next = True
            continue
        if capitalize_next and part.strip():
            part = _capitalize_first_alpha(part)
            capitalize_next = False
        rebuilt.append(part)
    result = "".join(rebuilt).strip()

    if add_terminal and result and result[-1] not in ".!?":
        result += "."
    return result
