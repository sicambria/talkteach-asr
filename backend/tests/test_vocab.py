"""Custom-vocabulary tests (#55): character extraction + non-destructive merge +
CTC vocab bootstrap. Pure, no ML."""

from __future__ import annotations

from talkteach.engines.vocab import build_ctc_vocab, characters_in, merge_vocab


def test_characters_maps_spaces_to_delimiter():
    chars = characters_in(["ab c"])
    assert "|" in chars  # space → word delimiter
    assert set("abc").issubset(chars)
    assert " " not in chars


def test_merge_preserves_existing_ids():
    base = {"<pad>": 0, "a": 1, "b": 2}
    merged, added = merge_vocab(base, ["abz"])
    assert merged["<pad>"] == 0 and merged["a"] == 1 and merged["b"] == 2  # untouched
    assert "z" in added
    assert merged["z"] == 3  # new id above the max


def test_merge_is_idempotent_when_covered():
    base = {"a": 0, "b": 1, "|": 2}
    merged, added = merge_vocab(base, ["a b a"])
    assert added == []  # nothing new
    assert merged == base


def test_build_ctc_vocab_specials_first():
    vocab = build_ctc_vocab(["hi"], specials=("<pad>", "<unk>", "|"))
    assert vocab["<pad>"] == 0
    assert vocab["<unk>"] == 1
    assert vocab["|"] == 2
    # corpus characters get ids after the specials
    assert vocab["h"] > 2 and vocab["i"] > 2


def test_build_ctc_vocab_deterministic():
    a = build_ctc_vocab(["the cat"])
    b = build_ctc_vocab(["the cat"])
    assert a == b  # sorted → reproducible
