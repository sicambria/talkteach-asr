# Plan — Honest automated measurement for D03, D05, D14 (defer D09/D13)

- **Type:** BENCHMARK
- **Status:** draft (planmax loop — self-scored, advisor-gated before code)
- **Branch/worktree:** off `main` (touches non-docs ML code → worktree-first per AGENTS.md invariant #1)
- **Scope decision (user-confirmed):** implement D14 (both halves) + D03 + D05 this session; D09 (needs E07
  augmentation-collator wiring) and D13 (combinatorial per-config training sweep) are deferred as separate
  scoped follow-up plans and stay `human_needed` — never fabricated.
- **Commits (each separate, in dependency order):**
  1. D14 quality-gate — Pearson r (gate SNR score vs per-clip WER), inference-only, real.
  2. D14 quality-gate — ROC-AUC via defect-injection self-labels (SNR-gate discrimination).
  3. D03 train-efficiency — real bounded whisper fine-tune, `gpu_hours` proxy `[partial]`.
  4. D05 data-efficiency — WER at bounded data sizes `[partial]`.

## Summary
Four SOTA domains currently abstain (`human_needed`). Grounding proved D14 is inference-only and D03/D05
need real CPU fine-tuning that is now feasible (train-clean-100 cached, per-epoch eval already enabled).
Turn each into a genuine automated measurement. Every proxied number is flagged `partial` so the existing
`assess_headline_eligibility` gate excludes it from the headline — no fabrication, no headline inflation.

## Non-negotiable honesty invariants (carried from the honest-scoreboard work)
- No hardcoded positive scores in `validate_*` (enforced by `test_no_validate_script_hardcodes_positive_score`).
- Bounded/proxy measurements set `metrics["partial"]` → excluded from headline mean at the one chokepoint.
- Real WER only; never label a simulation as measured (D-012). `[SIMULATION]` must not appear in real results.
- Speaker/sentence-disjoint eval: train on `train-clean-100`, evaluate on `test-clean` (disjoint speakers).

## Steps

### Shared enablers (land in commit 3, reused by 4)
- **E-1 · Expose training eval WER (opt-in, additive).** Add optional `eval_sink: Callable | None = None`
  param to `run_real_training` (`backend/talkteach/engines/_whisper_train.py:189`). When provided, register a
  new `TrainerCallback.on_evaluate` that forwards `(epoch, metrics["eval_wer"], elapsed_s)`; the existing
  `final_metrics`/`final_wer` (`_whisper_train.py:356-357`) also flows to the sink. Default `None` ⇒ zero
  behavior change ⇒ the 219 fast tests are untouched. `eval_strategy="epoch"` is already set
  (`_whisper_train.py:105`) so per-epoch eval already runs — the callback only *reads* it.
- **E-2 · Manifest slicer (pure).** `build_train_manifest(train_dir, target_minutes, seed)` in the harness:
  `get_clip_paths` + `get_transcript` (`backend/talkteach/sota/datasets.py:214,225`) → `[{path,text}]`,
  accumulate `soundfile` durations until `target_minutes`. Pure/deterministic given seed → unit-testable
  without training.

### D14 target reframe (advisor gap #1 — kills the tautology)
The ground-truth target is **measured downstream per-clip WER**, NOT the clean/noised injection label.
The gate's real job is predicting which clips transcribe badly. Scoring separability by the very SNR the
defect manipulates would make AUC≈1 regardless of gate quality — a shiny-empty number. Instead:
predictor = gate score (`est_snr_db`); target = *measured* per-clip WER. Defect injection is used only to
**widen real WER variance** (clean test-clean is too uniform for r to mean anything), never as a label source.
This makes the measurement able to fail: if a defect raises real WER but the SNR estimator misses it, r/AUC drop.

### Commit 1 — D14 gate-score vs *measured* WER (Pearson r, inference-only)
- New `HarnessRunner.measure_quality_gate(eval_dir, engine, max_clips)` (harness.py, near the other measures).
  Loop clips: gate score = `analyze_samples(...).est_snr_db` (`backend/talkteach/audio/quality.py:115`);
  transcribe (faster-whisper, same pattern as `measure_base_wer` harness.py:139) → per-clip WER via
  `wer(...)` (`_train_common.py:60`). `quality_gate_pearson_r = abs(pearsonr(snr, wer))` (scipy, function-local).
- Sign documented: higher SNR ↔ lower WER ⇒ raw r negative; report `abs(r)` as strength.
- Set `partial="Pearson r vs measured WER, SNR component, clean read speech; ROC-AUC pending"` ⇒ no full
  band yet, excluded from headline. Emit `quality_gate_pearson_r` + `num_clips`.
- Wire `d14_quality_gate` dispatch (`harness.py:688`) to call it (replace the `-1.0` stub). Convert
  `scripts/sota/validate_d14_quality_gate.py` from `write_abstention` → run harness + `write_domain_result`.
- **Test (fast):** pure test of the correlation-strength helper on a crafted monotone SNR↔WER set ⇒ r≈1;
  flat set ⇒ r≈0; degenerate constant input ⇒ NaN handled/skip. No model load.

### Commit 2 — D14 ROC-AUC of gate-score ranking clips by *measured* WER
- Extend `measure_quality_gate`: widen WER variance with additive-noise variants at a few SNRs
  (`backend/talkteach/audio/augment.py:92` `mix_noise`) — these produce clips with genuinely higher *measured*
  WER. Target label = `measured_wer > T` (T = median or a fixed poor-WER threshold, documented). `quality_gate_auc
  = roc_auc_score(measured_wer > T, -est_snr_db)` (sklearn, function-local). Recompute Pearson r over the widened
  set. Now both metrics present ⇒ band scores against `domains.py` D14 bands, but
  `partial="predicts measured WER; SNR component only (clipping/silence not exercised); WER-variance widened by
  synthetic noise; single engine"` keeps it out of the headline.
- **Test (fast):** synthetic — feed the pure AUC wrapper a case where gate-score tracks WER (AUC→1) AND a case
  where gate-score is uncorrelated with WER (AUC→0.5), proving it can fail; one-class/degenerate input skips.

### D03/D05 base-WER anchor + non-improvement-abstains (advisor gap #2 — INS-001 says naive LoRA degrades)
INS-001 already documented naive in-domain LoRA *degrading* WER (5.16→5.92%). Fine-tuning whisper-tiny on
5–30 min for ≤5 epochs on CPU is **more likely to degrade than improve**. The likely case — training completes
cleanly, WER gets worse — must have a defined honest output, not a silent bogus band. So BOTH measures first
capture **base (pre-finetune) WER** as the anchor, and treat non-improvement as a **terminal abstain state**:
if trained WER is not meaningfully below base, report the degradation (base X% → trained Y%, cite INS-001) and
emit `human_needed`/directional with reason — NO convergence time, NO positive band. `min_improvement` (e.g.
5% relative) is documented. This also makes D03 well-defined: "90% of final WER" is meaningless without a start
point; convergence = time to reach 90% of the *improvement from base→final*, only when final < base.

### Commit 3 — D03 Training Efficiency (real bounded fine-tune)
- E-1 + E-2 land here.
- `HarnessRunner.measure_train_efficiency(train_dir, eval_dir, engine, minutes, epochs)`: **base_wer** = eval WER
  before fine-tuning (reuse `measure_base_wer` on the eval subset). Slice a bounded manifest (E-2), force a
  **float32** whisper-tiny `TrainingPlan` (int8 is inference-only quantization — verify the model loads fp32 for
  training; if the plan's int8 breaks training, pin float32 and note it), eval split = held-out `test-clean`
  subset. Call `run_real_training` with an `eval_sink` capturing `(epoch, eval_wer, cumulative_s)`.
- **Non-improvement guard:** if `final_wer >= base_wer*(1-min_improvement)` → abstain (`human_needed`, reason
  "fine-tune did not improve WER: base X% → trained Y% (cf INS-001); convergence undefined"). No band, no gpu_hours.
- **Convergence-point (pure helper, tested):** `gpu_hours_to_converge(base_wer, curve, tol=0.10, cpu_gpu_factor=10)`
  = first eval time where `eval_wer ≤ base_wer - 0.9*(base_wer - final_wer)` (90% of the base→final improvement),
  `÷3600 ÷10` (CPU→A100 factor per domain description `domains.py:92-93`). Emit `gpu_hours` **plus raw
  `wall_clock_s`, `train_minutes`, `epochs`, `base_wer`, `final_wer`** as transparent directional data (advisor
  secondary note: the ÷10 × arbitrary-knobs band placement is a free parameter, so raw datum ships alongside).
- `partial="CPU-timed ÷10 A100 proxy; whisper-tiny; bounded to N min / K epochs; single seed; only if
  fine-tune improved over base"` ⇒ excluded from headline.
- Add `elif domain.id == "d03_train_efficiency"` dispatch. Convert `validate_d03_*` → harness + `write_domain_result`.
- **Test (fast):** `gpu_hours_to_converge` on a synthetic *improving* curve ⇒ correct epoch/time; on a
  *degrading/flat* curve ⇒ the non-improvement guard triggers (abstain), NOT a tiny gpu_hours. No real training.

### Commit 4 — D05 Data Efficiency (bounded data-size sweep)
- `HarnessRunner.measure_data_efficiency` (replace stub `harness.py:338`): **base_wer** anchor first; for
  `minutes in [5,15,30]` (bounded; domain default `[5,15,30,60,120]` — cap for CPU, flag partial), slice manifest
  (E-2), fine-tune whisper-tiny, capture final eval WER via `eval_sink` (E-1). `wer_by_minutes={5:…,15:…,30:…}`,
  metric `wer_at_5min`.
- **Non-improvement guard:** if the best `wer_by_minutes` is not meaningfully below `base_wer`, report the
  degradation and abstain from a positive band (directional/`human_needed` with reason + base/trained numbers) —
  do NOT score `wer_at_5min` against bands that presume fine-tuning worked.
- `partial="bounded data sizes [5,15,30]min (domain intends ≤120); whisper-tiny; single seed; LibriSpeech read
  speech; base_wer anchored"` ⇒ excluded from headline.
- Wire `d05_data_efficiency` dispatch (`harness.py:680`, replace `-1.0` stub). Convert `validate_d05_*` →
  harness + `write_domain_result`.
- **Test (fast):** band-scoring of `wer_at_5min` against D05 bands (pure); non-improvement guard (best≥base ⇒
  abstain); manifest-slicer determinism.

### Cross-cutting per commit
- **Scoreboard update (mechanism pinned):** banking dir is `/tmp/sota_results/` — all 15 `validate_d*.json`
  are present and current. Per commit: run only the new `validate_dNN --json /tmp/sota_results/validate_dNN_*.json`
  (overwrites just that domain's JSON, non-destructive to the other 12), then run the collect + reconstruct
  snippet (`scripts/sota/run_all.sh:93-128`: glob `validate_d*.json` → `rescore_scoreboard({'domains':…,
  'generated': <fresh UTC>})` → `generate(...)`) to regenerate `docs/sota-benchmarks/SCOREBOARD.{md,json}`;
  update the `OVERALL.md` `generated` stamp to match (single-source rule). D14 is fast; D03/D05 are the slow
  (~tens-of-min CPU) runs — may run in background before their commit.
- Each commit passes all kaizen gates (never `--no-verify`); `make lint` + `make test` green.

## Risks & Reversibility
- **Blast radius:** `_whisper_train.py` `run_real_training` gains one optional param — additive, default-off,
  so existing engine/train tests and the 219 fast suite are unaffected. `harness.py` gains measures + 3 dispatch
  branches (replacing abstain/stub paths). `validate_d03/05/14` flip from abstain to real-run. No `policy.py`
  change (so no calibration-experiment obligation). Docs: `OVERALL.md` stamp + `SCOREBOARD.{md,json}` regen.
- **int8-training risk:** if the CPU/int8 plan can't train, pin float32 for the measurement and document — does
  not affect inference-time int8 elsewhere.
- **CPU-time risk:** D03/D05 bounded to ~10-30 min data + ≤5 epochs on whisper-tiny to stay within budget; if a
  run is pathologically slow or errors, that domain **abstains with the concrete reason** (never fabricates) and
  I report it — reversible, no half-baked number ships.
- **Likely-degradation risk (INS-001):** the *expected* outcome is that a small CPU fine-tune degrades WER. This
  is now a first-class terminal state, not an error: the base-WER anchor + non-improvement guard makes D03/D05
  abstain with the base→trained numbers rather than emit a bogus convergence time / data-efficiency band. A
  documented negative result ("fine-tuning did not help under these bounds, cf INS-001") is an honest, valid
  output of this work.
- **Rollback:** all work in a worktree; abandon = delete branch. Each commit is independent; revert any one
  without touching the others. Regenerated scoreboard is deterministic from banked JSON (re-runnable).

## Test plan (shift-left; fast suite stays green, no GPU/ML)
- Pure helpers unit-tested WITHOUT training/model-load: correlation strength, ROC-AUC wrapper + degenerate
  one-class, defect-injection lowers SNR, `gpu_hours_to_converge`, manifest slicer determinism, D05 band scoring.
- Existing guards keep passing: `test_no_validate_script_hardcodes_positive_score`,
  `test_partial_scope_excluded_from_headline_even_when_well_powered` (partial gate),
  `test_hf_loader_decodes_without_torchcodec`, stamp-freshness/self-consistency.
- Real measurement itself verified by *running* each `validate_*` script (out-of-band, slow) and confirming the
  banked JSON carries a real number + `partial` flag, then that the regenerated scoreboard keeps D01 the only
  eligible domain (headline unchanged / not re-inflated).

## Standards & Guardrails Evidence
- [x] Tests / shift-left: `backend/tests/test_sota_scoring.py:1` — new pure helpers unit-tested in the fast suite without any model load; real training exercised only via out-of-band `validate_*` runs (fast-suite invariant AGENTS.md:27).
- [x] Reused patterns / grounding: `backend/talkteach/sota/harness.py:139` — reuse `measure_base_wer` transcription loop; also `analyze_samples` `backend/talkteach/audio/quality.py:115`, `mix_noise` `backend/talkteach/audio/augment.py:92`, `run_real_training` `backend/talkteach/engines/_whisper_train.py:189`, `write_domain_result` `scripts/sota/common.py:63`.
- [x] Security: `AGENTS.md:21` — no network beyond already-cached datasets, no secrets, no new services; heavy ML imports stay function-local per D-002. No auth/PII surface touched.
- [x] Evidence classification: `backend/talkteach/sota/scoring.py:1` — every proxied metric is measured-but-bounded and self-labels scope via `metrics["partial"]` (the `assess_headline_eligibility` gate), distinguished from fabrication; D03/D05 non-improvement is a documented negative result.
- [x] Reproducibility: `scripts/sota/common.py:44` — deterministic manifest slicing seeded via `build_base_parser --seed`; bounded data/epochs recorded in `partial`; banked JSON re-presentable via `backend/talkteach/sota/rescore.py:1` without re-measuring.
- [x] Statistical validity: `backend/talkteach/sota/harness.py:174` — per-clip WER + `confidence_interval` bootstrap already computed; D14 reports Pearson r + ROC-AUC vs measured WER with documented sign and a degenerate one-class guard; bounded runs flagged directional/partial.
- [x] Baseline / SOTA calibration: `backend/talkteach/sota/domains.py:87` — scored against anchored bands (D03 :87, D05 :131, D14 :334); D01 stays the only headline-eligible domain so the board is not re-inflated by proxied numbers.

## Scope discipline
Exactly the 3 domains the user selected; D09/D13 explicitly deferred; no `policy.py` change, no new deps
(sklearn/scipy/numpy already present), no speculative abstraction.

## Outcomes (2026-07-09 — completed, 4 commits + this addendum)
- **D14** did not become a scored band. The measurement (gate SNR vs *measured* WER) **discovered a
  real gate defect** — the SNR estimator saturates to its 60 dB ceiling on 100% of noise-degraded
  clips (silence-floor fallback), assigning its best score to its worst inputs. AUC 0.17 is a constant
  sentinel artifact, not discrimination (advisor), so D14 **abstains-with-finding** (`human_needed`) and
  the defect is filed as **INS-002** (gate NOT fixed — separate blast radius, scoped follow-up).
- **D03** (base 6.1% → trained 6.3%) and **D05** (base 6.4% → 5-min 7.1%; curve {5:7.1,15:6.0,30:8.2}%)
  both ran real bounded whisper-tiny fine-tunes and **abstain** — fine-tuning does not beat the zero-shot
  base on in-domain LibriSpeech: fresh empirical **INS-001** confirmations, not fabricated bands.
- **Bug caught by live data:** D05's first cut scored 900/platinum on a `wer_at_5min` (7.1%) that was
  *worse* than base (6.4%) because the guard checked "best-of-all-sizes." Fixed: the scored metric must
  itself beat base, unified into the pure, tested `scoring.beats_base` shared by D03 & D05.
- **rescore** now preserves abstentions (it was silently re-scoring D14's raw AUC into a band, inflating
  the headline to 650/eligible=2). Headline stayed **800/provisional, 1 eligible** throughout — no inflation.
- **Deferred as agreed:** D09 (needs E07 augmentation-collator wiring) and D13 (combinatorial per-config
  training sweep) remain `human_needed`.
