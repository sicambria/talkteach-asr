# OVERALL — the authoritative state of TalkTeach & the road to SOTA

> **This is the single source of truth for TalkTeach's SOTA position.** It supersedes the
> earlier split between this file and the `docs/sota-benchmarks/` suite (which now points *up*
> here as generated data + reference appendices). It sits above the roadmap docs
> ([`ROADMAP.md`](docs/roadmap/ROADMAP.md), [`ROADMAP_STATUS.md`](docs/roadmap/ROADMAP_STATUS.md),
> [`CALIBRATION.md`](docs/ml/CALIBRATION.md), [`BENCHMARKING.md`](docs/ml/BENCHMARKING.md)).
>
> **Numbers live in one place.** Every accuracy/efficiency figure is produced by the SOTA
> generator and stored in [`docs/sota-benchmarks/SCOREBOARD.md`](docs/sota-benchmarks/SCOREBOARD.md)
> / `.json`. This document *references* the scoreboard by its `generated` stamp rather than copying
> figures into prose, so the two can never silently drift (the prior root cause of the contradiction
> this rewrite resolved). Current scoreboard stamp: **`2026-07-09T09:03:05.083293+00:00`**.
> Regenerate after any scoring-policy change with **`make sota-rescore`** (seconds, no GPU); the
> dated entries in Part C are immutable historical records and are exempt from single-sourcing.

---

## Part A — Where we are now

### A.1 What TalkTeach is (and the honest SOTA position)
An **offline desktop GUI wizard** (Record → Check → Teach → Try) that turns the fragmented OSS
speech-training stack into one four-tap flow, with a hardware/data-aware **director** that makes
every ML decision automatically. Documented thesis: **~85 % is integration + UX; the genuine IP is
the director + reliability engineering, *not* new ML.** External product-maturity review
(2026-07-06): **530/1000, "advanced prototype."**

**Two distinct meanings of "SOTA" live in this repo — keep them separate:**
- **Capability-SOTA** (largely delivered): *"there is no OSS next-next-finish GUI that trains the
  best ASR models end-to-end."* This is the product thesis.
- **Accuracy-SOTA** (now *started*, not finished): a real-audio accuracy program exists as of
  2026-07-08 (journey S1). It is early — see the coverage caveat in A.2. On CPU-only hardware we do
  not *beat* whisper-large-v3; the honest, achievable target is: **the director auto-selects the
  WER-minimizing config for a given data + hardware budget, validated on real audio.**

### A.2 Current measured state (single-sourced from the scoreboard)
The authoritative numbers are in
[`SCOREBOARD.md`](docs/sota-benchmarks/SCOREBOARD.md) (stamp above). Read it there; the summary
here is deliberately qualitative so it cannot drift:

- **Coverage is partial and the headline is provisional.** Of the 15 domains, **8 are now measured
  on real audio** but **only one is adequately powered and in-scope** (D01 clean-speech WER, 100
  real LibriSpeech test-clean clips). The other seven are **excluded from the headline mean** as
  **"directional"** — either under-powered (too few clips/speakers) or **scope-partial** (the metric
  covers only part of the domain's definition). The remaining seven **abstain** (`human_needed`):
  they need training runs, human labels, or a working dataset loader, and emit **no fabricated
  score**. The scoreboard reports the exact headline, band (`provisional`), and the
  measured / eligible / directional / unmeasured counts.
- **The one solid result:** off-the-shelf (untrained) **whisper-small** on real LibriSpeech
  test-clean lands in the **gold** band — see D01 in the scoreboard for the WER, its 95 % CI, and
  the anchor. Caveat carried in the scoreboard: those 100 clips span only **2 speakers**, so the CI
  is wide and it is **not** a like-for-like comparison to full-test-set SOTA anchors.
- **Directional (do not headline):** two kinds. *Under-powered:* D04 real-time factor (20 clips <
  the domain's declared 100), D06 noise robustness (30 clips < 50, synthetic noise = upper bound),
  D12 speaker equity (**a per-speaker σ over n=2 speakers is not evidence of generalization** —
  needs ≥10). *Scope-partial* (measured, but the metric covers only part of the domain): D08 export
  fidelity (int8 quantization only — 1 of 3 export targets), D10 decoding (beam sweep only, no
  hotword/OOV biasing), D11 long-form (a ~10-min concatenated-clip proxy, not 60-min continuous),
  D15 resource (model disk footprint only). The partial-scope gate keeps these out of the headline
  even though several land in high bands.
- **Abstained (`human_needed`, score 0 — never fabricated):** D03/D05/D09/D13 need real training
  runs; D14 needs a hand-labelled quality set; **D02** (Common Voice) fails to load under HF
  `datasets` v5 (`EmptyDatasetError` / gated access); **D07** (FLEURS) loads but its metric counts
  languages and the spec is single-config (en_us). *B-001 update:* the torchcodec decode barrier is
  **fixed** (loader uses `Audio(decode=False)` + soundfile); D02/D07 remain blocked by the separate
  dataset-resolution / multi-config gaps above.
- **Synthetic-TTS proxy** (separate generator, single-sourced in
  [`benchmarks/REPORT.md`](benchmarks/REPORT.md)): the TTS×ASR harness reports whisper-tiny vs
  wav2vec2 on synthetic speech. **Synthetic-TTS WER is an indicative proxy only** and must never be
  confused with real WER (D-012) or used to change shipped `policy.py` defaults (A.6.7).

### A.3 This machine (the experiment sandbox)
`[ml]`+`[tts]` stack installed (torch, transformers, peft, faster-whisper, jiwer, librosa,
soundfile, piper, datasets, ctranslate2, onnxruntime); **espeak-ng + ffmpeg present**;
**huggingface.co reachable**; **CPU-only, no GPU**; LibriSpeech test-clean cached (~13 GB under
`~/.cache/talkteach/sota`). → `small`/`medium` brackets are runnable here; the `large` bracket
(whisper-large-v3, parakeet) is **GPU-queued**.

### A.4 Wiring debt — dead knobs the director exposes but the training path ignores
Verified against code (not docs). These are tracked as experiments E07–E10 (Part B, G2). Until they
are wired, the director *advertises* behavior it does not deliver — treat any claim that relies on
them as unproven:
- **Augmentation is not wired into any training collator.** `director.augmentation_for` returns an
  `AugmentationConfig`, and `audio/augment.py` implements every transform, but neither the Whisper
  nor the wav2vec2 collator consumes it, and `TrainingPlan` has no augmentation field. → **E09/E29.**
- **`early_stop_patience` is inert** — there is no `EarlyStoppingCallback` in either real loop; only
  the NaN-guard and cooperative-cancel end a run early. → **E10.**
- **NaN "auto-rollback to last good checkpoint" is not wired** — `observe_good_checkpoint` writes
  `last_good_checkpoint` but **no code reads it**; `NanRollbackGuard` only *stops* training. Recovery
  rides on HF `load_best_model_at_end`, which is itself disabled in the fallback-argument branch. The
  policy rationale string that promises "NaN-guard with rollback, early-stop patience" therefore
  over-promises. → **E08.**
- **No CI test exercises the real training path through production routing.** An opt-in integration
  test (`test_e2e_benchmark.py`) *does* route through `train()` → `should_simulate` → the real loop,
  but it is skipped unless `TALKTEACH_RUN_INTEGRATION=1` (+ `[ml]` + piper), so **CI never runs it**;
  the fast suite force-simulates. A regression in the real-vs-sim dispatch would pass CI. → **E07.**
- **LoRA `target_modules`/`lora_dropout` are hardcoded** (`["q_proj","v_proj"]`, `0.05`) — not plan
  fields. wav2vec2 **ignores all LoRA fields** and full-fine-tunes with a frozen feature encoder.
  `DecodeOptions` (beam/temp/hotwords) affects **only** the faster-whisper inference path — never
  training, never the benchmark's `generate`-based scoring, never the SOTA harness (which hardcodes
  `beam_size=5`). → **E23/E27/E28.**

### A.5 The director's current constants (all "proposed defaults", uncalibrated — M4)
Verified accurate against `director/policy.py`: sufficiency floor `MIN_TARGET_MINUTES=20`;
`adaptive_target` 25 min (Whisper-supported *or* auto-detect) / 45 min (non-Whisper); schedule
`_choose_schedule` = **<30 min → 12 epochs, lr 1e-4, freeze_encoder=True**; 30–120 min → 8 epochs,
lr 1e-4; ≥120 min → 5 epochs, lr 8e-5; LoRA rank **8 (<30 min) / 16 (≥30 min)**, alpha = 2·rank;
effective-batch target **16**. Engine choice: non-Whisper lang **and** ≥20 good-minutes → wav2vec2
`xls-r-300m`; CUDA ≥16 GiB → whisper-medium; CUDA/MPS ≥6 GiB → whisper-small; else whisper-tiny int8.
`audio/quality.py`: `SNR_MIN_DB=10`, `CLIP_FRACTION_MAX=0.005`, `SILENCE_FRACTION_MAX=0.8`,
`RMS_QUIET_DBFS=-40`, `MIN_DURATION_S=0.4`. **None empirically tuned** (the docstring says so; the
product path exposes no override — only the benchmark-only `plan_from_config` does).

### A.6 Mandatory guardrails (from prior dead-ends — do NOT re-learn these)
1. **Real speech, never tones** — sine tones have no phonetic content; WER on them is noise (D-013).
2. **Speaker/sentence-disjoint eval** — the in-product held-out split is a plain random 10 % with
   **no overlap guard** (Mo3 leakage; verified in both training engines). The product is
   single-speaker by construction, so speaker overlap is inherent and sentence-level leakage is
   unguarded. Every accuracy number must name its eval-disjointness *and its speaker count*.
3. **Confirm the real path** — not `[SIMULATION]`, and **`passed` not `skipped`** (a skipped opt-in
   test masquerades as a pass).
4. **Pin hyperparameters** for cross-engine comparison (`plan_from_config`, not director heuristics).
5. **Bound + clean disk** — `keep_artifacts: false` (default, verified); check `df` if the shell
   wedges; `rm -rf ~/.cache/huggingface` to reclaim.
6. **Heavy imports stay function-local** (D-002); run via `backend/.venv/bin/python` (3.11).
7. **Synthetic-TTS WER is an indicative proxy only** — it must **not** drive shipped `policy.py`
   defaults; CALIBRATION.md requires real labelled audio + the three GPU tiers for that.

---

## Part B — The experiment program toward SOTA

Prioritized and grouped. Each carries a **pre-registered metric**, a **baseline**, a
**definition-of-done (DoD)**, and a **feasibility** tag: **`CPU-now`** · **`CPU-heavy`** ·
**`GPU-queued`** · **`build`**. Priority: **P0** (grounding + trust) · **P1** (high value) ·
**P2** (breadth/ceiling). Status reflects the reconciled register in Part D.

### G1 — Real accuracy baseline *(the former credibility gap — now open, not empty)*
| ID | Experiment | Metric | Baseline | DoD | Feasibility | Pri | Status |
|----|-----------|--------|----------|-----|-------------|-----|--------|
| **E01** | Reproduce synthetic baseline + establish first real-audio WER | per-model WER | REPORT.md / published | ≥1 external real WER anchor per model; ≥4 domains ≥ bronze | CPU-now | **P0** | ✅ **done** (S1) |
| **E02** | Real-audio breadth on Common Voice (spontaneous/accented) | per-model WER; gap vs clean | — | WER gap recorded | CPU-now | P1 | ⛔ **blocked (B-001)** |
| **E03** | **Fix B-001** (HF `datasets` v5 / `torchcodec` loader) to unblock D02/D07 | loaders return audio | broken | CV17 + FLEURS load; D02/D07 measurable | CPU-now · build | **P0** | ▶ queued |
| **E04** | TTS→real generalization gap (fine-tune on TTS, eval on TTS + real) | Δ(WER_real − WER_TTS) | — | Δ recorded | CPU-now | P1 | ▶ queued |
| **E05** | Leakage audit — random-10 % split vs sentence/speaker-disjoint | Δ WER | — | Inflation measured; fix recommended | CPU-now | P1 | ▶ queued |
| **E06** | Representative D01/D12 — full 40-speaker / 2620-clip test-clean, not first-100-sorted | per-speaker WER σ, pooled WER + CI | current 2-speaker slice | D01 + D12 re-measured across ≥10 speakers → headline-eligible | CPU-heavy | **P0** | ▶ queued |

### G2 — Trust the training path *(wiring debt from A.4)*
| ID | Experiment | Metric | Baseline | DoD | Feasibility | Pri | Status |
|----|-----------|--------|----------|-----|-------------|-----|--------|
| **E07** | Real-path-through-`train()` CI test (not `run_real_training` directly) | test asserts real routing, no `[SIMULATION]` | CI gap | CI-able toy-model test picks the real path | CPU-now | **P0** | ▶ queued |
| **E08** | Wire + verify NaN auto-rollback to `last_good_checkpoint` | injected NaN → recovers | unwired | Rollback asserted, or the promise restated to match reality | CPU-now | **P0** | ▶ queued |
| **E09** | Wire `AugmentationConfig` into the collators | augmented batches observed | absent | Augmentation runs in the loop; unit-checked | CPU-now | P1 | ▶ queued |
| **E10** | Wire `EarlyStoppingCallback` from `plan.early_stop_patience` | run halts on val-WER plateau | inert | Early-stop fires; patience honored | CPU-now | P1 | ▶ queued |

### G3 — Reach stronger models *(the real accuracy ceiling)*
| ID | Experiment | Metric | Baseline | DoD | Feasibility | Pri | Status |
|----|-----------|--------|----------|-----|-------------|-----|--------|
| **E12** | **distil-small.en (166 M) / whisper-medium** vs whisper-small — close the gap to SOTA | real WER + train/decode cost | whisper-small (D01) | Accuracy/speed tradeoff recorded | CPU-now/heavy | **P1** | ▶ queued (Stage 3) |
| **E13** | wav2vec2 XLS-R-300M CTC on a non-English small set | real CTC WER | — | Real fine-tune completes; WER recorded | CPU-heavy | P1 | ▶ queued |
| **E14–E16** | Build **Canary** (AED multitask) / **Moonshine** (edge) / **Granite-Speech** adapters | loads + transcribes; base WER | unreachable | Adapter passes `ASREngine` contract | GPU-queued · build | P2 | ▶ queued |
| **E17** | NeMo/Parakeet RNN-T real train/export path (#25) | real WER + `.nemo` export | scaffold | Real path runs on a GPU | GPU-queued | P2 | ▶ queued |
| **E18** | whisper-large-v3 base + LoRA on the real eval sets (open ceiling) | WER anchor for `large` bracket | — | Large-bracket real WER recorded | GPU-queued | P2 | ▶ queued |

### G4 — Calibrate the director *(M4 — the #1 score-raiser; synthetic-proxy caveat A.6.7)*
LoRA rank/LR/epochs/freeze/target-module/batch/threshold/sufficiency sweeps **E19–E26** (see Part D
for the full list). **Re-scoped by the S2 finding (INS-001):** *in-domain* fine-tuning of an
already-strong pretrained model does not help on this box — so G4 now targets **out-of-domain
adaptation** (user vocab/accent/recording conditions), where the pretrained model is weak and
fine-tuning is expected to pay off. That is TalkTeach's actual use case. All P1/P2; CPU-heavy.

### G5 — Decoding & augmentation ablations *(cheap, real, inference-time)*
Beam size **E27**, temperature-fallback + hotword bias **E28**, augmentation efficacy at <10 min
**E29** (after E09). P1/P2, CPU-now.

### G6 — Robustness / real-world
Noise + denoise gate (DeepFilterNet) SNR sweep **E30**; representative-noise re-measure of D06 with
real noise rather than synthetic. P2, CPU-now.

**Sequencing.** P0 first: **E03 (unblock B-001)**, **E06 (representative D01/D12)**, and the
trust-the-loop wiring **E07/E08** — these turn the provisional headline into an adequately-powered
one and make the training path trustworthy. Then P1: model scaling **E12** (Stage 3), wiring
E09/E10, out-of-domain calibration E19–E22, decode E27, augment E29. P2 is breadth + the
GPU/adapter ceiling.

---

## Part C — Results log (dated historical records — immutable, exempt from single-sourcing)

Each row is a point-in-time measurement, kept verbatim as banked. **Live numbers are in the
scoreboard, not here.** Every synthetic-TTS WER is an indicative proxy (A.6.7).

| Exp | Date | What | Verdict | Detail |
|-----|------|------|---------|--------|
| **smoke** | 2026-07-08 | espeak+whisper-tiny, 2 train/2 eval, 1 epoch, real path (no `[SIMULATION]`) | ✅ real path confirmed | harness runs the real `Seq2SeqTrainer`; disk guard works |
| **E01 (synthetic)** | 2026-07-08 | `benchmark.py quick.yaml` — whisper-tiny vs wav2vec2 on synthetic TTS | ✅ reproduces REPORT.md | see [`benchmarks/REPORT.md`](benchmarks/REPORT.md) (indicative proxy) |
| **E01 / S1 (real)** | 2026-07-08 | First real-audio baseline on LibriSpeech test-clean (D01/D04/D06/D12) | ✅ banked | see [`SCOREBOARD.md`](docs/sota-benchmarks/SCOREBOARD.md) + [journey S1](docs/testing/journey-s1-real-audio-baseline.md); fixed INC-001 (WER normalization) + INC-002 (transcript parsing) |
| **E02 / S2 (real)** | 2026-07-08 | LoRA fine-tune whisper-tiny on 30–60 min in-domain LibriSpeech | ❌ **falsified** (WER *degraded* −6 % to −15 %) | in-domain FT of an already-strong model does not help; [journey S2](docs/testing/journey-s2-finetune-spike.md) + [INS-001](docs/errors/INS-001-lora-finetune-degrades-in-domain-wer.md) |

**The current frontier (Stage 3).** The open lever is **model size**, not in-domain fine-tuning
(INS-001): whisper-small is already the strongest CPU-runnable default; the queued work is
distil-small.en / whisper-medium (E12), fixing B-001 (E03) to reach spontaneous/multilingual, and
making D01/D12 representative (E06). Fine-tuning is retargeted at out-of-domain adaptation (G4).
See [`docs/plans/stage3-model-scaling.md`](docs/plans/stage3-model-scaling.md).

---

## Part D — Reconciled experiment-ID register (one spine)

Four numbering schemes had diverged. **Canonical = `experiments/*.yaml` + the experiment DB** (the
real run records). This document's E-numbers map onto that spine; journey stages (S-numbers) and the
Stage-3 plan are narratives of the same runs. Grandfathering note: OVERALL's original "E02
(real-audio baseline)" shipped as `experiments/e01_*.yaml`; the on-disk `e02` is the fine-tune spike.

| Canonical run record | This doc | Journey | What | Banked |
|----------------------|----------|---------|------|--------|
| `experiments/e01_real_audio_baseline.yaml` | E01 | S1 | First real-audio baseline (D01/04/06/12) | ✅ yes |
| `experiments/e02_lora_finetune_spike.yaml` | E02 | S2 | In-domain LoRA spike (negative) | ❌ no (falsified → INS-001) |
| _(future)_ | E03+ | S3 (Stage 3) | B-001 fix, model scaling, representative re-measure, wiring debt | — |

When adding an experiment: create `experiments/<name>.yaml` with a pre-registered metric + baseline +
DoD, give it the next E-number here, and (if it's a narrative arc) the next S-number. Update this
register and Part C in the same change.

---

## Part E — The generated scoreboard (single source of numbers)

The 15-domain scoreboard is machine-generated. **Do not hand-edit the numbers** — change the
measurement or the scoring policy (`backend/talkteach/sota/{domains,scoring}.py`) and regenerate:

- **Re-apply scoring policy to banked measurements** (seconds, no GPU/network):
  `make sota-rescore` → rewrites `docs/sota-benchmarks/SCOREBOARD.{md,json}` from their own raw
  metrics, preserving the measurement `generated` stamp.
- **Fresh measurement** (needs `[ml]` + the cached datasets): `make sota-baseline` (base models) or
  `make sota` (train+eval, CPU: hours). A fresh run advances the `generated` stamp — update this
  document's stamp reference (top of file) in the same change.

**Scoring policy (honest headline).** The overall band is the mean over **adequately-powered**
domains only; a measured-but-under-powered domain (too few clips, or a per-speaker metric over too
few speakers) is kept and shown but flagged **directional** and excluded from the mean. The headline
reads `provisional` until ≥3 domains are adequately powered, so a single domain cannot headline a
grade. Coverage (measured / directional / unmeasured) is reported beside the headline. Full domain
definitions, bands, and cited anchors: [`docs/sota-benchmarks/`](docs/sota-benchmarks/).

---

### The honest one-liner
TalkTeach has a strong **capability** story and a **real accuracy program that has just begun**: one
adequately-powered real-audio domain (whisper-small clean speech, gold), three under-powered
directional readings, and most domains unmeasured or blocked. Naive in-domain fine-tuning was tried
and **falsified** (INS-001); the open levers are **model-size scaling**, **unblocking B-001**, and
**making the baseline representative** — plus paying down the **training-path wiring debt** (A.4)
that the "automatic and smart" value prop rests on. Everything here is grounded in existing
harnesses; nothing requires inventing new ML.
