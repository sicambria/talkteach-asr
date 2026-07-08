# Learning Loop Architecture

TalkTeach's SOTA learning loop is the engine that turns raw benchmark results into
calibrated, auditable improvements to the director's policy. It is a 7-step
reinforcing cycle that mirrors the pre-registered experiment workflow mandated by
`OVERALL.md` Part B: every experiment carries a metric, a baseline, and a
definition-of-done before a single line of code runs.

## The 7-step loop

```
  1. DEFINE → 2. EXECUTE → 3. RECORD → 4. ANALYZE → 5. APPLY → 6. GUARD → 7. REPORT
      ↑                                                                              |
      └──────────────────────────────────────────────────────────────────────────────┘
```

| Step | Name | What happens | Tools / scripts |
|------|------|-------------|----------------|
| 1 | **DEFINE** | Pre-register an experiment: metric, baseline, DoD. Write a YAML config in `experiments/<name>.yaml`. Score against the proposal rubric (grounding/concreteness ≥ 90). | `experiments/*.yaml`, `docs/plans/` |
| 2 | **EXECUTE** | Run the experiment. Either a hyperparameter sweep (`sweep_runner.py`) or a full SOTA domain validation (`validate_dXX_*.py`). | `make experiment EXP=<name>`, `make sota`, `make sota-baseline`, `python scripts/sota/validate_d01_wer_clean.py` |
| 3 | **RECORD** | Results land in the SQLite experiment registry (`experiments.db`) and per-run `metrics.jsonl` curves. Nothing phones home — all data stays local. | `backend/talkteach/obs/experiment_db.py`, `backend/talkteach/obs/experiment.py`, `make experiments-db` |
| 4 | **ANALYZE** | Query the DB: compare runs, find best config per domain, check for regressions, compute bootstrap confidence intervals and Cohen's d effect sizes. | `python -m talkteach.obs.experiment_db --recent 10 --domain d01_wer_clean`, `talkteach/sota/scoring.py` |
| 5 | **APPLY** | Update `director/policy.py` defaults when calibration sweeps prove a better value. Record the change in `DECISIONS.md` as a new D-entry. Update `ROADMAP_STATUS.md`. | Edit `backend/talkteach/director/policy.py`, `docs/architecture/DECISIONS.md` |
| 6 | **GUARD** | Run all guardrails against the new results: NaN check, bias detection, hallucination scoring, data leakage audit, OOD confidence check. | `backend/talkteach/reliability/guardrails.py`, `make lint`, `make test` (198 fast tests must stay green) |
| 7 | **REPORT** | Auto-generate the SOTA scoreboard (`SCOREBOARD.md` + `SCOREBOARD.json`). Append to `OVERALL.md` Part C results log. The loop closes — the next experiment targets the largest remaining gap. | `python -m talkteach.sota.report`, `scripts/sota/run_all.sh` |

## Step details

### 1. DEFINE — pre-register the experiment

Every experiment in `OVERALL.md` Part B (E01–E30) is pre-registered with:

- **Metric**: what we measure (WER, CER, RTF, Cohen's d, etc.)
- **Baseline**: the current known value (or "none — first measurement")
- **Definition of Done (DoD)**: what constitutes success
- **Feasibility tag**: `CPU-now`, `CPU-heavy`, `GPU-queued`, or `build`

The sweep runner reads YAML configs from `experiments/<name>.yaml`. Each config
declares the engine, base model, dataset, fixed parameters, and the parameter grid.
See `docs/learning-loops/HYPERPARAMETER_SWEEPS.md` for the full config format.

### 2. EXECUTE — run the measurement

Two execution paths:

| Path | Command | Use case |
|------|---------|----------|
| Sweep runner | `make experiment EXP=<name>` | Grid search over hyperparameters (LoRA rank, LR, epochs, batch size) |
| SOTA harness | `make sota` or `make sota-baseline` | Run one or all 15 SOTA domains through the benchmark harness |

The sweep runner (`backend/talkteach/obs/sweep_runner.py:141`) expands the
parameter grid into a cartesian product, runs each cell via `run_cell()`, and
records results. The SOTA harness (`backend/talkteach/sota/harness.py:64`)
downloads datasets, dispatches to the right measurement method per domain, and
scores against band thresholds.

### 3. RECORD — persist results

Two complementary recording layers:

**Per-run metrics** (`talkteach/obs/experiment.py`): One JSON object per line in
`<workdir>/metrics.jsonl`. Contains step, epoch, loss, WER, CER, and a wall-clock
timestamp. The UI reads this curve back for the Advanced-mode loss/WER chart.

**Cross-run registry** (`talkteach/obs/experiment_db.py`): SQLite database at
`~/.cache/talkteach/experiments.db`. Each experiment is a row with config hash,
WER/CER, git commit, domain ID, and tags. Supports querying, comparison, and
regression checking.

See `docs/learning-loops/EXPERIMENT_TRACKING.md` for the full schema and query
guide.

### 4. ANALYZE — compute statistics

`talkteach/sota/scoring.py` provides:

- Bootstrap 95% confidence intervals (n=10,000, seed=42) via `confidence_interval()`
- Cohen's d effect sizes via `cohens_d()`
- Band scoring: `score_against_bands()` maps a metric value to 0–1000 on the SOTA scale

The experiment DB CLI supports comparison and regression detection:

```bash
python -m talkteach.obs.experiment_db --compare <run_a> <run_b>
python -m talkteach.obs.experiment_db --best d01_wer_clean
```

See `docs/sota-benchmarks/METHODOLOGY.md` for the full statistical protocol.

### 5. APPLY — update the director

When a calibration sweep demonstrates a statistically significant improvement,
update the default in `backend/talkteach/director/policy.py`, record the
delta in `docs/architecture/DECISIONS.md` as a new D-entry, and move the
corresponding item in `docs/roadmap/ROADMAP_STATUS.md` toward `✅`.

See `docs/learning-loops/CALIBRATION_LOOP.md` for the end-to-end protocol and
`docs/ml/CALIBRATION.md` for the original calibration design.

### 6. GUARD — run safety checks

Every experiment result passes through `run_all_guardrails()` in
`backend/talkteach/reliability/guardrails.py:252`. The five guardrails are:

1. **NaN guard**: detect NaN/Inf in loss or gradients (critical)
2. **Bias detection**: per-demographic-group WER gap (warning)
3. **Hallucination scoring**: repetition ratio + words-per-second anomaly (warning)
4. **Data leakage**: speaker/sentence overlap between train and eval (critical — hard block)
5. **OOD detection**: confidence-score distribution check (warning)

Guardrails integrate into training as callback hooks and into CI as regression
checks (`make lint`, `make test` — 198 fast tests must stay green).

See `docs/learning-loops/GUARDRAILS.md` for the full guardrail specification.

### 7. REPORT — auto-generate the scoreboard

`python -m talkteach.sota.report` generates:

- `docs/sota-benchmarks/SCOREBOARD.md` — Markdown table with per-domain scores,
  bands, and metric values
- `docs/sota-benchmarks/SCOREBOARD.json` — machine-readable JSON with confidence
  intervals per metric

Results are also appended manually to `OVERALL.md` Part C for narrative context.

## Loop invariants

- **No `[SIMULATION]` results in real-path reports** (D-012). Simulation data is
  clearly marked and never drives policy changes.
- **Synthetic-TTS WER is an indicative proxy only** (OVERALL.md A.6.7). It must
  not drive changes to shipped `policy.py` defaults without real-audio calibration.
- **Speaker/sentence-disjoint eval split** (OVERALL.md A.6.2). The Mo3 guardrail
  enforces this — reports must name their eval-disjointness.
- **Every experiment entry pre-registers its metric, baseline, and DoD** before
  execution.

## Cross-references

| Doc | Covers |
|-----|--------|
| `docs/learning-loops/EXPERIMENT_TRACKING.md` | SQLite schema, querying, `metrics.jsonl` per-run curves |
| `docs/learning-loops/HYPERPARAMETER_SWEEPS.md` | YAML config format, sweep runner CLI, interpreting results |
| `docs/learning-loops/CALIBRATION_LOOP.md` | Director calibration pipeline end-to-end |
| `docs/learning-loops/GUARDRAILS.md` | NaN, bias, hallucination, leakage, OOD — all guardrails |
| `docs/learning-loops/AI_WORKFLOWS.md` | AI assistant integration (Claude Code, OpenCode, Copilot) |
| `docs/sota-benchmarks/README.md` | The 1000-point SOTA scale and band definitions |
| `docs/sota-benchmarks/DOMAINS.md` | All 15 domains with thresholds and SOTA references |
| `docs/sota-benchmarks/METHODOLOGY.md` | Statistical rigor: bootstrap CI, effect sizes, significance |
| `docs/sota-benchmarks/BASELINES.md` | Current TalkTeach baseline scores |
| `docs/sota-benchmarks/SCOREBOARD.md` | Auto-generated scoreboard table |
| `docs/sota-benchmarks/VALIDATION.md` | How to run validation, Docker, CI, troubleshooting |
| `docs/ml/CALIBRATION.md` | Original calibration protocol and `scripts/calibrate.py` |
| `docs/architecture/DECISIONS.md` | Decision log — where calibration changes are recorded. D-016/D-017/D-018 codify the standing engineering rules. |
| `docs/architecture/PLAN.md` | Implementation plan & standing engineering principles (first principles, OSS reuse, continuous discovery). |
| `OVERALL.md` | Part B: the 30-experiment program. Part C: results log. |
| `AGENTS.md` | Tool configuration for AI assistants |
