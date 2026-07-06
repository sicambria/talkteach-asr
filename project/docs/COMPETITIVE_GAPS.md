# Competitive gap analysis — parity with the best existing toolsets

The design report's headline (Part A) is that **no** OSS tool ships an easy-to-use,
end-to-end GUI that trains SOTA ASR. That's about *packaging + UX*. This doc asks
a sharper, engineering question: **of the capabilities the best pro ASR-training
toolsets ship, which does TalkTeach's roadmap not yet cover?** Anything missing
becomes a roadmap item (see the "Parity" section appended to `ROADMAP.md`, items
#46–#57) so the gap is tracked, not forgotten.

## The three reference toolsets

1. **Hugging Face Transformers** (+ `Seq2SeqTrainer`, PEFT, `datasets`) — the
   de-facto Whisper fine-tuning path; TalkTeach's engine builds directly on it.
2. **NVIDIA NeMo** — production ASR (Conformer / Parakeet RNN-T/CTC), strong data
   tooling, augmentation, and export to ONNX/Riva.
3. **SpeechBrain** — research-flexible recipes, wav2vec2/CTC, rich augmentation
   and decoding.

(Honourable mentions consulted: ESPnet, WhisperX, faster-whisper, Kaldi.)

## What TalkTeach already matches

| Capability | TalkTeach | Notes |
|---|---|---|
| Whisper LoRA/PEFT fine-tune | ✅ #1 | the default engine, verified |
| RNN-T / Conformer (streaming/edge) | scaffold #25 | NeMo Parakeet adapter |
| wav2vec2/XLS-R CTC (low-resource) | scaffold #26 | director already selects it |
| WER/CER eval | ✅ #2 | jiwer; held-out split |
| Checkpoint resume | ✅ #1/#17 | `resume_from_checkpoint` |
| ONNX/CT2 export | ✅/scaffold #4 | CT2 int8 real; ONNX via optimum |
| VAD segmentation | ✅ #11 | Silero |
| Forced alignment | scaffold #12 | WhisperX / NeMo-FA |
| Diarization | design #33 | pyannote/NeMo |
| Mixed precision (fp16/bf16/int8) | ✅ #1 | from the `TrainingPlan` |

## Gaps found → new roadmap items (#46–#57)

| # | Gap (who has it) | Why it matters here |
|---|---|---|
| 46 | **Data augmentation** — SpecAugment, speed/pitch perturbation, noise/RIR mixing (NeMo, SpeechBrain) | The single biggest accuracy win on small datasets; the director should auto-enable it for tiny data. |
| 47 | **Dataset import** — folder of (audio, transcript) pairs, NeMo/JSON manifest, Common Voice TSV, LibriSpeech, HF `datasets` (all three) | Lets the user bring an existing corpus instead of only recording in-app. |
| 48 | **Subtitle / caption output** — SRT/VTT + plain-text transcript with timestamps (faster-whisper, WhisperX) | "Subtitle this video" is a top real-world ASR use case we don't serve. |
| 49 | **Long-form transcription** — chunked, VAD-windowed, timestamped decoding (faster-whisper) | "Try it" handles one short clip; long files need chunking. |
| 50 | **Decoding controls** — beam size, `initial_prompt`/hotword biasing, temperature fallback (faster-whisper, NeMo) | Cheap accuracy + lets the user bias toward their vocabulary. |
| 51 | **Punctuation + capitalization restoration / ITN** (NeMo) | Readable transcripts; big perceived-quality win. |
| 52 | **Richer evaluation** — per-utterance WER, a confusion/error report, confidence, normalized vs raw WER (all three) | Powers active learning (#32) and Advanced insight beyond one number. |
| 53 | **Local experiment metrics view** — TensorBoard-style loss/WER curves, on-device only (HF, NeMo, SpeechBrain) | Advanced mode depth without telemetry (honours D-008). |
| 54 | **Headless CLI** — train/eval/export from the terminal, no GUI (all three) | Power users, CI, and reproducible runs. |
| 55 | **Custom vocabulary / tokenizer extension** for new languages (NeMo, SpeechBrain) | Needed for truly unseen languages on the CTC path (#26). |
| 56 | **Optional multi-GPU / distributed** training (all three) | Out of scope for a modest laptop, but a documented escape hatch for power users. |
| 57 | **More export targets** — HF `safetensors`, GGUF (whisper.cpp), TorchScript (HF, llama.cpp ecosystem) | Interop with other runtimes you may already use. |

## Honest verdict

For its **target** — an easy-to-use, offline, one-tap trainer — TalkTeach's
roadmap is complete and the core is real. Against the **pro toolsets' full
surface**, the meaningful gaps are *data augmentation (#46)*, *dataset import
(#47)*, and *subtitle/long-form transcription (#48/#49)* — all additive,
none requiring new ML research, all now tracked. The rest are power-user niceties.
