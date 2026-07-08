# TalkTeach SOTA Scoreboard

**Generated:** 2026-07-08T14:00:54.165418+00:00

**Headline:** 800/1000 — provisional

**Coverage:** 1/15 domains adequately powered · 3 directional (measured but under-powered, excluded from the mean) · 11 unmeasured/blocked. The headline is the mean over adequately-powered domains only.

## Summary

| # | Domain | Score | Band | Primary Metric | Value |
|---|---|---|---|---|---|
| 1 | 💎 Speaker/Accent Generalization | **950** | diamond ⚠︎ directional | per_speaker_wer_std | 0.0091 |
| 2 | 🥇 ASR Accuracy — Clean Speech | **800** | gold | wer | 0.0268 |
| 3 | 🥇 Noise Robustness - WER at 0dB SNR | **800** | gold ⚠︎ directional | wer_delta_at_0db | 0.0870 |
| 4 | 🥉 Inference Speed - Real-Time Factor | **600** | bronze ⚠︎ directional | rtf | 0.4950 |
| 5 | ❓ ASR Accuracy - Spontaneous/Conversational | **0** | unmeasured | wer | — |
| 6 | ❓ Training Efficiency | **0** | unmeasured | gpu_hours | — |
| 7 | ❓ Data Efficiency | **0** | unmeasured | wer_at_5min | — |
| 8 | ❓ Multilingual Coverage | **0** | unmeasured | languages_under_15pct_wer | — |
| 9 | ❓ Export Portability | **0** | unmeasured | wer_delta_export | — |
| 10 | ❓ Augmentation Efficacy | **0** | unmeasured | rel_wer_reduction_5min | — |
| 11 | ❓ Decoding Quality | **0** | unmeasured | domain_wer_optimal | — |
| 12 | ❓ Long-Form Reliability | **0** | unmeasured | wer_delta_60min | — |
| 13 | ❓ Director Auto-Selection | **0** | unmeasured | oracle_match_rate | — |
| 14 | ❓ Data Quality Gate | **0** | unmeasured | quality_gate_auc | — |
| 15 | ❓ Resource Efficiency | **0** | unmeasured | mb_per_audio_minute | — |

## Per-Domain Details

### d01_wer_clean: ASR Accuracy — Clean Speech

- **Score:** 800/1000 (gold)
- **Engine:** small
- **Samples:** 100
- **SOTA Reference:** whisper-large-v3 ≈ 1.8–2.7% WER on LibriSpeech test-clean depending on normalization (OpenAI HF model card ~2.7%); 1000-tier (<1.0%) exceeds all known production ASR
- **Notes:** First real-audio baseline: whisper-small (off-the-shelf, CT2 int8) on 100 LibriSpeech test-clean clips spanning only 2 speakers (95% CI 2.2-7.1%). Not comparable to full-test-set SOTA anchors; a representative number needs the full 40-speaker set.

```json
{
  "wer": 0.02685,
  "cer": 0.00852,
  "num_clips": 100
}
```

### d04_rtf: Inference Speed - Real-Time Factor

- **Score:** 600/1000 (bronze)
- **Engine:** small
- **Samples:** 20
- **Headline:** excluded — directional: 20 clips < 100 required
- **SOTA Reference:** faster-whisper CT2 int8 tiny @ RTF ~0.02 on modern CPU
- **Notes:** ~2x real-time. Accuracy-speed trade-off vs tiny (RTF 0.082, WER 5.16%).

```json
{
  "rtf": 0.495,
  "num_clips": 20
}
```

### d06_noise_robustness: Noise Robustness - WER at 0dB SNR

- **Score:** 800/1000 (gold)
- **Engine:** small
- **Samples:** 30
- **Headline:** excluded — directional: 30 clips < 50 required
- **SOTA Reference:** Denoised Whisper + DeepFilterNet: Δ<3% at 0dB SNR (research)
- **Notes:** 8.7pp degradation at 0dB. Denoising needed for improvement.

```json
{
  "wer_delta_at_0db": 0.08696,
  "clean": 0.01708,
  "num_clips": 30
}
```

### d12_speaker_equity: Speaker/Accent Generalization

- **Score:** 950/1000 (diamond)
- **Engine:** small
- **Samples:** 2
- **Headline:** excluded — directional: 2 speaker(s) < 10 required
- **SOTA Reference:** Best commercial ASR: per-speaker WER σ < 1.5% on LibriSpeech
- **Notes:** n=2 speakers (directional). Full 40-speaker measurement needed.

```json
{
  "per_speaker_wer_std": 0.00909,
  "speaker_wer_spread": 0.01286,
  "num_speakers": 2
}
```

### d02_wer_spontaneous: ASR Accuracy - Spontaneous/Conversational

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** Best commercial APIs on Common Voice en
- **Notes:** Blocked: HF datasets v5 incompat (B-001)

```json
{}
```

### d03_train_efficiency: Training Efficiency

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** whisper-tiny LoRA on A100: ~0.17 GPU-hr to converge on 1hr data
- **Notes:** Requires training run

```json
{}
```

### d05_data_efficiency: Data Efficiency

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** Whisper-LoRA: ~3% WER with 30 min of fine-tuning data (literature)
- **Notes:** Requires training at multiple data sizes

```json
{}
```

### d07_multilingual: Multilingual Coverage

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** whisper-large-v3: ~60 langs <15% WER on FLEURS (OpenAI 2023)
- **Notes:** Blocked: HF datasets v5 incompat (B-001)

```json
{}
```

### d08_export_fidelity: Export Portability

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** CTranslate2 int8: Δ WER < 0.1% vs fp32 (CTranslate2 docs)
- **Notes:** Requires CT2 export + compare to fp32

```json
{}
```

### d09_augmentation: Augmentation Efficacy

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** SpecAugment: ~20% rel WER reduction on small data (Park et al. 2019)
- **Notes:** Requires training with augmentation variants

```json
{}
```

### d10_decoding: Decoding Quality

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** Beam=5 + hotword on whisper-tiny: marginal gain on general speech
- **Notes:** Requires beam/hotword sweep

```json
{}
```

### d11_longform: Long-Form Reliability

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** Chunked Whisper with overlapping windows: Δ < 1% at 60 min
- **Notes:** Requires long-form audio

```json
{}
```

### d13_director_accuracy: Director Auto-Selection

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** Calibrated director: picks WER-minimizing config ≥90% of time
- **Notes:** Requires director calibration

```json
{}
```

### d14_quality_gate: Data Quality Gate

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** SNR-based gate: AUC ~0.88 on Common Voice labelled subset (estimated)
- **Notes:** Requires hand-labelled quality set

```json
{}
```

### d15_resource_efficiency: Resource Efficiency

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** CTranslate2 whisper-tiny: ~50 MB disk, negligible RAM for inference
- **Notes:** Requires disk/RAM measurement

```json
{}
```
