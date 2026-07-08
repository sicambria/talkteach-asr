# INS-001 — LoRA Fine-Tuning Degrades In-Domain WER

**Date:** 2026-07-08  
**Type:** reference  
**Area:** training / fine-tuning  
**Status:** active  
**Trigger:** Stage 2 spike: LoRA fine-tune whisper-tiny on 30-60 min LibriSpeech → WER worsened
**Guardrail Links:** `experiments/e02_lora_finetune_spike.yaml` (falsified hypothesis), `docs/testing/journey-s2-finetune-spike.md` (experiment report), `scripts/journey/s2_spike.py` (spike harness)
**Automation Links:** `scripts/journey/s2_spike.py` (reusable spike harness), `experiments/e02_lora_finetune_spike.yaml` (pre-registered experiment), `backend/talkteach/director/plan_config.py` (pinned training plans)

## Summary

Fine-tuning whisper-tiny on 30-60 minutes of LibriSpeech data using LoRA (rank=8, frozen encoder, lr=1e-4) consistently degraded WER on the LibriSpeech test-clean eval set:
- 1 epoch, 30 min: 5.16% → 5.92% (-14.9% relative)
- 3 epochs, 60 min: 5.16% → 5.46% (-5.8% relative)

The model's training loss decreased (2.89 → 2.15 over 3 epochs) confirming optimization was working, but the WER metric moved in the wrong direction.

## Root Cause

**Whisper-tiny is near-Pareto-optimal on LibriSpeech.** The pretraining corpus (680k hours of web audio) almost certainly includes LibriSpeech data or very similar read-speech recordings. Adding 30-60 minutes of in-domain data provides no new information — the LoRA adapters can only add noise to an already-optimized representation.

This is an instance of the more general principle: **fine-tuning helps on data the model is NOT already good at.** When the pretrained model is already near the ceiling for a domain, additional same-domain data degrades performance.

## Prevention

- Before committing to a fine-tuning experiment, first verify the gap: if pretrained baseline is already close to SOTA on the target domain, fine-tuning is unlikely to help
- Reserve fine-tuning for out-of-domain adaptation: user-specific vocabulary, accents, recording conditions, and domains where the pretrained model is provably weak
- When fine-tuning is indicated, use a data-spike protocol: 1 epoch on 10 min to detect degradation before committing to full training

## Guardrail Updates

- New experimental protocol: spike with minimum viable training (1 epoch, small data) before scaling
- Pre-registration requirement: state the pretrained baseline gap to SOTA and justify why fine-tuning should close it
- Codified in OVERALL.md Part B — E12-E18 experiments should verify pretrained baseline gap before fine-tuning

## Automation Follow-Up

- [ ] Add spike protocol to experiment workflow in AGENTS.md
- [ ] Measure D02 (spontaneous speech) where pretrained model is likely weak → test fine-tuning on out-of-domain data
- [ ] Run whisper-small fine-tune spike to confirm the in-domain degradation pattern holds for larger models

## Related Links

- `docs/testing/journey-s2-finetune-spike.md` — complete experiment report
- `experiments/e02_lora_finetune_spike.yaml` — registered experiment (FALSIFIED)
- `scripts/journey/s2_spike.py` — reusable spike harness
