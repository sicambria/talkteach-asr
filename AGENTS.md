# AGENTS.md — TalkTeach AI Workflow Configuration

## Project Identity
TalkTeach: offline desktop ASR training wizard. Python 3.11 (FastAPI) backend,
Svelte 4 UI, Tauri v2 shell, GPL-3.0-or-later. See `README.md` and `OVERALL.md`.

## Essential Commands
- Test (fast, no GPU):   `cd backend && .venv/bin/python -m pytest -q`
- Test (integration):    `TALKTEACH_RUN_INTEGRATION=1 cd backend && .venv/bin/python -m pytest -m integration`
- Lint + type:           `make lint`
- Full PR gate:          `make prepush`
- Benchmark:             `make benchmark`
- Full report:           `make report`
- SOTA baseline:         `make sota-baseline`
- SOTA smoke (CI):       `make sota-smoke`
- SOTA full:             `make sota`
- SOTA single domain:    `python scripts/sota/validate_d01_wer_clean.py --baseline-only`
- SOTA Docker:           `docker build -f Dockerfile.sota -t talkteach-sota .`

## Code Conventions
- Heavy ML imports stay **function-local** (D-002 in docs/architecture/DECISIONS.md)
- Simulation fallback: `TALKTEACH_FORCE_SIMULATION=1` or deps absent
- Never confuse `[SIMULATION]` WER with real WER (D-012)
- Pre-register experiments: metric + baseline + DoD before implementation (OVERALL.md Part B)
- Update `docs/roadmap/ROADMAP_STATUS.md` when a roadmap item changes status
- Record non-obvious choices in `docs/architecture/DECISIONS.md` (top-5 scored 0-100)
- 226 fast tests must stay green (no GPU/ML deps needed)

## Experiment Workflow (Learning Loop)
1. Define: create YAML in `experiments/<name>.yaml` with pre-registered metric, baseline, DoD
2. Execute: `make experiment EXP=<name>` or `python scripts/sota/validate_dXX.py`
3. Record: results auto-written to `~/.cache/talkteach/experiments.db`
4. Report: `make experiments-db` or `python -m talkteach.sota.report`

## SOTA Domains (15 total)
D01-D15 cover accuracy, efficiency, robustness, portability, and automation.
Full definitions in `backend/talkteach/sota/domains.py`.
Validation scripts in `scripts/sota/validate_dXX_*.py`.
Scoreboard in `docs/sota-benchmarks/SCOREBOARD.md`.

## Engineering Philosophy

TalkTeach follows three standing engineering rules, documented in full at
`docs/architecture/PLAN.md` and formalized as D-016/D-017/D-018 in
`docs/architecture/DECISIONS.md`:

1. **First Principles Engineering** — decompose problems into objectives,
   constraints, and measurable requirements before choosing solutions. Challenge
   inherited assumptions. Justify designs with evidence and trade-off analysis.
2. **Open Source Reuse Before Reinvention** — search for mature OSS alternatives
   before implementing any non-trivial component. Custom code requires documented
   justification.
3. **Continuous Technology Discovery** — continuously identify custom code that
   could be replaced by higher-quality OSS; rank by impact; validate through
   reproducible benchmarks.

## Guardrails (must verify before committing)
- [ ] `make test` all green (226 tests)
- [ ] No `[SIMULATION]` in real-path results
- [ ] No `project/docs/` paths in any .md file (`grep -rn 'project/docs/' --include='*.md' .`)
- [ ] No hardcoded secrets or tokens
- [ ] Heavy imports are function-local
- [ ] Disk guard: `keep_artifacts` defaults false
- [ ] If changing `policy.py`: pre-register calibration experiment, record deltas
- [ ] Speaker/sentence-disjoint eval split (Mo3 guardrail from A.6.2)
- [ ] New guardrails wired into `reliability/guardrails.py`

## Tool-Specific Notes
- **Claude Code**: uses this file directly. Task agent prompts should reference `OVERALL.md`.
- **OpenCode**: uses this file directly. Prefer explore subagent for codebase search.
- **GitHub Copilot**: symlink `.github/copilot-instructions.md` → `AGENTS.md`
- **All**: talkteach backend runs on `127.0.0.1:8756`. UI dev on `localhost:1420`.

<!-- BEGIN kaizen (managed — do not edit inside this block) -->
# Agent Operating Contract (kaizen harness)

> Canonical, tool-agnostic driver. Per-agent files (`CLAUDE.md`, `.cursor/rules`, `.codex`,
> `opencode.jsonc`, `.github/copilot-instructions.md`) are thin overlays that import this file.
> This is the source of truth — edit here, then regenerate overlays (`kaizen init --check` detects drift).

## Session-start invariants (violation = blocker)
1. **Before ANY edit:** run `git branch --show-current` and `git worktree list --porcelain`. If on the
   default branch (see `.harness/config.json` → `defaultBranch`) and the task changes any substantive
   (non-docs) file, **STOP and create a worktree first**, then merge at the end.
2. **Never leave the default branch with uncommitted substantive changes.** Substantive work goes in a
   worktree → merge to the default branch only when it is clean.
3. **After ANY `git push`:** verify with `git rev-list --left-right --count origin/<branch>...<branch>`.
   The AHEAD count MUST be 0. If the command timed out, the push did NOT complete — re-verify.
4. **After context compaction:** re-read this file and the active plan before continuing.
5. **Never use `--no-verify`.** The gates are the product. A bypass that reaches the default branch is a
   defect. If a gate is wrong, fix the gate (and log the decision), don't skip it.

## Plan-before-code (enforced)
- Non-trivial work gets a plan file under `.harness/plans/` before implementation.
- Every plan MUST contain a `## Standards & Guardrails Evidence` section whose `path:line` citations
  **resolve against the working tree** — a hallucinated citation hard-fails the commit
  (`.harness/scripts/audits/verify-plan-evidence.mjs`). Check off every configured evidence dimension
  with a resolving citation or an explicit `N/A — reason`.

## Verify contract
- The stack's real checks live behind `.harness/config.json → verify` (`test`/`lint`/`build`/`e2e`/`healthcheck`).
- `.harness/scripts/verify.mjs` runs them. A required check that cannot be mechanically confirmed
  **abstains (`human_needed`)** and fails closed — it never silently passes.

## Incident & learning loop (closed)
- On discovering any real bug: check `.harness/archive/postmortems/INDEX.md` first, do RCA, then scaffold
  an incident note (metadata + Summary/Root Cause/Prevention/Guardrail Updates/Automation Follow-Up).
- The note MUST cite a concrete guardrail path and automation path — the loop closes on a real prevention
  artifact, never prose. `verify-learning-loop.mjs` gates it and regenerates the index deterministically.

## Memory (survives context resets, committed in-repo)
- `.harness/memory/memory.md` is the hot, auto-loaded index. `project.md`/`user.md` are semantic;
  `episodic/` holds daily journals; `procedural/` holds distilled reusable skills. All committed in-repo.

## Behavioral contract & invariants (the layer beneath the gates)
- The tiered agent contract (T0 halt / T1 waiver / T2 best-effort / T3 graceful), the agent execution state
  machine, stop triggers, assumption budget, and Intent Gate live in `.harness/memory/rules.md`. Re-read its
  T0/T1 tiers + state machine at session start, after compaction, and at plan→execution transitions.
- `.harness/INVARIANTS.md` is the invariant registry + blast-radius Protection Matrix: when a change's blast
  radius intersects a threat category, consult the named invariant and apply the tier-appropriate response.
- Rationale (the MAST-grounded failure-mode taxonomy) is in `.harness/reference/failure-modes.md` — a design
  artifact, deliberately **not** hot-loaded, to keep the per-session context budget lean.

## Overrides are audited, never silent
- Any gate override must append a justified entry to `.harness/archive/decisions/` — an override that
  leaves no trace is forbidden.

## Session-start contract-read canary
Prove you actually ingested the contract (not just this pointer overlay): four **canary words** are
embedded as HTML-comment markers (format `CANARY: <word>`), one in each of `AGENTS.md`,
`.harness/memory/rules.md`, `.harness/INVARIANTS.md`, and `.harness/memory/memory.md`. **Surface all four
at session start.** Claude enforces contract-read through its SessionStart hook; for hook-less providers
(Cursor / Codex / opencode / Copilot) this canary is the read-compliance signal they otherwise lack. The
marker *integrity* (exactly one per file, all listed here) is gated by
`.harness/scripts/audits/verify-canary.mjs` — a marker that drifts out of sync fails closed.
<!--CANARY: MARBLE-->
<!-- END kaizen -->
