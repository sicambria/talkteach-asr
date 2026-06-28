# TalkTeach roadmap

Phase 0 (this commit) is a tested vertical slice. This document is the full,
prioritized list of what stands between here and a finished product:
an easy-to-use, offline, cross-platform GUI that trains state-of-the-art
ASR models. Tiers map to the design report's phases (B.8). "✱" = grounded in an
explicit code marker (`grep -rn TODO|SIMULATION`).

Legend: **P0** = makes training *real* (the core promise) · **P1** = MVP ·
**P2** = robust & cross-platform · **P3** = delight & scale · **X** = cross-cutting quality.

---

## P0 — Make it actually train (replace the simulation)

The single most important gap: training is a faithful *simulation* today, even
with `[ml]` installed.

1. ✱ **Real Whisper-LoRA training loop** (`engines/whisper_lora.py` `TODO(phase-1)`):
   PEFT/LoRA + `Seq2SeqTrainer`, data collator, `Seq2SeqTrainingArguments` derived
   from the `TrainingPlan`, `resume_from_checkpoint`, fp16/bf16/int8 per plan.
2. **Real held-out eval → genuine smartness meter** (`compute_metrics` = WER/CER);
   replace the synthetic smartness curve with measured `1 − WER`.
3. **Wire the safety rails into the real loop**: fixed seed, gradient clipping,
   NaN/inf detection → auto-rollback to last good checkpoint (currently only named
   in `plan.rationale`, not enforced).
4. ✱ **Real export** for "Use on my computer": ONNX via **sherpa-onnx** + CTranslate2
   conversion + a tiny runnable inference app (`engines/whisper_lora.py` export is a
   dry-run placeholder).
5. **Real draft + "Try it" transcription** end-to-end via faster-whisper (wired but
   only active when `[ml]` present — verify on GPU + CPU/int8).
6. **Calibrate the director** (`director/policy.py`, `audio/quality.py`): every
   threshold/hyperparameter is a *proposed default*. Tune VRAM tiers, LR/epochs/
   patience, LoRA rank, and the quality thresholds against real hardware + datasets;
   then refine from telemetry. (Report B.5 calibration debt.)

## P0 — Security & data integrity (do before any release)

7. **Path-traversal fix**: `app.py` writes uploads to `clip_dir / audio.filename`
   directly — a malicious `filename` ("../../…") escapes the project dir. Sanitize
   to a basename / generated name.
8. **Tighten CSP**: `tauri.conf.json` `security.csp` is `null` (permissive). Lock it
   to the backend origin before shipping.
9. **Upload validation**: size limits, content-type/codec allow-list, reject
   oversized or malformed audio early.

---

## P1 — MVP (real product, one or two OSes)

### Audio pipeline (closes the "data-sufficiency/quality" gap)
10. **Bundle ffmpeg (LGPL build)** → decode webm/ogg/mp3 and resample to 16 kHz.
    Today non-WAV clips are ✱ "accepted but not checked" (`app.py`).
11. **Silero VAD**: auto-trim silence and auto-segment while recording.
12. **Forced alignment** (NeMo Forced Aligner / WhisperX): split long recordings
    into sentence clips for Screen 2.
13. **Live recording-quality feedback** (meter *while* recording), not just post-hoc;
    confidence-colored words in the correction screen.

### Desktop reliability ("just works")
14. **Compile the Tauri shell** on a provisioned machine (system WebKit/GTK dev libs;
    see `setup.sh`).
15. ✱ **Tauri sidecar**: auto-spawn the Python backend (`src-tauri/src/lib.rs`
    `TODO(phase-1)`) so the user never starts a server.
16. **No-install bundled runtime**: Python + pinned wheels + CPU/CUDA libs + ffmpeg
    via `uv`; the installer is the only thing the user touches (Report B.7).
17. **Checkpoint/resume exercised end-to-end** across crash/close/power-loss
    (SQLite WAL + autosave + per-epoch checkpoint resume — plumbing exists, prove it).
18. **Pre-flight screen wired to the UI**; cross-platform mic detection (replace the
    Linux `/dev/snd` heuristic with a real probe per OS).

### UX (easy-to-use)
19. ✱ **Wire UI to real data**: Screen 2 clip list + persist corrections; Screen 4
    persist results (`Screen2_Check.svelte`, `Screen4_Try.svelte` `TODO(backend)`).
20. **Browser audio → trainable format**: MediaRecorder emits webm; convert to WAV
    (ties to #10 ffmpeg) so recordings are analyzable + trainable.
21. **Karaoke prompt sets per language** (Common Voice CC0 sentences).
22. **First-run self-test**: ship a 2-minute toy dataset so "Teach!" is verifiable on
    first launch (Report B.7).
23. **Grown-up mode** panels surfacing the director's rationale + real metrics.

---

## P2 — Robust & cross-platform

24. **Signed installers for Windows + macOS + Linux**; CI build matrix.
25. ✱ **NeMo / Parakeet RNN-T engine** (`EngineKind.NEMO_RNNT`, currently
    `NotImplementedError`) for streaming/edge export.
26. **wav2vec2 / XLS-R CTC engine** for unsupported/low-resource languages (the
    director already *selects* it; the adapter is unbuilt).
27. **Cloud fallback**: one-tap remote/Colab training for GPU-less machines.
28. **In-app third-party credits screen** auto-generated from `THIRD_PARTY.md`
    (Report B.6 attribution requirement).
29. **Multi-project support** in the app layer (the data layer already supports it;
    `app.py` is single-project for Phase 0).
30. **Optional denoise** (DeepFilterNet / Demucs) for noisy uploads.

---

## P3 — Delight & scale

31. **Mascot art + sound + reactions**; gamification (replace the emoji placeholder).
32. **Active learning**: "the model is unsure about these 5 clips — fix these next."
33. **Multi-speaker / diarization** (today `distinct_speakers` is hardcoded to 1).
34. **Shareable model packs**; **"Publish to Hugging Face"** button.
35. **Adaptive data-sufficiency targets** by language difficulty (replace the fixed
    20–30 min floor with a learned/heuristic target).
36. **Internationalize the UI itself** (plain-language strings are English-only) so a
    non-English-speaking child can use it.
37. **Full accessibility pass**: keyboard nav, screen-reader labels, high-contrast +
    dyslexia-friendly font options.

---

## X — Cross-cutting engineering quality (continuous)

38. **CI** (GitHub Actions): pytest + UI build + `cargo check`/clippy on every PR.
39. **Lint/format/type gates**: ruff + mypy (Python), eslint/prettier + svelte-check
    (UI), rustfmt + clippy (Rust).
40. **Job durability**: training jobs are in-memory (`_jobs`); persist + reattach so a
    server/sidecar restart doesn't orphan a run.
41. **Observability**: structured logging, opt-in (off-by-default) telemetry, and an
    "Export a help bundle" button (Report B.7).
42. **Dependency hygiene**: resolve the `npm audit` findings, refresh pins, drop the
    deprecated Starlette `TestClient`/httpx warning.
43. **Test coverage for the real paths** once built (training loop, export, ffmpeg,
    `[ml]` integration tests behind a marker).
44. **OSS project hygiene**: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR
    templates, `CHANGELOG.md`, semver, a user-facing docs site.
45. **Landscape currency**: periodically re-verify the report's "no end-to-end OSS GUI"
    headline (Report Part C) — it is the claim most exposed to going stale.

---

## Parity — capabilities the best pro toolsets ship (from the gap analysis)

Derived by comparing TalkTeach against **Hugging Face Transformers, NVIDIA NeMo,
and SpeechBrain** (full analysis + rationale in
[`COMPETITIVE_GAPS.md`](COMPETITIVE_GAPS.md)). These are additive and need no new
ML research; formats/use-case coverage is mapped in [`FORMATS.md`](FORMATS.md).

46. **Data augmentation** — SpecAugment + speed/pitch perturbation + noise/RIR
    mixing; the director auto-enables it for tiny datasets (biggest small-data win).
47. **Dataset import** — a folder of (audio, transcript) pairs, plus manifest
    CSV/JSON, NeMo manifest, Common Voice TSV, LibriSpeech, and HF `datasets`.
48. **Subtitle / caption output** — SRT/VTT + timestamped plain-text transcript.
49. **Long-form transcription** — chunked, VAD-windowed, timestamped decoding for
    files longer than one short clip.
50. **Decoding controls** — beam size, `initial_prompt`/hotword biasing,
    temperature fallback (cheap accuracy + child-vocabulary biasing).
51. **Punctuation + capitalization restoration / inverse text normalization.**
52. **Richer evaluation** — per-utterance WER, an error/confusion report,
    confidence, normalized-vs-raw WER (also powers active learning #32).
53. **Local experiment metrics view** — on-device loss/WER curves (no telemetry;
    honours D-008) for Grown-up mode.
54. **Headless CLI** — train/eval/export from the terminal for power users + CI.
55. **Custom vocabulary / tokenizer extension** for genuinely unseen languages.
56. **Optional multi-GPU / distributed** training (documented escape hatch).
57. **More export targets** — HF `safetensors`, GGUF (whisper.cpp), TorchScript.

---

### The honest one-liner

Phase 0 proved the **integration + director + reliability plumbing** (the report's
named real risk). The road ahead is mostly **P0 (make training real +
secure)** and **P1 (audio pipeline + bundled, sidecar-driven desktop app)**; P2–P3
are breadth and delight. Nothing here is new ML research — it is disciplined
engineering, UX, and packaging.
