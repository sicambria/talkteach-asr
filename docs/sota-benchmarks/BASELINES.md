# SOTA Baselines — how to measure them

> **Reference appendix to [`OVERALL.md`](../../OVERALL.md)** — the single authoritative SOTA
> document. **This file no longer holds a baseline table** — that hand-maintained copy drifted from
> the generator (the root cause this consolidation fixed). The **live baseline scores are in the
> generated [`SCOREBOARD.md`](SCOREBOARD.md) / `.json`** (single source of numbers), summarized in
> `OVERALL.md` Part A.2. This file only documents *how to produce and regenerate* baselines.

## Current state (pointer, not a copy)
See [`SCOREBOARD.md`](SCOREBOARD.md) for the current per-domain scores, bands, coverage, and the
`directional` flags, and `OVERALL.md` Part A.2 for the qualitative summary. As of journey S1
(2026-07-08) one domain (D01 clean-speech WER) is adequately powered; D04/D06/D12 are measured but
directional; D02/D07 are blocked by **B-001**; the rest are unmeasured.

## How to produce baselines

```bash
# Download all SOTA datasets (~2.1 GB)
make sota-download

# Measure baseline (untrained) WER across all SOTA domains
make sota-baseline

# Or with specific engines
SOTA_ENGINES=whisper-tiny,whisper-small make sota-baseline

# Run full SOTA validation (train+eval) — needs [ml], CPU: hours
make sota

# Run a single domain's baseline
python scripts/sota/validate_d01_wer_clean.py --baseline-only
python scripts/sota/validate_d04_rtf.py --baseline-only
```

## How to regenerate the scoreboard (no re-measurement)

After a scoring-policy or domain-definition change, re-apply scoring to the already-banked raw
metrics — seconds, no GPU/network — with:

```bash
make sota-rescore   # rewrites SCOREBOARD.{md,json} from their own metrics; preserves the stamp
```

A *fresh* measurement (`make sota-baseline` / `make sota`) advances the `generated` stamp; when it
does, update the stamp reference at the top of `OVERALL.md` in the same change. **Never hand-edit
the numbers in `SCOREBOARD.*` or copy them into prose** — that is exactly the drift this layout
prevents.

## Synthetic-TTS proxy (a different, separate source)
The TTS×ASR benchmark harness (`scripts/benchmark.py` → `benchmarks/quick.yaml`) reports whisper vs
wav2vec2 on **synthetic TTS speech**, single-sourced in [`benchmarks/REPORT.md`](../../benchmarks/REPORT.md).
Per `OVERALL.md` A.6.7 these are **indicative proxies only** — never real WER, never a driver of
shipped `policy.py` defaults.

## Domain readiness (harness map)

| Domain | Harness method | Blockers |
|--------|----------------|----------|
| D01 / D04 / D06 / D12 | `measure_base_wer` / `measure_rtf` / `measure_noise_robustness` / `measure_speaker_equity` | Dataset download only (D06 also needs synthetic noise) |
| D05 / D13 | `measure_data_efficiency` / `measure_director_accuracy` — stubs | Training / exhaustive oracle sweep |
| D14 | not wired | Hand-labelled quality set |
| D02, D03, D07–D11, D15 | dedicated `validate_dXX_*.py` per domain | D02/D07 blocked by B-001; others need training/export/long-form data |

## Cross-references
- [`SCOREBOARD.md`](SCOREBOARD.md) — the auto-generated, authoritative scores
- [`DOMAINS.md`](DOMAINS.md) — full domain definitions with thresholds and anchors
- [`METHODOLOGY.md`](METHODOLOGY.md) — statistical protocol + the headline gate
- [`VALIDATION.md`](VALIDATION.md) — running the benchmarks
- [`OVERALL.md`](../../OVERALL.md) — the authoritative SOTA document (Parts A.2, C, E)
- `backend/talkteach/sota/harness.py` — per-domain measurement dispatch
- `Makefile` — `make sota-download`, `sota-baseline`, `sota`, `sota-rescore`
