# TTS × ASR benchmark report — `quick`

- Language: `en`
- Train clips: 6 · Eval clips (shared, held-out): 6
- Generated: 2026-06-28 11:03:35 CEST

## Scoreboard (ranked by ELO)

| # | Engine | ELO | W-L-T | Win% | Mean WER | Mean CER | Mean train(s) | Conditions |
|---|---|---|---|---|---|---|---|---|
| 1 | whisper | **1169** | 10-1-1 | 91% | 0.131 | 0.047 | 7.4 | 2 |
| 2 | wav2vec2 | **831** | 1-10-1 | 9% | 0.298 | 0.099 | 4.3 | 2 |

## Full matrix (per TTS × engine cell)

```
Benchmark 'quick'  lang=en  train=6 eval=6 clips

TTS     Engine    Status  WER    CER    Smartness  Train(s)  Detail
------  --------  ------  -----  -----  ---------  --------  ------
espeak  whisper   ok      0.238  0.089  0.762      8.6             
espeak  wav2vec2  ok      0.405  0.152  0.595      4.2             
piper   whisper   ok      0.024  0.005  0.976      6.3             
piper   wav2vec2  ok      0.191  0.047  0.809      4.4             
```

## How to read this

- **WER / CER** (lower is better) on the shared, held-out eval set are the ground-truth metrics. **Train(s)** is wall-clock fine-tune time.
- **ELO** is a leaderboard layer: each engine plays one match per (TTS, clip) and wins the clips it transcribes with lower WER. It aggregates across voices and clip difficulty into one number; with few clips treat it as indicative.
- Engines compared on **WER/CER/train-time**, not a single export format (formats differ per engine). See `docs/ml/BENCHMARKING.md`.
