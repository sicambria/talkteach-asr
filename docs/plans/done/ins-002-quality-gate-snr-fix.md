# Plan — INS-002: fix the quality-gate SNR estimator that saturates to 60 dB on broadband noise

**Type:** BUG · **Blast radius:** app-wide accept/reject (audio quality gate) · **Isolation:** worktree

## Context
The audio quality gate estimates SNR as speech-frame vs *silence-frame* energy, where "silent"
is an **absolute** threshold: `silent_mask = frame_dbfs < SILENCE_FRAME_DBFS` (−45 dBFS,
`backend/talkteach/audio/quality.py:40,155`). When no frame falls below −45 dBFS — exactly what
uniform broadband noise at a degrading level produces (every pause now carries noise energy above
−45 dBFS) — `silent_mask` is empty and the estimator hits a degenerate fallback:

```python
elif not silent_mask.any():
    est_snr_db = 60.0   # backend/talkteach/audio/quality.py:171-173
```

It assigns the gate's **best** score to its **worst** inputs. That `est_snr_db` then feeds the noise
gate (`if speech_mask.any() and est_snr_db < SNR_MIN_DB` at `quality.py:179`), which sets `ClipQuality.ok`,
which app.py turns into the clip's `is_good` accept/reject bit (`backend/talkteach/app.py:306-308`) and
the director's "minutes of GOOD audio". So a noisy recording is not only mis-scored — it is **accepted
for training**. This was discovered while turning D14 into a real measurement (INS-002); the D14 harness
currently detects the 60 dB ceiling and abstains (`backend/talkteach/sota/harness.py:548-566`) rather
than score a degenerate AUC. This change fixes the estimator so the gate is honest and D14 can stop
abstaining *on the ceiling artifact*.

Full RCA: `docs/errors/INS-002-quality-gate-snr-saturates-on-broadband-noise.md`.

## Verified facts (this session)
- Defect site and fallback confirmed at `backend/talkteach/audio/quality.py:171-173`; the silence-present
  temporal branch (`quality.py:174-176`) is correct and stays untouched.
- `est_snr_db` consumers: the in-module noise gate (`quality.py:179`) and the D14 harness
  (`backend/talkteach/sota/harness.py:513`). `policy.py`'s only `snr` hits are augmentation config
  (`noise_snr_db`, `policy.py:84,96`) — **not** consumers of `est_snr_db`; the "changing policy.py"
  calibration guardrail (`AGENTS.md:64`) does not literally apply, but its *spirit* (pre-register a
  calibration check before changing accept/reject) does and is honored below.
- The existing "clean sine is ok" test (`backend/tests/test_audio.py:61-72`, asserts `est_snr_db >= 10`)
  uses a continuous 0.25-amplitude sine with **no** sub-−45 dBFS frames — it currently passes *via the
  60 dB fallback*. Any fix MUST keep this clean case scoring high, or it is a false-reject regression.
- No FFT/spectral helper exists in the codebase (`grep rfft|np.fft|welch|spectral` → none), so the noise
  floor is estimated with a small pure-numpy Welch periodogram built on the existing frame machinery
  (`_frame_rms`, `quality.py:101-112`).
- Ceiling→abstain logic is pinned by `backend/tests/test_sota_scoring.py:277`; it stays valid (still
  abstains on a real ceiling), it simply stops *firing* once the estimator no longer saturates.

## Design
**Surgical, not a rewrite.** Only the degenerate `not silent_mask.any()` branch changes; the temporal
silence-present branch and all its calibration are preserved. The boundary discontinuity (temporal SNR
for ≥1 silent frame vs spectral SNR for 0 silent frames) already existed (temporal vs 60) and is made
*more* honest, not introduced.

**Spectral noise-floor estimate.** When there are no silent frames, estimate the noise floor spectrally
via a Welch-averaged power spectrum:
- Window each non-overlapping frame (Hann), `rfft`, `|·|²`, average across frames → per-bin PSD (drop DC).
- `signal = mean(psd)`, `floor = percentile(psd, 10)` (clamped to `_DBFS_FLOOR`).
- `est_snr_db = clip(10·log10(signal/floor), 0, 60)`.

Why this is correct across the three regimes (Welch averaging over K frames drives a *flat* spectrum's
mean/percentile ratio → 1):
- **Clean tone / harmonic speech** → spiky PSD, tiny inter-harmonic floor → high ratio → high SNR (clean
  0.25 sine + tiny noise ≈ ~40 dB → stays GOOD, keeps `test_audio.py:72` green).
- **Speech buried in broadband noise** (D14 widener, ≤12 dB) → near-flat PSD → ratio ≈ 1 → low SNR →
  `< SNR_MIN_DB` → `ISSUE_TOO_NOISY` → correctly REJECTED.
- **Pure white noise** → flat PSD → ~0–2 dB → rejected.

New pure helper `_spectral_snr_db(x, frame_len)` beside `_frame_rms`; deterministic, numpy-only. It
must be safe on the degenerate inputs that reach this branch: the **sub-frame clip**
(`test_audio.py:81`, `_frame_rms` returns a single whole-signal frame) and an **all-equal PSD** — the
floor is clamped to `_DBFS_FLOOR` so the ratio never divides by zero nor returns a spurious high SNR,
and with `< 2` frames it returns `0.0` (no Welch average possible → cannot certify "clean").

**Why the estimator tracks true SNR (verify empirically, don't trust the algebra).** With a Welch-
averaged PSD, `mean(psd) = (S+N)/n_bins` and the low-percentile floor `≈ N/n_bins`, so
`ratio ≈ (S+N)/N = SNR_linear + 1` → `est_snr_db ≈ 10·log10(SNR_linear + 1)`. That crosses `SNR_MIN_DB`
(10 dB) at true SNR ≈ 10 dB (10·log10(11) = 10.4), keeping the noise gate meaningful. This is the
prediction the calibration sweep must **measure**, not assume.

**Pre-registered calibration check** (parametrized tests committed *before* the fix is claimed).
Critically, thresholds below are **measure-then-assert**: implement, print each probe's actual
`est_snr_db`, then set assertions with margin around measured reality — never bake a predicted number
into a test (a self-check written to pass proves nothing).
| Probe | How it's built | Current (buggy) | Required after fix |
|---|---|---|---|
| **Known-SNR sweep** — structured base + broadband noise at true {3, 8, 15, 20} dB via `mix_noise` (`backend/talkteach/audio/augment.py:92`, the exact call the D14 widener uses) | seeded `default_rng` | all 60 dB | `est_snr_db` **monotonically increasing** in true SNR **and crosses ~`SNR_MIN_DB` near true 10 dB** (≈ `10·log10(SNR+1)`) — the load-bearing probe |
| Clean continuous sine (no silence) | preserves `test_audio.py:61` case | 60 dB, GOOD | stays high (capped), stays GOOD — no false reject |
| Pure white noise | seeded `default_rng` | 60 dB, GOOD | `est_snr_db < SNR_MIN_DB` → `ISSUE_TOO_NOISY`, BAD |
| Any clip with ≥1 silent frame (temporal path) | existing tests | temporal SNR | **unchanged** (branch untouched) |

The sweep is the real test: a sine-only clean probe passes tautologically (spike PSD → capped 60), so it
proves the metric isn't broken, not that it *discriminates*. The monotonic mix-SNR sweep is what proves
the fix actually recovers SNR and defeats the broadband-saturation bug.

## Steps
1. **Worktree** off `main` (`AGENTS.md:82`; touches backend Python, non-docs → substantive).
2. Add pure `_spectral_snr_db(x, frame_len)` helper to `backend/talkteach/audio/quality.py`; replace the
   `est_snr_db = 60.0` fallback (`quality.py:171-173`) with a call to it.
3. Add the calibration/regression tests to `backend/tests/test_audio.py`: the **known-SNR `mix_noise`
   sweep** (monotonic + crosses ~10 dB near true 10 dB) as the load-bearing probe, plus
   clean-continuous-stays-high, pure-noise-rejected, and the ≤1-frame safety path. **Measure-then-assert**:
   during impl, print each probe's real `est_snr_db` and set assertions with margin around the measured
   values — do not commit the predicted numbers. Keep `test_clean_moderate_sine_is_ok` green.
   *(Pre-code grep done: fast-suite continuous-audio `GOOD` assertions are confined to `test_audio.py`;
   `test_tts.py`'s `Verdict.GOOD` asserts are marker-gated (espeak/integration) on real speech, which has
   sub-−45 dBFS pauses → temporal path → unaffected. Run the espeak marker too if the binary is present.)*
4. Run the verify contract: `make test` (fast suite green) + `make lint` (`.harness/config.json:153-158`).
5. **D14 re-measurement (honest, feasibility-gated):** if `soundfile`+`faster_whisper`+eval audio are
   present, re-run `measure_quality_gate` and record whether `snr_ceiling_rate` now drops below 0.5 and
   D14 yields a real (non-degenerate) AUC/r. If deps/audio are absent, do **not** fabricate a band — leave
   D14's abstain-detection in place (it will simply stop firing on real data) and record the re-score as
   the standing INS-002 automation follow-up. Either way, report the actual outcome.
6. Update `docs/errors/INS-002-...md`: check off automation follow-up #1 (estimator fix + regression clip
   landed), cite the new test/helper, and set follow-up #2 (scored D14) to its real state from step 5.
7. Merge worktree → `main`; move this plan to `docs/plans/done/`. Commit logically: (a) estimator fix +
   calibration tests, (b) INS-002 doc update, (c) any D14 re-measure artifact.

## Risks & reversibility
- **Blast radius:** app-wide accept/reject — a clip that was silently accepted (60 dB) may now be rejected
  as "too noisy". That is the *intended* correction; the pre-registered clean-audio probes (step 3) are the
  guard against the *unintended* direction (false-rejecting clean continuous audio). If a clean probe drops
  below 15 dB, the fix is mis-calibrated → stop and revise before merge.
- **Reversibility:** single-branch change in one pure function + new tests; revert = drop the commit. No
  schema/state/migration. `est_snr_db`'s type/range (still a float, still clipped ≤ 60) is unchanged, so
  the D14 harness and app.py contracts are untouched.
- **Not in scope:** re-tuning `SILENCE_FRAME_DBFS`/`SNR_MIN_DB`, the temporal branch, or flipping D14 to a
  scored band without a real run (that would be fabrication).

## Test plan
- New: `test_audio.py` calibration probes — the known-SNR `mix_noise` sweep (monotonic, crosses ~10 dB),
  clean-continuous-stays-high, pure-noise-rejected, ≤1-frame safety. Thresholds set from measured reality.
- Preserved: `test_clean_moderate_sine_is_ok` (`test_audio.py:61`), the full fast suite, and the D14
  ceiling→abstain unit test (`test_sota_scoring.py:277`, still valid — stops firing, not removed).
- Marker-gated (run if binary present): `test_espeak_synthesizes_good_clip` (`test_tts.py:96`) — real
  speech must still verdict GOOD (temporal path, expected unchanged).
- Manual/feasibility: step 5 D14 re-measurement, reported honestly (run or abstain, never fabricated).

## Standards & Guardrails Evidence
- [x] Tests / shift-left: `backend/tests/test_audio.py:143` — the `mix_noise` SNR sweep + broadband-noise
  rejection probes assert both directions (clean stays high, noise drops+flags) with thresholds set from
  measured reality; fast suite `make test` (`.harness/config.json:154`).
- [x] Reused patterns / grounding: `backend/talkteach/audio/quality.py:115` — the spectral helper reuses
  the existing frame machinery `_frame_rms` and numpy-only DSP convention (`backend/talkteach/audio/quality.py:7`);
  no OSS spectral lib pulled in (no scipy dep). Fix grounded in the RCA
  `docs/errors/INS-002-quality-gate-snr-saturates-on-broadband-noise.md`.
- [x] Security: N/A — pure local numpy DSP on already-recorded samples; no new I/O, network, secrets, or
  dependency (`backend/talkteach/audio/quality.py:1`).
- [x] Evidence classification: `backend/talkteach/audio/quality.py:217` — *fact*: consumer chain (this
  noise gate → `ClipQuality.ok` → `backend/talkteach/app.py:306`); *measurement*: committed probe values in
  `backend/tests/test_audio.py:143`; *hypothesis*: real noisy-room incidence is level-dependent — not
  claimed as directly measured, only the broadband case is.
- [x] Reproducibility: `backend/tests/test_audio.py:143` — deterministic pure-numpy estimator; every probe
  uses a seeded `np.random.default_rng`; no wall-clock. D14 re-measure uses the harness's fixed
  `self.seed` (`backend/talkteach/sota/harness.py:110`).
- [x] Statistical validity: `backend/talkteach/sota/harness.py:548` — the fix removes the constant 60 dB
  sentinel that made any D14 r/AUC an artifact; the calibration is a directional guard, not a significance
  claim; D14 headline eligibility stays gated by the harness's small-n/scope checks.
- [x] Baseline / SOTA calibration: `backend/tests/test_sota_scoring.py:277` — baseline = pre-fix behavior
  (60 dB on broadband noise), against which the fix is validated; the bounded D14 re-run (AUC 0.83,
  ceiling_rate 0.0) is `partial` and a scored *headline* band remains a separate non-fabricated decision.
