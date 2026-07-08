# SOTA Methodology — Statistical Rigor

Every SOTA score is backed by a documented statistical protocol. This is not
optional: unmeasured variance, small samples, or data leakage can inflate a score
by 100+ points, creating the illusion of progress. The protocol is enforced by
the Mo3 guardrail and codified in `backend/talkteach/reliability/guardrails.py:172`
(data leakage) and `backend/talkteach/sota/scoring.py:37` (confidence intervals).

## Core statistical tools

### Bootstrap confidence intervals

Source: `backend/talkteach/sota/scoring.py:37`

```python
def confidence_interval(
    values: Sequence[float],
    n_bootstrap: int = 10000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
```

Parameters:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `n_bootstrap` | 10,000 | Large enough for stable percentile estimates; cheap on per-clip WER arrays |
| `alpha` | 0.05 | Standard 95% confidence level |
| `seed` | 42 | Fixed for reproducibility across runs |

The bootstrap resamples the original data with replacement `n_bootstrap` times,
computes the mean of each resample, and returns the 2.5th and 97.5th percentiles
of the bootstrap distribution. This gives a 95% CI without assuming normality.

For tiny samples (n < 3), the CI is degenerate — the function returns
`(mean, mean)` since bootstrap is unreliable on near-empty data.

### Cohen's d effect size

Source: `backend/talkteach/sota/scoring.py:65`

```python
def cohens_d(group_a: Sequence[float], group_b: Sequence[float]) -> float:
```

Effect size = difference in means / pooled standard deviation.

Interpretation:

| Cohen's d | Magnitude | Action |
|-----------|-----------|--------|
| d > 0.8 | Large | Clear winner — update default |
| 0.5 < d ≤ 0.8 | Medium | Promising — replicate on real audio |
| 0.2 < d ≤ 0.5 | Small | Signal exists but noisy — larger sample needed |
| d < 0.2 | Negligible | Default is fine; no change |

### Gini coefficient for demographic equity

Source: `backend/talkteach/sota/scoring.py:94`

```python
def demographic_equity_gini(per_group_metrics: dict[str, float]) -> float:
```

Gini coefficient of per-demographic-group metrics. 0 = perfect equity (all
groups have identical WER). Values near 1 = extreme inequity. This complements
the bias guardrail's simpler max-min gap check.

## Minimum sample sizes

Each domain specifies a minimum number of eval clips (or speakers) for
statistical validity:

| Domain | Min samples | Rationale |
|--------|-------------|-----------|
| D01 Clean WER | 100 | Standard LibriSpeech test-clean subset |
| D02 Spontaneous | 100 | Common Voice diversity needs more samples |
| D03 Training efficiency | 5 | Training runs are expensive; 5 repetitions suffices |
| D04 RTF | 100 | Per-clip RTF variance can be wide |
| D05 Data efficiency | 50 | Small-data regime — every sample matters |
| D06 Noise robustness | 50 | 5 SNR levels × 10 clips each |
| D07 Multilingual | 100 | Per-language sample size |
| D08 Export fidelity | 50 | Quantization WER differences are small — need precision |
| D09 Augmentation | 50 | Small-data regime |
| D10 Decoding | 30 | Hotword bias evaluation is targeted |
| D11 Long-form | 10 | 60-minute audio is expensive to process |
| D12 Speaker equity | 100 | Need ≥10 speakers to estimate variance |
| D13 Director accuracy | 20 | Each scenario is a config evaluation |
| D14 Quality gate | 200 | Human labels are noisy — need large set |
| D15 Resource efficiency | 20 | Pipeline-level measurement is costly |

The harness enforces these minimums — if fewer samples are available, the result
is flagged in the domain's `notes` field.

## Statistical significance for calibration

When comparing a new default against the current one:

1. Compute the WER difference per clip (or per speaker, or per scenario)
2. Compute the bootstrap 95% CI of the mean difference
3. Compute Cohen's d effect size
4. **Decision rule**: update the default if and only if:
   - d > 0.5 (medium+ effect)
   - CI excludes zero (statistically significant at 95% level)
   - The measurement is on real audio (not synthetic TTS proxy — A.6.7)
   - The result replicates on a second, independent dataset

### Replication requirement

A single calibration sweep is not sufficient to change a shipped default. The
winning configuration must be **replicated**:

1. **Same dataset, different split** — confirm the winner on a held-out fold
2. **Different dataset** — confirm on Common Voice if calibrated on LibriSpeech
3. **Different hardware tier** — CPU-only and GPU tiers may have different
   optimal defaults; each tier must be independently calibrated

### Statistical power analysis (rule of thumb)

For WER comparisons with typical variance:

| Desired detectable effect | Approx. samples needed (per group) |
|--------------------------|-------------------------------------|
| Δ WER = 5 pp | ~30 clips |
| Δ WER = 2 pp | ~100 clips |
| Δ WER = 1 pp | ~300 clips |
| Δ WER = 0.5 pp | ~800 clips |

These are rough estimates assuming WER std ≈ 0.10 per clip. For more precise
power analysis, run a pilot study and use the observed variance.

## Reproducibility

### Fixed random seed

All stochastic operations in the SOTA pipeline use a fixed seed:

- `random.seed(42)` for the bootstrap resampling
- `numpy.random.seed(42)` for noise generation
- `torch.manual_seed(42)` for training (when applicable)

The `SOTAHarness` constructor accepts a `seed` parameter (default 42), passed
through to `confidence_interval()` and `generate_synthetic_noise()`.

### Git commit tracking

Every experiment row in the experiment DB records the git commit SHA at run
time. Every `SOTAResult` carries the commit SHA. This means any score can be
traced back to the exact code that produced it.

### Deterministic config hashing

Config dicts are hashed deterministically via `hash_config()` in
`experiment_db.py:67`, which sorts keys before JSON serialization and computes
SHA-256. Two identical configs always produce the same hash.

## Eval-disjointness (the Mo3 guardrail)

Source: `OVERALL.md` A.6.2 and `backend/talkteach/reliability/guardrails.py:172`

The most common source of illusory gains: overlapping data between train and
eval. The Mo3 guardrail enforces:

1. **Speaker-disjoint split**: zero speakers appear in both train and eval
2. **Sentence-disjoint split**: zero sentences appear in both train and eval
   (enforced by sentence-hash deduplication)

The `check_data_leakage()` guardrail is severity **critical** — a hard block
that prevents training from proceeding. Every SOTA result must state its
eval-disjointness in its notes.

### Why random splits fail

The product's default held-out split is a random 10% with no overlap guard.
For LibriSpeech, this means ~10% of speakers appear in *both* train and
eval, and since LibriSpeech sentences repeat across speakers, sentence overlap
is also common. A model that memorizes speaker voiceprints or sentence patterns
will appear to have lower WER than it actually does. The Mo3 guardrail fixes
this.

## Scoring and banding

Source: `backend/talkteach/sota/scoring.py:128`

The `score_against_bands()` function maps a measured value to a 0–1000 score.
It walks the band thresholds from highest to lowest and returns the first
band the value meets or beats.

- **Lower-is-better metrics** (WER, CER, RTF, deltas): value ≤ threshold to
  achieve that score
- **Higher-is-better metrics** (language count, reduction rate, AUC, match
  rate): value ≥ threshold to achieve that score

If the value falls below the lowest band, the score is `lowest_band - 100`
(e.g., 500 if bronze is 600). A value of -1.0 (sentinel for "not measured")
always returns 0 with band "unmeasured."

### Confidence intervals and bands

A SOTA score is reported as a point estimate (the mean metric value). The 95%
CI is also computed and recorded in `SOTAResult.confidence_95`. If the CI
straddles a band boundary, the result's `notes` should mention this ambiguity.

Example: WER = 0.052 with 95% CI [0.048, 0.056]. The point estimate scores 700
(silver, ≤ 5.0%), but the upper bound of the CI crosses into bronze territory.
The notes should say: "Point estimate is silver (700), but CI upper bound
touches bronze — larger sample recommended."

## WER aggregation

Source: `backend/talkteach/sota/scoring.py:163`

Per-clip WER values are aggregated in two ways:

1. **Simple mean**: `mean(wer_per_clip)` — treats all clips equally
2. **Duration-weighted mean**: `sum(wer_i * duration_i) / sum(duration_i)` —
   longer clips contribute more

The `aggregate_wer()` function returns both. Duration-weighted is fairer when
clip lengths vary widely (e.g., Common Voice has clips from 1s to 20s), but
simple mean is more common in the literature and enables direct comparison.

## Reporting standards

Every SOTA result in a report or scoreboard must state:

1. The **metric value** (e.g., WER = 0.052)
2. The **95% CI** (e.g., [0.048, 0.056])
3. The **number of samples** (e.g., n = 100 clips)
4. The **eval-disjointness** (e.g., "speaker-disjoint, sentence-disjoint")
5. Whether the run was **real path** or `[SIMULATION]` (never the latter)
6. Whether the data was **real audio** or **synthetic TTS** (the latter is a
   proxy — A.6.7)
7. The **engine** and **base model** used
8. The **git commit** at run time

## Cross-references

- `backend/talkteach/sota/scoring.py:37` — `confidence_interval()`
- `backend/talkteach/sota/scoring.py:65` — `cohens_d()`
- `backend/talkteach/sota/scoring.py:94` — `demographic_equity_gini()`
- `backend/talkteach/sota/scoring.py:128` — `score_against_bands()`
- `backend/talkteach/sota/scoring.py:163` — `aggregate_wer()`
- `backend/talkteach/reliability/guardrails.py:172` — `check_data_leakage()` Mo3 guardrail
- `docs/sota-benchmarks/README.md` — the 1000-point scale
- `docs/sota-benchmarks/DOMAINS.md` — per-domain min_samples and thresholds
- `docs/sota-benchmarks/VALIDATION.md` — how to run benchmarks with proper seeds
- `docs/learning-loops/GUARDRAILS.md` — all guardrails including data leakage
- `docs/learning-loops/CALIBRATION_LOOP.md` — calibration protocol using these statistics
- `OVERALL.md` A.6 — mandatory guardrails including eval-disjointness
