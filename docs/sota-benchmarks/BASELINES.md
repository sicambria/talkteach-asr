# SOTA Baselines — Current TalkTeach Scores

This document records the current TalkTeach baseline score for each of the 15
SOTA domains. **Most domains are unmeasured.** The authoritative source of truth
for baseline scores is the experiment database (`~/.cache/talkteach/experiments.db`)
and the auto-generated scoreboard at `docs/sota-benchmarks/SCOREBOARD.md`.

## How to populate baselines

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

## Current baseline table

| Domain | Score | Band | Metric | Value | Engine | Notes |
|--------|-------|------|--------|-------|--------|-------|
| D01 Clean WER | **unmeasured** | — | wer | — | — | Run `make sota-baseline` |
| D02 Spontaneous WER | **unmeasured** | — | wer | — | — | Needs Common Voice download |
| D03 Training Efficiency | **unmeasured** | — | gpu_hours | — | — | Needs GPU for valid measurement |
| D04 RTF | **unmeasured** | — | rtf | — | — | Run `make sota-baseline` |
| D05 Data Efficiency | **unmeasured** | — | wer_at_5min | — | — | Needs training at multiple sizes |
| D06 Noise Robustness | **unmeasured** | — | wer_delta_at_0db | — | — | Needs noise data generation |
| D07 Multilingual | **unmeasured** | — | languages | — | — | Needs FLEURS download |
| D08 Export Fidelity | **unmeasured** | — | wer_delta_export | — | — | Needs export pipeline |
| D09 Augmentation | **unmeasured** | — | rel_wer_reduction | — | — | Needs augmentation wiring (E09) |
| D10 Decoding | **unmeasured** | — | domain_wer_optimal | — | — | Needs decode experiments (E27) |
| D11 Long-form | **unmeasured** | — | wer_delta_60min | — | — | Needs long-form test data |
| D12 Speaker Equity | **unmeasured** | — | per_speaker_wer_std | — | — | Run `make sota-baseline` |
| D13 Director Accuracy | **unmeasured** | — | oracle_match_rate | — | — | Needs oracle sweep |
| D14 Quality Gate | **unmeasured** | — | quality_gate_auc | — | — | Needs labelled quality set |
| D15 Resource Efficiency | **unmeasured** | — | mb_per_audio_minute | — | — | Needs full pipeline measurement |

### Overall

**Overall mean:** unmeasured — run `make sota-baseline`
**Overall band:** unmeasured

## Synthetic TTS proxy numbers (from benchmarks/REPORT.md)

The only real measured numbers in the repo come from the TTS×ASR benchmark
harness (`scripts/benchmark.py` → `benchmarks/quick.yaml`). These are on
**synthetic TTS speech**, not real audio. Per `OVERALL.md` A.6.7, they are
indicative proxies only and **must not** drive shipped `policy.py` changes.

From `benchmarks/REPORT.md` (2026-07-08, CPU, real path, prompt-disjoint):

| Engine | Mean WER (synthetic TTS) | Notes |
|--------|--------------------------|-------|
| whisper-tiny (LoRA) | 0.131 | 6 train / 6 eval clips, 1 epoch |
| wav2vec2 (CTC) | 0.286 | Same config |

Per-cell breakdown (best to worst):

| TTS voice | Engine | WER |
|-----------|--------|-----|
| piper | whisper-tiny | 0.024 |
| piper | wav2vec2 | 0.167 |
| espeak | whisper-tiny | 0.238 |
| espeak | wav2vec2 | 0.405 |

**These are synthetic proxy numbers only.** They do **not** represent real-world
ASR accuracy. The gaps between engines on synthetic TTS do **not** directly
predict gaps on real speech. Real-audio baselines (E02 in `OVERALL.md`) are
the P0 priority.

## Domain readiness

Domains that have partial or complete harness code but are blocked on data or
training:

| Domain | Harness code | Measurement method | Blockers |
|--------|-------------|-------------------|----------|
| D01 | `harness.py:355` | `measure_base_wer()` | Dataset download only |
| D04 | `harness.py:367` | `measure_rtf()` | Dataset download only |
| D06 | `harness.py:376` | `measure_noise_robustness()` | Dataset + synthetic noise |
| D12 | `harness.py:393` | `measure_speaker_equity()` | Dataset download only |
| D05 | `harness.py:403` | `measure_data_efficiency()` — stub | Needs training at multiple data sizes |
| D13 | `harness.py:407` | `measure_director_accuracy()` — stub | Needs exhaustive oracle sweep |
| D14 | `harness.py:411` | (not wired) | Needs hand-labelled quality set |
| D02, D03, D07–D11, D15 | `harness.py:416` | "Requires dedicated validation script" | Per-domain scripts needed |

## Recording a new baseline

When you run `make sota-baseline` or a single-domain validation, the results
are:

1. **Printed to stdout** with score, band, and metric values
2. **Written to `SCOREBOARD.md`** and `SCOREBOARD.json` by `python -m talkteach.sota.report`
3. **Recorded in the experiment DB** if using the sweep runner (training domains)
4. **Appended to `OVERALL.md` Part C** manually for narrative context

To update this document after running baselines:

```bash
make sota-baseline
# → Scoreboard auto-updated at docs/sota-benchmarks/SCOREBOARD.md
# → Manually copy relevant rows into this table above
```

## The P0 gap

Per `OVERALL.md` Part A.2: **there is zero accuracy baseline on real audio**
anywhere in the repo. The first real-audio WER number (E02: base whisper-tiny
on LibriSpeech test-clean) is the highest-priority measurement.

Once E02 is run, this document should be updated with the first real-audio
baseline row.

## Cross-references

- `benchmarks/REPORT.md` — synthetic TTS benchmark results
- `backend/talkteach/sota/harness.py` — benchmark harness with per-domain dispatch
- `docs/sota-benchmarks/DOMAINS.md` — full domain definitions with thresholds
- `docs/sota-benchmarks/SCOREBOARD.md` — auto-generated scoreboard
- `docs/sota-benchmarks/VALIDATION.md` — how to run baselines
- `docs/sota-benchmarks/README.md` — the 1000-point scale
- `OVERALL.md` Part A.2 — what is real vs. simulated
- `OVERALL.md` Part C — results log
- `Makefile` — `make sota-baseline`, `make sota`, `make sota-smoke`
