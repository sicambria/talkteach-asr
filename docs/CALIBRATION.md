# Calibrating the director (#6)

Every threshold and hyperparameter in `director/policy.py` and `audio/quality.py`
is a **proposed design default** drawn from the LoRA/Whisper literature (report
B.5) — not a value tuned against real recordings and hardware. This is honest
calibration debt: the director makes *sensible* choices, but we have not yet
*measured* that they are the best ones. This note is the protocol to fix that.

## The constants to tune

**Audio quality** (`audio/quality.py`) — judged against human-labelled clips:
`CLIP_FRACTION_MAX`, `RMS_QUIET_DBFS`, `SILENCE_FRAME_DBFS`, `SILENCE_FRACTION_MAX`,
`SNR_MIN_DB`, `MIN_DURATION_S`. The target metric is **agreement with a human**:
the fraction of clips where the checker's GOOD/BAD verdict matches a labeller.

**Director policy** (`director/policy.py`) — judged against held-out WER:
`MIN_TARGET_MINUTES` / `adaptive_target`, the VRAM tiers (`_TIER_PARAKEET`,
`_TIER_WHISPER_SMALL`), the epochs/LR/patience schedule in `_choose_schedule`,
LoRA rank/alpha, and the effective-batch target in `_choose_batch`.

## What to sweep against

- **Quality thresholds**: a few hundred child/adult clips, each hand-labelled
  good/bad with a reason. Reuse Common Voice + the self-test toy set as a start.
- **Policy hyperparameters**: small labelled speech sets per data-size bucket
  (≈15 min / 60 min / 2 h+) and per VRAM tier. Sweep one constant at a time,
  re-train, measure held-out WER, keep the value that minimises WER without
  destabilising the run (watch the NaN-guard / early-stop).
- **Hardware**: at minimum a CPU-only laptop, a 6–8 GiB GPU, and a ≥16 GiB GPU,
  so the tier boundaries are validated where they actually flip.

## The harness — `scripts/calibrate.py`

```bash
python scripts/calibrate.py --constant SNR_MIN_DB --values 6,8,10,12 --data ./labelled
```

It sweeps one constant over candidate values and writes `calibration_results.json`
(`{constant, value, metric, note}` per row). The sweep loop and reporting are
real; the per-value **evaluator** (re-run the quality check, or re-train and
measure WER) is the part to wire in — it needs labelled audio and the `[ml]`
extras, so it lives in the calibration workflow, not the sandbox.

## Recording results

Each calibrated constant gets a one-line entry: old default → chosen value, the
dataset/hardware it was measured on, and the metric delta. Record it in
`DECISIONS.md` (a new D-entry) so the change is auditable, then update the
constant and its `# proposed default` comment. The matrix (`ROADMAP_STATUS.md`)
moves #6 from 🟡 toward ✅ as constants are tuned.

## Then: refine from telemetry

Once opt-in telemetry exists (D-008 — strictly off by default, never for a kids'
app without explicit consent), aggregate *anonymised* outcome stats (final WER,
data minutes, hardware tier) to refine the defaults across many real runs. This
is the long-tail step; it never gates a release and never phones home silently.

## Status

**Tier C** (#6). The protocol and the `scripts/calibrate.py` harness exist; the
real evaluator, the labelled datasets, and the GPU sweeps are pending. Until then
the constants remain documented *proposed defaults* and the director says so in
`plan.rationale`.
