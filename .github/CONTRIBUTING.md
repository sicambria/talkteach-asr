# Contributing to TalkTeach

Thanks for wanting to help. TalkTeach is a **easy-to-use, offline-first,
cross-platform ASR-training desktop app** (Tauri shell + Svelte UI + a Python
FastAPI backend). It is mostly *integration and UX*, not new ML research — so
most contributions are about making the four-tap wizard (**Record → Check →
Teach → Try**) more reliable, more honest, and easier for a 10-year-old to use.

Two things shape almost every decision here, and they should shape your PR too:

1. **It runs on a kid's laptop, offline, with no GPU.** The pure core (director,
   audio DSP, data layer, policy, reliability) imports and tests with **zero ML
   dependencies**. Heavy/native deps (torch, faster-whisper, ffmpeg, …) live
   behind lazy, import-guarded, function-local imports and degrade gracefully.
   Don't break that invariant.
2. **It handles children's voice recordings.** Recordings never leave the device
   by default; there is no telemetry without explicit opt-in. Keep it that way
   (see [`SECURITY.md`](SECURITY.md) and `project/docs/DECISIONS.md` D-008).

This repo is **literate**: we explain *why*, not just *what*. Code comments,
commit bodies, and the decision log all favour the reasoning behind a choice.
Please match that voice.

---

## Where things live

| Path | What |
|---|---|
| `backend/talkteach/` | The Python backend — director, audio, data, reliability, engines, FastAPI app |
| `ui/` | Svelte 4 four-screen wizard + typed API client |
| `src-tauri/` | Tauri v2 desktop shell (sidecar-spawns the backend) |
| `project/docs/` | All the prose. Start here. |

Docs you'll likely touch:

- [`project/docs/PLAN.md`](../project/docs/PLAN.md) — the working plan and the canonical
  **verification commands** (kept in sync with reality).
- [`project/docs/ROADMAP.md`](../project/docs/ROADMAP.md) — the prioritized list (P0–P3 + X).
- [`project/docs/ROADMAP_STATUS.md`](../project/docs/ROADMAP_STATUS.md) — the traceability matrix;
  **update it if your change moves a roadmap item's tier or status.**
- [`project/docs/DECISIONS.md`](../project/docs/DECISIONS.md) — the decision log (read the tier system below).
- [`project/docs/PHASE0_STATUS.md`](../project/docs/PHASE0_STATUS.md) — what is real vs. simulated.
- [`CHANGELOG.md`](../CHANGELOG.md) — add a line under `[Unreleased]`.

---

## Setup

### Backend (Python ≥ 3.10; we develop on 3.11 via [`uv`](https://github.com/astral-sh/uv))

```bash
cd backend
uv venv .venv                                   # creates a Python 3.11 venv
VIRTUAL_ENV=.venv uv pip install -e '.[dev]'    # light dev deps: pytest, ruff, mypy
```

To enable the **real** training/inference/export paths (large download, GPU
recommended) add the `[ml]` extra:

```bash
VIRTUAL_ENV=.venv uv pip install -e '.[ml]'     # torch, transformers, peft, faster-whisper, jiwer, …
```

Everything in the pure core works — and the whole light test suite passes —
**without** `[ml]`. The `[ml]` paths are exercised behind pytest markers (below).

Run the server to poke at it:

```bash
.venv/bin/python -m talkteach.app               # serves http://127.0.0.1:8756
curl http://127.0.0.1:8756/api/health
```

### UI (Node ≥ 18)

```bash
cd ui
npm install
npm run build        # production build → ui/dist  (this is also a gate)
npm run dev          # Vite dev server on :1420; backend must run on :8756
```

### Desktop shell (Tauri) — optional, needs a provisioned machine

Compiling the native shell needs the Rust toolchain plus system WebKit/GTK dev
libraries (root required on Linux). The full recipe is in the README under
"Quick start (desktop app)". You do **not** need it to contribute to the backend
or UI.

---

## The gates (run these before you push)

A `Makefile` at the repo root wraps the canonical commands so you don't have to
memorise them:

| Target | Does |
|---|---|
| `make test` | `pytest -q` in `backend/` — fast, no ML/network needed |
| `make lint` | `ruff check` + `ruff format --check` + `mypy` (config in `backend/pyproject.toml`) |
| `make format` | `ruff check --fix` + `ruff format` (auto-fix in place) |
| `make check` | **the PR gate** — `make lint` + `make test` (ruff + format-check + mypy + pytest) |
| `make ui-check` | UI build + `svelte-check` + prettier check |
| `make all` | `make check` + `make ui-check` — everything that runs without a GPU |

`make check` is the Python gate that CI runs and the PR template asks you to
confirm; run `make ui-check` (or `make all`) when you touch the UI. The
underlying commands, if you prefer to run them by hand:

```bash
# Python (fast — this is the Phase-0 invariant: green with or without [ml])
backend/.venv/bin/python -m pytest -q

# Lint / format / type
ruff check backend
ruff format --check backend
mypy talkteach            # run from backend/ (config in backend/pyproject.toml)

# UI
cd ui && npm run build && npx svelte-check
```

### The heavy, opt-in paths

End-to-end ML and ffmpeg work can't run in a vanilla CI box, so it's gated
behind markers (see `project/docs/DECISIONS.md` D-002). On a machine with `[ml]` installed
and ffmpeg on `PATH`:

```bash
TALKTEACH_RUN_INTEGRATION=1 backend/.venv/bin/python -m pytest -m integration
backend/.venv/bin/python -m pytest -m ffmpeg
```

If you add a code path that needs a GPU, the network, or a native binary, hide
it behind one of these markers and import its deps lazily — never at module top
level.

---

## The tier system (please read — it's how we stay honest)

TalkTeach is built under a sandbox where some things *cannot* be run to
completion (signed installers, real GPU training, compiling the Tauri shell).
Rather than fake "done," every roadmap item is assigned an honest **tier** —
this is decision **D-001** in [`project/docs/DECISIONS.md`](../project/docs/DECISIONS.md):

- **Tier A — done & verified here:** real code + tests that pass in this
  environment.
- **Tier B — coded & guarded; integration deferred:** real code paths, written
  and import-guarded; the full run needs network/GPU/root, so it sits behind a
  marker or a provisioned machine, with a documented "how to verify."
- **Tier C — design + scaffolding:** a design doc, code scaffold, and/or script;
  the full build needs hardware/certs/art outside the sandbox.

When you contribute, say which tier your work lands in, and update the
traceability matrix (`project/docs/ROADMAP_STATUS.md`) so it stays the authoritative
spine. A Tier-B feature without a "how to verify" note isn't finished.

---

## Decisions: don't ask, decide (and record it)

This project follows an unusual but deliberate convention. When a non-obvious
choice comes up, **generate the top ~5 options, score them 0–100 against this
project's constraints (easy-to-use, offline-first, GPL-3.0, integration-not-
research, must degrade on a GPU-less laptop), pick the best, and append an entry
to [`project/docs/DECISIONS.md`](../project/docs/DECISIONS.md)** — don't open a discussion thread to ask.

The log is append-only; if a decision is later reversed, a new entry supersedes
it and links back. Read a few existing entries (D-001 … D-010) before adding
yours so the scoring stays calibrated to the same constraints.

---

## Commits & pull requests

**Conventional Commits.** The title is `type: short imperative summary`, where
`type` is one of `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `perf`,
`build`, `ci`. The **body explains *why*** the change exists, not just what it
does — that's the house style. Example:

```
feat: spawn the Python backend as a Tauri sidecar

The desktop app must work with zero terminal steps for a child. Bundling the
backend as an externalBin sidecar (roadmap #15) removes the "start the server first"
footgun and keeps everything offline on 127.0.0.1:8756.
```

**One coherent unit per commit.** Don't mix a security fix with a UI refactor.

**Before opening a PR:**

1. `make check` is green (ruff + mypy + pytest + UI build).
2. You added or updated tests for the behaviour you changed.
3. You added a line under `[Unreleased]` in `CHANGELOG.md`.
4. If a roadmap item changed tier or status, you updated
   `project/docs/ROADMAP_STATUS.md`.
5. Your PR title is a valid conventional-commit subject.

The pull-request template will walk you through this checklist.

---

## License

By contributing you agree your contributions are licensed under
**GPL-3.0-or-later**, the project license (see [`LICENSE`](../LICENSE) and the
rationale in `README.md` / report B.6). Third-party components and their
verified licenses are tracked in [`project/docs/THIRD_PARTY.md`](../project/docs/THIRD_PARTY.md);
if you add a dependency, add it there too.

Questions that aren't a bug or a feature request? The maintainer is **Gaspar
Incze** — <inczegaspar@gmail.com>.
