# SOTA Validation — Running the Benchmarks

> **Reference appendix to [`OVERALL.md`](../../OVERALL.md)** — the single authoritative SOTA
> document. To **re-apply the scoring policy to already-banked measurements** without a GPU or
> re-measurement (seconds), run **`make sota-rescore`**: it rewrites
> [`SCOREBOARD.md`](SCOREBOARD.md) / `.json` from their own raw metrics and preserves the
> measurement `generated` stamp. A *fresh* measurement (`make sota-baseline` / `make sota`)
> advances the stamp — then update the stamp reference at the top of `OVERALL.md`.

How to run the SOTA benchmark suite, what each command does, what you need
installed, and how to troubleshoot common failures.

## Quick start

```bash
# 1. Install the full ML stack (one-time)
make setup-ml

# 2. Download all benchmark datasets (~2.1 GB)
make sota-download

# 3. Run baseline measurements (untrained WER, no training — ~30 min on CPU)
make sota-baseline

# 4. Run full validation (train + eval — hours on CPU)
make sota

# 5. CI smoke test (D01 + D04 only, no training — ~5 min)
make sota-smoke
```

## Command reference

### `make sota-download`

Downloads all SOTA benchmark datasets to `~/.cache/talkteach/sota/`:

| Dataset | Size | Used by |
|---------|------|---------|
| LibriSpeech test-clean | ~340 MB | D01, D04, D06, D08, D10, D11, D12, D15 |
| LibriSpeech train-clean-100 | ~6 GB | D03, D05, D09, D13 |
| Common Voice en (test) | ~200 clips | D02 |
| FLEURS (test, en+es+1) | ~300 clips | D07 |
| Synthetic noise | Generated | D06 |

The download script is `scripts/sota/download_data.sh`. Datasets are cached —
subsequent runs skip already-downloaded data.

### `make sota-baseline`

Measures **untrained (base) model** performance across all CPU-runnable SOTA
domains. No training is performed. Uses `scripts/sota/run_all.sh --baseline`.

Currently measures: D01 (clean WER), D04 (RTF), D06 (noise robustness), D12
(speaker equity). Other domains are skipped with notes (training needed, data
unavailable, etc.).

Override engines:

```bash
# Use whisper-tiny and whisper-small as the two engines
SOTA_ENGINES=whisper-tiny,whisper-small make sota-baseline

# Use whisper-base only
SOTA_ENGINES=whisper-base make sota-baseline
```

### `make sota`

Runs **full validation** — training + evaluation — across all domains that
support it. This takes **hours on CPU** because it fine-tunes models for
domains like D05 (data efficiency at multiple training sizes).

Full SOTA is the pre-registered measurement for most domains. It should be
run before updating the scoreboard or publishing results.

### `make sota-smoke`

Fast **CI-safe** smoke test. Runs D01 (clean WER) and D04 (RTF) in baseline-only
mode — no training, no large downloads needed beyond LibriSpeech test-clean.
Takes ~5 minutes.

```bash
make sota-smoke
# => backend/.venv/bin/python scripts/sota/validate_d01_wer_clean.py --baseline-only --json /tmp/sota_d01.json
# => backend/.venv/bin/python scripts/sota/validate_d04_rtf.py --baseline-only --json /tmp/sota_d04.json
```

Errors are non-fatal (`|| true`) so CI doesn't block on download failures.

### Single domain

```bash
# D01: Clean speech WER
python scripts/sota/validate_d01_wer_clean.py --baseline-only

# D01 with full training
python scripts/sota/validate_d01_wer_clean.py

# D04: Real-Time Factor
python scripts/sota/validate_d04_rtf.py --baseline-only

# Export results as JSON
python scripts/sota/validate_d01_wer_clean.py --baseline-only --json /tmp/d01.json
```

### Run all domains from Python

```python
from talkteach.sota.harness import SOTAHarness
from talkteach.sota.domains import ALL_DOMAINS
from talkteach.sota.report import generate

harness = SOTAHarness(
    engines=["whisper-tiny"],
    baseline_only=True,    # skip training-intensive domains
    seed=42,
)
scoreboard = harness.run_all(cpu_only=True)

# Print results
for r in scoreboard.sorted_by_score:
    print(f"{r.domain_id}: {r.score_0_1000}/1000 ({r.band}) — {r.notes}")

# Generate scoreboard files
md, json_data = generate(scoreboard)
```

### Docker

```bash
docker build -f Dockerfile.sota -t talkteach-sota .
docker run --rm talkteach-sota
```

The Docker image bundles all dependencies, downloads datasets at build time,
and runs the full SOTA suite. Useful for reproducible, isolated runs on cloud
instances.

## System requirements

### Required system dependencies

| Dependency | Why needed | Install |
|-----------|-----------|---------|
| **ffmpeg** | Audio decoding (webm → WAV, resampling) | `apt install ffmpeg` / `brew install ffmpeg` |
| **espeak-ng** | espeak TTS voice for benchmark (D09, synthetic speech) | `apt install espeak-ng` / `brew install espeak-ng` |
| **Python 3.11** | Backend runtime | `uv venv backend/.venv` |
| **git** | Commit tracking in experiment DB | System package |

### Python dependencies

Installed via `make setup-ml`:

```bash
uv venv backend/.venv
VIRTUAL_ENV=backend/.venv uv pip install -e 'backend[ml,export,tts,dev]'
```

Key packages: `torch`, `transformers`, `peft`, `faster-whisper`, `jiwer`,
`librosa`, `soundfile`, `datasets`, `ctranslate2`, `onnxruntime`, `numpy`,
`scipy`, `pyyaml`.

### CPU vs GPU

| Benchmark type | CPU? | Notes |
|---------------|------|-------|
| D01 Clean WER (baseline) | Yes | Base model inference only |
| D04 RTF (baseline) | Yes | RTF measurement is CPU-relevant |
| D06 Noise robustness | Yes | Noise mixing + inference |
| D12 Speaker equity | Yes | Per-speaker grouping + inference |
| D05 Data efficiency (train) | Yes (slow) | Fine-tuning on CPU takes minutes per cell |
| D03 Training efficiency | GPU needed | GPU-hours metric is meaningless on CPU |
| D13 Director accuracy | CPU-possible | Sweep is combinatorial — CPU takes hours |
| Full calibration sweeps (E19–E26) | CPU-possible | Multi-hour program on CPU; minutes on GPU |

The `runnable_cpu` field on each domain (`domains.py:31`) indicates whether the
measurement is valid on CPU. Training-intensive domains technically run on CPU
but the timings are not representative.

### Disk space

| Item | Space |
|------|-------|
| Datasets (~2.1 GB) | `~/.cache/talkteach/sota/` |
| Experiment DB | `~/.cache/talkteach/experiments.db` (small) |
| Training artifacts per run | `~/.cache/talkteach/workdirs/` (tens of MB, auto-cleaned) |
| HuggingFace cache | `~/.cache/huggingface/` (several GB for models) |

The disk guard (`keep_artifacts: false`) auto-cleans training artifacts after
each run. The HuggingFace cache can grow large; clear it with:

```bash
rm -rf ~/.cache/huggingface/hub
```

### Network

- **huggingface.co** must be reachable (model downloads)
- **datasets** are downloaded via HF `datasets` library or direct HTTP
- No other network access is required — everything runs offline after
  datasets and models are cached

## CI integration

### GitHub Actions

The CI pipeline includes:

```yaml
- name: SOTA smoke test
  run: make sota-smoke
```

This runs D01 + D04 baseline-only. It's fast enough for every PR (~5 min
with cached datasets and models).

### Pre-commit / local gate

```bash
make sota-smoke    # Fast: validates harness works
make test          # 198 fast tests — no ML deps
make lint          # ruff + mypy
```

Full SOTA (`make sota`) is **not** in CI — it takes hours and is run
manually before releases or scoreboard updates.

## Troubleshooting

### Missing system dependencies

**espeak-ng not found:**
```
apt install espeak-ng
# or
brew install espeak-ng
```

**ffmpeg not found:**
```
apt install ffmpeg
# or
brew install ffmpeg
```

Without espeak-ng, espeak benchmark cells are skipped. Without ffmpeg,
audio decoding falls back to `soundfile` (supports WAV/FLAC only).

### Dataset download failures

**`ConnectionError` or `ReadTimeout` when downloading LibriSpeech:**

The HuggingFace `datasets` library downloads from HF Hub. If the connection
is slow or blocked:

```bash
# Set HF mirror (if available in your region)
export HF_ENDPOINT=https://hf-mirror.com

# Or increase timeout
export HF_DATASETS_DOWNLOAD_TIMEOUT=600

# Retry
make sota-download
```

**Download cache issues:**

```bash
# Clear and re-download
rm -rf ~/.cache/talkteach/sota/
make sota-download
```

### Disk space

**`OSError: [Errno 28] No space left on device`**

```bash
# Check free space
df -h ~

# Clear HuggingFace cache (safest — just re-downloads models)
rm -rf ~/.cache/huggingface/hub

# Clear SOTA dataset cache (re-downloads ~2.1 GB)
rm -rf ~/.cache/talkteach/sota/

# Clear training artifacts
rm -rf backend/.data/sweeps/
```

The disk guard (`keep_artifacts: false`) prevents training workdirs from
accumulating, but the HF cache is outside its scope.

### Out of memory (OOM)

**Training OOM on CPU:**

```bash
# Reduce batch size in the sweep config
fixed_params:
  batch_size: 2      # down from 4
  grad_accum: 8      # compensate for smaller batch
```

**Inference OOM:**

```bash
# Use a smaller model
SOTA_ENGINES=whisper-tiny make sota-baseline

# Use int8 compute type (default in harness)
# Already set: compute_type="int8" in harness.py
```

### Model load failures

**`OSError: .../whisper-tiny not found`**

The model needs to be downloaded from HuggingFace first. The harness
automatically downloads via `faster_whisper`, but if HF is unreachable:

```bash
# Pre-download the model
python -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cpu', compute_type='int8')"
```

### Scoreboard not updating

The scoreboard is auto-generated only when `run_all.sh` completes:

```bash
# Run the full pipeline
bash scripts/sota/run_all.sh --baseline

# Or generate from an existing scoreboard object
python -m talkteach.sota.report
```

If `SCOREBOARD.md` still shows the placeholder:

1. Check that `scripts/sota/run_all.sh` completed without errors
2. Verify `python -m talkteach.sota.report` can import the module
3. Check that `docs/sota-benchmarks/` is writable

### Guardrails failing during validation

If `check_data_leakage()` fires a critical error during validation:

```
[FAIL] data_leakage_speaker (severity: critical)
Detail: Speaker overlap detected: N speakers in both train and eval
```

**Fix:** Re-split your data by speaker ID, not random sampling. The Mo3
guardrail is a hard block — results with speaker overlap are unreliable.

### Synthetic vs. real path

If you see `[SIMULATION]` in results where you expected real measurements:

1. Verify `[ml]` extras are installed: `pip list | grep faster-whisper`
2. Verify `TALKTEACH_FORCE_SIMULATION` is not set
3. Verify the eval dataset exists on disk at `~/.cache/talkteach/sota/`
4. Check that audio files actually exist in the paths the harness is reading

## Cross-references

- `scripts/sota/download_data.sh` — dataset download script
- `scripts/sota/run_all.sh` — master validation runner
- `scripts/sota/validate_d01_wer_clean.py` — D01 validation script
- `backend/talkteach/sota/harness.py` — benchmark harness
- `backend/talkteach/sota/datasets.py` — dataset loading and synthetic noise
- `backend/talkteach/sota/report.py` — scoreboard generation
- `Dockerfile.sota` — Docker setup for reproducible runs
- `docs/sota-benchmarks/README.md` — the 1000-point scale
- `docs/sota-benchmarks/DOMAINS.md` — per-domain definitions and requirements
- `docs/sota-benchmarks/METHODOLOGY.md` — statistical protocol
- `docs/sota-benchmarks/BASELINES.md` — current baseline scores
- `docs/sota-benchmarks/SCOREBOARD.md` — auto-generated scoreboard
- `docs/architecture/DEPENDENCIES.md` — dependency management
- `Makefile` — all Make targets
