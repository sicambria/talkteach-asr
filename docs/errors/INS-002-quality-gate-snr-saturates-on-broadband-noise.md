# INS-002 — Quality Gate SNR Estimate Saturates to 60 dB on Broadband Noise

**Date:** 2026-07-09  
**Type:** reference  
**Area:** audio / quality gate  
**Status:** active  
**Trigger:** D14 quality-gate measurement — noised clips (worst inputs) received the gate's BEST SNR score
**Guardrail Links:** `backend/talkteach/sota/harness.py` (`measure_quality_gate` detects the 60 dB ceiling rate and abstains-with-finding instead of scoring a degenerate number), `scripts/sota/validate_d14_quality_gate.py` (runs it)
**Automation Links:** `backend/tests/test_sota_scoring.py` (unit test pins the ceiling-detection → abstain logic), `backend/talkteach/audio/quality.py` (defect site: `analyze_samples`)

## Summary

While turning D14 (quality-gate) into a real measurement — correlating the gate's SNR
score against *measured* downstream WER — the gate was found to assign its **maximum**
score to its **worst** inputs. Adding broadband white noise to clean LibriSpeech clips at
a realistic degrading level (≤12 dB SNR) drove measured WER up (0.10 → 0.40) while
`analyze_samples(...).est_snr_db` jumped to the **60 dB ceiling** for ~100% of noised
clips, versus a genuine 24–36 dB range on the clean originals.

Consequence for D14: any ROC-AUC / Pearson r computed over such a set is an artifact of a
constant sentinel (60) sitting above the real clean range, not a measure of the gate's
discrimination. D14 therefore **abstains with this finding** (`human_needed`) rather than
shipping a recipe-dependent number.

## Root Cause

`backend/talkteach/audio/quality.py` estimates SNR as speech-frame energy vs
**silence-frame** energy. When a clip has no frames below the silence threshold — exactly
what uniform broadband noise produces (every frame now carries noise energy) — the
`silent_mask` is empty and the estimator hits this fallback:

```python
elif not silent_mask.any():
    # No noise floor frames — assume a clean signal (cap high).
    est_snr_db = 60.0
```

The fallback assumes "no silence ⇒ continuous clean speech," but the other cause of "no
silence" is "speech buried in constant noise." For a gate whose entire job is *rejecting*
bad audio, defaulting to the best score in the ambiguous case is a quality-gate **escape**:
a recording made in constant background noise (fan, AC, street hum) has no silence floor →
is rated ~60 dB "clean" → is accepted for training.

## Prevention

- **Do not fix the gate in the D14-measurement change** — altering `est_snr_db` changes
  accept/reject behaviour across the whole app (import wizard, training data selection) and
  is separate blast radius. This note records the defect; the fix is its own scoped change.
- Candidate fix (for that later change): when `silent_mask` is empty, estimate the noise
  floor from a low percentile of *all* frame energies (or a spectral-flatness / stationary-
  noise estimator) instead of assuming clean; add a regression clip (clean + broadband
  noise) asserting `est_snr_db` drops.
- Until fixed, D14 stays `human_needed` with this mechanism as the reason — never a
  fabricated positive band.

## Guardrail Updates

- `measure_quality_gate` computes `snr_ceiling_rate` (fraction of noised clips pinned at the
  60 dB ceiling) and abstains when it exceeds 0.5 — the degenerate case can never be scored
  into a positive band.
- The abstention reason names this note, so the scoreboard row points a reader at the RCA.

## Automation Follow-Up

- [ ] Scoped follow-up: replace the `no-silence ⇒ 60 dB` fallback with a percentile/spectral
      noise-floor estimate; add the clean+noise regression clip to `backend/tests`.
- [ ] Re-enable a scored D14 once the estimator no longer saturates (broadband noise then
      yields a real SNR range, giving a non-degenerate AUC vs measured WER).
