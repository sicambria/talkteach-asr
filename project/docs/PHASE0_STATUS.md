# Phase 0 status — what is real, what is simulated, what's next

This spike validates the **integration risk** the design report (Part C) named as
the real danger: not the wizard UI, but the *director + reliability + dependency*
plumbing. It does so by building those parts first, for real, with tests.

## What is REAL and tested (110+ passing fast tests, no GPU/ML deps)

| Area | Real behavior | Tests |
|---|---|---|
| **Director / policy** | Probes hardware (CUDA via torch→nvidia-smi→CPU fallback), maps (hardware, data, language) → a complete `TrainingPlan` (engine, base checkpoint, precision, batch/grad-accum, epochs, LR, LoRA rank, freeze, safety rails) with a human-readable rationale. | `test_director.py` (15) |
| **Sufficiency gate** | Blocks "Teach!" until ≥ target minutes of *good* audio; floors target at 20 min; warns on poor good-fraction. | in `test_director.py` |
| **Audio quality** | Pure-numpy clipping / RMS-quiet / silence-fraction / crude-SNR checks → plain-language issues; aggregates clips → `DataProfile`. | `test_audio.py` (11) |
| **Data layer** | One SQLite DB per project, WAL + foreign keys, idempotent schema, clip/run lifecycle, minutes math, SQL-injection-guarded `update_run`, reopen persistence. | `test_data.py` (7) |
| **Reliability pre-flight** | Disk/RAM/GPU/mic checks with graceful degradation (CPU-only and missing mic are warnings, never hard blockers). | `test_preflight.py` (8) |
| **Engine adapter** | `ASREngine` interface; `WhisperLoRAEngine.is_available()` names missing deps; **simulation** train streams a rising smartness curve, writes per-epoch checkpoints, and honors cooperative cancellation. | `test_engines.py` (8) |
| **HTTP job server** | All 10 endpoints; PCM-WAV decoding via stdlib `wave` (no ffmpeg); threaded training jobs with live status; gate enforced (HTTP 409); graceful 200 + `available:false` for transcription without `[ml]`. | `test_api.py` (8) |

Verified live: `python -m talkteach.app` boots under uvicorn and serves
`/api/health`, `/api/preflight`, `/api/sufficiency`.

> **Update (Phase 0):** several items below have since been built.
> The authoritative, per-item status is now [`ROADMAP_STATUS.md`](ROADMAP_STATUS.md).
> This section is kept for the original Phase-0 framing.

## What is SIMULATED or scaffolded

- **Real LoRA/PEFT training — now implemented.** ✅ The real `Seq2SeqTrainer`
  loop (data collator, `Seq2SeqTrainingArguments` derived from the `TrainingPlan`,
  `compute_metrics`=WER, `resume_from_checkpoint`, NaN-guard) lives in
  `engines/_whisper_train.py` and runs when `[ml]` is installed and real clips
  exist on disk (DECISIONS.md D-012); verified end-to-end on `whisper-tiny` by the
  opt-in `integration` test. The dependency-free, `[SIMULATION]`-marked stand-in
  remains the fallback for GPU-less / no-`[ml]` environments and the fast suite.
- **Real transcription/export** activate only when `faster-whisper` / `ctranslate2`
  are present; otherwise they degrade gracefully.
- **Svelte UI builds today** — `npm install && npm run build` produces `ui/dist/`
  (46 modules, verified). Four screens, typed API client, kid-friendly styling.
- **Desktop shell (Tauri v2) — compiled and verified end-to-end (2026-06-28).**
  The scaffold is structurally correct and idiomatic (lib.rs `run()` + main.rs,
  valid `Cargo.toml`, valid `tauri.conf.json` with a complete icon set incl.
  generated `.ico`/`.icns`, and a root `package.json` orchestrator exposing
  `npm run tauri`). On a Linux/Wayland host with WebKit/GTK present, `npm run
  tauri dev` compiled the shell, launched the window, `setup()` spawned the
  Python backend as a sidecar, and the UI reached it over the live API
  (`GET /api/health` → `200`, version `0.1.0`). Producing per-OS installers still
  needs WebKit/GTK present and a per-target PyInstaller freeze (see RELEASING.md).
- **No ffmpeg** here, so browser `webm` clips are accepted-but-unchecked; PCM WAV
  is fully analyzed. Phase 1 bundles ffmpeg (LGPL build) to handle all formats.
- **Forced alignment / VAD trimming** (Silero, NeMo Forced Aligner) are Phase 1.

## Path forward (from report B.8)

- **Phase 1 (MVP):** real Whisper-LoRA training loop; Silero VAD trim; bundle
  ffmpeg; compile the Tauri shell and spawn the backend as a sidecar; ONNX export
  via sherpa-onnx; ship on Windows + one of macOS/Linux.
- **Phase 2 (robust/cross-platform):** signed installers for all 3 OSes;
  no-install runtime via `uv`; NeMo/Parakeet streaming engine; cloud fallback;
  in-app third-party-credits screen; self-test toy dataset.
- **Phase 3 (delight):** mascot/gamification, active learning, shareable model
  packs, "publish to Hugging Face."

## Calibration debt (tracked from report B.5)

Every threshold/hyperparameter in `director/policy.py` and `audio/quality.py` is a
**proposed default** drawn from the literature, not yet empirically tuned. They
are marked as such in code and must be calibrated against real hardware/datasets
during Phase 0–1, then refined from telemetry.
