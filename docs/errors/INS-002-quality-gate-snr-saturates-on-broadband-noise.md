# INS-002 — Quality Gate SNR Estimate Saturates to 60 dB on Broadband Noise

**Date:** 2026-07-09  
**Type:** reference  
**Area:** audio / quality gate  
**Status:** resolved  
**Trigger:** D14 quality-gate measurement — noised clips (worst inputs) received the gate's BEST SNR score
**Guardrail Links:** `backend/talkteach/audio/quality.py` (`_spectral_snr_db` replaces the 60 dB fallback with a spectral noise-floor estimate — the fix), `backend/talkteach/sota/harness.py` (`measure_quality_gate` still detects a genuine ceiling rate and abstains-with-finding), `scripts/sota/validate_d14_quality_gate.py` (runs it)
**Automation Links:** `backend/tests/test_audio.py` (calibration/regression probes: `test_snr_sweep_is_monotonic_and_tracks_true_snr`, `test_pure_broadband_noise_is_rejected`, `test_snr_gate_crosses_near_true_10db`), `backend/tests/test_sota_scoring.py` (pins ceiling-detection → abstain logic — still valid, now dormant)

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
**silence-frame** energy, where a frame is "silent" iff its level is below an **absolute**
threshold: `silent_mask = frame_dbfs < SILENCE_FRAME_DBFS` (`SILENCE_FRAME_DBFS = -45.0`
dBFS). When no frame falls below that threshold — exactly what uniform broadband noise at a
degrading level produces (every frame, including the pauses, now carries noise energy above
−45 dBFS) — the `silent_mask` is empty and the estimator hits this fallback:

```python
elif not silent_mask.any():
    # No noise floor frames — assume a clean signal (cap high).
    est_snr_db = 60.0
```

The fallback assumes "no silence ⇒ continuous clean speech," but the other cause of "no
silence" is "speech buried in constant noise." For a gate whose job is *rejecting* bad audio,
defaulting to the best score in the ambiguous case is a quality-gate **escape**.

**Scope of the evidence (do not overstate):** this is *directly demonstrated* here only for
**uniform, full-clip broadband noise at ≤~12 dB SNR** (the D14 widener) — the diagnostic is
threshold-sensitive: at ~18 dB SNR the estimate is still real (~18 dB), at ~12 dB and below it
saturates to 60 dB. Because the threshold is **absolute (−45 dBFS)**, real pause-containing
recordings are affected *when their background-noise floor lifts even the quietest frames above
−45 dBFS* — plausible for audibly noisy environments (fan/AC/street at a real level), but **not**
for quiet-room recordings whose pauses stay below −45 dBFS. The real-recording incidence is
**level-dependent and not directly measured here** — the scoped follow-up should quantify it.

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

## Resolution (2026-07-09)

The scoped fix landed in a worktree behind a pre-registered calibration check. `_spectral_snr_db`
replaces the `no-silence ⇒ 60 dB` fallback with a Welch-averaged spectral noise-floor estimate:
`10·log10(mean_psd / p10_psd)`, clamped `[0, 60]`. A flat spectrum (broadband noise) → ~0 dB; a peaky
one (clean tone / harmonic speech) → high dB. For additive broadband noise at true SNR *s* it recovers
`~10·log10(s_linear + 1)`, so `SNR_MIN_DB` (10 dB) is meaningful again. **Surgical:** only the
empty-`silent_mask` branch changed; the temporal branch and its calibration are untouched.

Measured (seed=0) `mix_noise` sweep on a structured base — true **3/8/10/15/20 dB → est
5.4/9.2/11.0/15.9/20.6 dB** (monotonic, crosses the gate at true 10 dB); pure broadband noise
**60 → 0.65 dB** (now rejected); a clean continuous tone stays **60** (no false reject). Because the
estimate no longer keys off the absolute −45 dBFS silence threshold, the earlier *level-dependent
real-noisy-room* caveat is substantially addressed: a noisy-room recording whose pauses clear −45 dBFS
now also gets a real spectral SNR instead of the 60 dB ceiling.

**D14 re-measured (real, bounded run — 40 clips, test-clean, seed=42):** `snr_ceiling_rate` **1.0 → 0.0**,
and the gate now genuinely predicts measured WER — `pearson_r = 0.64`, `ROC-AUC = 0.83`, no `degenerate`
flag. It returns `partial` (SNR component only, single engine) → correctly **excluded from the headline**
by the scope gate, but it is a real measure, not an abstention on a constant sentinel. A larger scored
run remains available via `validate_d14_quality_gate.py`; the artifact-abstention no longer applies.

## Automation Follow-Up

- [x] Scoped follow-up: replace the `no-silence ⇒ 60 dB` fallback with a spectral noise-floor estimate
      (`backend/talkteach/audio/quality.py:_spectral_snr_db`); regression probes added to
      `backend/tests/test_audio.py`.
- [x] D14 no longer saturates: broadband noise yields a real SNR range → non-degenerate AUC (0.83) vs
      measured WER on a bounded run; `snr_ceiling_rate` = 0.0. (Headline eligibility still gated by the
      `partial`/small-n scope rules — a scored *headline* band is a separate, non-fabricated decision.)
