# Changelog

All notable changes to TalkTeach are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While we're pre-1.0, the `0.x` line may make breaking changes between minor
versions; we'll call them out under **Changed** with a ⚠️.

## [Unreleased]

### Changed

- ⚠️ **Repositioned from a "kids' app" to Easy/Advanced tiers.** The child /
  grown-up / family / 10-year-old persona is gone across the repo; the product now
  presents **Easy** (the wizard — great defaults, few options) and **Advanced** (the
  `⚙` toggle — full detail/config). One code identifier renamed
  (`grownUpMode → advancedMode`); no API/DB/i18n-key changes. The friendly Easy-mode
  tone (mascot, palette, "smartness" meter) is kept on purpose. See DECISIONS.md
  D-015, `plans/terminology-easy-advanced.md`.

### Added

- **Advanced-mode UI sweep (#57, #53, #48, #50, #52, #47)** — the parity features
  that shipped backend/CLI-only (D-014) now have a home in Advanced mode; Easy mode
  is unchanged. All verifiable end-to-end (ML deps present).
  - **Export-format picker (#57):** `GET /api/export/formats` (real vs scaffold);
    Screen4 Advanced picker. Easy keeps one-tap CTranslate2.
  - **Caption download (#48):** `/api/transcribe` returns segments + server-formatted
    SRT/VTT; Screen4 "Save captions" (Easy `.srt`) + Advanced format picker.
  - **Loss/WER curve (#53):** `GET /api/metrics/{run_id}` reads the real trainer's
    `metrics.jsonl` (honest "simulated run" when absent); Screen3 Advanced sparkline.
  - **Decode controls (#50):** `/api/transcribe` accepts beam / hotwords /
    temperature; Screen4 Advanced controls (blank → today's defaults).
  - **"Where it still struggles" report (#52):** `GET /api/eval/{run_id}` → hardest
    clips + confusions, labeled an active-learning signal (not accuracy; the held-out
    figure is `best_val_wer`); Screen3 Advanced.
  - **Dataset import (#47):** `POST /api/import` (`<input webkitdirectory>`,
    traversal-safe copy) + Screen0 "Import a folder"; folder-of-pairs / LibriSpeech /
    in-folder manifest via the tested auto-detector.
  - See DECISIONS.md D-015, `plans/advanced-mode-ui-sweep.md`.
- **UI parity sweep (#18, #13, #36, #37)** — front-end gaps closed with Svelte 4 +
  WebAudio only (no new runtime deps).
  - **Pre-flight screen (#18):** `ScreenPreflight.svelte` renders live
    `GET /api/preflight` (disk / memory / speed / microphone) with a clear
    "you're ready" vs "fix this first" state and a re-check button, wired as an
    interstitial between New-project and Record.
  - **Live recording meter (#13):** a client-side WebAudio RMS level bar on the
    record screen (AnalyserNode on the existing `getUserMedia` stream), with a
    coarse `aria-live` "we can hear you" status for screen-reader users.
  - **i18n plumbing (#36):** every static string on Screen0–4 + the pre-flight
    screen keyed through `$t()`, an extended `en` catalog, a topbar language
    switcher, and a programmatic `qa` pseudo-locale that proves the swap.
  - **Accessibility quick-wins (#37):** end-to-end tab order, Enter/Space
    activation (the drop zone is now a real keyboard button), no keyboard traps,
    focus moved to each screen's heading on change (`lib/a11y.js::focusOnMount`),
    and `aria-live` regions on the meter, training progress, and "Saved ✓".
    Verified axe-clean (no new violations vs baseline) + a headless keyboard walk;
    manual screen-reader certification, WCAG-AA contrast, high-contrast/dyslexia
    toggles, reduced-motion, and RTL remain tracked in `ACCESSIBILITY.md`.
- **Competitive-parity batch (#46–#57)** — additive, pure-Python, CPU/CI-tested
  (torch-free imports; heavy paths guarded). See `project/docs/ROADMAP_STATUS.md`
  and `DECISIONS.md` D-014.
  - **Subtitles (#48):** SRT / VTT / timestamped text via `transcript/subtitles.py`;
    Whisper now exposes real per-segment timestamps (`transcribe_segments`).
  - **Long-form transcription (#49):** overlapping-window chunking + stitch
    (`transcript/longform.py`).
  - **Decoding controls (#50):** beam size, hotword/prompt biasing, temperature
    fallback (`transcript/decode.py::DecodeOptions`) — opt-in, default preserves the
    stock decode.
  - **Punctuation restoration (#51):** rule-based capitalization + terminal
    punctuation (`transcript/punctuate.py`).
  - **Richer evaluation (#52):** per-utterance WER, an error/confusion report, and a
    raw-vs-normalized (cosmetic) gap (`eval/report.py`).
  - **Dataset import (#47):** folder-of-pairs, CSV/TSV, JSON array, NeMo JSONL,
    Common Voice, LibriSpeech → the canonical manifest (`data/import_manifest.py`).
  - **Data augmentation (#46):** SpecAugment + speed/pitch/noise (`audio/augment.py`),
    auto-enabled for tiny datasets by the director (`policy.augmentation_for`).
  - **Headless CLI (#54):** `talkteach import | eval | augment | metrics | subtitle |
    transcribe | train | export` (`talkteach/cli.py`, `[project.scripts]`).
  - **Local experiment metrics (#53):** on-device `metrics.jsonl` loss/WER curves,
    no telemetry (`obs/experiment.py`, D-008).
  - **Custom vocabulary (#55):** non-destructive CTC vocab merge/bootstrap
    (`engines/vocab.py`, `VOCAB.md`).
  - **Export targets (#57):** real HF **safetensors**; TorchScript/GGUF are honest
    dry-run scaffolds (Whisper `.generate` resists `torch.jit`).
  - **Multi-GPU (#56):** documented `torchrun`/`accelerate` escape hatch
    (`MULTIGPU.md`) — no fake in-app flag.

## [0.1.0] — 2026-06-28

The first public release. **Phase 0 built a tested vertical slice** that validates
the hard part (the director + reliability + dependency plumbing) for real, with
tests, before the wizard polish; the **Phase 0** build-out then
turned the simulated edges into real product behaviour, gated behind honest tiers
(see `project/docs/DECISIONS.md` D-001 and `project/docs/ROADMAP_STATUS.md`).
**110+ passing fast tests, no GPU and no ML framework required.**

### Added

- **Director:** probes hardware (CUDA → nvidia-smi → CPU fallback), data,
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
- **FastAPI job server** (`backend/talkteach/app.py`): health, project, preflight,
  clips/analyze, sufficiency, transcribe/draft, train, train/{id}, transcribe,
  export — plus `/api/clips`, `/api/clips/{id}/transcript`, `/api/prompts`,
  `/api/plan`, `/api/selftest`, and `/api/help-bundle`. Threaded training jobs
  with live status, the gate enforced (HTTP 409), and graceful `available:false`
  responses when `[ml]` is absent.
- **Planning spine** so the breadth stays honest and traceable: `project/docs/DECISIONS.md`
  (ADR-lite, top-5-scored choices), `project/docs/ROADMAP.md` (prioritized P0–P3 + X),
  `project/docs/ROADMAP_STATUS.md` (per-item tier + evidence matrix), `project/docs/PLAN.md`, and
  `project/docs/LEARNINGS.md`.
- **Lint / type / CI guardrails** (roadmap X #38–39): ruff (lint + format) and
  mypy for the backend, svelte-check for the UI, configured in
  `backend/pyproject.toml`; GitHub Actions CI and `make` targets (`test`, `lint`,
  `format`, `check`) so every later change is held to the same gates.
- **Real Whisper-LoRA training** (P0 #1–3): the actual `Seq2SeqTrainer` loop with
  pure, unit-tested helpers (`build_training_arguments`, the data collator,
  `compute_metrics` = WER/CER via jiwer) and safety rails (seed, grad-clip,
  NaN-guard → checkpoint rollback). End-to-end fine-tune behind
  `-m integration` (D-002). A dependency-free, `[SIMULATION]`-marked stand-in
  remains the fallback for GPU-less / no-`[ml]` environments.
- **Real export & transcription** (P0 #4–5): LoRA-merge → CTranslate2 int8 export
  with an ONNX/sherpa scaffold (D-006); faster-whisper "Try it" inference.
- **Audio pipeline** (P1 #10–13): ffmpeg decode/resample to 16 kHz mono (D-010),
  Silero VAD trimming, a forced-alignment adapter scaffold, and a live
  recording-quality meter.
- **Desktop reliability** (P1 #15,16,18): the Tauri shell spawns the Python
  backend as a sidecar (`tauri-plugin-shell`, killed on exit); a PyInstaller
  sidecar build script + bundled-runtime strategy; a real cross-platform
  microphone probe (PortAudio) replacing the Linux-only `/dev/snd` heuristic.
- **UX wired to the live API** (P1 #19–23): the four-screen wizard
  (Record → Check → Teach → Try) plus a hidden Advanced mode, a typed API client,
  and simple styling; Screen 2 lists real clips and persists corrections;
  Screen 1 shows karaoke prompts (CC0) and a "practice set" self-test; Screen 3's
  Advanced mode shows the director's rationale + hardware. Builds to `ui/dist/`
  via `npm run build`.
- **Full language picker** (#36): `GET /api/languages` serves the ~99 Whisper
  languages (single source of truth in `director/language.py`), and the New-Project
  screen pairs friendly quick-picks with a searchable box for all of them, plus
  "let it figure out" (auto-detect) and the XLS-R fallback for any non-Whisper
  language. Documented in `project/docs/LANGUAGES.md`.
- **Tauri v2 desktop shell:** idiomatic `lib.rs` + `main.rs`, valid `Cargo.toml`
  and `tauri.conf.json` with a complete icon set, and a root `package.json`
  orchestrator exposing `npm run tauri`.
- **P2/P3 breadth** (#24,25,26,28,30,32,34,35,36): NeMo + wav2vec2 engine
  scaffolds (with graceful fallback), active-learning clip ranking, adaptive
  data-sufficiency targets, an auto-generated in-app credits screen, an i18n
  string-catalog scaffold, a denoise scaffold, a model-pack builder, and a signed
  release-matrix workflow scaffold.
- **Observability** (X #41): local-only JSON-lines logging and a redacted
  "help bundle" exporter (`/api/help-bundle`); no telemetry by default (D-008).
- **OSS project hygiene** (X #44): `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, this changelog, GitHub issue/PR templates + Dependabot, and the
  research report under `reports/` that the design implements.
- **Per-feature design docs** under `project/docs/` (engines, calibration,
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

[Unreleased]: https://github.com/sicambria/talkteach-asr/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sicambria/talkteach-asr/releases/tag/v0.1.0
