# SOTA Benchmark Scale

> **Reference appendix to [`OVERALL.md`](../../OVERALL.md)** — the single authoritative SOTA
> document. Live scores are single-sourced from the generated
> [`SCOREBOARD.md`](SCOREBOARD.md) / `.json`; this file explains the *scale and scoring*, it does
> not hold current results. Regenerate the scoreboard with `make sota-rescore`.

TalkTeach measures progress on a **1000-point scale** anchored to the best known
real-world production ASR system. Score = 1000 means "at or above the best
publicly documented system on this metric." Score = 0 means "not functional."

## The band definitions

| Band | Score range | Threshold (WER-like) | What it means |
|------|------------|---------------------|---------------|
| **Platinum** | 1000 | Best known production system | Surpasses or equals the reference SOTA |
| **Diamond** | 950 | Near-SOTA, within striking distance | Excellent — small gap to the best |
| **Platinum** | 900 | Strong, production-grade | Very good — usable in production |
| **Gold** | 800 | Solid, above-average | Good — meaningful capability |
| **Silver** | 700 | Functional, has gaps | Usable — works but not stellar |
| **Bronze** | 600 | Baseline functionality | Functional — meets minimum bar |
| **Pending** | — | — | Pre-registered but not yet run |
| **Unmeasured** | — | — | No measurement exists |
| **Error** | — | — | Measurement failed |

### Band labels

The band labels are normalized in `talkteach/sota/scoring.py:140`:

```python
BAND_NAMES = {
    1000: "platinum",
    950: "diamond",
    900: "platinum",
    800: "gold",
    700: "silver",
    600: "bronze",
    500: "bronze",
}
```

Note that both 1000 and 900 map to "platinum" — this is intentional: 1000 is
SOTA-level platinum (beats the reference), 900 is production-grade platinum
(strong but not best-known).

## How scoring works

Each domain defines a list of `Band` objects — (score, threshold, description):

```python
Band(1000, 0.010, "WER ≤ 1.0% — surpasses best known production ASR"),
Band(950,  0.015, "WER ≤ 1.5% — whisper-large-v3 territory"),
Band(900,  0.020, "WER ≤ 2.0% — near whisper-large-v3"),
Band(800,  0.030, "WER ≤ 3.0% — strong fine-tuned OSS"),
Band(700,  0.050, "WER ≤ 5.0% — usable for clean speech applications"),
Band(600,  0.080, "WER ≤ 8.0% — functional baseline"),
```

The `score_against_bands()` function at `talkteach/sota/scoring.py:128` maps a
measured value to a score:

- For metrics where **lower is better** (WER, CER, RTF, WER delta): the first
  band whose threshold the value is ≤ gets the score
- For metrics where **higher is better** (language coverage, augmentation
  efficacy, oracle match rate, quality gate AUC): the first band whose threshold
  the value is ≥ gets the score

If the value falls below the lowest band, the score is `lowest_band - 100`.

## The SOTA = 1000 anchor

Every domain names a specific real-world system as its SOTA=1000 reference.
This is not an abstract target — it's a documented, publicly verifiable claim:

| Domain | SOTA=1000 reference |
|--------|-------------------|
| D01 Clean WER | whisper-large-v3 ≈ 1.8–2.7% WER on LibriSpeech test-clean (OpenAI HF card ~2.7%); 1000-tier (<1.0%) exceeds all known production ASR |
| D02 Spontaneous | Best commercial APIs (Deepgram Nova-2, Whisper API) on Common Voice en |
| D03 Training efficiency | whisper-tiny LoRA on A100: ~0.17 GPU-hr to converge on 1hr data |
| D04 RTF | faster-whisper CT2 int8 tiny @ RTF ~0.02 on modern CPU |
| D05 Data efficiency | Whisper-LoRA: ~3% WER with 30 min of fine-tuning data (literature) |
| D06 Noise robustness | Denoised Whisper + DeepFilterNet: Δ<3% at 0dB SNR (research) |
| D07 Multilingual | whisper-large-v3: ~60 languages with usable WER on FLEURS (OpenAI, 2023) |
| D08 Export fidelity | CTranslate2 int8 quantization: Δ WER < 0.1% vs fp32 (CTranslate2 docs) |
| D09 Augmentation | SpecAugment: ~20% relative WER reduction on small datasets (Park et al., 2019) |
| D10 Decoding | Beam=5 + hotword prompt on whisper-tiny: marginal gain on general speech |
| D11 Long-form | Chunked Whisper with overlapping windows: Δ < 1% at 60 min |
| D12 Speaker equity | Best commercial ASR: per-speaker WER σ < 1.5% on LibriSpeech |
| D13 Director accuracy | Calibrated director: should pick WER-minimizing config in ≥90% of scenarios |
| D14 Quality gate | SNR-based gate: AUC ~0.88 on Common Voice labelled subset (estimated) |
| D15 Resource efficiency | CTranslate2 whisper-tiny: ~50 MB disk, negligible RAM for inference |

## Overall score

The overall TalkTeach SOTA score is the **mean over adequately-powered domains only**. A domain
that produced a score but is statistically under-powered — too few clips against its declared
`min_samples`, or a per-speaker metric over fewer than `min_speakers` speakers — is kept and shown
but flagged **directional** and **excluded from the mean** (see `scoring.aggregate_headline`).
"Unmeasured"/"pending" domains are excluded too. The headline reads **`provisional`** until at
least 3 domains are adequately powered, so a single domain cannot headline a grade. Coverage
(measured / directional / unmeasured) is reported beside the headline.

## Scoreboard

The authoritative scoreboard is at `docs/sota-benchmarks/SCOREBOARD.md`. It is
auto-generated by `python -m talkteach.sota.report` after running
`scripts/sota/run_all.sh`. The JSON version is at
`docs/sota-benchmarks/SCOREBOARD.json`.

A typical scoreboard entry:

```
| # | Domain | Score | Band | Primary Metric | Value |
|---|--------|-------|------|---------------|-------|
| 1 | D01: ASR Accuracy — Clean Speech | 800 | gold | wer | 0.0520 |
| 2 | D04: Inference Speed — RTF | 900 | platinum | rtf | 0.0450 |
```

## TalkTeach's honest position

As of `OVERALL.md` Part A (see it for the current, single-sourced state):

- **Capability-SOTA** (the product thesis: "there is no OSS next-next-finish GUI
  for training ASR") is largely delivered
- **Accuracy-SOTA** — a real-audio program **exists** (journey S1, 2026-07-08) but is early:
  one adequately-powered domain (D01 clean-speech WER on real LibriSpeech), three under-powered
  directional readings, the rest unmeasured or blocked (B-001). The headline is `provisional`.

The 1000-point scale exists to grow this coverage. Each domain is pre-registered with a
measurement method, a SOTA reference, and band thresholds. The current frontier (Stage 3) is
model-size scaling + unblocking B-001 + making the baseline representative — see `OVERALL.md`.

## Band definitions per domain

Full band definitions for all 15 domains are in `docs/sota-benchmarks/DOMAINS.md`.
Each domain includes:

- The metric and whether higher or lower is better
- Band thresholds with score, threshold value, and description
- The SOTA=1000 reference system
- Applicable engines
- Required datasets
- Whether it runs on CPU or needs GPU
- Minimum sample count for statistical validity

## Cross-references

- `backend/talkteach/sota/scoring.py:128` — `score_against_bands()` implementation
- `backend/talkteach/sota/domains.py` — all 15 domain definitions with bands
- `backend/talkteach/sota/harness.py` — benchmark harness that measures and scores
- `backend/talkteach/sota/report.py` — scoreboard generation (Markdown + JSON)
- `docs/sota-benchmarks/DOMAINS.md` — full domain catalog with thresholds
- `docs/sota-benchmarks/METHODOLOGY.md` — statistical rigor behind the scores
- `docs/sota-benchmarks/BASELINES.md` — current TalkTeach baseline scores
- `docs/sota-benchmarks/SCOREBOARD.md` — auto-generated scoreboard table
- `docs/sota-benchmarks/VALIDATION.md` — how to run the benchmarks
- `docs/learning-loops/README.md` — how scoring fits into the learning loop
- `OVERALL.md` Part A.1 — honest SOTA position
