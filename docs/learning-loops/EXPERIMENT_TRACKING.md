# Experiment Tracking

TalkTeach tracks every experiment in a local SQLite database so results are
searchable, comparable, and never lost across sessions. The tracking system has
two layers:

1. **Per-run metrics** — append-only `metrics.jsonl` files in each training workdir
2. **Cross-run registry** — SQLite at `~/.cache/talkteach/experiments.db`

## Per-run metrics (`metrics.jsonl`)

Source: `backend/talkteach/obs/experiment.py`

Every training run writes one JSON object per evaluation point to
`<workdir>/metrics.jsonl`:

```json
{"step": 1, "epoch": 1.0, "loss": 0.9, "wer": 0.4, "t": 1719000000.0}
```

### Reading curves

```python
from talkteach.obs.experiment import read_curve, summarize

# Get all points
curve = read_curve("/path/to/workdir")

# Get summary stats
summary = summarize("/path/to/workdir")
# => {"points": 42, "best_wer": 0.132, "final_wer": 0.145, "final_loss": 0.87, "final_epoch": 5.0}
```

### Writing metrics

```python
from talkteach.obs.experiment import log_metrics

log_metrics("/path/to/workdir", step=100, epoch=2.0, loss=0.52, wer=0.28)
```

Non-finite values (NaN, ±Inf) are silently dropped so the log stays chartable.
Malformed lines from interrupted runs are skipped on read.

## Cross-run registry (SQLite)

Source: `backend/talkteach/obs/experiment_db.py`

### Schema

```sql
CREATE TABLE IF NOT EXISTS experiments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL UNIQUE,      -- unique ID for this run
    config_hash TEXT NOT NULL,             -- SHA-256 of config (first 16 chars)
    config      TEXT NOT NULL,             -- JSON of full hyperparameter config
    git_commit  TEXT NOT NULL,             -- short SHA of git HEAD at run time
    engine      TEXT NOT NULL,             -- whisper_lora, wav2vec2_ctc, etc.
    base_model  TEXT NOT NULL,             -- openai/whisper-tiny, etc.
    dataset     TEXT NOT NULL,             -- evaluation dataset name
    domain_id   TEXT,                      -- SOTA domain ID if applicable
    wer         REAL,                      -- final WER
    cer         REAL,                      -- final CER
    best_wer    REAL,                      -- best WER across all epochs
    best_cer    REAL,                      -- best CER across all epochs
    train_s     REAL,                      -- training wall-clock seconds
    epochs      INTEGER,                   -- number of epochs trained
    status      TEXT NOT NULL DEFAULT 'running',  -- running | completed | failed | cancelled
    notes       TEXT,                      -- free-text notes or error message
    started_at  TEXT NOT NULL,             -- ISO 8601 timestamp
    completed_at TEXT,                     -- ISO 8601 timestamp, set on completion/failure
    tags        TEXT                       -- JSON array of tags for filtering
);
```

### Indexes

```sql
CREATE INDEX idx_experiments_run_id ON experiments(run_id);
CREATE INDEX idx_experiments_engine ON experiments(engine);
CREATE INDEX idx_experiments_wer ON experiments(wer);
CREATE INDEX idx_experiments_status ON experiments(status);
CREATE INDEX idx_experiments_tags ON experiments(tags);
```

### Config hashing

Config dicts are hashed deterministically for deduplication:

```python
from talkteach.obs.experiment_db import hash_config

h = hash_config({"lora_rank": 8, "lr": 1e-4, "epochs": 5})
# => "a3f8..." (first 16 chars of SHA-256 of sorted JSON)
```

### Database location

Default: `~/.cache/talkteach/experiments.db`

Override via environment variable: `TALKTEACH_EXPERIMENT_DB=/path/to/custom.db`

The database uses WAL journal mode and enables foreign keys.

## CLI reference

The experiment DB module is directly invocable:

```bash
# Show the 10 most recent experiments
python -m talkteach.obs.experiment_db --recent 10

# Filter by engine
python -m talkteach.obs.experiment_db --engine whisper_lora --recent 20

# Filter by status
python -m talkteach.obs.experiment_db --status completed

# Filter by SOTA domain
python -m talkteach.obs.experiment_db --domain d01_wer_clean

# Show best result for a domain
python -m talkteach.obs.experiment_db --best d01_wer_clean

# Compare two runs head-to-head
python -m talkteach.obs.experiment_db --compare sweep_abc_001 sweep_abc_004

# Export all experiments to JSON
python -m talkteach.obs.experiment_db --export /tmp/all_experiments.json

# Query a custom database path
python -m talkteach.obs.experiment_db --db /custom/path.db --recent 50
```

Equivalent via Make:

```bash
make experiments-db    # Shows recent 10
```

## Programmatic API

### Logging a new experiment

```python
from talkteach.obs.experiment_db import log_experiment

row_id = log_experiment(
    run_id="lora_rank_8_2026-07-08_001",
    config={"lora_rank": 8, "lr": 1e-4, "epochs": 5},
    engine="whisper_lora",
    base_model="openai/whisper-tiny",
    dataset="librispeech_test_clean",
    domain_id="d01_wer_clean",
    tags=["lora_sweep", "calibration"],
)
```

### Updating metrics

```python
from talkteach.obs.experiment_db import update_metrics, mark_completed, mark_failed

# During training — update intermediate metrics
update_metrics(run_id, wer=0.35, cer=0.12, epochs=3)

# On completion — set status + final metrics
mark_completed(run_id, wer=0.28, cer=0.09, best_wer=0.24, train_s=342.1, epochs=5,
               notes="LoRA rank 8 converged well")

# On failure
mark_failed(run_id, error="CUDA OOM — batch_size too large")
```

### Querying

```python
from talkteach.obs.experiment_db import query_recent, best_by_domain, compare_runs, regression_check

# Get recent completed whisper_lora experiments
runs = query_recent(limit=20, engine="whisper_lora", status="completed")

# Get best WER for a domain
best = best_by_domain("d01_wer_clean")
# => {"run_id": "...", "best_wer": 0.052, ...} or None

# Compare two runs
cmp = compare_runs(run_a, run_b)
# => {"run_a": "run_a", "wer_a": 0.28, "run_b": "run_b", "wer_b": 0.35,
#     "delta_wer": -0.07, "winner": "run_a"}

# Check for regression
reg = regression_check("d01_wer_clean", current_wer=0.35, tolerance=0.01)
# => {"regression": True, "current_wer": 0.35, "prior_best": 0.28, "delta": 0.07}
```

## Integration with sweep runner

The sweep runner (`backend/talkteach/obs/sweep_runner.py`) automatically:
1. Calls `log_experiment()` with `status='running'` for each grid cell
2. Calls `mark_completed()` with final WER/CER on success
3. Calls `mark_failed()` with the exception message on failure
4. Tags all cells with the sweep name + `"sweep"` tag

This means every cell of every hyperparameter sweep is queryable and comparable.

## Integration with SOTA harness

The SOTA harness (`backend/talkteach/sota/harness.py`) produces `SOTAResult`
dataclasses that carry per-domain scores, but does *not* automatically write to
the experiment DB. For sweep-based SOTA validation (domains that require training
at multiple data sizes), the sweep runner handles DB recording.

For one-shot SOTA measurements (D01, D04, D06, D12), results are written to
`docs/sota-benchmarks/SCOREBOARD.md` and `SCOREBOARD.json` by
`python -m talkteach.sota.report`.

## Cross-references

- `backend/talkteach/obs/experiment.py:22` — `metrics_path()` and `log_metrics()`
- `backend/talkteach/obs/experiment_db.py:83` — `log_experiment()` entry point
- `backend/talkteach/obs/experiment_db.py:295` — CLI entry point
- `backend/talkteach/obs/sweep_runner.py:141` — `run_sweep()` integration
- `docs/learning-loops/HYPERPARAMETER_SWEEPS.md` — sweep config format
- `docs/learning-loops/README.md` — learning loop overview
- `docs/sota-benchmarks/METHODOLOGY.md` — statistical analysis of experiment data
