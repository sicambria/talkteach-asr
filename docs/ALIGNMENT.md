# Forced alignment — long take → sentence clips (#12)

When a child reads a paragraph in one breath, Screen 2 wants clean *per-sentence*
clips to review and correct. Forced alignment maps each spoken word to a
timestamp against the known transcript, so we can cut on sentence boundaries
instead of guessing from silence alone. This complements Silero VAD (#11): VAD
finds *where speech is*; alignment finds *where each word/sentence is*.

## Backends (pick one at install time)

| Backend | License | Notes |
|---|---|---|
| **WhisperX** | BSD-2-Clause | wav2vec2-based aligner; pairs naturally with our Whisper transcripts |
| **NeMo Forced Aligner** | Apache-2.0 | strong multilingual alignment; ties into the Phase-2 NeMo engine (#25) |

Both are optional, heavy deps. `audio/align.py::aligner_available()` probes
`whisperx`, `nemo_forced_aligner`, and `ctc_forced_aligner`; whichever is present
wins. There is no default download — alignment is purely additive.

## Wiring `align()` (`audio/align.py`)

`align(audio_path, transcript, language)` currently raises a friendly
`ImportError` (callers fall back to VAD-only segmentation). The build wires the
chosen backend behind that guard:

1. lazily import the available backend;
2. run it to get word-level timings;
3. normalise to `list[AlignedWord]` (`word`, `start_s`, `end_s`) — the one shape
   the rest of the code depends on.

Because the return type is normalised, swapping WhisperX for NeMo-FA changes only
the body of `align()`; nothing downstream moves.

## Cutting Screen-2 clips (`group_into_sentences`)

The boundary logic is **pure and unit-tested**, so it works with no aligner
installed: `group_into_sentences(words)` starts a new clip after any word whose
text ends in sentence punctuation (`.!?`), emitting `Segment(start_s, end_s)`
spans. Screen 2 slices the original WAV at those spans into reviewable
per-sentence clips. If no aligner is present, the flow degrades to VAD segments —
coarser, but never broken.

## Verify

```bash
cd backend && .venv/bin/python -m pytest tests/test_audio_pipeline.py -q   # pure grouping logic
# With a backend (provisioned machine):
uv pip install whisperx          # or a NeMo-FA build
```

## Status

**Tier C** (#12). The adapter boundary and the sentence-grouping logic are
written and tested; `align()` is a guarded scaffold pending one of the aligner
backends (which need `[ml]` + a model download). Verified licenses are tracked in
`docs/THIRD_PARTY.md`.
