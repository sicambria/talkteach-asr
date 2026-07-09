# Hot memory (auto-loaded)

> The lean, always-loaded context index. Keep it short. Link deeper notes with [[slug]].
> Update this in the same change as the work it describes.

## Now
- Last captured session: 2026-07-09 (see `.harness/memory/episodic/2026-07-09.md`)
- **Active experiments:** E01 (banked), E02 (falsified). Next: Stage 3 — model-size scaling.
- **Blockers:** B-001 torchcodec decode barrier **FIXED** (loader uses `Audio(decode=False)`+soundfile). D02 still blocked by CV17 `EmptyDatasetError` (datasets v5 / gated); D07 needs multi-config FLEURS (metric counts languages, spec is single en_us).
- **Scoreboard:** headline **provisional** — **8/15 measured** but only **1 eligible** (D01 clean WER, gold). **7 directional**: under-powered (D04/D06/D12) + **scope-partial** (D08/D10/D11/D15, gated out by `metrics["partial"]`). **7 abstain (`human_needed`, score 0, never fabricated)**: D02/D07 (loader) + D03/D05/D09/D13 (need training) + D14 (needs labels). No `validate_*` may hardcode a positive score (static test). Numbers single-sourced in `docs/sota-benchmarks/SCOREBOARD.md`; canonical narrative in `OVERALL.md`. Regenerate: full `bash scripts/sota/run_all.sh --baseline --engines small`; re-present only with `make sota-rescore`.

## Journey State (2026-07-08)
- **S1 (banked):** First real-audio baseline — whisper-small clean-speech in the gold band (D01),
  measured on 100 clips / **2 speakers** (wide CI) — not comparable to full-set SOTA anchors → E06.
  Two critical bugs fixed: transcript parsing (INC-002) and WER normalization (INC-001).
  D04 (RTF), D06 (noise), D12 (speaker σ) are measured but **directional** (under-powered). Exact
  numbers: `docs/sota-benchmarks/SCOREBOARD.md` (single source).
- **S2 (falsified):** LoRA fine-tuning on in-domain LibriSpeech degrades WER (-6% to -15%).
  Whisper-tiny is near-Pareto-optimal on LibriSpeech. Model size, not fine-tuning, closes the gap.
  Insight: fine-tuning helps on out-of-domain data where the pretrained model is weak (INS-001).
- **Next lever:** Stage 3 — model-size scaling (distil-large-v3, medium) + fix B-001 to unblock
  D02/D07 + make D01/D12 representative across ≥10 speakers (E06). Fine-tuning is retargeted at
  out-of-domain adaptation (INS-001), not in-domain.

## Key Numbers (single-sourced — do not copy here)
Live per-domain scores, bands, CIs, and `directional` flags are in
`docs/sota-benchmarks/SCOREBOARD.md` / `.json` (regenerate with `make sota-rescore`); the canonical
narrative is `OVERALL.md`. Numbers are deliberately not duplicated in memory to prevent drift.
Shape only: D01 clean-speech = the one adequately-powered domain (gold); D04/D06/D12 = directional;
D02/D07 = blocked (B-001); the rest unmeasured.

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
