# AI Assistant Workflows

How AI coding assistants — Claude Code, OpenCode, and GitHub Copilot — integrate
with TalkTeach's experiment workflow. The project's `AGENTS.md` at the repo root
is the single source of truth for AI tool configuration; this document describes
the workflow templates those tools should follow.

## The AGENTS.md contract

`AGENTS.md` configures every AI assistant with:

- **Project identity**: Python 3.11 backend, Svelte 4 UI, Tauri v2 shell, GPL-3.0
- **Essential commands**: `make test`, `make lint`, `make prepush`, `make sota`, etc.
- **Code conventions**: heavy ML imports function-local (D-002), simulation
  fallback, synthetic-TTS caveat (D-012)
- **Experiment workflow**: define → execute → record → report
- **Guardrails**: 11-item checklist every AI must verify before committing

## Supported assistants

| Assistant | Configuration | Symlink / Setup |
|-----------|--------------|-----------------|
| **Claude Code** | `AGENTS.md` at repo root | Reads directly; task agent prompts should reference `OVERALL.md` |
| **OpenCode** | `AGENTS.md` at repo root | Prefers explore subagent for codebase search |
| **GitHub Copilot** | `.github/copilot-instructions.md` | Symlink to `AGENTS.md` |

## Workflow templates

### Template 1: Experiment proposal

When the user asks to design a new experiment, the AI should:

1. **Check pre-registration requirements** from `OVERALL.md` Part B:
   - Propose a **metric** (WER, CER, RTF, Cohen's d, etc.)
   - State the **baseline** (current known value, or "none — first measurement")
   - Define the **definition of done** (what constitutes success)
   - Assign a **feasibility tag**: `CPU-now`, `CPU-heavy`, `GPU-queued`, or `build`

2. **Score the proposal** against the rubric in `OVERALL.md` Part B:
   - Grounding (real measurement, not speculation): 0–100
   - Feasibility (runnable on available hardware): 0–100
   - Impact (expected improvement in WER or director accuracy): 0–100

3. **Draft the YAML config** for `experiments/<name>.yaml` following the format
   in `docs/learning-loops/HYPERPARAMETER_SWEEPS.md`.

4. **Propose a sequencing decision**: does this block other experiments, depend
   on them, or run independently?

Example prompt:

```
Design a calibration experiment to find the optimal LoRA rank for
whisper-tiny on 15 minutes of data. Pre-register the metric, baseline, and
DoD. Draft the sweep YAML. Score feasibility and impact.
```

### Template 2: Sweep analysis

When sweep results are available, the AI should:

1. **Query the experiment DB** for all cells in the sweep:
   ```bash
   python -m talkteach.obs.experiment_db --recent 50
   ```

2. **Compute statistics** using `talkteach/sota/scoring.py`:
   - Bootstrap 95% CI on the best cell's WER
   - Cohen's d effect size of best vs. current default
   - WER-vs-parameter curve shape (is there a clear minimum?)

3. **Render a recommendation**:
   - If statistically significant and practically meaningful: recommend updating
     `policy.py` with the new default
   - If not significant: recommend a larger sweep or a different parameter
   - Flag synthetic-vs-real caveat (A.6.7): if the sweep used synthetic TTS,
     mark the recommendation as "synthetic proxy — needs real-audio replication"

4. **Propose the DECISIONS.md entry** in the format:
   ```
   ### D-NNN — Calibrated <constant> from <old> to <new>
   ```

Example prompt:

```
Analyze the results of the LoRA rank sweep (experiments/lora_rank_calibration.yaml).
Compute effect sizes, confidence intervals, and recommend whether to update
the policy.py default. Flag the synthetic-TTS caveat.
```

### Template 3: Director update

When a calibration result is accepted and ready to ship, the AI should:

1. **Update `backend/talkteach/director/policy.py`**:
   - Change the constant to the calibrated value
   - Update the comment from `# proposed default` to `# calibrated — see D-NNN`
   - Verify no other branches or edge cases are affected

2. **Record the decision** in `docs/architecture/DECISIONS.md` as a new D-entry
   following the established format.

3. **Update `docs/roadmap/ROADMAP_STATUS.md`** — move the corresponding
   calibration item toward `✅`.

4. **Run the guardrails**:
   ```bash
   make test    # 198 fast tests must stay green
   make lint    # ruff + mypy
   ```

5. **Verify no regression** in the director's behavior:
   ```bash
   python -m talkteach.obs.experiment_db --best d01_wer_clean
   ```

Example prompt:

```
The LoRA rank sweep shows rank=16 beats rank=8 by Cohen's d=0.7 on synthetic
TTS. Apply this as a proposed default in policy.py, record the decision in
DECISIONS.md, and flag it as synthetic-proxy-only until real-audio replication.
```

## Using the Make targets

The AI should use these Make targets (from `Makefile`) rather than raw commands:

| Target | What it does |
|--------|-------------|
| `make test` | Fast test suite (198 tests, no GPU/ML deps) |
| `make lint` | ruff check + format-check + mypy |
| `make prepush` | Full pre-push gate (Python + UI + Rust) |
| `make experiment EXP=<name>` | Run a pre-registered sweep |
| `make sota-baseline` | Measure untrained WER across all SOTA domains |
| `make sota` | Full SOTA validation (train+eval) |
| `make sota-smoke` | Fast CI smoke: D01+D04 only, no training |
| `make experiments-db` | Show recent 10 experiments |
| `make benchmark` | TTS×ASR benchmark + ELO scoreboard |
| `make report` | Full benchmark fully automatically |

## Guardrails for AI agents

The 11-item guardrail checklist from `AGENTS.md` applies to every AI action:

1. `make test` all green (198 tests)
2. No `[SIMULATION]` in real-path results
3. No `project/docs/` paths in any .md file
4. No hardcoded secrets or tokens
5. Heavy imports are function-local
6. Disk guard: `keep_artifacts` defaults false
7. If changing `policy.py`: pre-register calibration experiment, record deltas
8. Speaker/sentence-disjoint eval split (Mo3 guardrail A.6.2)
9. New guardrails wired into `reliability/guardrails.py`
10. Synthetic-TTS WER never drives shipped `policy.py` changes (A.6.7)
11. Record non-obvious choices in `DECISIONS.md` (top-5 scored 0–100)

## Skills

The following Claude Code skills are available for specialised workflows:

| Skill | When to use |
|-------|------------|
| `journey` | Run a rigorous, documented scientific journey to improve a measurable quality via experiments |
| `keepgoing` | "What should I do next?" — survey remaining work, brainstorms 5 candidate directions |
| `planmax` | Plan-score-iterate-implement workflow for complex features |

## OpenCode-specific notes

OpenCode should use the **explore subagent** for codebase search (as noted in
`AGENTS.md`). The project's own subagents and permission rules are configured
via `opencode.json` or files under `.opencode/`.

## CI integration

AI-generated changes are validated by the same CI gates as human changes:

- **GitHub Actions**: runs `make prepush` (Python lint + type + tests + UI
  build + check + Rust fmt + clippy + check)
- **Pre-commit hooks**: run `ruff` on staged Python files

The AI should run `make prepush` before proposing a PR to ensure CI will pass.

## Cross-references

- `AGENTS.md` — master configuration for all AI assistants
- `OVERALL.md` — Part B: the 30-experiment program and pre-registration template
- `docs/learning-loops/README.md` — learning loop architecture
- `docs/learning-loops/HYPERPARAMETER_SWEEPS.md` — sweep YAML format
- `docs/learning-loops/EXPERIMENT_TRACKING.md` — querying experiment results
- `docs/learning-loops/CALIBRATION_LOOP.md` — director update workflow
- `docs/learning-loops/GUARDRAILS.md` — guardrails the AI must verify
- `docs/architecture/DECISIONS.md` — where decisions are recorded
- `docs/roadmap/ROADMAP_STATUS.md` — status tracking
- `Makefile` — all available targets
