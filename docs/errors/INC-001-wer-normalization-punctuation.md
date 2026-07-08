# INC-001 — WER Normalization Defect (Punctuation Inflating WER)

**Date:** 2026-07-08  
**Type:** incident  
**Area:** SOTA scoring pipeline  
**Status:** resolved  
**Trigger:** First real-audio measurement on LibriSpeech returned WER 16.8% for whisper-tiny, 2× published value (~8.3%)

## Summary

`wer()` in `backend/talkteach/sota/scoring.py` used `jiwer.process_words()` which does NOT strip punctuation by default. Whisper outputs punctuation (commas, periods); LibriSpeech references have none. This inflated WER by ~75% (18.9% → 4.6% on same 30 clips, a 3× inflation).

All prior WER measurements in this repo were invalid — including the synthetic TTS benchmark in `benchmarks/REPORT.md` which reported whisper-tiny WER 0.131 (13.1%) vs the corrected value of ~5%.

## Root Cause

`jiwer.process_words()` treats punctuation characters as part of word tokens. The word "world." does not match "world". Standard ASR evaluation convention (used by Whisper, LibriSpeech, ESPnet, etc.) normalizes text by lowercasing and stripping punctuation before computing WER.

The code's own lowercasing in `measure_base_wer()` was insufficient — lowercasing alone doesn't remove punctuation.

## Prevention

Added `_normalize_text()` helper in `scoring.py` that applies standard ASR normalization:
1. Lowercase
2. Remove punctuation (via regex `[^\w\s']` — preserves apostrophes in contractions)
3. Collapse multiple spaces
4. Strip leading/trailing whitespace

Applied in both `wer()` and `cer()`. All callers benefit automatically.

## Guardrail Updates

- Added pre-commit guard: `wer()` must apply normalization — implicit in function body; future code review should verify
- New implicit guard: any new WER/CER measurement must reproduce a known published number (e.g. whisper-tiny on LS test-clean) within published CI before results are trusted
- Rule codified in journey skill contract §4 (fidelity gate): reproduce committed baseline number before trusting any delta

## Automation Follow-Up

- [ ] Add unit test: `test_wer_normalizes_punctuation()` — assert that "hello world." vs "hello world" gives WER=0
- [ ] Audit all existing WER measurements (REPORT.md, synthetic benchmarks) and re-measure with fixed `wer()`
- [ ] Add `librispeech_test_clean` smoke test to CI that verifies whisper-tiny WER within [0.04, 0.12] (covering published ~8.3% with tolerance for sample variance)

## Related Links

- `backend/talkteach/sota/scoring.py:14-47` — fixed `wer()` and `cer()` functions
- `docs/testing/journey-s1-real-audio-baseline.md` — complete report
- Journey skill contract §4 (fidelity gate)
- https://github.com/jitsi/jiwer — jiwer documentation (default `process_words` behavior)
