# Hyperparameter Sweeps

Automated grid-search over training hyperparameters, powered by the sweep runner
in `backend/talkteach/obs/sweep_runner.py`. Sweeps are the primary mechanism for
director calibration (E19–E26 in `OVERALL.md` Part B).

## YAML config format

Sweeps are defined as YAML files in `experiments/<name>.yaml`:

```yaml
name: lora_rank_sweep
description: Sweep LoRA rank {4,8,16,32} on whisper-tiny with 15 min of training data
engine: whisper_lora
base_model: openai/whisper-tiny
dataset: librispeech_train_clean_100
train_minutes: 15
eval_dataset: librispeech_test_clean
eval_clips: 50
domain_id: d01_wer_clean           # optional — links to a SOTA domain
fixed_params:
  epochs: 5
  lr: 1e-4
  freeze_encoder: true
  lora_alpha: "auto"               # "auto" resolves to 2 * lora_rank
grid:
  lora_rank: [4, 8, 16, 32]
```

### Config fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Human-readable name; used as run_id prefix |
| `description` | no | Free-text description of the sweep's purpose |
| `engine` | yes | Engine name: `whisper_lora`, `wav2vec2_ctc`, etc. |
| `base_model` | yes | HF model ID: `openai/whisper-tiny`, `openai/whisper-small`, etc. |
| `dataset` | yes | Training dataset (e.g., `librispeech_train_clean_100`) |
| `train_minutes` | no | Training data duration in minutes (default: 15) |
| `eval_dataset` | yes | Evaluation dataset (e.g., `librispeech_test_clean`) |
| `eval_clips` | no | Number of eval clips to score (default: 50) |
| `domain_id` | no | SOTA domain ID for result tracking |
| `fixed_params` | no | Parameters held constant across all grid cells |
| `grid` | yes | Parameter grid for sweeping (cartesian product) |

### `auto` parameter resolution

The value `"auto"` for certain parameters triggers automatic resolution:

- `lora_alpha: "auto"` → `lora_alpha = 2 * lora_rank`

This is implemented in `resolve_auto_params()` at `sweep_runner.py:58`. More
auto-resolutions can be added as needed.

### Grid expansion

The grid is expanded as a cartesian product. For example:

```yaml
grid:
  lora_rank: [4, 8]
  lr: [1e-4, 2e-4]
```

Produces 4 cells:

1. `{lora_rank: 4, lr: 1e-4}`
2. `{lora_rank: 4, lr: 2e-4}`
3. `{lora_rank: 8, lr: 1e-4}`
4. `{lora_rank: 8, lr: 2e-4}`

## Launching sweeps

### Via Make

```bash
make experiment EXP=lora_rank_sweep
```

This runs `python -m talkteach.obs.sweep_runner --config experiments/lora_rank_sweep.yaml`.

### Direct CLI

```bash
python -m talkteach.obs.sweep_runner --config experiments/lora_rank_sweep.yaml

# Custom workdir
python -m talkteach.obs.sweep_runner --config experiments/lora_rank_sweep.yaml \
    --workdir /tmp/sweep_output

# Custom DB path
python -m talkteach.obs.sweep_runner --config experiments/lora_rank_sweep.yaml \
    --db ~/my_experiments.db

# Export results to JSON
python -m talkteach.obs.sweep_runner --config experiments/lora_rank_sweep.yaml \
    --json results.json
```

### CLI options

| Option | Description |
|--------|-------------|
| `--config PATH` | Required. Path to sweep config YAML |
| `--workdir PATH` | Working directory for training artifacts (default: `backend/.data/sweeps/`) |
| `--db PATH` | Experiment database path (default: `~/.cache/talkteach/experiments.db`) |
| `--json PATH` | Write results JSON to this path after the sweep |

### Overriding workdir via environment

```bash
TALKTEACH_SWEEP_DIR=/mnt/fast_scratch/sweeps python -m talkteach.obs.sweep_runner --config ...
```

## Interpreting results

The sweep runner prints per-cell WER/CER as each cell completes, and a summary
with the best cell at the end:

```
[sweep] lora_rank_sweep: 4 combinations from grid ['lora_rank', 'lora_alpha']

[sweep] Cell 1/4: {'lora_rank': 4, 'lora_alpha': 'auto'}
  run_id: lora_rank_sweep_a3f8e2c1_000
  WER: 0.3520 CER: 0.1240

[sweep] Cell 2/4: {'lora_rank': 8, 'lora_alpha': 'auto'}
  run_id: lora_rank_sweep_b4d9f3a2_001
  WER: 0.2810 CER: 0.0980

...

[sweep] Best: lora_rank_sweep_e6a1c4b3_003 WER=0.2450
  lora_rank: 32
  lora_alpha: 64
```

### Querying sweep results

All cells are recorded in the experiment DB with the sweep name and `"sweep"`
tag. Query them:

```bash
# Find all cells from a specific sweep
python -m talkteach.obs.experiment_db --recent 50 | grep lora_rank_sweep

# Compare the best two cells
python -m talkteach.obs.experiment_db --compare \
    lora_rank_sweep_e6a1c4b3_003 lora_rank_sweep_a3f8e2c1_000
```

### Statistical analysis

For rigorous comparison, use the scoring utilities:

```python
from talkteach.sota.scoring import cohens_d, confidence_interval
from talkteach.obs.experiment_db import query_recent

# Get per-clip WER values from metrics.jsonl
from talkteach.obs.experiment import read_curve
curve = read_curve(workdir)

# Compute bootstrap CI
ci = confidence_interval(per_clip_wer, n_bootstrap=10000)

# Effect size between two configs
d = cohens_d(wer_config_a, wer_config_b)
```

See `docs/sota-benchmarks/METHODOLOGY.md` for the full statistical protocol.

## Example sweep configs

### LoRA rank sweep (E19)

```yaml
name: lora_rank_calibration
description: Pre-registered E19 — sweep LoRA rank {4,8,16,32} per data bucket
engine: whisper_lora
base_model: openai/whisper-tiny
dataset: librispeech_train_clean_100
train_minutes: 15
eval_dataset: librispeech_test_clean
eval_clips: 50
domain_id: d01_wer_clean
fixed_params:
  epochs: 5
  lr: 1e-4
  freeze_encoder: true
  lora_alpha: "auto"
grid:
  lora_rank: [4, 8, 16, 32]
```

### Learning rate sweep (E20)

```yaml
name: lr_calibration
description: Pre-registered E20 — sweep LR {5e-5,1e-4,2e-4,5e-4}
engine: whisper_lora
base_model: openai/whisper-tiny
dataset: librispeech_train_clean_100
train_minutes: 15
eval_dataset: librispeech_test_clean
eval_clips: 50
domain_id: d01_wer_clean
fixed_params:
  epochs: 5
  lora_rank: 8
  lora_alpha: "auto"
  freeze_encoder: true
grid:
  lr: [5e-5, 1e-4, 2e-4, 5e-4]
```

### Epochs × data quantity (E21)

```yaml
name: epochs_data_quantity
description: Pre-registered E21 — validate _choose_schedule breakpoints
engine: whisper_lora
base_model: openai/whisper-tiny
dataset: librispeech_train_clean_100
train_minutes: 15
eval_dataset: librispeech_test_clean
eval_clips: 50
domain_id: d01_wer_clean
fixed_params:
  lora_rank: 8
  lora_alpha: "auto"
  lr: 1e-4
  freeze_encoder: true
grid:
  epochs: [1, 3, 5, 8, 12]
  train_minutes: [5, 15, 30]
```

### Effective batch size sweep (E24)

```yaml
name: batch_size_calibration
description: Pre-registered E24 — sweep effective batch {4,8,16,32}
engine: whisper_lora
base_model: openai/whisper-tiny
dataset: librispeech_train_clean_100
train_minutes: 15
eval_dataset: librispeech_test_clean
eval_clips: 50
domain_id: d01_wer_clean
fixed_params:
  epochs: 5
  lora_rank: 8
  lora_alpha: "auto"
  lr: 1e-4
  freeze_encoder: true
  batch_size: 4
grid:
  grad_accum: [1, 2, 4, 8]
```

## Guardrails during sweeps

Sweeps automatically exercise the following guardrails per cell:

- Each cell is wrapped in try/except — failures are recorded as `failed` status
  in the DB with the error message
- Disk guard: `keep_artifacts` defaults to `false` in `plan_config`
- NaN guard: the underlying training loop checks for NaN loss/gradients

See `docs/learning-loops/GUARDRAILS.md` for all guardrails.

## Sweep → director calibration pipeline

When a sweep identifies a clear winner (statistically significant improvement
over the current default), the result feeds into the calibration loop:

1. Record result in experiment DB (automatic)
2. Compute effect size vs. current default via `cohens_d()`
3. If significant and replicated: update `director/policy.py` default
4. Record the delta in `docs/architecture/DECISIONS.md`
5. Update `docs/roadmap/ROADMAP_STATUS.md`

See `docs/learning-loops/CALIBRATION_LOOP.md` for the full end-to-end protocol.

## Cross-references

- `backend/talkteach/obs/sweep_runner.py:141` — `run_sweep()` entry point
- `backend/talkteach/obs/sweep_runner.py:242` — CLI entry point
- `backend/talkteach/obs/sweep_runner.py:50` — `expand_grid()` cartesian product
- `backend/talkteach/obs/sweep_runner.py:58` — `resolve_auto_params()`
- `backend/talkteach/obs/experiment_db.py` — experiment registry schema and API
- `docs/learning-loops/EXPERIMENT_TRACKING.md` — querying sweep results
- `docs/learning-loops/CALIBRATION_LOOP.md` — sweep → director calibration pipeline
- `docs/learning-loops/README.md` — learning loop overview
- `docs/sota-benchmarks/METHODOLOGY.md` — statistical analysis of sweep results
- `OVERALL.md` Part B — E19–E26 calibration experiments
