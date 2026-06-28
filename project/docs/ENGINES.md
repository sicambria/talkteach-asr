# Engines — the adapter contract & the three engines (#25, #26)

The director decides *what* to train; an **engine adapter** is the only place that
touches heavy ML frameworks (torch, transformers, peft, faster-whisper,
ctranslate2). Keeping that boundary thin is what lets the FastAPI server, the
director, and the whole test suite import and run on a plain laptop with no GPU.

## The contract (`engines/base.py`)

`ASREngine` is an ABC with four methods, each mapped to a child-facing screen:

| Method | Screen | What it does |
|---|---|---|
| `is_available() -> (bool, str)` | "Teach!" awake/asleep + Grown-up mode | reports missing deps in plain language |
| `train(plan, manifest, workdir, progress, should_stop)` | **Teach!** | runs the job, streams `TrainProgress` (a "smartness" meter, never a loss curve), checkpoints to `workdir`, resumes on restart, cancels cleanly |
| `transcribe(audio_path, model_dir=None)` | **Try it** | one clip → recognised text |
| `export(model_dir, out_dir, fmt)` | **Use on my computer** | portable offline runtime (see `EXPORT.md`) |

The framework-free `TrainingPlan` (from the director) is the only input — the
engine never asks the user a question. Heavy imports are function-local so this
package imports with zero ML deps; unmet deps raise `EngineUnavailableError`
(a grown-up-readable message, never a traceback at the kid).

## The three engines

| `EngineKind` | Engine | Use | State |
|---|---|---|---|
| `WHISPER_LORA` | Whisper + PEFT/LoRA | default; multilingual, low-VRAM | **built** (`engines/whisper_lora.py`, Tier A/B) |
| `WAV2VEC2_CTC` | wav2vec2 / XLS-R + CTC head | low-resource / unseen languages | **built** (`engines/wav2vec2_ctc.py`, Tier B; real CTC fine-tune, CPU/CI-runnable) |
| `NEMO_RNNT` | NeMo Parakeet / FastConformer-Transducer | streaming / edge export | **built, GPU-only** (`engines/nemo_rnnt.py`; needs `[nemo]` + CUDA, self-skips otherwise) |

The three engines are compared head-to-head on real synthetic speech by the
benchmark — see [BENCHMARKING.md](BENCHMARKING.md). Comparable axes are
WER/CER/train-time (export formats differ: Whisper→CTranslate2, wav2vec2→ONNX,
NeMo→`.nemo`).

## How the director selects (`director/policy.py::_choose_engine_and_model`)

1. **Language outside Whisper's set** *and* enough data (`good_minutes ≥
   MIN_TARGET_MINUTES`) → `WAV2VEC2_CTC` on `facebook/wav2vec2-xls-r-300m` (a
   self-supervised multilingual base adapts to new languages better).
2. Otherwise Whisper-LoRA, sized by VRAM tier: ≥16 GiB → `whisper-medium` fp16;
   ≥6 GiB CUDA/MPS → `whisper-small` fp16; else `whisper-tiny` int8 on CPU.
3. `EngineKind.NEMO_RNNT` is reserved for the streaming/edge deployment path.

`engines/__init__.py::get_engine(kind)` returns the adapter. The app checks
`is_available()` first: a director-selected-but-unbuilt engine **falls back to
Whisper-LoRA** rather than dead-ending a child's flow.

## Build plan for the scaffolds

**NeMo RNN-T (#25)** — datasets: NeMo manifest JSONL (`audio_filepath`, `text`,
`duration`). Training: `EncDecRNNTBPEModel` fine-tune from a Parakeet checkpoint,
adapter modules to keep it light. Export: ONNX → **sherpa-onnx** (Apache-2.0) for
streaming/edge. Deps go in a `[nemo]` extra; `is_available()` already probes
`nemo_toolkit`.

**wav2vec2/XLS-R CTC (#26)** — datasets: the same `[{path, text}]` manifest plus a
per-language **character vocab** built from the transcripts. Training:
`Wav2Vec2ForCTC` on XLS-R-300m with a fresh CTC head, `Wav2Vec2CTCTokenizer` +
`Wav2Vec2Processor`, freeze the feature extractor. Export: merge → CT2 int8 (same
path as Whisper) for the default desktop case.

Both reuse the director's `TrainingPlan` (epochs/LR/precision/batch already
chosen) and the existing checkpoint/resume + safety-rail machinery.

## Verify (on a provisioned machine)

```bash
uv pip install -e 'backend[ml,export]'
TALKTEACH_RUN_INTEGRATION=1 pytest -m integration   # Whisper-LoRA fine-tune on the toy set
# NeMo/CTC: once a [nemo]/CTC adapter lands, the same marker exercises it.
```

## Status

Whisper-LoRA: **Tier B** (built + guarded, integration behind a marker). NeMo
RNN-T (#25) and wav2vec2 CTC (#26): **Tier C** — real `ASREngine` scaffolds that
satisfy the contract and report unavailable; the training/export bodies are
pending the build plan above and a GPU.
