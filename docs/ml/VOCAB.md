# Custom vocabulary / tokenizer extension (#55)

For a genuinely *unseen* language on the CTC path (wav2vec2 / XLS-R, #26), the
character vocabulary that the CTC head decodes over may not contain the characters
the transcripts use. If a character isn't in the vocab, the head can never emit it —
so the model is capped below the data's real ceiling no matter how long it trains.

TalkTeach closes that gap with a small, **pure** vocabulary layer
(`backend/talkteach/engines/vocab.py`) plus a thin guarded step to rebuild the live
tokenizer.

## What's pure (and unit-tested)

- `characters_in(texts)` — the sorted character set used across a corpus, mapping
  whitespace to the CTC word-delimiter token (`|`).
- `build_ctc_vocab(texts, specials=…)` — bootstrap a fresh `token→id` vocab for a
  brand-new language: reserved specials (`<pad>`, `<unk>`, `|`, …) take the low ids,
  corpus characters follow, deterministically.
- `merge_vocab(base_vocab, extra_words)` — **non-destructively** extend an existing
  vocab: every existing token keeps its id (so a partially-trained head keeps its
  learned rows), and only the genuinely missing characters get fresh contiguous ids.
  Idempotent when the base already covers the corpus.

Tests: `backend/tests/test_vocab.py`.

## The guarded step (rebuild a live tokenizer)

Turning a merged vocab into a working `Wav2Vec2CTCTokenizer` needs `transformers`,
so it lives behind the usual `[ml]` guard. The recipe:

```python
import json, tempfile, os
from talkteach.engines.vocab import build_ctc_vocab

vocab = build_ctc_vocab(transcripts)            # {token: id}
d = tempfile.mkdtemp()
json.dump(vocab, open(os.path.join(d, "vocab.json"), "w"))

from transformers import Wav2Vec2CTCTokenizer    # guarded: needs [ml]
tok = Wav2Vec2CTCTokenizer(
    os.path.join(d, "vocab.json"),
    unk_token="<unk>", pad_token="<pad>", word_delimiter_token="|",
)
# ...then resize the model head to len(tok) before fine-tuning.
```

When you **extend** an already-trained head, use `merge_vocab` (not
`build_ctc_vocab`) so the existing ids — and the head rows trained for them — are
preserved, and only new rows are added for the appended characters.

## Scope / tier

Pure vocab logic is Tier A (real + tested here). The live-tokenizer rebuild and the
head resize are Tier B (guarded, exercised on a provisioned `[ml]` machine alongside
the wav2vec2-CTC engine). This is the standard TalkTeach split (DECISIONS.md D-002).
