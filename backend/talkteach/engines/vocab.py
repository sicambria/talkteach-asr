"""Custom vocabulary / tokenizer extension for unseen languages (#55).

The CTC path (wav2vec2/XLS-R, #26) uses a *character* vocabulary. For a genuinely
unseen language, that vocab may lack characters the transcripts use, so the head
can never emit them. This module derives the missing symbols from a corpus and
merges them into an existing vocab **without disturbing the existing ids** (so a
partially-trained head keeps its learned rows). The merge is pure and unit-tested;
actually rebuilding a live 🤗 ``Wav2Vec2CTCTokenizer`` from the merged vocab is a
thin guarded step documented in project/docs/VOCAB.md.
"""

from __future__ import annotations

from collections.abc import Iterable

# Symbols a CTC vocab conventionally reserves; never treated as "characters".
DEFAULT_SPECIALS = ("<pad>", "<s>", "</s>", "<unk>", "|")


def characters_in(texts: Iterable[str], *, word_delimiter: str = "|") -> list[str]:
    """The sorted set of characters used across ``texts`` (spaces → ``word_delimiter``).

    Whitespace collapses to the CTC word-delimiter token (``|`` by convention); every
    other character is kept as-is. Deterministic (sorted) for reproducible vocabs.
    """
    chars: set[str] = set()
    for text in texts:
        for ch in text:
            if ch.isspace():
                chars.add(word_delimiter)
            else:
                chars.add(ch)
    return sorted(chars)


def merge_vocab(
    base_vocab: dict[str, int],
    extra_words: Iterable[str],
    *,
    word_delimiter: str = "|",
) -> tuple[dict[str, int], list[str]]:
    """Extend ``base_vocab`` (token→id) with characters missing for ``extra_words``.

    Existing tokens keep their ids; new characters are appended with fresh
    contiguous ids starting above the current maximum. Returns ``(merged_vocab,
    added_tokens)``. ``added_tokens`` is empty when the base already covers
    everything (idempotent).
    """
    merged = dict(base_vocab)
    next_id = (max(merged.values()) + 1) if merged else 0
    added: list[str] = []
    for ch in characters_in(extra_words, word_delimiter=word_delimiter):
        if ch not in merged:
            merged[ch] = next_id
            added.append(ch)
            next_id += 1
    return merged, added


def build_ctc_vocab(
    texts: Iterable[str],
    *,
    specials: Iterable[str] = DEFAULT_SPECIALS,
    word_delimiter: str = "|",
) -> dict[str, int]:
    """Build a fresh CTC ``token→id`` vocab from a corpus (specials first) (#55).

    Specials (pad/unk/delimiter/…) take the low ids; corpus characters follow. Use
    this to bootstrap a tokenizer for a brand-new language, or feed the result to
    :func:`merge_vocab` to grow an existing one.
    """
    vocab: dict[str, int] = {}
    for tok in specials:
        if tok not in vocab:
            vocab[tok] = len(vocab)
    merged, _ = merge_vocab(vocab, texts, word_delimiter=word_delimiter)
    return merged
