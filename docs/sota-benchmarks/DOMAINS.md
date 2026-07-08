# SOTA Benchmark Domains

All 15 domains defined in `backend/talkteach/sota/domains.py`. Each domain
measures one dimension of ASR quality on a 0–1000 scale anchored to a specific
real-world production system.

## Domain summary table

| ID | Name | Metric | Higher is better? | CPU? | Min samples |
|----|------|--------|-------------------|------|-------------|
| D01 | ASR Accuracy — Clean Speech | `wer` | No | Yes | 100 |
| D02 | ASR Accuracy — Spontaneous Speech | `wer` | No | Yes | 100 |
| D03 | Training Efficiency — Time-to-Convergence | `gpu_hours` | No | Yes | 5 |
| D04 | Inference Speed — Real-Time Factor | `rtf` | No | Yes | 100 |
| D05 | Data Efficiency — WER vs. Training Minutes | `wer_at_5min` | No | Yes | 50 |
| D06 | Noise Robustness — WER Degradation at 0dB SNR | `wer_delta_at_0db` | No | Yes | 50 |
| D07 | Multilingual Coverage — Languages < 15% WER | `languages_under_15pct_wer` | **Yes** | Yes | 100 |
| D08 | Export Portability — Quantization WER Fidelity | `wer_delta_export` | No | Yes | 50 |
| D09 | Augmentation Efficacy — Relative WER Reduction | `rel_wer_reduction_5min` | **Yes** | Yes | 50 |
| D10 | Decoding Quality — Optimal Beam + Hotword Bias | `domain_wer_optimal` | No | Yes | 30 |
| D11 | Long-Form Reliability — WER at 60 min | `wer_delta_60min` | No | Yes | 10 |
| D12 | Speaker/Accent Generalization — Per-Speaker WER Variance | `per_speaker_wer_std` | No | Yes | 100 |
| D13 | Director Auto-Selection — Optimal Config Choice Rate | `oracle_match_rate` | **Yes** | Yes | 20 |
| D14 | Data Quality Gate — ROC-AUC vs. Human Labels | `quality_gate_auc` | **Yes** | Yes | 200 |
| D15 | Resource Efficiency — Disk + RAM per Audio Minute | `mb_per_audio_minute` | No | Yes | 20 |

---

## D01: ASR Accuracy — Clean Speech

**Metric:** WER on LibriSpeech test-clean (read speech, studio quality).
The most widely cited ASR benchmark.

**SOTA=1000:** whisper-large-v3 @ ~1.8% WER on LibriSpeech test-clean (OpenAI, 2023)

**Engines:** `whisper_lora`, `wav2vec2_ctc`

**Datasets:** `librispeech_test_clean`

**Band thresholds (lower WER = higher score):**

| Score | WER ≤ | Description |
|-------|-------|-------------|
| 1000 | 1.0% | Surpasses best known production ASR |
| 950 | 1.5% | whisper-large-v3 territory |
| 900 | 2.0% | Near whisper-large-v3 |
| 800 | 3.0% | Strong fine-tuned OSS |
| 700 | 5.0% | Usable for clean speech applications |
| 600 | 8.0% | Functional baseline |

**Current baseline:** unmeasured — run `make sota-baseline`

---

## D02: ASR Accuracy — Spontaneous/Conversational Speech

**Metric:** WER on Common Voice English test set (accented, spontaneous, diverse
microphones). Measures real-world robustness beyond studio-quality read speech.

**SOTA=1000:** Best commercial APIs (Deepgram Nova-2, Whisper API) on Common Voice en

**Engines:** `whisper_lora`, `wav2vec2_ctc`

**Datasets:** `common_voice_en`

**Band thresholds (lower WER = higher score):**

| Score | WER ≤ | Description |
|-------|-------|-------------|
| 1000 | 3.0% | Best commercial API on conversational speech |
| 950 | 4.0% | Excellent real-world performance |
| 900 | 5.0% | Pro-grade conversational ASR |
| 800 | 8.0% | Solid OSS on spontaneous speech |
| 700 | 12.0% | Usable for many real-world tasks |
| 600 | 18.0% | Functional baseline on diverse audio |

**Current baseline:** unmeasured

---

## D03: Training Efficiency — Time-to-Convergence

**Metric:** Normalized GPU-hours to reach 90% of final WER on 1 hour of training
data. CPU hours are converted via a 10× factor.

**SOTA=1000:** whisper-tiny LoRA on A100: ~0.17 GPU-hr to converge on 1hr data

**Engines:** `whisper_lora`, `wav2vec2_ctc`

**Datasets:** `librispeech_train_clean_100`

**Band thresholds (lower GPU-hours = higher score):**

| Score | GPU-hrs ≤ | Description |
|-------|-----------|-------------|
| 1000 | 0.3 | Near-instant fine-tuning |
| 950 | 0.5 | whisper-tiny on A100 converges in ~10 min |
| 900 | 1.0 | Efficient fine-tune |
| 800 | 2.0 | Reasonable training time |
| 700 | 4.0 | Moderate cost |
| 600 | 8.0 | Trainable on a single GPU overnight |

**Current baseline:** unmeasured

---

## D04: Inference Speed — Real-Time Factor

**Metric:** RTF = decode_time / audio_duration on LibriSpeech test-clean.
RTF < 1 means faster than real-time. RTF < 0.1 means 10× real-time.

**SOTA=1000:** faster-whisper CT2 int8 tiny @ RTF ~0.02 on modern CPU

**Engines:** `whisper_lora`

**Datasets:** `librispeech_test_clean`

**Band thresholds (lower RTF = higher score):**

| Score | RTF ≤ | Description |
|-------|-------|-------------|
| 1000 | 0.01 | 100× real-time, edge-device capable |
| 950 | 0.02 | faster-whisper CTranslate2 int8 territory |
| 900 | 0.05 | Excellent throughput |
| 800 | 0.10 | Strong real-time performance |
| 700 | 0.30 | Usable for batch processing |
| 600 | 1.00 | Real-time capable |

**Current baseline:** unmeasured — run `make sota-baseline`

---

## D05: Data Efficiency — WER vs. Training Minutes

**Metric:** WER achieved with 5 minutes of training data on LibriSpeech.
Measures few-shot adaptation capability.

**SOTA=1000:** Whisper-LoRA: ~3% WER with 30 min of fine-tuning data (literature)

**Engines:** `whisper_lora`

**Datasets:** `librispeech_train_clean_100`

**Band thresholds (lower WER at 5 min = higher score):**

| Score | WER ≤ | Description |
|-------|-------|-------------|
| 1000 | 5.0% | Exceptional few-shot learning |
| 950 | 7.0% | Strong few-shot |
| 900 | 10.0% | Good data efficiency |
| 800 | 15.0% | Usable adaptation |
| 700 | 20.0% | Moderate data needs |
| 600 | 30.0% | High data requirement |

**Current baseline:** unmeasured — requires training at multiple data sizes

---

## D06: Noise Robustness — WER Degradation at 0dB SNR

**Metric:** Absolute WER increase from clean to 0dB SNR babble noise.
Smaller delta = more robust.

**SOTA=1000:** Denoised Whisper + DeepFilterNet: Δ<3% at 0dB SNR (research)

**Engines:** `whisper_lora`

**Datasets:** `librispeech_test_clean`, `wham_noise` (or synthetic)

**Band thresholds (lower WER delta = higher score):**

| Score | Δ WER ≤ | Description |
|-------|---------|-------------|
| 1000 | 2.0% | Exceptional noise robustness |
| 950 | 5.0% | Very robust to noise |
| 900 | 8.0% | Good noise handling |
| 800 | 12.0% | Moderate robustness |
| 700 | 20.0% | Noise-sensitive |
| 600 | 30.0% | Severely degraded by noise |

**Current baseline:** unmeasured

---

## D07: Multilingual Coverage — Languages with WER < 15%

**Metric:** Number of languages on FLEURS test where WER < 15%.
Higher is better.

**SOTA=1000:** whisper-large-v3: ~60 languages with usable WER on FLEURS (OpenAI, 2023)

**Engines:** `whisper_lora`

**Datasets:** `fleurs`

**Band thresholds (more languages = higher score):**

| Score | Languages ≥ | Description |
|-------|-------------|-------------|
| 1000 | 80 | Near-universal ASR |
| 950 | 60 | whisper-large-v3 territory |
| 900 | 40 | Strong multilingual |
| 800 | 20 | Solid coverage |
| 700 | 10 | Basic multilingual |
| 600 | 5 | Minimal multilingual support |

**Current baseline:** unmeasured — requires FLEURS dataset download

---

## D08: Export Portability — Quantization WER Fidelity

**Metric:** Absolute WER increase from fp32 base model to each export format
(CTranslate2 int8, ONNX fp16, safetensors). Smaller is better.

**SOTA=1000:** CTranslate2 int8 quantization: Δ WER < 0.1% vs fp32

**Engines:** `whisper_lora`

**Datasets:** `librispeech_test_clean`

**Band thresholds (lower WER delta = higher score):**

| Score | Δ WER ≤ | Description |
|-------|---------|-------------|
| 1000 | 0.1% | Lossless quantization |
| 950 | 0.3% | Negligible export loss |
| 900 | 0.5% | Minimal quality degradation |
| 800 | 1.0% | Acceptable trade-off |
| 700 | 2.0% | Noticeable but usable |
| 600 | 5.0% | Significant quality loss |

**Current baseline:** unmeasured

---

## D09: Augmentation Efficacy — Relative WER Reduction at 5 min Data

**Metric:** Relative WER reduction from SpecAugment + speed/pitch/noise
augmentation at 5 minutes of training data. Higher is better.

**SOTA=1000:** SpecAugment: ~20% relative WER reduction on small datasets (Park et al., 2019)

**Engines:** `whisper_lora`, `wav2vec2_ctc`

**Datasets:** `librispeech_train_clean_100`

**Band thresholds (higher relative reduction = higher score):**

| Score | Rel. reduction ≥ | Description |
|-------|-----------------|-------------|
| 1000 | 30% | Exceptional augmentation benefit |
| 950 | 25% | Strong augmentation impact |
| 900 | 20% | Good augmentation efficacy |
| 800 | 15% | Useful augmentation |
| 700 | 10% | Modest benefit |
| 600 | 5% | Marginal improvement |

**Current baseline:** unmeasured — requires augmentation wiring (E09, E29)

---

## D10: Decoding Quality — Optimal Beam + Hotword Bias

**Metric:** WER with optimal beam search + hotword biasing on a domain-specific
vocabulary set. Also measures OOV error reduction.

**SOTA=1000:** Beam=5 + hotword prompt on whisper-tiny: marginal gain on general speech

**Engines:** `whisper_lora`

**Datasets:** `librispeech_test_clean`

**Band thresholds (lower domain WER = higher score):**

| Score | WER ≤ | Description |
|-------|-------|-------------|
| 1000 | 1.0% | Domain WER ≤ 1.0% with bias, OOV ≥ 50% reduction |
| 950 | 2.0% | Domain WER ≤ 2.0%, OOV ≥ 40% |
| 900 | 3.0% | Domain WER ≤ 3.0%, OOV ≥ 30% |
| 800 | 5.0% | Domain WER ≤ 5.0%, OOV ≥ 20% |
| 700 | 8.0% | Domain WER ≤ 8.0%, OOV ≥ 10% |
| 600 | 12.0% | Domain WER ≤ 12.0%, OOV > 0% |

**Current baseline:** unmeasured — requires decode control experiments (E27, E28)

---

## D11: Long-Form Reliability — WER at 60 min Continuous Speech

**Metric:** Absolute WER increase from 1-minute clip to a 60-minute continuous
recording. Measures chunking/overlapping-window quality.

**SOTA=1000:** Chunked Whisper with overlapping windows: Δ < 1% at 60 min

**Engines:** `whisper_lora`

**Datasets:** `librispeech_test_clean`

**Band thresholds (lower WER delta at 60 min = higher score):**

| Score | Δ WER ≤ | Description |
|-------|---------|-------------|
| 1000 | 0.5% | Near-perfect long-form handling |
| 950 | 1.0% | Excellent chunking |
| 900 | 2.0% | Good long-form reliability |
| 800 | 3.0% | Moderate boundary artifacts |
| 700 | 5.0% | Noticeable degradation |
| 600 | 8.0% | Significant long-form issues |

**Current baseline:** unmeasured

---

## D12: Speaker/Accent Generalization — Per-Speaker WER Variance

**Metric:** Standard deviation of per-speaker WER on LibriSpeech test-clean.
Lower σ = more consistent performance.

**SOTA=1000:** Best commercial ASR: per-speaker WER σ < 1.5% on LibriSpeech

**Engines:** `whisper_lora`, `wav2vec2_ctc`

**Datasets:** `librispeech_test_clean`

**Band thresholds (lower std dev = higher score):**

| Score | σ ≤ | Description |
|-------|-----|-------------|
| 1000 | 0.5% | Perfect speaker equity |
| 950 | 1.0% | Excellent consistency across speakers |
| 900 | 1.5% | Good generalization |
| 800 | 2.5% | Moderate speaker variation |
| 700 | 4.0% | Significant variation |
| 600 | 6.0% | Large speaker-dependent differences |

**Current baseline:** unmeasured — run `make sota-baseline`

---

## D13: Director Auto-Selection — Optimal Config Choice Rate

**Metric:** Percentage of (hardware, data, language) scenarios where the director
selects the WER-minimizing config. This is the central validation of TalkTeach's
"zero-config" promise.

**SOTA=1000:** Calibrated director: should pick WER-minimizing config in ≥ 90% of scenarios

**Engines:** `whisper_lora`, `wav2vec2_ctc`

**Datasets:** `librispeech_train_clean_100`

**Band thresholds (higher match rate = higher score):**

| Score | Match rate ≥ | Description |
|-------|-------------|-------------|
| 1000 | 98% | Near-perfect auto-selection |
| 950 | 95% | Excellent director accuracy |
| 900 | 90% | Strong auto-selection, few mistakes |
| 800 | 80% | Good, but leaves some gains on the table |
| 700 | 65% | Better than random, needs calibration |
| 600 | 50% | Marginally better than coin flip |

**Current baseline:** unmeasured — requires exhaustive oracle sweep

---

## D14: Data Quality Gate — ROC-AUC vs. Human Labels

**Metric:** ROC-AUC of the audio quality gate (SNR + clipping + silence checks)
against human GOOD/BAD labels. Also: Pearson r between quality score and
downstream WER.

**SOTA=1000:** SNR-based gate: AUC ~0.88 on Common Voice labelled subset (estimated)

**Engines:** (none — audio-only gate)

**Datasets:** `labelled_quality_set` (requires hand-labelling)

**Band thresholds (higher AUC = higher score):**

| Score | AUC ≥ | Description |
|-------|-------|-------------|
| 1000 | 0.95 | Near-perfect quality discrimination |
| 950 | 0.92 | Excellent gate precision |
| 900 | 0.88 | Strong quality prediction |
| 800 | 0.82 | Good discrimination |
| 700 | 0.75 | Moderate, catches obvious bad clips |
| 600 | 0.65 | Better than random, misses many |

**Current baseline:** unmeasured — requires hand-labelled quality set

---

## D15: Resource Efficiency — Disk + RAM per Audio Minute

**Metric:** Disk footprint (MB) + normalized RAM-hours per minute of transcribed
audio, covering the full pipeline: import → decode → quality → train → export →
inference.

**SOTA=1000:** CTranslate2 whisper-tiny: ~50 MB disk, negligible RAM for inference

**Engines:** `whisper_lora`

**Datasets:** `librispeech_test_clean`

**Band thresholds (lower MB per audio-minute = higher score):**

| Score | MB/min ≤ | Description |
|-------|----------|-------------|
| 1000 | 10 | Edge-device capable |
| 950 | 20 | Very lightweight |
| 900 | 50 | Efficient |
| 800 | 100 | Reasonable desktop footprint |
| 700 | 200 | Moderate resource usage |
| 600 | 500 | Heavy but functional |

**Current baseline:** unmeasured

---

## Programmatic access

```python
from talkteach.sota.domains import ALL_DOMAINS, get_domain

# List all domains
for d in ALL_DOMAINS:
    print(f"{d.id}: {d.name} ({d.metric})")

# Look up a specific domain
d01 = get_domain("d01_wer_clean")
print(d01.sota_1000_reference)
# => "whisper-large-v3 @ 1.8% WER on LibriSpeech test-clean (OpenAI, 2023)"

# Check if a value achieves a band
from talkteach.sota.scoring import score_against_bands
bands = [(b.score, b.threshold) for b in d01.bands]
score, band = score_against_bands(0.035, bands, higher_is_better=False)
print(f"WER 3.5% → Score {score}, Band: {band}")
# => WER 3.5% → Score 800, Band: gold
```

## Cross-references

- `backend/talkteach/sota/domains.py` — source of all domain definitions
- `backend/talkteach/sota/scoring.py:128` — `score_against_bands()`
- `backend/talkteach/sota/harness.py:322` — `run_domain()` dispatches measurements
- `docs/sota-benchmarks/README.md` — the 1000-point scale overview
- `docs/sota-benchmarks/METHODOLOGY.md` — statistical protocol
- `docs/sota-benchmarks/BASELINES.md` — current TalkTeach baseline scores
- `docs/sota-benchmarks/VALIDATION.md` — how to run each domain's validation
