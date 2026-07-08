# Plan: Consolidate the SOTA story into one authoritative document

**Date:** 2026-07-08
**Type:** IMPROVEMENT
**Status:** DONE

## Objective
Resolve the contradiction between `OVERALL.md` ("no real-audio baseline / E02 missing") and the
newer `docs/sota-benchmarks/SCOREBOARD` ("2.69% gold / 788 silver") by making **`OVERALL.md` the
single authoritative SOTA document**, fixing the misleading scoreboard generator so its
single-sourced numbers are honest, and demoting the sibling docs to appendices — so the two can
never silently drift again.

## What changed
- **Generator honesty** (`backend/talkteach/sota/`): a small-n headline gate — a measured domain
  that is under-powered (too few clips vs its declared `min_samples`, or a per-speaker metric over
  `< min_speakers`) is kept and shown but flagged **directional** and **excluded from the mean**;
  the headline reads `provisional` until ≥3 domains are adequately powered; coverage
  (measured/directional/unmeasured) is reported. Corrected the d01 SOTA anchor (was a false-precise
  "1.8%"; now a cited 1.8–2.7% range). Fixed the malformed summary-table delimiter. Routed
  `run_all.sh` through the venv (`${PYTHON:-…}`) so `make sota-baseline` no longer crashes on bare
  `python`.
- **Rescore entrypoint** (`backend/talkteach/sota/rescore.py`, `make sota-rescore`): re-applies the
  scoring policy to the banked `SCOREBOARD.json` and regenerates in seconds with no GPU/network,
  preserving the measurement `generated` stamp. This is the regeneration path (the old
  `make sota`/`sota-baseline` re-render path was broken).
- **Single source of numbers**: `OVERALL.md` and the `docs/sota-benchmarks/*.md` appendices now
  *reference* the generated scoreboard by its stamp instead of copying figures; dated historical
  records (Part C, journeys, experiment YAMLs) are exempt.
- **Docs**: rewrote `OVERALL.md` as canonical (honest state, S2/INS-001/Stage-3 absorbed, one
  reconciled experiment-ID register, wiring-debt section); demoted the sota-benchmarks suite to
  appendices; rewrote `BASELINES.md` (was a stale hand-maintained duplicate). Swept active
  cross-refs (`stage3-model-scaling.md`) and hot memory.

## Standards & Guardrails Evidence
- [x] **Tests / shift-left:** `backend/tests/test_sota_scoring.py:129` — new fast tests for the
  small-n gate, coverage aggregation, rescore reproducibility, scoreboard self-consistency, and the
  OVERALL.md↔scoreboard stamp/stale-literal guards. Full fast suite (208 passed, 8 skipped) green.
- [x] **Reused patterns / grounding:** `backend/talkteach/sota/rescore.py:30` reuses
  `report.generate` + `scoring.score_against_bands`; `backend/talkteach/sota/harness.py:491` and
  `scripts/sota/run_all.sh:143` both consume the shared `scoring.aggregate_headline` rather than
  duplicating the headline logic.
- [x] **Security:** N/A — benchmark scoring + documentation only; no user data, credentials, or
  network trust boundaries touched (`backend/talkteach/sota/scoring.py:1`).
- [x] **Evidence classification:** `docs/sota-benchmarks/SCOREBOARD.json:5` — coverage block +
  per-domain `directional`/`directional_reason` distinguish adequately-powered measurements from
  under-powered (directional) and unmeasured/blocked ones.
- [x] **Reproducibility:** `backend/talkteach/sota/rescore.py:1` — deterministic re-render that
  preserves the `generated` stamp; a fast stamp-equality test binds `OVERALL.md` to the scoreboard
  (`backend/tests/test_sota_scoring.py:144`).
- [x] **Statistical validity:** `backend/talkteach/sota/scoring.py:216` — `assess_headline_eligibility`
  gates the headline on sample/speaker count; 95% CI already computed per domain
  (`backend/talkteach/sota/scoring.py:72`).
- [x] **Baseline / SOTA calibration:** `backend/talkteach/sota/domains.py:56` — d01 anchor corrected
  to a cited 1.8–2.7% range (1000-tier = <1.0%), replacing the false-precise 1.8%.

## Verification
- `make lint` (ruff + ruff-format + mypy) clean; 208 fast tests pass, 8 skipped.
- `make sota-rescore` reproduces the committed scoreboard (self-consistency test).
- Guardrail greps: no new `project/docs/` paths; no stray `</content>` in touched Markdown; no secrets.
