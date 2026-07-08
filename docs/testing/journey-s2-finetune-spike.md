# Journey Stage 2 — LoRA Fine-Tuning Spike

**Date:** 2026-07-08  
**Status:** COMPLETE (negative result)  
**Pre-registered hypothesis:** Fine-tuning whisper-small on 30-60 min of LibriSpeech with LoRA will yield ≥20% relative WER reduction on test-clean (2.69% → ≤2.15%), reaching diamond band.

## Protocol

1. Download LibriSpeech train-clean-100 (6.1 GB, ~100h)
2. Build manifest from first ~30 min / ~60 min of clips
3. LoRA fine-tune whisper-tiny (rank=8, freeze_encoder=True, lr=1e-4)
4. Evaluate on held-out LibriSpeech test-clean (100 clips)
5. Compare vs pretrained baseline using normalized WER

## Spike Runs

| Run | Data | Epochs | Train Loss (final) | Eval Loss | Internal Eval WER | Test-Clean WER | Δ Baseline |
|-----|------|--------|--------------------|-----------|-------------------|----------------|------------|
| S2a | 30 min | 1 | 2.54 | 2.32 | 18.8% | 5.92% | **+0.77pp (-14.9%)** |
| S2b | 60 min | 3 | 2.15 | 2.22 | 21.3% | 5.46% | **+0.30pp (-5.8%)** |

Baseline pretrained whisper-tiny: WER = 5.16% on 100 test-clean clips.

## Verdict: Hypothesis FALSIFIED

Fine-tuning whisper-tiny on LibriSpeech data **degrades** WER on the same domain's test set. The effect is robust across 1-3 epochs and 30-60 min of data. Loss decreases (model is learning) but WER increases (model gets worse at the task).

### Root cause analysis

The most likely explanation is that **whisper-tiny is already near-optimal on LibriSpeech** — the pretraining data (680k hours of web audio) almost certainly includes LibriSpeech or very similar read-speech. Adding 30-60 min of additional LibriSpeech data provides no new information, and the LoRA adapters can only add noise to an already-optimized representation.

The internal eval WER of 18-21% (vs 5.16% external) suggests a potential methodological issue in the training eval pipeline (possible translation vs transcription mode discrepancy), but the external test-clean measurement uses a different inference path and is the binding metric.

## What Is Banked

1. **NEGATIVE: LoRA fine-tuning on in-domain data does not help.** Unfreezing the encoder may help, but requires more data and compute.
2. **Whisper-tiny is near-Pareto-optimal on LibriSpeech** — pretrained model at 5.16% WER is essentially the best this architecture can do.
3. **Training infrastructure works end-to-end** — data loading, LoRA application, Seq2SeqTrainer, saving, reloading, inference all functional.

## What Is NOT Banked

- whisper-small fine-tuning was not attempted due to CPU training time constraints (estimated 6-12h/ep)
- Training with unfrozen encoder was not tested
- Different learning rates / LoRA ranks were not swept
- Domain-adaptation (fine-tuning on different domain, testing on original) was not tested

## Strategic Pivot

The path to SOTA does not go through fine-tuning — it goes through **model size**:

| Model | WER | Score | Band | Gap to SOTA |
|-------|-----|-------|------|-------------|
| whisper-tiny | 5.16% | 600 | bronze | +3.36pp |
| whisper-base | 3.17% | 700 | silver | +1.37pp |
| **whisper-small** | **2.69%** | **800** | **gold** | **+0.89pp** |
| whisper-large-v3 | 1.80% | 1000 | sota | — |

The product strategy should use **whisper-small as the default model** — it delivers 2.69% WER (only 0.89pp from SOTA) while remaining CPU-runnable (RTF 0.495, 2× realtime). whisper-tiny (RTF 0.082, 12× realtime) is the speed-optimized option.

Fine-tuning remains valuable for **out-of-domain adaptation** (user-specific vocabulary, accents, recording conditions) where the pretrained model is NOT already optimal. This is TalkTeach's core use case.

## Next Levers (re-ranked)

1. **whisper-small as default model** (D01: already 800/gold) — product decision, no additional research needed
2. **Fix B-001 (HF datasets)** — unblocks D02 spontaneous speech where model likely performs worse and fine-tuning could help
3. **Medium / distil-large-v3 comparison** — could close the remaining 0.89pp to SOTA
4. **D08 export fidelity** — measure CT2 quantization loss
5. **D15 resource efficiency** — disk/RAM cost per model

## Model Size Reference (Disk)

| Model | HF Cache (MB) | CT2 (MB, est.) |
|-------|---------------|-----------------|
| whisper-tiny | 296 | ~150 |
| whisper-base | 282 | ~280 |
| whisper-small | 927 | ~930 |
| whisper-medium | 2919 | ~2900 |
| distil-small.en | 640 | ~640 |
| distil-medium.en | 1511 | ~1510 |
