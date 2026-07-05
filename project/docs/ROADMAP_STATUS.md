# ROADMAP traceability matrix

Authoritative status of every item in [`ROADMAP.md`](ROADMAP.md). This is the
spine of the Phase 0 effort: each item maps to a **tier**, the
**evidence** (file/test/doc), and the **commit** that delivered it.

Tiers (see [`DECISIONS.md`](DECISIONS.md) D-001):

- **A — done & verified here**: real code + tests that pass in this environment.
- **B — coded & guarded; integration deferred**: real code paths written and
  import-guarded; full run needs network/GPU/root, so it's behind a marker or a
  provisioned machine. "How to verify" is documented.
- **C — design + scaffolding**: design doc, code scaffold, and/or script; the
  full build needs hardware/certs/art outside this sandbox.

Status: ✅ delivered · 🟡 partial · ⬜ not started.

| # | Item | Tier | Status | Evidence |
|---|------|------|--------|----------|
| 1 | Real Whisper-LoRA training loop | B | ✅ | `engines/whisper_lora.py` (real loop), pure helpers in `engines/_whisper_train.py`, `tests/test_whisper_train.py`; e2e behind `-m integration` |
| 2 | Real held-out eval → WER smartness | B | ✅ | `compute_metrics` + `wer`/`cer` in `engines/_whisper_train.py`, `tests/test_whisper_train.py` |
| 3 | Safety rails wired into the loop | B | ✅ | seed/grad-clip/NaN-guard rollback in `_whisper_train.py` + callback; `tests/test_whisper_train.py::test_nan_guard` |
| 4 | Real export (CT2 + ONNX/sherpa) | B | 🟡 | `engines/whisper_lora.py::export` merges LoRA→CT2 int8; ONNX/sherpa scaffold + `EXPORT.md` |
| 5 | Real draft + "Try it" transcription | B | ✅ | `engines/whisper_lora.py::transcribe` (faster-whisper); CPU/int8 path documented |
| 6 | Calibrate the director | C | 🟡 | `CALIBRATION.md` (protocol + harness `scripts/calibrate.py`); constants stay proposed defaults. TTS×ASR benchmark added: `BENCHMARKING.md`, `scripts/benchmark.py`, `talkteach/tts/` (espeak+piper) |
| 7 | Path-traversal fix | A | ✅ | `app.py` `_safe_clip_name`, `tests/test_api.py::test_upload_path_traversal_is_contained` |
| 8 | Tighten CSP | A | ✅ | `src-tauri/tauri.conf.json` `security.csp`; `tests` n/a (config) |
| 9 | Upload validation | A | ✅ | `app.py` size + extension/codec allow-list, `tests/test_api.py` |
| 10 | Bundle ffmpeg + decode/resample | B | 🟡 | `audio/decode.py` (ffmpeg subprocess, guarded), `tests/test_audio_pipeline.py`; bundling via `scripts/build_sidecar.py` + `BUNDLING.md` |
| 11 | Silero VAD trim/segment | B | ✅ | `audio/vad.py` (guarded), pure segmentation logic tested in `tests/test_audio_pipeline.py` |
| 12 | Forced alignment | C | 🟡 | `audio/align.py` adapter scaffold + `ALIGNMENT.md` |
| 13 | Live recording-quality feedback | B | 🟡 | backend helper `audio/quality.py::live_meter` + `tests/test_audio_pipeline.py`; UI live-meter wiring (WebAudio, client-side) pending |
| 14 | Compile the Tauri shell | A | ✅ | **compiled + ran end-to-end** (2026-06-28): `npm run tauri dev` → window + sidecar spawn + live `/api/health` 200; recipe in README + `setup.sh`. Per-OS installers still a release-pipeline step (`RELEASING.md`) |
| 15 | Tauri sidecar auto-spawn backend | B | ✅ | `src-tauri/src/lib.rs` sidecar spawn + `tauri.conf.json` externalBin; `SIDECAR.md` |
| 16 | No-install bundled runtime | C | 🟡 | `scripts/build_sidecar.py` (PyInstaller sidecar) + `BUNDLING.md` (tiny core + uv ML pack) |
| 17 | Checkpoint/resume exercised e2e | A | ✅ | `find_latest_checkpoint` + resume in `tests/test_whisper_train.py`, `tests/test_durability.py`; sim writes per-epoch checkpoints (`tests/test_engines.py`) |
| 18 | Pre-flight wired to UI + mic probe | A/B | 🟡 | cross-platform PortAudio mic probe in `reliability/preflight.py` + `GET /api/preflight` (done, tested); a dedicated pre-flight *screen* in the UI is pending (the API is ready) |
| 19 | Wire UI to real data | A | ✅ | `Screen2_Check.svelte`, `Screen4_Try.svelte` use the API; `api.js` endpoints |
| 20 | Browser audio → trainable format | B | ✅ | `Screen1_Record.svelte` MediaRecorder→upload; server decode (#10) |
| 21 | Karaoke prompt sets per language | A | ✅ | `backend/talkteach/prompts/` (CC0 sentences) + `/api/prompts` + UI |
| 22 | First-run self-test toy dataset | A | ✅ | `scripts/make_toy_dataset.py` + `/api/selftest` + `SELFTEST.md` |
| 23 | Grown-up mode panels | A | ✅ | `Screen3_Teach.svelte` rationale panel reads `plan.rationale` |
| 24 | Signed installers + CI build matrix | C | 🟡 | `.github/workflows/release.yml` (matrix scaffold), `RELEASING.md` |
| 25 | NeMo / Parakeet RNN-T engine | C | 🟡 | `engines/nemo_rnnt.py` real but GPU-only (needs `[nemo]` + CUDA, self-skips otherwise) + `ENGINES.md` |
| 26 | wav2vec2 / XLS-R CTC engine | B | ✅ | `engines/wav2vec2_ctc.py` real CTC fine-tune (`_wav2vec2_train.py`), CPU/CI-runnable; benchmarked vs Whisper |
| 27 | Cloud fallback | C | ⬜ | `CLOUD_FALLBACK.md` design |
| 28 | In-app credits screen | A | ✅ | `scripts/gen_credits.py` from `THIRD_PARTY.md` → `ui/src/lib/credits.json` + screen |
| 29 | Multi-project support | B | 🟡 | data layer already multi-project; `MULTIPROJECT.md` design for app layer |
| 30 | Optional denoise | C | 🟡 | `audio/denoise.py` scaffold (guarded) + `DENOISE.md` |
| 31 | Mascot art + gamification | C | ⬜ | `MASCOT.md` design; needs an artist |
| 32 | Active learning | B | ✅ | `director/active_learning.py::rank_clips` (uncertainty ranking, pure) + `tests/test_p2p3.py` |
| 33 | Multi-speaker / diarization | C | ⬜ | `DIARIZATION.md` design |
| 34 | Shareable model packs / HF publish | C | 🟡 | `MODEL_PACKS.md` design + `scripts/pack_model.py` |
| 35 | Adaptive data-sufficiency targets | B | ✅ | `director/policy.py::adaptive_target` + `tests/test_p2p3.py` |
| 36 | Internationalize the UI | B | 🟡 | `ui/src/lib/i18n.js` + string catalog scaffold + `I18N.md` |
| 37 | Accessibility pass | B | 🟡 | a11y attributes added; `ACCESSIBILITY.md` checklist |
| 38 | CI (GitHub Actions) | A | ✅ | `.github/workflows/ci.yml` |
| 39 | Lint/format/type gates | A | ✅ | `pyproject.toml` ruff+mypy; `ui/eslint.config.js`, prettier, svelte-check; rustfmt/clippy in CI |
| 40 | Job durability | A | ✅ | `app.py` startup reconcile, `tests/test_durability.py` |
| 41 | Observability | A | ✅ | `obs/logging.py` structured logs, help-bundle exporter; `OBSERVABILITY.md` |
| 42 | Dependency hygiene | A | ✅ | npm audit notes, TestClient/httpx warning fix; `DEPENDENCIES.md` |
| 43 | Test coverage for real paths | A | ✅ | 100 fast tests + 3 `-m integration` (real train **and** CT2 export **and** faster-whisper transcribe, all verified) |
| 44 | OSS project hygiene | A | ✅ | CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG, templates |
| 45 | Landscape currency | A | ✅ | `LANDSCAPE.md` re-verification checklist + cadence |

### Parity items (from the competitive gap analysis — `COMPETITIVE_GAPS.md`)

The tractable additive slice (#46–#57) is now built — pure-Python, CPU/CI-tested,
following the pure-helper + guarded-ML split (D-002). ITN (part of #51), the neural
punctuation model, live multi-GPU (#56), and GGUF/TorchScript export stay scaffold/
doc (reasons in each row + the plan `plans/roadmap-parity-batch.md`).

| # | Item | Tier | Status | Evidence |
|---|------|------|--------|----------|
| 46 | Data augmentation (SpecAugment, perturbation, noise) | B | ✅ | `audio/augment.py` (pure numpy: spec_augment/perturb_speed/perturb_pitch/mix_noise), `director/policy.py::augmentation_for` auto-enable, `tests/test_augment.py`; collator wiring guarded |
| 47 | Dataset import (folder pairs, CSV/JSON, NeMo, Common Voice, LibriSpeech) | A | ✅ | `data/import_manifest.py` (+ auto-detect), `tests/test_dataset_import.py` |
| 48 | Subtitle / caption output (SRT/VTT/txt) | A | ✅ | `transcript/subtitles.py` + `engines/base.py::transcribe_segments` (real timestamps in Whisper override), `tests/test_transcript.py` |
| 49 | Long-form chunked transcription | B | ✅ | `transcript/longform.py` (pure plan_chunks/merge_segments + guarded transcribe_long), `tests/test_transcript.py` |
| 50 | Decoding controls (beam, hotword/prompt bias, temp fallback) | B | ✅ | `transcript/decode.py::DecodeOptions` threaded into `whisper_lora.transcribe`, `tests/test_transcript.py` |
| 51 | Punctuation/capitalization restoration | A | ✅ | `transcript/punctuate.py` (rule-based), `tests/test_transcript.py`; neural restorer + ITN documented as guarded future path |
| 52 | Richer evaluation (per-utterance WER, error/confusion report, raw-vs-norm) | A | ✅ | `eval/report.py` (jiwer alignments), `tests/test_eval_report.py`; feeds #32 |
| 53 | Local experiment metrics view (no telemetry) | A | ✅ | `obs/experiment.py` (metrics.jsonl writer/reader), wired into `_whisper_train` callback, `tests/test_experiment.py` (D-008) |
| 54 | Headless CLI (train/eval/export/import/subtitle/augment/metrics) | A | ✅ | `talkteach/cli.py` + `[project.scripts]`, `tests/test_cli.py`; pure subcommands verified e2e, model subcommands guarded |
| 55 | Custom vocabulary / tokenizer extension | B | ✅ | `engines/vocab.py` (pure merge/build), `tests/test_vocab.py`, `VOCAB.md`; live tokenizer rebuild guarded |
| 56 | Optional multi-GPU / distributed | C | 🟡 | `MULTIGPU.md` (torchrun/accelerate escape hatch); no fake flag — HF multi-GPU is launcher-driven; live run needs hardware |
| 57 | More export targets (safetensors real; GGUF/TorchScript scaffold) | B | 🟡 | `whisper_lora.py::export` safetensors branch + CLI `--format`; torchscript/gguf honest dry-run (Whisper `.generate` resists `torch.jit`), `EXPORT.md` |

## How to verify the Tier B/C items on a provisioned machine

- **Training/export/transcribe (1–5)**: `uv pip install -e '.[ml,export]'` then
  `TALKTEACH_RUN_INTEGRATION=1 pytest -m integration` (downloads `whisper-tiny`,
  runs a 1-epoch fine-tune on the toy dataset; needs ~2 GB disk, CPU is fine).
- **ffmpeg (10, 20)**: install ffmpeg, re-run `pytest -m ffmpeg`.
- **Tauri sidecar (15)/compile (14)**: see README "Quick start (desktop app)";
  needs Rust + WebKit/GTK dev libs.
- **Installers (24)**: `.github/workflows/release.yml` runs on tag on the GH
  matrix; signing needs secrets (documented in `RELEASING.md`).
- **Parity batch (46–57)**: the pure logic runs in the default `make test` (no
  deps). Model-touching paths (guarded transcribe in #49/#50, safetensors export in
  #57, the training-callback metrics in #53) verify on an `[ml,export]` machine via
  the CLI, e.g. `talkteach subtitle clip.wav --format srt` and
  `talkteach export --model runs/x --out out --format safetensors`.
