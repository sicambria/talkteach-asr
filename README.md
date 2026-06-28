# TalkTeach

**Teach a computer to understand a voice or language — so easily a 10-year-old can.**

TalkTeach is a free, offline, cross-platform desktop app that turns the fragmented
open-source speech-training stack (Whisper, NeMo, faster-whisper, Silero VAD,
sherpa-onnx, …) into a single four-tap wizard — **Record → Check → Teach → Try** —
with every ML decision made automatically by a hardware-and-data-aware *director*,
guardrails that make a doomed training run impossible to start, and bundled
dependencies that remove install pain.

It exists to close the exact gap documented in the companion research report
(see **Provenance** below): *there is no end-to-end, open-source, "next-next-finish"
GUI that actually trains state-of-the-art ASR models.* TalkTeach is mostly
**integration and UX**, not new ML.

> **Status: Phase 0 → world-class, in progress.** The Python backend (director,
> audio pipeline, data layer, reliability pre-flight, FastAPI job server) is real
> and tested: **97 passing tests** (fast suite, no GPU). **Real Whisper-LoRA
> training is implemented** — a PEFT/LoRA `Seq2SeqTrainer` loop with measured WER
> and safety rails, verified end-to-end on `whisper-tiny` via the opt-in
> `integration` test. It trains for real when the `[ml]` extra is installed and
> real recordings exist, and otherwise falls back to a clearly-marked simulation
> (see [`project/docs/DECISIONS.md`](project/docs/DECISIONS.md) D-012). The Svelte UI is wired to the live
> API; the Tauri shell spawns the backend as a sidecar (build-ready, not compiled
> here — needs WebKit/GTK dev libs). See
> [`project/docs/ROADMAP_STATUS.md`](project/docs/ROADMAP_STATUS.md) for the per-item status
> matrix and [`project/docs/PHASE0_STATUS.md`](project/docs/PHASE0_STATUS.md) for real vs.
> scaffolded.

---

## Why it exists (provenance)

The design is the direct implementation of **Part B** of
`reports/ASR_training_GUI_wizard_research_and_design_2026-06-27.md` in the
companion **Turan_engine** repo. That report (Part A) verified — across a deep-
research run, 48 claims adversarially 3-vote-checked — that no OSS tool ships a
child-proof GUI that trains the best models end-to-end, and (Part C) names the
strongest counter-argument: the hard part isn't the wizard, it's the *director +
reliability engineering*. TalkTeach builds the director **first and with tests**
for exactly that reason.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Shell:  Tauri (Rust)  — src-tauri/      [scaffolded]          │
│ UI:     Svelte 4 wizard — ui/           [scaffolded]          │
│         Record → Check → Teach → Try  + hidden Grown-up mode  │
├──────────────────────────────────────────────────────────────┤
│ API:    FastAPI job server — backend/talkteach/app.py  [REAL] │
│         health · project · preflight · clips/analyze ·        │
│         sufficiency · transcribe/draft · train · train/{id} · │
│         transcribe · export                                   │
├──────────────────────────────────────────────────────────────┤
│ Director (the IP) — backend/talkteach/director/        [REAL] │
│   hardware probe · data probe · language probe ·             │
│   sufficiency gate · policy → zero-config TrainingPlan       │
├──────────────────────────────────────────────────────────────┤
│ Audio  — talkteach/audio/        clipping/SNR/silence  [REAL] │
│ Data   — talkteach/data/         SQLite (WAL) project  [REAL] │
│ Reliab.— talkteach/reliability/  pre-flight checks     [REAL] │
│ Engines— talkteach/engines/      adapter + Whisper-LoRA       │
│          (real faster-whisper/CT2 when [ml] present;          │
│           faithful simulation otherwise)              [BOTH]  │
└──────────────────────────────────────────────────────────────┘
```

## Quick start (backend)

Requires Python ≥ 3.10 and [`uv`](https://github.com/astral-sh/uv) (or pip).

```bash
cd backend
uv venv .venv && source .venv/bin/activate
uv pip install -e .            # light deps only — no GPU, no ML framework needed
pytest -q                      # 97 tests, ~1.3s (no GPU/ML deps needed)
python -m talkteach.app        # serves http://127.0.0.1:8756
```

Then probe it:

```bash
curl http://127.0.0.1:8756/api/health
curl http://127.0.0.1:8756/api/preflight
curl http://127.0.0.1:8756/api/sufficiency
```

To enable **real** training/inference (large download, GPU recommended):

```bash
uv pip install -e '.[ml]'      # torch, transformers, peft, faster-whisper, …
```

## Quick start (UI — web preview)

Requires Node ≥ 18. The Svelte UI **builds and runs as a web app today**
(`npm run build` produces `ui/dist/`, verified):

```bash
cd ui
npm install
npm run build                  # production build → ui/dist  (verified working)
npm run dev                    # or: Vite dev server on :1420; backend must run on :8756
```

## Quick start (desktop app — Tauri shell)

The native desktop shell is fully scaffolded and **build-ready** (Tauri v2 layout,
icons, orchestrator scripts). It is *not* compiled in this spike environment
because the Linux build needs system WebKit/GTK dev libraries that require root to
install. On a provisioned machine:

```bash
# 1. Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 2. System deps (Linux example — Debian/Ubuntu; macOS/Windows differ)
sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file \
     libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev

# 3. From the repo root: run / build the desktop app
npm install                    # installs @tauri-apps/cli at the root
npm run tauri dev              # launches the desktop app (spawns the Svelte UI)
npm run tauri build            # produces a signed-able installer per OS
```

The Python backend must be running on `:8756` (Phase 1 will spawn it
automatically as a Tauri sidecar — see `src-tauri/src/lib.rs`).

## Project layout

| Path | What | State |
|---|---|---|
| `backend/talkteach/director/` | Zero-config "director" — the real IP | **Real + tested** |
| `backend/talkteach/audio/` | Clip quality (clipping/SNR/silence), sufficiency aggregation | **Real + tested** |
| `backend/talkteach/data/` | One-SQLite-per-project store (WAL, autosave) | **Real + tested** |
| `backend/talkteach/reliability/` | Pre-flight (disk/RAM/GPU/mic), graceful degradation | **Real + tested** |
| `backend/talkteach/engines/` | `ASREngine` adapter + real `WhisperLoRAEngine` & `Wav2Vec2CTCEngine` (real fine-tunes) + GPU-gated NeMo | **Real training** when `[ml]` present; simulation fallback |
| `backend/talkteach/tts/` | TTS providers (espeak + piper) — synthetic *speech* for testing/benchmarking | **Real**; `[tts]` extra / espeak-ng binary |
| `backend/talkteach/benchmark.py` + `benchmarks/` | TTS × ASR benchmark — compare engines on real synthetic speech (WER/CER/time) | **Real**; run via `scripts/benchmark.py` |
| `backend/talkteach/app.py` | FastAPI job server | **Real + tested** |
| `ui/` | Svelte 4 four-screen wizard wired to the live API | **Builds + svelte-check/eslint/prettier clean** |
| `src-tauri/` | Tauri v2 shell — spawns the backend as a sidecar | Build-ready; native compile needs WebKit dev libs |
| `project/docs/` | Status matrix, decisions, per-feature design docs | — |

## Testing

```bash
cd backend && pytest -q
```

Over 100 fast tests cover the director's decision boundaries, the audio DSP +
pipeline helpers, the SQLite layer (incl. WAL persistence + SQL-injection guard),
the engine simulation + the *pure* real-training helpers (args-from-plan, WER,
NaN-guard, checkpoint discovery), the TTS resampler/registry, security
(path-traversal/upload validation), job durability + the redacted help bundle,
pre-flight degradation, and the full HTTP flow. All run with **no GPU and no ML
framework installed**. The real fine-tunes and the TTS→ASR benchmark are opt-in:

```bash
cd backend && pytest -q                                   # 100+ fast tests (no ML)
TALKTEACH_RUN_INTEGRATION=1 pytest -m integration         # real whisper-tiny fit ([ml] + net)
pytest -m espeak                                           # measurement-is-real ([ml] + espeak-ng)

# Compare ASR engines for real on synthetic speech (espeak + piper):
python scripts/benchmark.py --config benchmarks/quick.yaml   # needs backend[ml,tts]
```

See [project/docs/BENCHMARKING.md](project/docs/BENCHMARKING.md) for the
engine-comparison methodology and [project/docs/TTS.md](project/docs/TTS.md) for the
speech generators.

Lint/type/format gates: `ruff check`, `ruff format --check`, `mypy talkteach`
(or just `make check`); UI: `cd ui && npm run build && npm run check && npm run lint`.

## License

**GPL-3.0-or-later** (see [`LICENSE`](LICENSE)) — the lowest-friction path given
the project reuses copyleft-adjacent tooling and the maintainer approved GPL (see
report B.6). Third-party components and their **verified** licenses are listed in
[`project/docs/THIRD_PARTY.md`](project/docs/THIRD_PARTY.md); a credits screen will surface these
in-app per Phase 2.
