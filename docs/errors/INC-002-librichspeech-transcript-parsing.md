# INC-002 — LibriSpeech Transcript Parsing (`.trans.txt` Naming)

**Date:** 2026-07-08  
**Type:** incident  
**Area:** SOTA data loading  
**Status:** resolved  
**Trigger:** D01 baseline returned 0 clips and WER=-1.0 despite LibriSpeech test-clean being cached on disk

## Summary

`get_transcript()` in `backend/talkteach/sota/datasets.py` looked for `{chapter_id}.trans.txt` but LibriSpeech `.trans.txt` files are named `{speaker_id}-{chapter_id}.trans.txt` (e.g. `121-123852.trans.txt` not `123852.trans.txt`). This caused 0 transcripts to be loaded, silently returning `None` for all 2620 clips.

## Root Cause

Assumed `.trans.txt` filename convention matched the parent directory name (chapter ID). LibriSpeech actually uses `{speaker_id}-{chapter_id}.trans.txt` where speaker_id is the grandparent directory's name. The code `audio_path.parent.name` returns the chapter ID, producing the wrong filename.

## Prevention

Changed to glob for `*.trans.txt` files in the parent directory instead of guessing the filename. This handles any LibriSpeech `.trans.txt` naming convention and is robust to future format changes.

## Guardrail Updates

- Existing guard: `measure_base_wer` should return WER=-1.0 with `num_clips=0` when no clips load — this correctly signaled the problem
- New implicit guard: validation scripts should fail loudly when `num_clips=0` (currently returns WER=-1.0 with band "unmeasured")
- Add `assert clips > 0` after `load_clip_transcript_pairs()` in all measurement functions

## Automation Follow-Up

- [ ] Add unit test: `test_get_transcript_parses_librichspeech_format()` — verify transcripts load from actual LibriSpeech tree structure
- [ ] Add `num_clips > 0` assertion in `measure_base_wer()`, `measure_rtf()`, `measure_noise_robustness()`, `measure_speaker_equity()`
- [ ] Add CI smoke: verify `load_clip_transcript_pairs()` loads ≥100 clips from a synthetic test tree

## Related Links

- `backend/talkteach/sota/datasets.py:213-222` — fixed `get_transcript()`
- `docs/testing/journey-s1-real-audio-baseline.md` — complete report
