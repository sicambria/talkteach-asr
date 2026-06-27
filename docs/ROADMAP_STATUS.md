# ROADMAP traceability matrix

Authoritative status of every item in [`ROADMAP.md`](ROADMAP.md). This is the
spine of the "Phase 0 → world-class" effort: each item maps to a **tier**, the
**evidence** (file/test/doc), and the **commit** that delivered it.

Tiers (see [`DECISIONS.md`](../DECISIONS.md) D-001):

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
| 4 | Real export (CT2 + ONNX/sherpa) | B | 🟡 | `engines/whisper_lora.py::export` merges LoRA→CT2 int8; ONNX/sherpa scaffold + `docs/EXPORT.md` |
| 5 | Real draft + "Try it" transcription | B | ✅ | `engines/whisper_lora.py::transcribe` (faster-whisper); CPU/int8 path documented |
| 6 | Calibrate the director | C | 🟡 | `docs/CALIBRATION.md` (protocol + harness `scripts/calibrate.py`); constants stay proposed defaults |
| 7 | Path-traversal fix | A | ✅ | `app.py` `_safe_clip_name`, `tests/test_api.py::test_upload_path_traversal_is_contained` |
| 8 | Tighten CSP | A | ✅ | `src-tauri/tauri.conf.json` `security.csp`; `tests` n/a (config) |
| 9 | Upload validation | A | ✅ | `app.py` size + extension/codec allow-list, `tests/test_api.py` |
| 10 | Bundle ffmpeg + decode/resample | B | 🟡 | `audio/decode.py` (ffmpeg subprocess, guarded), `tests/test_decode.py`; bundling via `scripts/fetch_runtime.py` + `docs/BUNDLING.md` |
| 11 | Silero VAD trim/segment | B | ✅ | `audio/vad.py` (guarded), pure segmentation logic tested in `tests/test_vad.py` |
| 12 | Forced alignment | C | 🟡 | `audio/align.py` adapter scaffold + `docs/ALIGNMENT.md` |
| 13 | Live recording-quality feedback | A | ✅ | `audio/quality.py::live_meter`, UI live meter in `Screen1_Record.svelte` |
| 14 | Compile the Tauri shell | C | ⬜ | needs root/WebKit libs; recipe in README + `setup.sh`; documented Tier C |
| 15 | Tauri sidecar auto-spawn backend | B | ✅ | `src-tauri/src/lib.rs` sidecar spawn + `tauri.conf.json` externalBin; `docs/SIDECAR.md` |
| 16 | No-install bundled runtime | C | 🟡 | `scripts/fetch_runtime.py` + `docs/BUNDLING.md` (uv-based) |
| 17 | Checkpoint/resume exercised e2e | A | ✅ | `tests/test_engines.py` resume tests + `tests/test_durability.py` |
| 18 | Pre-flight wired to UI + mic probe | A | ✅ | cross-platform mic in `reliability/preflight.py`, `Screen0`/preflight call; `tests/test_preflight.py` |
| 19 | Wire UI to real data | A | ✅ | `Screen2_Check.svelte`, `Screen4_Try.svelte` use the API; `api.js` endpoints |
| 20 | Browser audio → trainable format | B | ✅ | `Screen1_Record.svelte` MediaRecorder→upload; server decode (#10) |
| 21 | Karaoke prompt sets per language | A | ✅ | `backend/talkteach/prompts/` (CC0 sentences) + `/api/prompts` + UI |
| 22 | First-run self-test toy dataset | A | ✅ | `scripts/make_toy_dataset.py` + `/api/selftest` + `docs/SELFTEST.md` |
| 23 | Grown-up mode panels | A | ✅ | `Screen3_Teach.svelte` rationale panel reads `plan.rationale` |
| 24 | Signed installers + CI build matrix | C | 🟡 | `.github/workflows/release.yml` (matrix scaffold), `docs/RELEASING.md` |
| 25 | NeMo / Parakeet RNN-T engine | C | 🟡 | `engines/nemo_rnnt.py` scaffold (guarded) + `docs/ENGINES.md` |
| 26 | wav2vec2 / XLS-R CTC engine | C | 🟡 | `engines/wav2vec2_ctc.py` scaffold (guarded) + `docs/ENGINES.md` |
| 27 | Cloud fallback | C | ⬜ | `docs/CLOUD_FALLBACK.md` design |
| 28 | In-app credits screen | A | ✅ | `scripts/gen_credits.py` from `THIRD_PARTY.md` → `ui/src/lib/credits.json` + screen |
| 29 | Multi-project support | B | 🟡 | data layer already multi-project; `docs/MULTIPROJECT.md` design for app layer |
| 30 | Optional denoise | C | 🟡 | `audio/denoise.py` scaffold (guarded) + `docs/DENOISE.md` |
| 31 | Mascot art + gamification | C | ⬜ | `docs/MASCOT.md` design; needs an artist |
| 32 | Active learning | C | 🟡 | `director/active_learning.py` (uncertainty ranking, pure) + `docs/ACTIVE_LEARNING.md` |
| 33 | Multi-speaker / diarization | C | ⬜ | `docs/DIARIZATION.md` design |
| 34 | Shareable model packs / HF publish | C | 🟡 | `docs/MODEL_PACKS.md` design + `scripts/pack_model.py` |
| 35 | Adaptive data-sufficiency targets | B | ✅ | `director/policy.py::adaptive_target` + `tests/test_director.py` |
| 36 | Internationalize the UI | B | 🟡 | `ui/src/lib/i18n.js` + string catalog scaffold + `docs/I18N.md` |
| 37 | Accessibility pass | B | 🟡 | a11y attributes added; `docs/ACCESSIBILITY.md` checklist |
| 38 | CI (GitHub Actions) | A | ✅ | `.github/workflows/ci.yml` |
| 39 | Lint/format/type gates | A | ✅ | `pyproject.toml` ruff+mypy; `ui/.eslintrc`, prettier, svelte-check; rustfmt/clippy in CI |
| 40 | Job durability | A | ✅ | `app.py` startup reconcile, `tests/test_durability.py` |
| 41 | Observability | A | ✅ | `obs/logging.py` structured logs, help-bundle exporter; `docs/OBSERVABILITY.md` |
| 42 | Dependency hygiene | A | ✅ | npm audit notes, TestClient/httpx warning fix; `docs/DEPENDENCIES.md` |
| 43 | Test coverage for real paths | A | ✅ | new test modules; markers for integration |
| 44 | OSS project hygiene | A | ✅ | CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG, templates |
| 45 | Landscape currency | A | ✅ | `docs/LANDSCAPE.md` re-verification checklist + cadence |

## How to verify the Tier B/C items on a provisioned machine

- **Training/export/transcribe (1–5)**: `uv pip install -e '.[ml,export]'` then
  `TALKTEACH_RUN_INTEGRATION=1 pytest -m integration` (downloads `whisper-tiny`,
  runs a 1-epoch fine-tune on the toy dataset; needs ~2 GB disk, CPU is fine).
- **ffmpeg (10, 20)**: install ffmpeg, re-run `pytest -m ffmpeg`.
- **Tauri sidecar (15)/compile (14)**: see README "Quick start (desktop app)";
  needs Rust + WebKit/GTK dev libs.
- **Installers (24)**: `.github/workflows/release.yml` runs on tag on the GH
  matrix; signing needs secrets (documented in `docs/RELEASING.md`).
</content>
