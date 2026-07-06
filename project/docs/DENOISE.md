# Optional denoise for noisy uploads (#30)

Users record in real rooms — fans, siblings, a TV down the hall. A noisy clip gets
flagged "too noisy" by the quality checker (`audio/quality.py`, `SNR_MIN_DB`) and
doesn't count toward the sufficiency gate, which can stall a user who actually
spoke clearly. Optional denoise cleans the recording *before* quality analysis so
good speech buried under noise isn't thrown away.

## Where it sits in the pipeline

```
record/upload → decode+resample → [optional] denoise → quality check → store
```

It runs after decode (so the input is canonical 16 kHz mono WAV) and before the
quality verdict, so a cleaned clip is judged on its cleaned audio.

## Backends (`audio/denoise.py`)

| Backend | License | Notes |
|---|---|---|
| **DeepFilterNet** | MIT OR Apache-2.0 (model weights separate) | real-time-ish speech enhancement; the default |
| **Demucs** | MIT | heavier source-separation; fallback / future option |

`denoise_available()` probes `df` (DeepFilterNet) and `demucs`. When neither is
installed, `denoise_file()` is a **non-destructive passthrough** (it copies the
file unchanged and returns that path), so callers can always use the returned
path regardless of whether a backend is present.

## Two hard rules

1. **Opt-in.** Denoise is never on by default. The user enables it (a "this clip
   sounds noisy — clean it up?" prompt, or an Advanced-mode toggle). Default
   behaviour is unchanged: a noisy clip is flagged, not silently rewritten.
2. **Never destructive.** `denoise_file()` writes a *new* file
   (`<name>.denoised.wav`) and never modifies the original. The user's real
   recording is always preserved; training/analysis can use the cleaned copy while
   the original stays recoverable.

## Verify

```bash
cd backend && .venv/bin/python -c "from talkteach.audio.denoise import denoise_available; print(denoise_available())"
# With a backend (provisioned machine):
uv pip install deepfilternet     # then denoise_file() enhances instead of copying
```

## Status

**Tier C** (#30). The guarded `audio/denoise.py` step exists with the DeepFilterNet
path scaffolded and a safe passthrough fallback; pipeline wiring (the opt-in
prompt + inserting the step before quality analysis) and a real backend install
are pending. Licenses are tracked in `THIRD_PARTY.md`.
