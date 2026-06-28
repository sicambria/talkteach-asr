# Changelog

All notable changes to TalkTeach are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While we're pre-1.0, the `0.x` line may make breaking changes between minor
versions; we'll call them out under **Changed** with a ⚠️.

## [Unreleased]

The "Phase 0 → world-class" effort. Phase 0 proved the *integration risk* the
design report named (director + reliability + dependency plumbing) with a tested
vertical slice; this work turns the simulated edges into the real product, gated
behind honest tiers (see `DECISIONS.md` D-001 and `docs/ROADMAP_STATUS.md`).

### Added

- **Planning spine** so the breadth stays honest and traceable: `DECISIONS.md`
  (ADR-lite, top-5-scored choices), `docs/ROADMAP.md` (prioritized P0–P3 + X),
  `docs/ROADMAP_STATUS.md` (per-item tier + evidence matrix), `docs/PLAN.md`, and
  `docs/LEARNINGS.md`.
- **Lint / type / CI guardrails** (roadmap X #38–39): ruff (lint + format) and
  mypy for the backend, svelte-check for the UI, configured in
  `backend/pyproject.toml`; GitHub Actions CI and `make` targets (`test`, `lint`,
  `format`, `check`) so every later change is held to the same gates.
- **Real Whisper-LoRA training** (P0 #1–3): the actual `Seq2SeqTrainer` loop with
  pure, unit-tested helpers (`build_training_arguments`, the data collator,
  `compute_metrics` = WER/CER via jiwer) and safety rails (seed, grad-clip,
  NaN-guard → checkpoint rollback). End-to-end fine-tune behind
  `-m integration` (D-002).
- **Real export & transcription** (P0 #4–5): LoRA-merge → CTranslate2 int8 export
  with an ONNX/sherpa scaffold (D-006); faster-whisper "Try it" inference.
- **Audio pipeline** (P1 #10–13): ffmpeg decode/resample to 16 kHz mono (D-010),
  Silero VAD trimming, a forced-alignment adapter scaffold, and a live
  recording-quality meter.
- **Desktop reliability** (P1 #15,16,18): the Tauri shell spawns the Python
  backend as a sidecar (`tauri-plugin-shell`, killed on exit); a PyInstaller
  sidecar build script + bundled-runtime strategy; a real cross-platform
  microphone probe (PortAudio) replacing the Linux-only `/dev/snd` heuristic.
- **UX wired to the live API** (P1 #19–23): Screen 2 lists real clips and
  persists corrections; Screen 1 shows karaoke prompts (CC0) and a "practice set"
  self-test; Screen 3's Grown-up mode shows the director's rationale + hardware;
  new endpoints (`/api/clips`, `/api/clips/{id}/transcript`, `/api/prompts`,
  `/api/plan`, `/api/selftest`).
- **P2/P3 breadth** (#24,25,26,28,30,32,34,35,36): NeMo + wav2vec2 engine
  scaffolds (with graceful fallback), active-learning clip ranking, adaptive
  data-sufficiency targets, an auto-generated in-app credits screen, an i18n
  string-catalog scaffold, a denoise scaffold, a model-pack builder, and a signed
  release-matrix workflow scaffold.
- **Observability** (X #41): local-only JSON-lines logging and a redacted
  "help bundle" exporter (`/api/help-bundle`); no telemetry by default (D-008).
- OSS project hygiene (X #44): `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, this changelog, and GitHub issue/PR templates + Dependabot.
- Thirteen per-feature design docs under `docs/` (engines, calibration,
  alignment, releasing, cloud fallback, multi-project, denoise, diarization,
  model packs, i18n, accessibility, mascot, landscape currency).

### Fixed

- **P0 security hardening (do-before-release):** path-traversal on uploads —
  filenames are now a server-generated `clip_<uuid>.<ext>` with a codec
  allow-list, so the filename is no longer a trust boundary (#7, D-004); a locked
  Tauri Content-Security-Policy targeting only `'self'` + the local backend
  (#8, D-005); upload size + extension/codec validation (#9).

### Changed

- Training jobs reconcile against the database and their on-disk checkpoints on
  startup so a backend/sidecar restart no longer orphans a run (#40, D-007).

## [0.1.0] — 2026-06-28

**Phase 0 — tested vertical slice.** A working end-to-end skeleton that validates
the hard part (the director + reliability + dependency plumbing) for real, with
tests, before building the wizard polish on top. **54 passing tests, no GPU and
no ML framework required.**

### Added

- **Director (the IP):** probes hardware (CUDA → nvidia-smi → CPU fallback), data,
  and language, and maps `(hardware, data, language)` to a complete, zero-config
  `TrainingPlan` (engine, base checkpoint, precision, batch/grad-accum, epochs,
  LR, LoRA rank, freeze, safety rails) with a human-readable rationale; plus a
  **sufficiency gate** that blocks "Teach!" until there's enough *good* audio.
- **Audio layer:** pure-numpy clipping / RMS-quiet / silence-fraction / crude-SNR
  checks turned into plain-language issues, aggregated into a `DataProfile`.
- **Data layer:** one SQLite database per project (WAL + foreign keys, idempotent
  schema, clip/run lifecycle, minutes math, SQL-injection-guarded `update_run`,
  reopen persistence).
- **Reliability pre-flight:** disk / RAM / GPU / mic checks with graceful
  degradation — CPU-only and a missing mic are warnings, never hard blockers.
- **Engine adapter:** the `ASREngine` interface and `WhisperLoRAEngine`, whose
  training runs a faithful, dependency-free **simulation** (rising "smartness"
  curve, per-epoch checkpoints, cooperative cancellation) until the `[ml]` extra
  is installed.
- **FastAPI job server** (`backend/talkteach/app.py`): 10 endpoints — health,
  project, preflight, clips/analyze, sufficiency, transcribe/draft, train,
  train/{id}, transcribe, export — with stdlib-`wave` PCM decoding (no ffmpeg),
  threaded training jobs with live status, the gate enforced (HTTP 409), and
  graceful `available:false` responses when `[ml]` is absent.
- **Svelte UI scaffold:** the four-screen wizard (Record → Check → Teach → Try)
  plus a hidden Grown-up mode, a typed API client, and kid-friendly styling;
  builds to `ui/dist/` via `npm run build`.
- **Tauri v2 desktop shell scaffold:** idiomatic `lib.rs` + `main.rs`, valid
  `Cargo.toml` and `tauri.conf.json` with a complete icon set, and a root
  `package.json` orchestrator exposing `npm run tauri`. Build-ready; native
  compile needs system WebKit/GTK dev libraries.

[Unreleased]: https://github.com/inczegaspar/speechrecog-teach/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/inczegaspar/speechrecog-teach/releases/tag/v0.1.0
