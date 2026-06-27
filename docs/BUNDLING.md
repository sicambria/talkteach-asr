# No-install bundled runtime (roadmap #16)

The promise: the installer is the only thing the family touches — no Python, no
pip, no CUDA setup. This note records the strategy; it is **Tier C** (the full
per-OS build runs in the release pipeline, not the sandbox).

## Two layers

1. **The backend sidecar** (always bundled) — a frozen single-file executable
   (`scripts/build_sidecar.py`, PyInstaller) carrying the *light* backend
   (director, audio DSP, data, reliability, FastAPI). Small, starts instantly,
   ships in every installer. This alone makes Record → Check → the gate work
   offline with zero install.

2. **The ML pack** (on-demand) — torch + transformers + faster-whisper + ffmpeg
   are large (GB-scale, CPU/CUDA variants). Bundling them into every installer
   would make it enormous, so they are fetched on first "Teach!" with explicit
   consent, into a `uv`-managed, relocatable environment beside the app:

   ```bash
   uv venv "$APPDATA/TalkTeach/ml"            # relocatable, no system Python needed
   uv pip install --python "$APPDATA/TalkTeach/ml" \
       'talkteach-backend[ml,export]'         # pinned wheels; CUDA variant picked per host
   ```

   `uv` resolves and caches pinned wheels reproducibly and is itself a single
   static binary we can bundle (Apache-2.0/MIT — see THIRD_PARTY.md).

## ffmpeg

An LGPL ffmpeg build is downloaded/bundled as a subprocess binary (THIRD_PARTY.md
explains the licensing) and put on the sidecar's PATH; `audio/decode.py` finds it
via `shutil.which`.

## Why not freeze everything into one binary?

PyInstaller-freezing torch + CUDA produces a multi-GB, fragile binary and breaks
GPU driver discovery. Splitting "tiny always-bundled core" from "consented ML
pack via uv" keeps the base installer small and the GPU story robust.

## Verify

```bash
python scripts/build_sidecar.py     # builds the core sidecar for the host triple
# then run it standalone:
./src-tauri/binaries/talkteach-backend-<triple>   # serves http://127.0.0.1:8756
```
</content>
