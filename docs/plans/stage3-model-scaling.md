# Plan: Journey Stage 3 — Model-Size Scaling & Remaining Domains

**Date:** 2026-07-08  
**Type:** EXPERIMENT  
**Status:** PLANNED  
**Previous stages:** S1 (baseline, banked), S2 (fine-tuning, falsified)

## Objective

Close the remaining gap to SOTA (whisper-large-v3 @ 1.8% WER) and complete the SOTA scoreboard with the highest-value remaining domains.

## Current State

| Domain | Status | Score | Gap |
|--------|--------|-------|-----|
| D01 Clean WER | Measured | 800/gold | 0.89pp to SOTA (2.69% → 1.8%) |
| D04 RTF | Measured | 600/bronze | — |
| D06 Noise | Measured | 800/gold | — |
| D12 Speaker | Measured | 950/diamond (directional) | — |
| D02 Spontaneous | Blocked (B-001) | unmeasured | — |
| D07 Multilingual | Blocked (B-001) | unmeasured | — |
| D08 Export Fidelity | Unmeasured | unmeasured | — |
| D09-D11, D13-D15 | Unmeasured | unmeasured | — |

## Strategic Insight from S1+S2

**Fine-tuning doesn't help on in-domain data.** The pretrained models are already near-Pareto-optimal on LibriSpeech. The path to SOTA is through model size: whisper-small (2.69%) is within 0.89pp of whisper-large-v3 (1.8%). Larger pretrained models may close this gap entirely without any training.

## Stage 3 Hypothesis

Using a larger pretrained model (distil-large-v3, distil-large-v3.5, or medium) will reduce D01 WER from 2.69% to ≤2.0% (diamond band, 900+), potentially reaching ≤1.8% (SOTA, 1000/1000).

## Stage 3 Experiments

### E03: Model-Size Scaling on D01
- **Hypothesis:** distil-large-v3 or whisper-medium achieves WER ≤2.0% on LibriSpeech test-clean (diamond, 900+)
- **Metric:** WER on 100 test-clean clips
- **Baseline:** whisper-small @ 2.69% (800/gold)
- **Target:** ≤2.0% WER (diamond, 900)
- **DoD:** WER ≤2.0% OR documented ceiling for CPU-runnable models
- **Models to test:** distil-large-v3, distil-large-v3.5, whisper-medium
- **Protocol:** Measure WER on 50-100 test-clean clips per model. Compare to whisper-small baseline.
- **Risk:** CPU inference may be too slow (>10s/clip). Spike with 10 clips first.

### E04: Fix B-001 → D02 Spontaneous Speech
- **Hypothesis:** HF datasets v5 incompatibility is the sole blocker for D02/D07
- **Metric:** Common Voice test subset loads correctly
- **Baseline:** Current state: `datasets 5.0.0` + `torchcodec` missing
- **Target:** Load ≥50 Common Voice clips with transcripts
- **Protocol:** Either upgrade torchcodec or use a different audio loading path
- **Risk:** May require dependency changes with cascading effects

### E05: D08 Export Fidelity
- **Hypothesis:** CT2 int8 quantization introduces ≤0.5pp WER degradation vs fp32
- **Metric:** WER delta between fp32 inference and CT2 int8 inference
- **Baseline:** Literature reports Δ<0.1% for CT2 int8
- **Target:** Δ≤0.5pp WER
- **Protocol:** Measure WER with transformers fp32 vs faster-whisper int8 on same 100 clips
- **Note:** We already have both measurements — just need to pair them on identical clips

## Standards & Guardrails Evidence

- [x] Tests / shift-left: `backend/tests/test_whisper_train.py:8` — 198 fast tests pass before any experiment
- [x] Reused patterns / grounding: `scripts/sota/validate_d01_wer_clean.py:16` — SOTAHarness for WER; `backend/talkteach/director/plan_config.py:43` — plan_from_config for pinned plans
- [x] Security: N/A — benchmark measurements only, no user data or secrets involved
- [x] Evidence classification: `backend/talkteach/sota/scoring.py:14` — WER measured (banked) with 95% CI; model comparisons directional when n<100
- [x] Reproducibility: `backend/talkteach/sota/scoring.py:14` — fixed seed (42), normalized text, documented protocol in `docs/testing/journey-s1-real-audio-baseline.md`
- [x] Statistical validity: `backend/talkteach/sota/scoring.py:58` — bootstrap CI on per-clip WER; ≥50 clips for ≥5% difference detectability
- [x] Baseline / SOTA calibration: `backend/talkteach/sota/domains.py:46` — D01 bands anchored to whisper-large-v3 @ 1.8%; intermediate bands verified against published whisper model sizes

## Execution Order

1. **E03 (model scaling):** Quick spike — measure distil-large-v3 on 10 clips. If promising, scale to 50+. If too slow, document the CPU ceiling.
2. **E05 (export fidelity):** Pair existing measurements on same 100 clips. Lowest effort, immediate scoreboard gain.
3. **E04 (fix B-001):** Unblocks D02 and D07. Enables out-of-domain fine-tuning experiments.
4. **Remaining domains:** D09-D11, D13-D15 as resources permit.

## Success Criteria

- [ ] D01 score improved from 800/gold to ≥900/diamond (WER ≤2.0%)
- [ ] At least 2 additional domains scored (target: 6/15 measured, overall ≥800/gold)
- [ ] B-001 resolved or documented with concrete fix path
- [ ] Export fidelity characterized (D08 scored)
- [ ] All findings documented with proper evidence classification
