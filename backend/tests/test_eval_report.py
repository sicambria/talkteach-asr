"""Richer-evaluation tests (#52): per-utterance WER, error/confusion report,
raw-vs-normalized. jiwer-only, no torch."""

from __future__ import annotations

from talkteach.eval import error_report, normalized_vs_raw, per_utterance_wer
from talkteach.eval.report import worst_utterances


def test_per_utterance_wer_scores_each():
    refs = ["the cat sat", "hello world"]
    hyps = ["the cat sat", "goodbye world"]  # 2nd has one substitution of two words
    scores = per_utterance_wer(refs, hyps)
    assert len(scores) == 2
    assert scores[0].wer == 0.0  # perfect
    assert scores[1].wer == 0.5  # 1 of 2 words wrong
    assert scores[0].words == 3


def test_per_utterance_length_mismatch_raises():
    import pytest

    with pytest.raises(ValueError):
        per_utterance_wer(["a"], ["a", "b"])


def test_worst_utterances_ranks_by_wer():
    refs = ["perfect match", "all wrong here", "one slip up"]
    hyps = ["perfect match", "nothing right there", "one slip down"]
    worst = worst_utterances(refs, hyps, k=2)
    assert worst[0].reference == "all wrong here"  # highest WER first
    assert len(worst) == 2


def test_error_report_tallies_confusions():
    refs = ["the cat sat on the mat", "the cat ran"]
    hyps = ["the dog sat on a mat", "the cat ran"]
    rep = error_report(refs, hyps)
    subs = {(s["ref"], s["hyp"]): s["count"] for s in rep["top_substitutions"]}
    assert subs[("cat", "dog")] == 1
    assert subs[("the", "a")] == 1
    assert rep["counts"]["substitutions"] == 2
    assert rep["counts"]["insertions"] == 0
    assert rep["counts"]["deletions"] == 0


def test_error_report_insertions_and_deletions():
    rep = error_report(["hello world"], ["hello there world"])  # inserted "there"
    ins = {i["word"]: i["count"] for i in rep["top_insertions"]}
    assert ins["there"] == 1
    rep2 = error_report(["hello there world"], ["hello world"])  # deleted "there"
    dels = {d["word"]: d["count"] for d in rep2["top_deletions"]}
    assert dels["there"] == 1


def test_normalized_vs_raw_isolates_cosmetic_error():
    # Only casing differs → normalized WER is 0 (we lowercase), raw is not (jiwer
    # keeps case). Punctuation is NOT stripped by _normalise, so we test casing.
    refs = ["Hello World"]
    hyps = ["hello world"]
    out = normalized_vs_raw(refs, hyps)
    assert out["normalized_wer"] == 0.0
    assert out["raw_wer"] > 0.0
    assert out["cosmetic_gap"] == out["raw_wer"]
