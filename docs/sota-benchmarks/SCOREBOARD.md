# TalkTeach SOTA Scoreboard

**Generated:** 2026-07-09T08:11:17.202418+00:00

**Headline:** 800/1000 — provisional

**Coverage:** 1/15 domains adequately powered · 7 directional (measured but under-powered, excluded from the mean) · 7 unmeasured/blocked. The headline is the mean over adequately-powered domains only.

## Summary

| # | Domain | Score | Band | Primary Metric | Value |
|---|---|---|---|---|---|
| 1 |  Long-Form Reliability — WER at 60 min Continuous Speech | **1000** | sota ⚠︎ directional | wer_delta_60min | 0.0044 |
| 2 | 💎 Export Portability — Quantization WER Fidelity | **950** | diamond ⚠︎ directional | wer_delta_export | 0.0020 |
| 3 | 💎 Decoding Quality — Optimal Beam + Hotword Bias | **950** | diamond ⚠︎ directional | domain_wer_optimal | 0.0155 |
| 4 | 💎 Speaker/Accent Generalization — Per-Speaker WER Variance | **950** | diamond ⚠︎ directional | per_speaker_wer_std | 0.0091 |
| 5 | 🥇 ASR Accuracy — Clean Speech | **800** | gold | wer | 0.0269 |
| 6 | 🥇 Noise Robustness — WER Degradation at 0dB SNR | **800** | gold ⚠︎ directional | wer_delta_at_0db | 0.0870 |
| 7 | 🥈 Inference Speed — Real-Time Factor | **700** | silver ⚠︎ directional | rtf | 0.2923 |
| 8 | 🥉 Resource Efficiency — Disk + RAM per Audio Minute | **600** | bronze ⚠︎ directional | mb_per_audio_minute | 463.6883 |
| 9 | 🧑‍🔬 ASR Accuracy — Spontaneous/Conversational Speech | **0** | human_needed | wer | — |
| 10 | 🧑‍🔬 Training Efficiency — Time-to-Convergence | **0** | human_needed | gpu_hours | — |
| 11 | 🧑‍🔬 Data Efficiency — WER vs. Training Minutes | **0** | human_needed | wer_at_5min | — |
| 12 | 🧑‍🔬 Multilingual Coverage — Languages with WER < 15% | **0** | human_needed | languages_under_15pct_wer | — |
| 13 | 🧑‍🔬 Augmentation Efficacy — Relative WER Reduction at 5 min Data | **0** | human_needed | rel_wer_reduction_5min | — |
| 14 | 🧑‍🔬 Director Auto-Selection — Optimal Config Choice Rate | **0** | human_needed | oracle_match_rate | — |
| 15 | ❓ Data Quality Gate — ROC-AUC vs. Human Labels | **0** | unmeasured | quality_gate_auc | — |

## Per-Domain Details

### d01_wer_clean: ASR Accuracy — Clean Speech

- **Score:** 800/1000 (gold)
- **Engine:** 
- **Samples:** 100
- **SOTA Reference:** whisper-large-v3 ≈ 1.8–2.7% WER on LibriSpeech test-clean depending on normalization (OpenAI HF model card ~2.7%); 1000-tier (<1.0%) exceeds all known production ASR

```json
{
  "wer": 0.026854219948849106,
  "cer": 0.008522054762092638,
  "num_clips": 100
}
```

### d02_wer_spontaneous: ASR Accuracy — Spontaneous/Conversational Speech

- **Score:** 0/1000 (human_needed)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** Best commercial APIs on Common Voice en

```json
{
  "status": "not measured",
  "requires": "a working Common Voice 17 loader (fails with EmptyDatasetError under HF datasets v5 / gated access here) or local CV clips at the SOTA cache"
}
```

### d03_train_efficiency: Training Efficiency — Time-to-Convergence

- **Score:** 0/1000 (human_needed)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** whisper-tiny LoRA on A100: ~0.17 GPU-hr to converge on 1hr data

```json
{
  "status": "not measured",
  "requires": "GPU training run measuring time-to-convergence on LibriSpeech train-clean-100 (extract the cached tar first)"
}
```

### d04_rtf: Inference Speed — Real-Time Factor

- **Score:** 700/1000 (silver)
- **Engine:** 
- **Samples:** 20
- **Headline:** excluded — directional: 20 clips < 100 required
- **SOTA Reference:** faster-whisper CT2 int8 tiny @ RTF ~0.02 on modern CPU

```json
{
  "rtf": 0.29227158901379263,
  "num_clips": 20
}
```

### d05_data_efficiency: Data Efficiency — WER vs. Training Minutes

- **Score:** 0/1000 (human_needed)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** Whisper-LoRA: ~3% WER with 30 min of fine-tuning data (literature)

```json
{
  "status": "not measured",
  "requires": "training runs at 5/15/30/60/120 min of LibriSpeech train-clean-100 to trace the WER-vs-data curve (extract the cached tar first)"
}
```

### d06_noise_robustness: Noise Robustness — WER Degradation at 0dB SNR

- **Score:** 800/1000 (gold)
- **Engine:** 
- **Samples:** 30
- **Headline:** excluded — directional: 30 clips < 50 required
- **SOTA Reference:** Denoised Whisper + DeepFilterNet: Δ<3% at 0dB SNR (research)

```json
{
  "clean": 0.017080745341614908,
  "snr_20db": 0.017080745341614908,
  "snr_10db": 0.027950310559006212,
  "snr_5db": 0.046583850931677016,
  "snr_0db": 0.10403726708074534,
  "num_clips": 30,
  "wer_delta_at_0db": 0.08695652173913043
}
```

### d07_multilingual: Multilingual Coverage — Languages with WER < 15%

- **Score:** 0/1000 (human_needed)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** whisper-large-v3: ~60 langs <15% WER on FLEURS (OpenAI 2023)

```json
{
  "status": "not measured",
  "requires": "multi-language FLEURS sweep (add configs beyond en_us to DATASET_SPECS['fleurs'] and a measure_multilingual loop) to count languages < 15% WER"
}
```

### d08_export_fidelity: Export Portability — Quantization WER Fidelity

- **Score:** 950/1000 (diamond)
- **Engine:** 
- **Samples:** 50
- **Headline:** excluded — directional: int8 quantization only (1 of 3 export targets; baseline is CT2-float32, not PyTorch fp32)
- **SOTA Reference:** CTranslate2 int8: Δ WER < 0.1% vs fp32 (CTranslate2 docs)

```json
{
  "wer_delta_export": 0.0020470829068577265,
  "wer_ct2_float32": 0.02047082906857728,
  "wer_ct2_int8": 0.022517911975435005,
  "num_clips": 50,
  "partial": "int8 quantization only (1 of 3 export targets; baseline is CT2-float32, not PyTorch fp32)"
}
```

### d09_augmentation: Augmentation Efficacy — Relative WER Reduction at 5 min Data

- **Score:** 0/1000 (human_needed)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** SpecAugment: ~20% rel WER reduction on small data (Park et al. 2019)

```json
{
  "status": "not measured",
  "requires": "paired with/without-augmentation training runs on train-clean-100; also blocked on the unwired augmentation collator (OVERALL.md wiring debt)"
}
```

### d10_decoding: Decoding Quality — Optimal Beam + Hotword Bias

- **Score:** 950/1000 (diamond)
- **Engine:** 
- **Samples:** 30
- **Headline:** excluded — directional: beam sweep on general read speech only; no hotword/OOV domain-vocab biasing
- **SOTA Reference:** Beam=5 + hotword on whisper-tiny: marginal gain on general speech

```json
{
  "domain_wer_optimal": 0.015527950310559006,
  "best_beam": 1,
  "wer_beam_1": 0.015527950310559006,
  "wer_beam_5": 0.017080745341614908,
  "num_clips": 30,
  "partial": "beam sweep on general read speech only; no hotword/OOV domain-vocab biasing"
}
```

### d11_longform: Long-Form Reliability — WER at 60 min Continuous Speech

- **Score:** 1000/1000 (sota)
- **Engine:** 
- **Samples:** 74
- **Headline:** excluded — directional: proxy: 10.22 min of concatenated read speech, not 60 min of naturally continuous audio
- **SOTA Reference:** Chunked Whisper with overlapping windows: Δ < 1% at 60 min

```json
{
  "wer_delta_60min": 0.004372267332916926,
  "wer_short_clips": 0.030605871330418487,
  "wer_longform": 0.03497813866333541,
  "longform_minutes": 10.22,
  "num_clips": 74,
  "partial": "proxy: 10.22 min of concatenated read speech, not 60 min of naturally continuous audio"
}
```

### d12_speaker_equity: Speaker/Accent Generalization — Per-Speaker WER Variance

- **Score:** 950/1000 (diamond)
- **Engine:** 
- **Samples:** 2
- **Headline:** excluded — directional: 2 speaker(s) < 10 required
- **SOTA Reference:** Best commercial ASR: per-speaker WER σ < 1.5% on LibriSpeech

```json
{
  "per_speaker_wer_std": 0.00909389597338464,
  "speaker_wer_spread": 0.012860711020370636,
  "num_speakers": 2
}
```

### d13_director_accuracy: Director Auto-Selection — Optimal Config Choice Rate

- **Score:** 0/1000 (human_needed)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** Calibrated director: picks WER-minimizing config ≥90% of time

```json
{
  "status": "not measured",
  "requires": "exhaustive training sweep over (hardware, data, language) scenarios to build the WER-minimizing oracle, then director-vs-oracle comparison"
}
```

### d14_quality_gate: Data Quality Gate — ROC-AUC vs. Human Labels

- **Score:** 0/1000 (unmeasured)
- **Engine:** tiny
- **Samples:** 100
- **SOTA Reference:** SNR-based gate: AUC ~0.88 on Common Voice labelled subset (estimated)

```json
{
  "quality_gate_pearson_r": 0.3832935135862975,
  "num_clips": 100,
  "partial": "Pearson r of gate SNR score vs measured WER; SNR component only; clean read speech (low quality variance); single engine"
}
```

### d15_resource_efficiency: Resource Efficiency — Disk + RAM per Audio Minute

- **Score:** 600/1000 (bronze)
- **Engine:** 
- **Samples:** 20
- **Headline:** excluded — directional: model disk footprint scored (per SOTA anchor); peak RAM reported not scored; marginal per-audio-min storage not accounted
- **SOTA Reference:** CTranslate2 whisper-tiny: ~50 MB disk, negligible RAM for inference

```json
{
  "mb_per_audio_minute": 463.6882514953613,
  "model_disk_mb": 463.6882514953613,
  "peak_rss_mb": 1039.62109375,
  "rss_delta_mb": 455.58984375,
  "audio_minutes": 2.608,
  "num_clips": 20,
  "partial": "model disk footprint scored (per SOTA anchor); peak RAM reported not scored; marginal per-audio-min storage not accounted"
}
```
