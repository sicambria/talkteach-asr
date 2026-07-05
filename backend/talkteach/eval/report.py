"""Richer evaluation: per-utterance WER/CER, an error/confusion report, and a
raw-vs-normalized comparison (#52).

One aggregate WER hides *which* clips are bad and *what* the model gets wrong. These
pure jiwer helpers surface that: rank the worst utterances (active learning #32),
tally the most common word confusions (what to fix), and show how much of the WER is
just casing/punctuation (raw) versus real errors (normalized). No torch — jiwer only.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from talkteach.engines._train_common import _normalise, cer, wer


@dataclass(frozen=True)
class UtteranceScore:
    """Per-clip metrics. ``index`` is the position in the input lists."""

    index: int
    reference: str
    hypothesis: str
    wer: float
    cer: float
    words: int = field(default=0)


def per_utterance_wer(references: list[str], hypotheses: list[str]) -> list[UtteranceScore]:
    """Score each (ref, hyp) pair individually (pure).

    Uses the same light normalisation (lowercase + collapsed whitespace) as the
    training metrics, so scores are comparable to the smartness meter. Raises
    ``ValueError`` if the lists differ in length.
    """
    if len(references) != len(hypotheses):
        raise ValueError("references and hypotheses must be the same length")
    scores: list[UtteranceScore] = []
    for i, (ref, hyp) in enumerate(zip(references, hypotheses, strict=True)):
        scores.append(
            UtteranceScore(
                index=i,
                reference=ref,
                hypothesis=hyp,
                wer=wer([ref], [hyp]),
                cer=cer([ref], [hyp]),
                words=len(_normalise(ref).split()),
            )
        )
    return scores


def worst_utterances(
    references: list[str], hypotheses: list[str], *, k: int = 5
) -> list[UtteranceScore]:
    """The ``k`` highest-WER utterances (ties broken by more words). Feeds #32."""
    scores = per_utterance_wer(references, hypotheses)
    scores.sort(key=lambda s: (s.wer, s.words), reverse=True)
    return scores[:k]


def error_report(references: list[str], hypotheses: list[str]) -> dict:
    """Aggregate word-level substitutions / insertions / deletions (pure).

    Built on ``jiwer.process_words`` alignments. Returns the most common confusions
    plus raw counts and the corpus WER, so a grown-up can see *what* the model
    confuses (e.g. "cat"→"cot"), not just how often.
    """
    import jiwer

    refs = [_normalise(r) for r in references]
    hyps = [_normalise(h) for h in hypotheses]

    substitutions: Counter[tuple[str, str]] = Counter()
    insertions: Counter[str] = Counter()
    deletions: Counter[str] = Counter()

    for ref, hyp in zip(refs, hyps, strict=False):
        # jiwer needs a non-empty reference; skip degenerate pairs from the tallies.
        if not ref.split():
            continue
        out = jiwer.process_words([ref], [hyp])
        ref_words = out.references[0]
        hyp_words = out.hypotheses[0]
        for chunk in out.alignments[0]:
            if chunk.type == "substitute":
                r_span = ref_words[chunk.ref_start_idx : chunk.ref_end_idx]
                h_span = hyp_words[chunk.hyp_start_idx : chunk.hyp_end_idx]
                for r_word, h_word in zip(r_span, h_span, strict=False):
                    substitutions[(r_word, h_word)] += 1
            elif chunk.type == "delete":
                for r_word in ref_words[chunk.ref_start_idx : chunk.ref_end_idx]:
                    deletions[r_word] += 1
            elif chunk.type == "insert":
                for h_word in hyp_words[chunk.hyp_start_idx : chunk.hyp_end_idx]:
                    insertions[h_word] += 1

    return {
        "wer": wer(references, hypotheses),
        "cer": cer(references, hypotheses),
        "counts": {
            "substitutions": sum(substitutions.values()),
            "insertions": sum(insertions.values()),
            "deletions": sum(deletions.values()),
        },
        # Sorted, JSON-friendly (lists, not tuples) top confusions.
        "top_substitutions": [
            {"ref": r, "hyp": h, "count": c} for (r, h), c in substitutions.most_common(20)
        ],
        "top_insertions": [{"word": w, "count": c} for w, c in insertions.most_common(20)],
        "top_deletions": [{"word": w, "count": c} for w, c in deletions.most_common(20)],
    }


def normalized_vs_raw(references: list[str], hypotheses: list[str]) -> dict:
    """WER on raw text vs normalised text (pure).

    The gap tells you how much error is merely casing/punctuation/spacing (cosmetic,
    fixable with #51 restoration) versus genuine recognition error. ``raw`` compares
    the strings verbatim; ``normalized`` lowercases + collapses whitespace.
    """
    raw = _raw_wer(references, hypotheses)
    norm = wer(references, hypotheses)  # already normalised internally
    return {
        "raw_wer": raw,
        "normalized_wer": norm,
        "cosmetic_gap": max(0.0, raw - norm),
    }


def _raw_wer(references: list[str], hypotheses: list[str]) -> float:
    """WER with NO normalisation (verbatim), for the raw-vs-normalized delta."""
    import jiwer

    if not any(r.strip() for r in references):
        return 1.0
    return float(jiwer.wer(references, hypotheses))
