# TalkTeach docs

Design notes, decision records, and per-feature deep-dives. Most of these are
**engineering reference** rather than end-user help — the app itself is meant to
need no manual. Start with the [root README](../../README.md) for the overview.

## Orientation (read these first)

| Doc | What it is |
| --- | --- |
| [DECISIONS.md](DECISIONS.md) | Decision log (ADR-lite) — the top-5-scored choices and why. |
| [ROADMAP.md](ROADMAP.md) | Prioritized P0–P3 + X roadmap from Phase 0 onward. |
| [ROADMAP_STATUS.md](ROADMAP_STATUS.md) | Per-item status matrix: tier + evidence + commit. The authoritative "what's real". |
| [PHASE0_STATUS.md](PHASE0_STATUS.md) | What is real vs. simulated vs. scaffolded. |
| [PLAN.md](PLAN.md) | The implementation plan / commit sequence (internal working doc). |
| [LEARNINGS.md](LEARNINGS.md) | Retrospective — what went wrong and the gotchas (internal). |

## The product & its claim

| Doc | What it is |
| --- | --- |
| [COMPETITIVE_GAPS.md](COMPETITIVE_GAPS.md) | Gap analysis — parity with the best existing toolsets. |
| [LANDSCAPE.md](LANDSCAPE.md) | Keeping the headline "nobody ships this" claim current. |
| [THIRD_PARTY.md](THIRD_PARTY.md) | Third-party components and their verified licenses. |
| [FORMATS.md](FORMATS.md) | Formats & use cases that work out of the box. |

## The engine room (ML & audio)

| Doc | What it is |
| --- | --- |
| [ENGINES.md](ENGINES.md) | The adapter contract and the three engines. |
| [CALIBRATION.md](CALIBRATION.md) | Calibrating the zero-config director. |
| [AUDIO_PIPELINE.md](AUDIO_PIPELINE.md) | Decode / resample / VAD / quality meter. |
| [ALIGNMENT.md](ALIGNMENT.md) | Forced alignment — long take → sentence clips. |
| [DENOISE.md](DENOISE.md) | Optional denoise for noisy uploads. |
| [DIARIZATION.md](DIARIZATION.md) | Multi-speaker / diarization. |
| [EXPORT.md](EXPORT.md) | "Use on my computer" — model export (CT2 / ONNX / safetensors). |
| [VOCAB.md](VOCAB.md) | Custom vocabulary / tokenizer extension for unseen languages (#55). |
| [MULTIGPU.md](MULTIGPU.md) | Optional multi-GPU / distributed training escape hatch (#56). |
| [BENCHMARKING.md](BENCHMARKING.md) | Comparing ASR engines for real. |
| [TTS.md](TTS.md) | Synthetic speech for testing & benchmarking. |
| [MODEL_PACKS.md](MODEL_PACKS.md) | Shareable model packs & "Publish to Hugging Face". |
| [CLOUD_FALLBACK.md](CLOUD_FALLBACK.md) | One-tap remote training fallback. |

## App, shell & delivery

| Doc | What it is |
| --- | --- |
| [SIDECAR.md](SIDECAR.md) | Tauri sidecar — the backend "just runs". |
| [BUNDLING.md](BUNDLING.md) | No-install bundled runtime. |
| [RELEASING.md](RELEASING.md) | Signed installers for Windows / macOS / Linux. |
| [DEPENDENCIES.md](DEPENDENCIES.md) | Dependency hygiene. |
| [OBSERVABILITY.md](OBSERVABILITY.md) | Local-only logging and the redacted help bundle. |
| [MULTIPROJECT.md](MULTIPROJECT.md) | Multi-project support in the app layer. |

## UX & content

| Doc | What it is |
| --- | --- |
| [PROMPTS.md](PROMPTS.md) | Karaoke prompt sets. |
| [SELFTEST.md](SELFTEST.md) | First-run self-test. |
| [ACCESSIBILITY.md](ACCESSIBILITY.md) | Accessibility as part of the ease-of-use promise. |
| [LANGUAGES.md](LANGUAGES.md) | Supported **speech** languages (~99 Whisper + XLS-R for any other). |
| [I18N.md](I18N.md) | Internationalizing the **UI** text (interface language). |
| [MASCOT.md](MASCOT.md) | Mascot, sound & gamification. |

The research report this design implements is at
[`reports/`](../../reports/ASR_training_GUI_wizard_research_and_design_2026-06-27.md).
