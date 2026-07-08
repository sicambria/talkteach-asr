# Hot memory (auto-loaded)

> The lean, always-loaded context index. Keep it short. Link deeper notes with [[slug]].
> Update this in the same change as the work it describes.

## Now
- Last captured session: 2026-07-08 (see `.harness/memory/episodic/2026-07-08.md`)
- **Active experiments:** E01 (banked), E02 (falsified). Next: Stage 3 — model-size scaling.
- **Blockers:** B-001 (HF datasets v5 incompat — blocks D02, D07)
- **Scoreboard:** 4/15 domains measured, overall 788/1000 (silver). whisper-small @ 2.69% WER is the strategic anchor.

## Journey State (2026-07-08)
- **S1 (banked):** First real-audio baseline — whisper-small WER 2.69% (800/gold, 0.89pp from SOTA).
  Two critical bugs fixed: transcript parsing (INC-002) and WER normalization (INC-001).
  D04 RTF 0.495 (600/bronze), D06 noise delta 8.7pp (800/gold), D12 speaker sigma 0.91% (950/diamond).
- **S2 (falsified):** LoRA fine-tuning on in-domain LibriSpeech degrades WER (-6% to -15%).
  Whisper-tiny is near-Pareto-optimal on LibriSpeech. Model size, not fine-tuning, closes the gap.
  Insight: fine-tuning helps on out-of-domain data where the pretrained model is weak (INS-001).
- **Next lever:** whisper-small is already only 0.89pp from SOTA. Stage 3 focuses on model-size
  scaling (distil-large-v3, medium) + fixing B-001 to unblock D02 spontaneous speech.

## Key Numbers (banked)
| Domain | Model | Metric | Value | Score | Band |
|--------|-------|--------|-------|-------|------|
| D01 Clean WER | small | WER | 2.69% | 800 | gold |
| D04 RTF | small | RTF | 0.495 | 600 | bronze |
| D06 Noise | small | Δ@0dB | 8.70pp | 800 | gold |
| D12 Speaker | small | σ WER | 0.91% | 950 | diamond |

## Invariants to remember
- Default branch is protected: substantive work goes through a worktree + merge.
- Never `--no-verify`. Fix the gate, log the decision.
- WER measurements MUST use ASR normalization (lowercase + punct removal) — see INC-001.
- LibriSpeech `.trans.txt` uses `{speaker}-{chapter}.trans.txt` naming — see INC-002.
- Always spike fine-tuning before scaling: 1 epoch on small data to detect degradation — see INS-001.
- Behavioral contract + agent state machine + stop triggers: `.harness/memory/rules.md` (tiers T0–T3).
  Invariant registry + blast-radius Protection Matrix: `.harness/INVARIANTS.md`. Re-read the T0/T1 tiers +
  state machine after compaction and at plan→execution transitions.

<!-- Contract-read canary (L4) — see the protocol in AGENTS.md. Do not remove. -->
<!--CANARY: COMPASS-->
