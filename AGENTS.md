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
- 198 fast tests must stay green (no GPU/ML deps needed)

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
- [ ] `make test` all green (198 tests)
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
