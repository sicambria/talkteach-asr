# Plan: TTS-backed end-to-end ASR benchmark harness + docs reorg

> In-repo canonical record of the plan executed for the TTS/benchmark work.
> Status tracked in commits; see `docs/ml/BENCHMARKING.md` and `TTS.md` for usage.

## Context

The app's end-to-end automated path was real in *plumbing* but not in *meaning*: it
trained on sine **tones**, so WER measured noise, not recognition; hyperparameters
weren't pinnable for experiments; and the wav2vec2/NeMo engines were stubs. So you
could not validate that a model learned words, nor compare OSS engines on real audio.

**Outcome:** real TTS (espeak + piper, pluggable) → configurable benchmark → train each
ASR engine on a shared dataset → measure WER/CER on a **shared held-out eval set** →
TTS×ASR report. Plus a CI fast-path proving the measurement is real, and a docs reorg.

## Phases

0. **Docs reorg** (separate commit): `project/docs/` → `docs/`, `DECISIONS.md` →
   `docs/`, community-health files → `.github/`; only `README`/`LICENSE`/
   `CHANGELOG` at root; ~40 cross-references rewritten; `git mv` preserves history.
1. **TTS package** `backend/talkteach/tts/`: `TTSProvider` ABC (mirrors `ASREngine`),
   `EspeakProvider` (system binary), `PiperProvider` (neural, `[tts]`), registry,
   `synthesize_dataset` → same manifest shape as `make_toy_dataset`. 16 kHz mono.
2. **Configurable plans** `director/plan_config.py`: `plan_from_config(cfg)` builds a
   pinned `TrainingPlan`, bypassing the director's heuristics; defaults fall back to
   policy constants. Product flow untouched.
3. **Real engines**: `wav2vec2_ctc` real (`Wav2Vec2ForCTC` + CTC, CPU-testable);
   shared training helpers extracted from `_whisper_train.py`; Whisper `transcribe`
   gains a transformers path so a trained adapter can be scored. `nemo_rnnt` real path
   but **GPU/opt-in only**, never gates CI. `pyproject` extras: `[tts]`, `[nemo]`,
   optimum in `[export]`.
4. **Benchmark harness** `talkteach/benchmark.py` + `scripts/benchmark.py` +
   `benchmarks/*.yaml`: TTS×ASR matrix; disjoint shared eval set; quality-gate clips;
   per-cell train + WER/CER + train-time; JSON + table; missing deps → `skipped`.
5. **Tests + CI**: `espeak` marker; `test_tts.py`; `test_e2e_benchmark.py` split into
   **measurement-is-real** (fast, no training: clean speech low WER, tones high WER)
   and **training-improves** (opt-in, loose bounds). New `benchmark-smoke` CI job
   (`apt-get install espeak-ng` + `[ml,tts]`, `pytest -m espeak`); default `python` job
   stays dep-light.
6. **Docs**: `docs/ml/BENCHMARKING.md` + `TTS.md`; decision record; this plan;
   README cross-link.

## Tiering / caveats

- wav2vec2 real + CI-able; NeMo real-path but GPU/opt-in (never in CI).
- No assertion that a tiny fine-tune strictly lowers WER (flaky) — that's opt-in, loose.
- Cross-engine comparability is on WER/CER/train-time, not a unified export format.

## Verification

`pytest -q` unchanged (heavy tests marker-gated); `pytest -m espeak` green with the
binary; `python scripts/benchmark.py --config benchmarks/quick.yaml` produces a sane
matrix (piper+whisper-tiny → low WER on the shared eval set); ruff/mypy clean; no stale
root-`docs/` references after the move.
