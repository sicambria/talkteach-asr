# Director Calibration Loop

The end-to-end pipeline for tuning the director's constants (`policy.py` defaults
and `audio/quality.py` thresholds) against measured data. This is the mechanism
behind **M4** — "Calibrate the director" — the #1 recommended score-raiser from
`OVERALL.md` Part A.5.

## The calibration debt

Every threshold and hyperparameter in the director is a **proposed design
default** drawn from the LoRA/Whisper literature — not a value empirically tuned
against real recordings and hardware. This is honest calibration debt: the
director makes *sensible* choices, but none have been *measured* to be optimal.

The constants to tune are catalogued in `docs/ml/CALIBRATION.md`:

**Director policy** (`backend/talkteach/director/policy.py`):
- `MIN_TARGET_MINUTES` / `adaptive_target` (25/45 min breakpoints)
- VRAM tiers (`_TIER_WITH_GPU`, `_TIER_NO_GPU`)
- Schedule `_choose_schedule`: epochs, LR, freeze_encoder per data bucket
- LoRA rank (8/16) and alpha (= 2×rank)
- Effective-batch target (16)

**Audio quality** (`backend/talkteach/audio/quality.py`):
- `SNR_MIN_DB` (10)
- `CLIP_FRACTION_MAX` (0.005)
- `SILENCE_FRACTION_MAX` (0.8)
- `RMS_QUIET_DBFS` (−40)
- `MIN_DURATION_S` (0.4)

## The calibration protocol

```
  Data Labels → Sweep → Measure → Statistical Test → Update Defaults → Record in DECISIONS.md
```

### Step 1: Data Labels

For **quality thresholds**: hand-label a few hundred speech clips as GOOD/BAD
with a reason. Common Voice + the self-test toy set is the starting point. The
target is human agreement.

For **policy hyperparameters**: use a small labelled speech set per data-size
bucket (≈15 min / 60 min / 2 h+) and per hardware tier (CPU-only, 6–8 GiB GPU,
≥16 GiB GPU).

### Step 2: Sweep

Run a hyperparameter sweep over candidate values. One constant at a time.
Re-train and measure held-out WER for each candidate.

```bash
make experiment EXP=snr_min_db_calibration
```

The sweep runner (`backend/talkteach/obs/sweep_runner.py`) iterates the grid,
records per-cell WER/CER to the experiment DB, and identifies the best cell.

See `docs/learning-loops/HYPERPARAMETER_SWEEPS.md` for the YAML config format and
sweep runner CLI.

### Step 3: Measure

For each cell, measure the target metric:

- **Quality thresholds**: agreement with human labels (fraction of clips where
  the checker's GOOD/BAD matches the human)
- **Policy hyperparameters**: held-out WER on a speaker/sentence-disjoint
  evaluation set

The measurement must be on **real audio** — synthetic TTS WER is an indicative
proxy only (OVERALL.md A.6.7) and does **not** drive shipped `policy.py` changes.

### Step 4: Statistical Test

Apply the statistical protocol from `docs/sota-benchmarks/METHODOLOGY.md`:

```python
from talkteach.sota.scoring import cohens_d, confidence_interval

# Compute effect size of best candidate vs. current default
d = cohens_d(wer_best_candidate, wer_current_default)

# Bootstrap confidence interval on the WER difference
ci = confidence_interval(wer_differences, n_bootstrap=10000, seed=42)
```

Thresholds for action:

| Result | Action |
|--------|--------|
| Cohen's d > 0.5 AND CI excludes zero | Update default (large, reliable effect) |
| Cohen's d 0.2–0.5 OR CI straddles zero | Flag as "promising — needs replication" |
| Cohen's d < 0.2 | Default is fine; no change |

### Step 5: Update Defaults

When a sweep proves a better value with statistical significance:

1. Edit `backend/talkteach/director/policy.py` — change the constant
2. Update the `# proposed default` comment to `# calibrated — see D-NNN`
3. Verify the director still produces sensible plans for all hardware tiers

For quality thresholds, edit `backend/talkteach/audio/quality.py`.

### Step 6: Record in DECISIONS.md

Create a new D-entry in `docs/architecture/DECISIONS.md`:

```
### D-NNN — Calibrated <constant> from <old_value> to <new_value>

Context: calibration sweep EXX showed a statistically significant improvement.
Options (score /100):
  1. <new_value>  92 — Cohen's d = X.XX, CI [...], best WER Y.YY
  2. <old_value>  70 — previous proposed default
Decision: <new_value>.
Consequence: updated in policy.py; tested on CPU, 6 GiB GPU, 16 GiB GPU.
```

Then update `docs/roadmap/ROADMAP_STATUS.md` — move the corresponding
calibration item toward `✅`.

## The original calibration harness

The original calibration protocol is defined in `docs/ml/CALIBRATION.md` and
`scripts/calibrate.py`:

```bash
python scripts/calibrate.py --constant SNR_MIN_DB --values 6,8,10,12 --data ./labelled
```

This sweeps one constant over candidate values and writes
`calibration_results.json`. The sweep loop and reporting are real; the per-value
**evaluator** (re-run quality check, or re-train and measure WER) is the part
that the sweep runner now fulfills.

## Hardware requirements

To fully calibrate the director, measurements must span all three hardware tiers:

| Tier | VRAM | Representative | Status |
|------|------|---------------|--------|
| CPU-only | 0 GiB | Laptop CPU | Runnable on this box |
| Low GPU | 6–8 GiB | GTX 1060, RTX 2060 | GPU-queued |
| High GPU | ≥16 GiB | RTX 3080+, A100 | GPU-queued |

The tier boundaries in `policy.py` (`_TIER_WITH_GPU` at 6 GiB and `_TIER_WITH_GPU`
at 16 GiB for whisper-medium) must be validated where the flip actually occurs.

## Synthetic proxy caveat (A.6.7)

All calibration sweeps on this box (CPU-only) use synthetic TTS speech because
real labelled audio is not yet available. Synthetic-TTS WER is an **indicative
proxy only** and must **not** drive changes to shipped `policy.py` defaults.

The honest calibration path is:

1. **Synthetic sweeps** (CPU-now): identify promising directions, rule out
   dead-ends, narrow the search space
2. **Real-audio replication** (needs labelled real-speech dataset): confirm the
   best candidates from synthetic sweeps on real speech
3. **Shipped defaults** update only after real-audio replication passes
   statistical significance

This is the "flag + defer" pattern: synthetic results inform priorities but
don't change defaults.

## Calibration experiments (from OVERALL.md Part B, G4)

| ID | Experiment | Constant | Status |
|----|-----------|----------|--------|
| E19 | LoRA rank {4,8,16,32} | `_choose_rank` | Pre-registered, P1 |
| E20 | LR {5e-5,1e-4,2e-4,5e-4} | `_choose_schedule` LR | Pre-registered, P1 |
| E21 | Epochs × data minutes | `_choose_schedule` breakpoints | Pre-registered, P1 |
| E22 | freeze_encoder on/off | `_choose_schedule` freeze | Pre-registered, P1 |
| E23 | LoRA target_modules | `_choose_modules` (hardcoded) | Pre-registered, P2 |
| E24 | Effective batch {4,8,16,32} | `_choose_batch` | Pre-registered, P2 |
| E25 | Quality thresholds | `audio/quality.py` constants | Pre-registered, P2 |
| E26 | adaptive_target sufficiency floor | `MIN_TARGET_MINUTES` | Pre-registered, P2 |

## Telemetry refinement (future)

Once opt-in telemetry exists (D-008 — strictly off by default, never phones
home), aggregate anonymised outcome stats (final WER, data minutes, hardware
tier) to refine defaults across many real runs. This is the long-tail step:
it never gates a release and never phones home silently.

## Cross-references

- `docs/ml/CALIBRATION.md` — original calibration protocol and `scripts/calibrate.py`
- `docs/learning-loops/HYPERPARAMETER_SWEEPS.md` — sweep config format and runner
- `docs/learning-loops/EXPERIMENT_TRACKING.md` — querying sweep results from DB
- `docs/learning-loops/GUARDRAILS.md` — guardrails that run during calibration
- `docs/sota-benchmarks/METHODOLOGY.md` — statistical significance protocol
- `docs/architecture/DECISIONS.md` — where calibration decisions are recorded
- `docs/roadmap/ROADMAP_STATUS.md` — calibration items status tracker
- `OVERALL.md` Part A.5 — current director constants (all uncalibrated)
- `OVERALL.md` Part B, G4 — pre-registered calibration experiments E19–E26
- `backend/talkteach/director/policy.py` — the constants to calibrate
- `backend/talkteach/audio/quality.py` — quality thresholds to calibrate
