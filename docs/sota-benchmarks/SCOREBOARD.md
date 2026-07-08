# TalkTeach SOTA Scoreboard

**Generated:** 2026-07-08T14:00:54.165418+00:00
**Overall Mean:** 788/1000 — Band: silver

## Summary

| # | Domain | Score | Band | Primary Metric | Value |
|---|---|---|---|---|
| 1 | 💎 Speaker/Accent Generalization | **950** | diamond | per_speaker_wer_std | 0.0091 |
| 2 | 🥇 ASR Accuracy — Clean Speech | **800** | gold | wer | 0.0268 |
| 3 | 🥇 Noise Robustness - WER at 0dB SNR | **800** | gold | wer_delta_at_0db | 0.0870 |
| 4 | 🥉 Inference Speed - Real-Time Factor | **600** | bronze | rtf | 0.4950 |
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
- **SOTA Reference:** whisper-large-v3 @ 1.8% WER on LibriSpeech test-clean (OpenAI, 2023)
- **Notes:** First real-audio baseline. 2.69% WER - 0.89pp from SOTA.

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
- **SOTA Reference:** Denoised Whisper + DeepFilterNet: delta <3% at 0dB SNR
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
- **SOTA Reference:** Best commercial ASR: per-speaker WER sigma < 1.5%
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
- **SOTA Reference:** 
- **Notes:** Blocked: HF datasets v5 incompat (B-001)

```json
{}
```

### d03_train_efficiency: Training Efficiency

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** 
- **Notes:** Requires training run

```json
{}
```

### d05_data_efficiency: Data Efficiency

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** 
- **Notes:** Requires training at multiple data sizes

```json
{}
```

### d07_multilingual: Multilingual Coverage

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** 
- **Notes:** Blocked: HF datasets v5 incompat (B-001)

```json
{}
```

### d08_export_fidelity: Export Portability

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** 
- **Notes:** Requires CT2 export + compare to fp32

```json
{}
```

### d09_augmentation: Augmentation Efficacy

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** 
- **Notes:** Requires training with augmentation variants

```json
{}
```

### d10_decoding: Decoding Quality

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** 
- **Notes:** Requires beam/hotword sweep

```json
{}
```

### d11_longform: Long-Form Reliability

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** 
- **Notes:** Requires long-form audio

```json
{}
```

### d13_director_accuracy: Director Auto-Selection

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** 
- **Notes:** Requires director calibration

```json
{}
```

### d14_quality_gate: Data Quality Gate

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** 
- **Notes:** Requires hand-labelled quality set

```json
{}
```

### d15_resource_efficiency: Resource Efficiency

- **Score:** 0/1000 (unmeasured)
- **Engine:** 
- **Samples:** 0
- **SOTA Reference:** 
- **Notes:** Requires disk/RAM measurement

```json
{}
```
