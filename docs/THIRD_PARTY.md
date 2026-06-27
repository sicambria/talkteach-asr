# Third-party components and licenses

Licenses **verified against each project's actual LICENSE file on 2026-06-28**
(the same verification that fed the design report). Re-confirm at integration
time — software licenses can change between releases. Model *weights* may carry
terms separate from the code license.

| Component | Role in TalkTeach | License (verified) |
|---|---|---|
| **Tauri** | Desktop shell (one installer per OS) | MIT OR Apache-2.0 |
| **Svelte / Vite** | Wizard UI | MIT |
| **FastAPI / Starlette / Uvicorn** | Job server | MIT / BSD-3-Clause |
| **NumPy** | Audio DSP | BSD-3-Clause |
| **HF Transformers + PEFT** | Default training engine (Whisper-LoRA) | Apache-2.0 |
| **faster-whisper** | Draft transcripts + "Try it" inference | MIT |
| **CTranslate2** | Export runtime | MIT |
| **NVIDIA NeMo** (Phase 2) | Streaming/edge engine (Parakeet) | Apache-2.0 |
| **NeMo Forced Aligner** (Phase 2) | Auto-segment long audio | Apache-2.0 |
| **WhisperX** (Phase 2 alt aligner) | Forced alignment | **BSD-2-Clause** |
| **SpeechBrain / wav2vec2-XLS-R** | Low-resource engine | Apache-2.0 |
| **Silero VAD** (Phase 1) | Trim silence / auto-segment | MIT |
| **librosa** | Audio quality metrics (optional) | ISC |
| **soundfile** | Audio I/O (optional) | BSD-3-Clause |
| **DeepFilterNet** (optional denoise) | Noise cleanup | **MIT OR Apache-2.0** (dual; weights separate) |
| **Demucs** (optional denoise) | Noise cleanup | MIT |
| **sherpa-onnx** (Phase 2) | Streaming ONNX export + tiny runner | Apache-2.0 |
| **Label Studio** (Phase 3 option) | Rich correction UI | Apache-2.0 |
| **uv** | No-install Python runtime bundling | Apache-2.0 OR MIT |
| **ffmpeg** (Phase 1, subprocess) | Audio decode/resample | **LGPL-2.1+ base**; GPL only if built `--enable-gpl` |
| **sox** (optional, subprocess) | Audio I/O | GPL |

## Notes that changed the plan

- **WhisperTemple is NOT reusable.** It was surveyed as a competitor but ships
  **no license** (all rights reserved) — TalkTeach uses none of its code.
- **ffmpeg** is invoked as a *subprocess* ("mere aggregation"), and an
  LGPL-only build (no `--enable-gpl`) is preferred so the binary stays
  permissively licensed regardless of TalkTeach's own GPL-3.0 license.
- Because TalkTeach itself is **GPL-3.0-or-later**, any GPL dependency (e.g. a
  GPL ffmpeg build or sox) can be combined freely; the permissive components
  (Apache/BSD/MIT/ISC) only require attribution, surfaced via the in-app credits
  screen planned for Phase 2.
