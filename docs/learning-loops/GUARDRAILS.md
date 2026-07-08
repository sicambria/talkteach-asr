# ML Safety Guardrails

All guardrails live in `backend/talkteach/reliability/guardrails.py`. They are
the safety net that catches model quality issues, training accidents, and data
leakage **before** results are trusted or defaults are changed. Guardrails run
automatically during training (as callback hooks) and in CI (as regression
checks).

## Architecture

Each guardrail is a function that returns a `GuardrailResult` dataclass:

```python
@dataclass
class GuardrailResult:
    name: str                # e.g. "bias_detection", "hallucination_rate"
    passed: bool
    severity: str            # "critical" | "warning" | "info"
    value: float | None = None
    threshold: float | None = None
    detail: str = ""
    recommendation: str = ""
```

The aggregate `GuardrailReport` collects all results:

```python
@dataclass
class GuardrailReport:
    all_passed: bool = True
    results: list[GuardrailResult]
    critical_count: int = 0
    warning_count: int = 0
```

The master runner is `run_all_guardrails()` at `guardrails.py:252`. It accepts
all available data (loss values, per-group WER, transcripts, speaker sets,
confidence scores) and runs every guardrail for which data is provided.

## The five guardrails

### 1. NaN/Inf guard (`check_nan_gradient`)

Source: `backend/talkteach/reliability/guardrails.py:45`

Checks for NaN or Inf in:

- **Loss values**: `math.isnan(loss_value) or math.isinf(loss_value)`
- **Gradient norms** (optional): same check on `grad_norm`

| Condition | Severity | Recommendation |
|-----------|----------|----------------|
| NaN/Inf loss | **critical** | Roll back to last good checkpoint, reduce learning rate |
| NaN/Inf gradient | **critical** | Enable gradient clipping, reduce learning rate |
| Both clean | info | — |

This guardrail is already implemented in the training loop (`_whisper_train.py`).
The codified version ensures it's consistently applied and reportable.

### 2. Bias detection (`check_bias_demographic`)

Source: `backend/talkteach/reliability/guardrails.py:73`

Checks for demographic bias by measuring the maximum WER gap between groups.

Input: `per_group_wer: dict[str, float]` — WER per demographic group.
Threshold: `max_gap = 0.15` (15 percentage points absolute difference).

| Condition | Severity | Recommendation |
|-----------|----------|----------------|
| Gap > 0.15 | warning | Collect more data for underrepresented groups |
| Gap ≤ 0.15 | info | — |
| < 2 groups | info | Bias check skipped (need ≥2 groups) |

The check uses the absolute WER difference between the best and worst group.
For more sophisticated equity measurement, `talkteach/sota/scoring.py:94`
provides `demographic_equity_gini()` which computes the Gini coefficient.

### 3. Hallucination scoring (`check_hallucination_rate`)

Source: `backend/talkteach/reliability/guardrails.py:110`

Detects hallucinated ASR output using three signals from the decoded transcript:

| Signal | Threshold | What it catches |
|--------|-----------|-----------------|
| Bigram repetition ratio | > 0.3 | "the the the the..." loops |
| Words per second (too slow) | < 0.5 wps | Stuck on silence, no output |
| Words per second (too fast) | > 5.0 wps | Nonsense rapid-fire output |

The repetition ratio is computed as `max(bigram_count) / total_words`. A high
ratio indicates the model is stuck in a repetition loop.

Severity: **warning** when any signal fires; **info** when clean.

### 4. Data leakage check (`check_data_leakage`)

Source: `backend/talkteach/reliability/guardrails.py:172`

**This is the Mo3 guardrail** — the hard block that prevents inflated,
illusory gains from overlapping train/eval data. It enforces `OVERALL.md` A.6.2:
speaker/sentence-disjoint eval split.

Inputs:
- `train_speakers: set[str]` — speaker IDs in the training set
- `eval_speakers: set[str]` — speaker IDs in the evaluation set
- `train_sentences: set[str]` (optional) — sentence hashes in training
- `eval_sentences: set[str]` (optional) — sentence hashes in evaluation

| Overlap | Severity | Action |
|---------|----------|--------|
| **Speaker overlap** | **critical** | **Hard block** — training must not proceed. Split by SPEAKER, not randomly. |
| Sentence overlap (with disjoint speakers) | **critical** | Remove overlapping sentences from eval. |
| No overlap | info | Clean — eval is truly disjoint. |

This guardrail is a **hard block**: training should not proceed if it fails.
It is cheaper to fix the split than to throw away a run.

### 5. OOD confidence check (`check_ood_confidence`)

Source: `backend/talkteach/reliability/guardrails.py:215`

Detects out-of-distribution (OOD) audio via confidence scores from the model's
decoder.

Input: `confidence_scores: list[float]` — per-clip mean confidence.
Thresholds:
- `confidence_threshold = 0.3` — clips below this are "low confidence"
- `max_low_confidence_ratio = 0.1` — at most 10% of clips may be low confidence

| Condition | Severity | Recommendation |
|-----------|----------|----------------|
| > 10% clips below 0.3 confidence | warning | Model may be OOD — add more in-domain training data |
| ≤ 10% low confidence | info | — |
| No scores available | info | — |

This guardrail is most useful during evaluation of a fine-tuned model on a
diverse or unseen test set.

## Integration points

### Training callback hooks

Guardrails can be wired into the training loop as callbacks:

- **Per-epoch**: run NaN check on the current loss; if critical, trigger
  rollback to `last_good_checkpoint` (E08 — currently unwired, see `OVERALL.md` A.4)
- **Per-evaluation**: run hallucination scoring on decoded samples; flag if
  the repetition rate spikes
- **Pre-train**: run data leakage check on the train/eval split; **hard block**
  if speakers overlap

### CI regression checks

In CI (`make lint` + `make test`), the 198 fast tests exercise guardrail
functions with synthetic data:

```python
def test_nan_guard_catches_nan_loss():
    result = check_nan_gradient(float("nan"))
    assert not result.passed
    assert result.severity == "critical"

def test_leakage_guard_blocks_speaker_overlap():
    result = check_data_leakage({"spk1", "spk2"}, {"spk2", "spk3"})
    assert not result.passed
    assert result.severity == "critical"

def test_bias_guard_skips_single_group():
    result = check_bias_demographic({"group_a": 0.15})
    assert result.passed  # skipped, not failed
```

### Pre-flight checks

The pre-flight system (`backend/talkteach/reliability/preflight.py`) is a
separate but related system. While guardrails monitor *training quality*,
pre-flight checks monitor *machine readiness*: disk space, RAM, GPU presence,
microphone availability. Pre-flight runs before training starts; guardrails
run during and after.

## Formatting reports

```python
from talkteach.reliability.guardrails import run_all_guardrails, format_report

report = run_all_guardrails(
    loss_value=0.34,
    per_group_wer={"male": 0.12, "female": 0.14},
    transcripts=["hello world", "test test test test test"],
    audio_durations=[2.0, 3.0],
    train_speakers={"spk1", "spk2", "spk3"},
    eval_speakers={"spk4", "spk5"},
    confidence_scores=[0.85, 0.72, 0.91, 0.68],
)

print(format_report(report))
# ============================================================
# GUARDRAIL REPORT
# ============================================================
# Status: ALL PASSED
# Critical: 0  Warnings: 0
#
# [PASS] nan_check (severity: info)
# [PASS] bias_demographic (severity: info)
#        Value: 0.0200  Threshold: 0.15
#        Detail: WER gap between best (0.120) and worst (0.140) group: 0.020
# [PASS] hallucination_check (severity: info)
#        Detail: OK (wps=1.2, repeat=0.17)
# [PASS] data_leakage (severity: info)
#        Detail: Disjoint: 3 train, 2 eval speakers, zero overlap
# [PASS] ood_confidence (severity: info)
#        Detail: OK — 0/4 clips below threshold
```

## Guardrail ↔ Security doc

The guardrails complement the security posture documented in D-004 (upload
sanitisation), D-005 (CSP), and D-008 (telemetry). While those guard against
*attacks* (path traversal, XSS, privacy leaks), these guard against *bad ML*
(NaN gradients, biased models, hallucinating decoders, data leakage, OOD
predictions). Both are required for a production-grade system.

## Guardrail invariants

- **No guardrail failure is silently swallowed.** Failed guardrails produce
  a `GuardrailReport` with `all_passed=False` and a readable summary.
- **Critical failures are hard blocks.** Data leakage and NaN loss/gradient
  severity `critical` means training should stop or not start.
- **Warnings are actionable.** Every warning carries a `recommendation` field
  telling the developer (or, in future, the user) what to do.
- **Guardrails are testable without ML deps.** All guardrail functions accept
  pure Python data and return pure Python results — no torch, no network.

## Cross-references

- `backend/talkteach/reliability/guardrails.py:45` — NaN/gradient check
- `backend/talkteach/reliability/guardrails.py:73` — bias detection
- `backend/talkteach/reliability/guardrails.py:110` — hallucination scoring
- `backend/talkteach/reliability/guardrails.py:172` — data leakage (Mo3 guardrail)
- `backend/talkteach/reliability/guardrails.py:215` — OOD confidence check
- `backend/talkteach/reliability/guardrails.py:252` — `run_all_guardrails()`
- `backend/talkteach/reliability/guardrails.py:292` — `format_report()`
- `backend/talkteach/reliability/preflight.py` — pre-flight checks (machine readiness)
- `backend/talkteach/sota/scoring.py:94` — `demographic_equity_gini()`
- `docs/architecture/DECISIONS.md` D-004, D-005, D-008 — security decisions
- `docs/architecture/OBSERVABILITY.md` — logging and telemetry posture
- `docs/learning-loops/CALIBRATION_LOOP.md` — guardrails during calibration
- `docs/learning-loops/README.md` — guard step in the learning loop
- `OVERALL.md` A.6 — mandatory guardrails from prior dead-ends
