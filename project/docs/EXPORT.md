# Export — "Use on my computer" (roadmap #4)

When a child taps **Use on my computer**, TalkTeach packages the model they just
taught into a portable, offline runtime they can copy to any machine. This note
explains what that produces and how to verify it.

## What gets produced

Real training (`engines/_whisper_train.py`) saves a **PEFT/LoRA adapter** plus the
Whisper processor into the run dir (`~/.talkteach/default/runs/<id>/`). An adapter
is tiny and not runnable on its own, so export does two steps
(`engines/whisper_lora.py::export`):

1. **Merge** — load the base Whisper checkpoint named in `adapter_config.json`,
   merge the LoRA weights in (`PeftModel.merge_and_unload()`), and save the full
   model to `runs/<id>/_merged/`.
2. **Convert** — turn the merged model into the requested runtime format.

## Formats (DECISIONS.md D-006)

| Format | Dep extra | Why / when | Status |
|---|---|---|---|
| **CTranslate2 int8** (default) | `[export]` (`ctranslate2`) | Fastest CPU inference; pairs with the faster-whisper "Try it" path; the family runs it offline. | Real path implemented |
| **ONNX** (via 🤗 optimum → sherpa-onnx) | `optimum` + `onnxruntime` | Streaming / edge / mobile; the Phase-2 deployment target. | Scaffolded code path |
| **HF safetensors** (`fmt="safetensors"`, #57) | `[ml]` (`transformers`) | Interop with any 🤗 Transformers runtime the family already uses; loads with `from_pretrained`. | Real path implemented |
| **TorchScript / GGUF** (`fmt="torchscript"`/`"gguf"`, #57) | — | Other runtimes (LibTorch, whisper.cpp). | Documented dry-run scaffold |

**Why TorchScript/GGUF are scaffold, not real:** Whisper's decoding runs through
`.generate()` (kv-cache + beam search), which does not `torch.jit.script`/`trace`
cleanly, and GGUF conversion needs whisper.cpp's own tooling. Rather than ship a
broken trace, `fmt="torchscript"`/`"gguf"` fall through to the honest dry-run
manifest (below). Use CTranslate2 (CPU) or safetensors (interop) today.

When the needed dependency is absent, export writes an `export_manifest.json`
dry-run describing exactly what *would* be produced and how to enable it — the
flow never dead-ends (the Phase-0 graceful-degradation contract).

## Verify on a provisioned machine

```bash
uv pip install -e 'backend[ml,export]'
# After a real run produced runs/<id>/ with an adapter:
python - <<'PY'
from talkteach.engines.whisper_lora import WhisperLoRAEngine
r = WhisperLoRAEngine().export("runs/1", "exports/1", fmt="ctranslate2")
print(r.format, r.path, r.notes)
PY
# Then transcribe with the export:
#   WhisperModel("exports/1") via faster-whisper  → "Try it"
```

The end-to-end fine-tune→export path is exercised by `pytest -m integration`
(see `tests/test_integration_train.py`) on a machine with the extras + network.

## Inference with the export ("Try it", #5)

`engines/whisper_lora.py::transcribe(audio_path, model_dir=…)` loads the CT2
export with faster-whisper (`WhisperModel(model_dir, device="auto",
compute_type="default")`), which auto-selects int8 on CPU and float16 on GPU.
Passing no `model_dir` falls back to a base checkpoint so "Try it" works before
the first training run.
