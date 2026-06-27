# Audio pipeline (roadmap #10–13)

How raw recordings become clean, trainable, quality-checked clips. The pipeline
is designed so the *pure logic* runs everywhere and the *heavy backends* (ffmpeg,
Silero, a forced aligner) are optional and degrade gracefully.

```
record/upload → decode+resample (ffmpeg) → VAD trim/segment (Silero)
              → [optional] forced-align into sentences → quality check → store
```

## #10 / #20 — Decode + resample (`audio/decode.py`)

ffmpeg (LGPL build, invoked as a subprocess — see `THIRD_PARTY.md`) converts any
format (webm/opus from the browser, mp3, m4a, ogg, flac) to **16 kHz mono PCM
WAV**, the one canonical form the quality checker and trainer expect
(DECISIONS.md D-010). `build_decode_command` is pure and unit-tested;
`decode_to_wav`/`decode_to_samples` run it and raise `AudioDecodeError` (caught by
`/api/clips/analyze`, which then marks the clip "not checked yet") when ffmpeg is
absent. **Tier B** here: ffmpeg isn't installed in the sandbox, so bundling is via
`scripts/fetch_runtime.py` + `docs/BUNDLING.md`.

## #11 — Silero VAD (`audio/vad.py`)

Silero VAD (MIT, torch) finds speech regions; `merge_segments` (pure,
unit-tested) pads, merges spans across short gaps, drops too-short spans, and
splits over-long spans into ≤15 s clips. This trims dead air and auto-segments a
long take into reviewable clips. `detect_speech` is the guarded backend call.

## #12 — Forced alignment (`audio/align.py`) — Tier C scaffold

`group_into_sentences` (pure, unit-tested) turns word-level timings into
sentence-bounded clips for Screen 2. The aligner backends (WhisperX / NeMo Forced
Aligner) are wired behind a guarded `align()` that currently raises a friendly
ImportError → callers fall back to VAD-only segmentation. See
`docs/ALIGNMENT.md` for backend selection.

## #13 — Live recording-quality feedback (`audio/quality.py::live_meter`)

A cheap, pure per-chunk level read (RMS → 0–1 bar + quiet/good/loud status) the
recorder shows *while* recording, so the child gets "speak up" / "too loud" hints
live, not just a post-hoc verdict. The full post-hoc check stays in
`analyze_samples`.

## Verify

```bash
cd backend && .venv/bin/python -m pytest tests/test_audio_pipeline.py -q   # pure cores
# With backends:
uv pip install -e '.[ml,vad]'   # silero + torch
sudo apt install ffmpeg          # or bundle it (docs/BUNDLING.md)
.venv/bin/python -m pytest -m ffmpeg -q
```
</content>
