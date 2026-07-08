# Implementation plan — Phase 0

This is the working plan for the effort tracked in
[`ROADMAP_STATUS.md`](../roadmap/ROADMAP_STATUS.md). It is ordered by the tightest
constraint outward: guardrails first (so they gate everything after), then the
P0 promise (make training real + secure), then P1 product, then P2/P3 breadth.

## Principles

1. **Guardrails before features.** CI, lint, type, and format gates land first so
   every later commit is held to them.
2. **Pure core, guarded edges.** Heavy ML/native deps stay behind lazy,
   import-guarded function-local imports. The director, data, audio-DSP, and
   policy layers import and test with zero ML deps — this is the Phase-0
   invariant and we keep it.
3. **Honest tiers.** Code that can't run here (network/GPU/root) is written,
   guarded, and documented with a "how to verify," not faked. See
   [`DECISIONS.md`](DECISIONS.md) D-001/D-002.
4. **Logical commits.** One coherent unit per commit, message explains *why*.
5. **Document as we go.** Plans here, decisions in `DECISIONS.md`, errors and
   insights in [`LEARNINGS.md`](LEARNINGS.md).

## First Principles Engineering

Apply first-principles thinking before making architectural or implementation
decisions. Decompose every problem into its fundamental objectives, constraints,
assumptions, and measurable requirements rather than following existing
implementations by default.

For every significant component:

- identify the core problem being solved;
- distinguish essential complexity from accidental complexity;
- challenge inherited assumptions;
- evaluate alternative solution spaces;
- justify the chosen design using evidence, benchmarks, and trade-off analysis;
- explicitly document why simpler or more general approaches were rejected.

Avoid local optimizations that increase overall system complexity. Optimize for
correctness, simplicity, maintainability, extensibility, reproducibility, and
measurable real-world performance.

See [`DECISIONS.md`](DECISIONS.md) D-016.

## Open Source Reuse Before Reinvention

Treat existing, well-maintained open-source software as the default
implementation strategy.

Before implementing any non-trivial algorithm, framework, utility, workflow,
parser, optimizer, benchmark, visualization, or infrastructure component:

- actively search for mature, production-proven OSS alternatives;
- compare multiple candidates using objective evaluation criteria;
- document trade-offs including maturity, maintenance activity, community
  adoption, license compatibility, security history, performance, extensibility,
  and long-term sustainability;
- prefer composition over custom implementation whenever practical;
- minimize custom code by leveraging proven libraries.

Only implement custom solutions when at least one of the following is true:

- no suitable OSS solution exists;
- measurable performance or capability requirements cannot be achieved;
- licensing prevents use;
- security or compliance requires a custom implementation;
- repository-specific requirements fundamentally differ from available solutions.

Every custom implementation must include documented justification explaining why
existing OSS solutions were not adopted.

See [`DECISIONS.md`](DECISIONS.md) D-017.

## Continuous Technology Discovery

During repository analysis, continuously identify opportunities to replace
custom implementations with higher-quality OSS components. Produce a migration
backlog ranked by expected impact, engineering effort, technical risk,
maintenance cost reduction, and projected improvement in benchmark scores.
Whenever a replacement is proposed, estimate expected gains in correctness,
performance, maintainability, reliability, developer productivity, and total cost
of ownership, and validate these estimates through reproducible benchmarks before
adoption.

See [`DECISIONS.md`](DECISIONS.md) D-018.

## Commit sequence

1. **Spine** — `DECISIONS.md`, `ROADMAP_STATUS.md`, this plan, `LEARNINGS.md`.
2. **Guardrails (X 38–45 tooling)** — ruff/mypy/eslint/prettier/svelte-check/
   rustfmt configs, GitHub Actions CI, pre-commit, OSS hygiene docs & templates.
   Fix any lint/type findings on the existing 3K LOC.
3. **P0 security (#7–9)** — filename sanitisation, CSP lock, upload validation.
4. **P0 training (#1–3)** — real Whisper-LoRA loop; pure helpers + WER metric;
   safety rails (seed, grad-clip, NaN-guard → rollback). jiwer added to `[ml]`.
5. **P0 export/transcribe (#4,5)** — LoRA-merge → CT2 int8 export; faster-whisper
   inference; ONNX/sherpa scaffold.
6. **P1 audio (#10–13)** — ffmpeg decode/resample, Silero VAD, alignment adapter,
   live quality meter.
7. **P1 desktop (#14–18)** — Tauri sidecar spawn, mic probe, bundled-runtime
   script, durability/resume, preflight wiring.
8. **P1 UX (#19–23)** — wire screens to the API, browser audio, prompt sets,
   self-test toy dataset, advanced rationale panel.
9. **P2/P3 (#24–37)** — engine scaffolds, credits generator, active-learning
   ranking, adaptive targets, i18n/a11y, and design docs for the rest.
10. **X durability/observability/deps (#40–43)** — job reconcile, structured
    logging + help bundle, dependency hygiene, coverage.
11. **Coherence pass** — ruff/mypy/pytest green; docs↔code cross-check; matrix
    reconciled; README/CHANGELOG updated.

## Environment facts (verified 2026-06-28)

- `backend/.venv` is a **Python 3.11** venv (system Python is 3.14); ML deps
  (torch, transformers, faster-whisper) **are** installed there; jiwer added.
- No system Rust toolchain, no ffmpeg, no root (WebKit/GTK libs can't be
  installed) → Tauri compile and ffmpeg runs are Tier B/C here.
- Network reaches huggingface.co (200) → end-to-end fine-tune is *possible* on a
  provisioned run but kept behind a marker (slow, flaky, large download).
- Baseline: 54 passed, 3 skipped (`pytest -q`), one Starlette/httpx deprecation
  warning (#42).

## Verification commands

```bash
# Python (fast, no ML/network needed)
cd backend && .venv/bin/python -m pytest -q

# Lint/type/format
ruff check backend && ruff format --check backend && mypy backend/talkteach

# UI
cd ui && npm run build && npx svelte-check

# Opt-in heavy paths (provisioned machine)
TALKTEACH_RUN_INTEGRATION=1 .venv/bin/python -m pytest -m integration
```
</content>
