# OVERALL — state of TalkTeach & the road to SOTA

> Created 2026-07-08. **No prior `OVERALL.md` existed** (nothing in the repo referenced
> one); this is the first. It is the single-page answer to *"where are we now, and what
> are the next best experiments toward state-of-the-art?"* It sits above the roadmap docs
> ([`ROADMAP.md`](project/docs/ROADMAP.md), [`ROADMAP_STATUS.md`](project/docs/ROADMAP_STATUS.md),
> [`CALIBRATION.md`](project/docs/CALIBRATION.md), [`BENCHMARKING.md`](project/docs/BENCHMARKING.md))
> and points down into them.

---

## Part A — Where we are now

### A.1 What TalkTeach is (and the honest SOTA position)
An **offline desktop GUI wizard** (Record → Check → Teach → Try) that turns the fragmented
OSS speech-training stack into one four-tap flow, with a hardware/data-aware **director**
that makes every ML decision automatically. The documented thesis (research report Part B):
**~85 % is integration + UX; the genuine IP is the director + reliability engineering, *not*
new ML.** External product-maturity review (2026-07-06): **530/1000, "advanced prototype."**

**Two meanings of "SOTA" live in this repo, and only one has ever been worked:**
- **Capability-SOTA** (heavily documented): *"there is no OSS next-next-finish GUI that trains
  the best ASR models end-to-end."* This is the product thesis and it is largely delivered.
- **Accuracy-SOTA** (essentially absent): **there is no target WER, no external benchmark
  anchor (no LibriSpeech / Common Voice / FLEURS number), and no accuracy baseline anywhere
  in the repo.** All evaluation to date is on **synthetic TTS speech**.

So "next 30 experiments toward SOTA" is really **"establish the first real accuracy program the
project has ever had, and calibrate the director that is its central unvalidated pillar."** On
this hardware (CPU-only) we cannot *beat* whisper-large-v3; the achievable, honest target is:
**the director auto-selects the WER-minimizing config for a given data + hardware budget, and we
measure that on real audio, not just synthetic.**

### A.2 What is real vs. simulated
- **Real, CPU-runnable** (`[ml]` extra): Whisper-LoRA fine-tune (PEFT + `Seq2SeqTrainer`) and
  wav2vec2-CTC fine-tune, with real `jiwer` WER/CER, CT2-int8 + safetensors export, and a real
  TTS×ASR **benchmark harness** (`scripts/benchmark.py` → `benchmarks/*.yaml`).
- **Simulation fallback** (`[SIMULATION]`): when ML deps are absent, the manifest is empty, no
  clip exists on disk, or `TALKTEACH_FORCE_SIMULATION=1`. Emits a synthetic smartness curve —
  **never to be confused with `1 − WER`** (D-012).
- **The only real measured numbers in the repo** — [`benchmarks/REPORT.md`](benchmarks/REPORT.md),
  `quick` config, en, 6 train / 6 eval, synthetic TTS: **whisper-tiny mean WER 0.131 · wav2vec2
  0.298** (per-cell best `piper+whisper 0.024`, worst `espeak+wav2vec2 0.405`).

### A.3 This machine (the experiment sandbox)
`[ml]`+`[tts]` stack installed (torch, transformers, peft, faster-whisper, jiwer, librosa,
soundfile, piper, datasets, ctranslate2, onnxruntime); **espeak-ng + ffmpeg present**;
**huggingface.co reachable**; **CPU-only, no GPU**; 662 GB free. → `small` and `medium` benchmark
brackets are runnable here; the `large` bracket (whisper-large-v3, parakeet) is **GPU-queued**.

### A.4 Structural findings that shape the program (dead knobs / unwired paths)
Verified against code, not docs:
- **Augmentation is not wired into any training collator.** `director.augmentation_for` returns a
  recommended `AugmentationConfig`, but neither the Whisper nor wav2vec2 collator reads it.
  (ROADMAP #46 says "collator wiring guarded"; it is in fact *absent*.) → **E09/E29.**
- **`early_stop_patience` is inert** — no `EarlyStoppingCallback` in either real loop; only the
  NaN-guard and cooperative cancel end a run early. → **E10.**
- **NaN "auto-rollback to last good checkpoint" is not wired** — `observe_good_checkpoint` writes
  `last_good_checkpoint` but no production code reads it; recovery rides on HF
  `load_best_model_at_end` (itself dropped in the fallback arg branch). → **E08.**
- **No automated test exercises the real training path *through production routing*** — the
  integration test calls `run_real_training` directly, bypassing `should_simulate`; the fast suite
  forces simulation. A regression in the real loop or the real-vs-sim decision passes CI. → **E07.**
- **LoRA `target_modules` is hardcoded** to `["q_proj","v_proj"]`, `lora_dropout=0.05` — not plan
  fields. → **E23.** wav2vec2 **ignores all LoRA fields** and full-fine-tunes with a frozen feature
  encoder. `DecodeOptions` (beam/temp/hotwords) affects **only** the faster-whisper inference path,
  **never** training or the benchmark's scoring (transformers `generate`). → **E27/E28.**

### A.5 The director's current constants (all "proposed defaults", uncalibrated — M4)
`director/policy.py`: sufficiency floor `MIN_TARGET_MINUTES=20`; `adaptive_target` 25 min
(Whisper-supported) / 45 min (non-Whisper); schedule `_choose_schedule` = **<30 min → 12 epochs,
lr 1e-4, freeze_encoder=True**; 30–120 min → 8 epochs; ≥120 min → 5 epochs, lr 8e-5; LoRA rank
**8 (<30 min) / 16 (≥30 min)**, alpha = 2·rank; effective-batch target **16**. Engine choice:
non-Whisper lang → wav2vec2 `xls-r-300m`; CUDA ≥16 GiB → whisper-medium; ≥6 GiB → whisper-small;
else whisper-tiny int8. `audio/quality.py`: `SNR_MIN_DB=10`, `CLIP_FRACTION_MAX=0.005`,
`SILENCE_FRACTION_MAX=0.8`, `RMS_QUIET_DBFS=-40`, `MIN_DURATION_S=0.4`. **None empirically tuned.**

### A.6 Mandatory guardrails (from prior dead-ends — do NOT re-learn these)
1. **Real speech, never tones** — sine tones have no phonetic content; WER on them is noise (D-013).
2. **Speaker/sentence-disjoint eval** — the in-product held-out split is a random 10 % with no
   overlap guard (Mo3 leakage); reported gains can be illusory. Every accuracy number below must
   name its eval-disjointness.
3. **Confirm the real path** — not `[SIMULATION]`, and **`passed` not `skipped`** (a skipped opt-in
   test masquerades as a pass; the first integration run silently skipped on a missing dep).
4. **Pin hyperparameters** for cross-engine comparison (`plan_from_config`, not director heuristics).
5. **Bound + clean disk** — an earlier run kept every checkpoint (~2.4 GB each) and blew a per-user
   quota, presenting as a *totally unresponsive shell*. `keep_artifacts: false` (default); check `df`
   if the shell wedges; `rm -rf ~/.cache/huggingface` to reclaim.
6. **Heavy imports stay function-local** (D-002); run via `backend/.venv/bin/python` (3.11).
7. **Synthetic-TTS WER is an indicative proxy only** — it must **not** drive changes to shipped
   `policy.py` defaults; CALIBRATION.md requires real labelled audio + the three GPU tiers for that.

---

## Part B — The next 30 experiments toward SOTA

Prioritized and grouped. Each carries a **pre-registered metric**, a **baseline**, a
**definition-of-done (DoD)**, and a **feasibility** tag:
**`CPU-now`** (runnable on this box) · **`CPU-heavy`** (runnable but hours) · **`GPU-queued`**
(needs a GPU) · **`build`** (needs a new adapter/code before it can run).
Priority: **P0** = do first (grounding + trust) · **P1** = high value · **P2** = breadth/ceiling.

### G1 — Establish the missing accuracy baseline *(the biggest credibility gap)*
| ID | Experiment | Metric (pre-registered) | Baseline | DoD | Feasibility | Pri |
|----|-----------|-------------------------|----------|-----|-------------|-----|
| **E01** | Reproduce the synthetic baseline (`quick.yaml`) on this box | whisper-tiny / wav2vec2 mean WER, CER | REPORT.md 0.131 / 0.298 | Harness runs **real path** (not sim/skip); numbers within noise of REPORT.md | CPU-now | **P0** |
| **E02** | **First real-audio baseline** — base (untrained) WER of whisper-tiny/base/small on a speaker-disjoint slice of **LibriSpeech test-clean** | per-model WER on real human speech | *none exists* | ≥1 external real WER anchor recorded per model | CPU-now | **P0** |
| **E03** | Real-audio baseline on **Common Voice** (accented/spontaneous) | per-model WER; gap vs E02 | — | WER gap clean-read vs recorded quantified | CPU-now | P1 |
| **E04** | **TTS→real generalization gap** — fine-tune whisper-tiny on TTS, eval on TTS-held-out **and** real audio | Δ(WER_real − WER_TTS) | — | Quantifies the Mo3 optimism; Δ recorded | CPU-now | **P0** |
| **E05** | **Leakage audit** — WER under the product's random-10 % split vs a sentence/speaker-disjoint split | Δ WER (leaky − disjoint) | — | Inflation from leakage measured; fix recommended | CPU-now | P1 |
| **E06** | **FLEURS multilingual spot-check** — base WER on en + es + one low-resource lang | per-lang base WER | — | Multilingual claim anchored with ≥3 langs | CPU-now | P2 |

### G2 — Trust the training path *(prerequisite for trusting any accuracy number)*
| ID | Experiment | Metric | Baseline | DoD | Feasibility | Pri |
|----|-----------|--------|----------|-----|-------------|-----|
| **E07** | Real-path-through-`train()` test (not `run_real_training` directly) | test passes with real WER curve, no `[SIMULATION]` | M3 gap | CI-able toy-model test asserts production routing picks real | CPU-now | **P0** |
| **E08** | Wire + verify **NaN auto-rollback** to `last_good_checkpoint` | injected NaN → recovers from last good ckpt | M2 gap (unwired) | Rollback asserted, or the "rolled back" message restated to match reality | CPU-now | **P0** |
| **E09** | Wire `AugmentationConfig` into the training collators | augmented batches observed in a run | #46 (absent) | Augmentation actually runs in the loop; unit-checked | CPU-now | P1 |
| **E10** | Wire `EarlyStoppingCallback` from `plan.early_stop_patience` | run halts on a val-WER plateau | inert knob | Early-stop fires; patience honored | CPU-now | P1 |
| **E11** | Sim-vs-real dispatch audit | both branches asserted, never mislabeled (D-012) | — | Test covers deps-present→real and deps-absent→sim | CPU-now | P1 |

### G3 — Reach stronger models *(the real accuracy ceiling)*
| ID | Experiment | Metric | Baseline | DoD | Feasibility | Pri |
|----|-----------|--------|----------|-----|-------------|-----|
| **E12** | Benchmark **distil-whisper-small.en** (166 M, already loads) vs whisper-base | WER + train(s) | whisper-base | Accuracy/speed tradeoff recorded | CPU-now | P1 |
| **E13** | Exercise **wav2vec2 XLS-R-300M** CTC on a non-English small set (director's low-resource pick) | real CTC WER | — | Real fine-tune completes; WER recorded | CPU-heavy | P1 |
| **E14** | Build a **`canary`** engine adapter (NVIDIA Canary, AED multitask) | loads + transcribes; joins `large` bracket | *unreachable* | Adapter passes `ASREngine` contract; base WER | GPU-queued · build | P2 |
| **E15** | Build a **`moonshine`** adapter (edge/streaming, small) | loads + transcribes | *unreachable* | Adapter passes contract; base WER (CPU-capable) | build | P2 |
| **E16** | Build a **`granite_speech`** adapter (IBM speech-LLM) | loads + transcribes | *unreachable* | Adapter passes contract; base WER | GPU-queued · build | P2 |
| **E17** | Exercise the **NeMo/Parakeet RNN-T** real train/export path (#25) | real fine-tune WER + `.nemo` export | scaffold only | Real path runs on a GPU; WER recorded | GPU-queued | P2 |
| **E18** | **whisper-large-v3** base + LoRA on the real eval sets (the open ceiling) | WER anchor for `large` bracket | — | Large-bracket real WER recorded | GPU-queued | P2 |

### G4 — Calibrate the director *(M4 — the #1 recommended score-raiser; synthetic-proxy caveat A.6.7)*
| ID | Experiment | Metric | Baseline | DoD | Feasibility | Pri |
|----|-----------|--------|----------|-----|-------------|-----|
| **E19** | **LoRA rank** sweep {4,8,16,32} (alpha=2r) per data bucket | WER vs rank | rank 8/16 | WER(rank) curve; recommendation (proxy-flagged) | CPU-now | P1 |
| **E20** | **Learning-rate** sweep {5e-5,1e-4,2e-4,5e-4} | WER + stability (NaN/plateau) | 1e-4 | WER(lr) curve; stable range identified | CPU-now | P1 |
| **E21** | **Epochs × data-quantity** {1,3,5,8,12} × {5,15,30 min} — validate `_choose_schedule` breakpoints | WER surface | 12@<30 / 8 / 5 | Breakpoints confirmed or adjusted | CPU-heavy | P1 |
| **E22** | **freeze_encoder on/off** at small data | Δ WER | freeze=True <30 min | Effect measured; default confirmed/flipped | CPU-now | P1 |
| **E23** | **LoRA `target_modules`** {q,v} vs {q,k,v,o} vs +fc | WER vs module set | q,v (hardcoded) | Best set identified; exposed as a plan field | CPU-now · build | P2 |
| **E24** | **Effective-batch** {4,8,16,32} via grad_accum | WER + train(s) | eff-batch 16 | WER/throughput tradeoff recorded | CPU-now | P2 |
| **E25** | **Audio-quality thresholds** (`SNR_MIN_DB`, `CLIP_FRACTION_MAX`, `SILENCE_FRACTION_MAX`) vs human GOOD/BAD labels | agreement with labeller | current defaults | Threshold→agreement curve on a labelled set | CPU-now · needs labels | P2 |
| **E26** | **`adaptive_target`** sufficiency floor — WER vs data-minutes knee | WER(minutes) knee vs 25/45-min floor | 25/45 min | Knee located; floor confirmed or moved | CPU-heavy | P2 |

### G5 — Decoding & augmentation ablations *(cheap, real, inference-time)*
| ID | Experiment | Metric | Baseline | DoD | Feasibility | Pri |
|----|-----------|--------|----------|-----|-------------|-----|
| **E27** | **Beam size** {1,3,5,8} on the faster-whisper transcribe path (real audio) | WER + latency | beam 5 | WER/latency tradeoff; default confirmed | CPU-now | P1 |
| **E28** | **Temperature-fallback + `initial_prompt`/hotword** bias on a vocab-heavy set | Δ WER from biasing | no bias | Biasing gain measured | CPU-now | P2 |
| **E29** | **Augmentation efficacy** at <10 min (after E09) — on/off | Δ WER | off | `augmentation_for` auto-enable validated | CPU-now | P1 |

### G6 — Robustness / real-world
| ID | Experiment | Metric | Baseline | DoD | Feasibility | Pri |
|----|-----------|--------|----------|-----|-------------|-----|
| **E30** | **Noise robustness + denoise gate** — babble/RIR SNR sweep on eval; then DeepFilterNet denoise (#30) | WER vs input SNR, ±denoise | clean | Degradation curve + whether denoise recovers it | CPU-now | P2 |

**Sequencing.** P0 first (E01, E02, E04, E07, E08) — ground the numbers and make the training path
trustworthy. Then P1 (real-audio breadth E03/E05, wiring E09/E10, calibration E19–E22, decode E27,
augment E29, distil E12). P2 is breadth + the GPU/adapter ceiling (E14–E18, E23–E26, E28, E30).

---

## Part C — Results log

Numbers below are recorded as they are produced. **Every synthetic-TTS WER is an indicative proxy
(A.6.7) and does not, by itself, change shipped `policy.py` defaults.** Eval-disjointness is named
per row.

| Exp | Date | Config / command | Metric | Result | Verdict | Notes |
|-----|------|------------------|--------|--------|---------|-------|
| E01 | _pending_ | `benchmark.py --config benchmarks/quick.yaml` | whisper-tiny / wav2vec2 mean WER | _to record_ | — | prompt-disjoint TTS eval; compare vs REPORT.md 0.131/0.298 |

_Remaining experiments E02–E30 are specified above and queued. This log is appended to as runs
complete; each entry states its eval-disjointness and whether it was the real path or `[SIMULATION]`._

---

### The honest one-liner
The project has a strong **capability** story and **zero accuracy baseline**. The highest-value
work is not chasing whisper-large-v3 on a CPU — it is **establishing the first real-audio baseline
(E02), proving the training path is real end-to-end (E07/E08), and calibrating the director (E19–E26)
that the whole "automatic and smart" value prop rests on.** Everything here is grounded in existing
harnesses; nothing requires inventing new ML.
