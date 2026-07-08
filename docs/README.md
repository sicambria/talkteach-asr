# TalkTeach docs

Design notes, decision records, and per-feature deep-dives. Most of these are
**engineering reference** rather than end-user help — the app itself is meant to
need no manual. Start with the [root README](../README.md) for the overview.

## Orientation (read these first)

| Doc | What it is |
| --- | --- |
| [ROADMAP.md](roadmap/ROADMAP.md) | Prioritized P0–P3 + X roadmap from Phase 0 onward. |
| [ROADMAP_STATUS.md](roadmap/ROADMAP_STATUS.md) | Per-item status matrix: tier + evidence + commit. The authoritative "what's real". |
| [PHASE0_STATUS.md](roadmap/PHASE0_STATUS.md) | What is real vs. simulated vs. scaffolded. |
| [OVERALL.md](../OVERALL.md) | Single-page: state of the project & 30-experiment road to SOTA. |

## Architecture & decisions

| Doc | What it is |
| --- | --- |
| [DECISIONS.md](architecture/DECISIONS.md) | Decision log (ADR-lite) — every non-obvious choice, top-5 scored 0–100. |
| [PLAN.md](architecture/PLAN.md) | Implementation plan / commit sequence (internal working doc). |
| [LEARNINGS.md](architecture/LEARNINGS.md) | Retrospective — what went wrong and the gotchas. |
| [LANDSCAPE.md](architecture/LANDSCAPE.md) | Keeping the headline claim current. |
| [COMPETITIVE_GAPS.md](architecture/COMPETITIVE_GAPS.md) | Parity with the best existing toolsets. |
| [THIRD_PARTY.md](architecture/THIRD_PARTY.md) | Third-party components and their verified licenses. |
| [FORMATS.md](architecture/FORMATS.md) | Formats & use cases that work out of the box. |
| [DEPENDENCIES.md](architecture/DEPENDENCIES.md) | Dependency hygiene. |
| [OBSERVABILITY.md](architecture/OBSERVABILITY.md) | Local-only logging and the redacted help bundle. |

## ML & audio

| Doc | What it is |
| --- | --- |
| [ENGINES.md](ml/ENGINES.md) | The adapter contract and the three engines. |
| [CALIBRATION.md](ml/CALIBRATION.md) | Calibrating the zero-config director. |
| [BENCHMARKING.md](ml/BENCHMARKING.md) | Comparing ASR engines for real. |
| [TTS.md](ml/TTS.md) | Synthetic speech for testing & benchmarking. |
| [AUDIO_PIPELINE.md](ml/AUDIO_PIPELINE.md) | Decode / resample / VAD / quality meter. |
| [ALIGNMENT.md](ml/ALIGNMENT.md) | Forced alignment — long take → sentence clips. |
| [DENOISE.md](ml/DENOISE.md) | Optional denoise for noisy uploads. |
| [DIARIZATION.md](ml/DIARIZATION.md) | Multi-speaker / diarization. |
| [EXPORT.md](ml/EXPORT.md) | Model export (CT2 / ONNX / safetensors). |
| [VOCAB.md](ml/VOCAB.md) | Custom vocabulary / tokenizer extension. |
| [MULTIGPU.md](ml/MULTIGPU.md) | Optional multi-GPU / distributed training. |
| [CLOUD_FALLBACK.md](ml/CLOUD_FALLBACK.md) | One-tap remote training fallback. |

## Features & UX

| Doc | What it is |
| --- | --- |
| [PROMPTS.md](features/PROMPTS.md) | Karaoke prompt sets. |
| [SELFTEST.md](features/SELFTEST.md) | First-run self-test. |
| [ACCESSIBILITY.md](features/ACCESSIBILITY.md) | Accessibility promise + status. |
| [LANGUAGES.md](features/LANGUAGES.md) | Supported speech languages. |
| [I18N.md](features/I18N.md) | Internationalizing the UI text. |
| [MASCOT.md](features/MASCOT.md) | Mascot, sound & gamification. |

## Delivery & packaging

| Doc | What it is |
| --- | --- |
| [SIDECAR.md](features/SIDECAR.md) | Tauri sidecar — the backend "just runs". |
| [BUNDLING.md](features/BUNDLING.md) | No-install bundled runtime. |
| [RELEASING.md](features/RELEASING.md) | Signed installers for Windows / macOS / Linux. |
| [MODEL_PACKS.md](features/MODEL_PACKS.md) | Shareable model packs & "Publish to Hugging Face". |
| [MULTIPROJECT.md](features/MULTIPROJECT.md) | Multi-project support in the app layer. |

## Plans & reports

| Doc | What it is |
| --- | --- |
| [advanced-mode-ui-sweep.md](plans/advanced-mode-ui-sweep.md) | Plan: Advanced-mode UI features. |
| [roadmap-parity-batch.md](plans/roadmap-parity-batch.md) | Plan: Competitive-parity batch (#46–#57). |
| [tts-benchmark-harness.md](plans/tts-benchmark-harness.md) | Plan: TTS × ASR benchmark harness. |
| [ui-parity-sweep.md](plans/ui-parity-sweep.md) | Plan: UI parity sweep. |
| [terminology-easy-advanced.md](plans/terminology-easy-advanced.md) | Plan: Terminology change (kids → Easy/Advanced). |
| [ASR_training_GUI_…](reports/ASR_training_GUI_wizard_research_and_design_2026-06-27.md) | Original research report this design implements. |
| [2026-07-06.md](assessment/2026-07-06.md) | External product maturity assessment (530/1000). |

## Learning loops & SOTA benchmarks

| Doc | What it is |
| --- | --- |
| [README.md](learning-loops/README.md) | Learning loop architecture & pitch. |
| [EXPERIMENT_TRACKING.md](learning-loops/EXPERIMENT_TRACKING.md) | Experiment registry + SQLite schema. |
| [HYPERPARAMETER_SWEEPS.md](learning-loops/HYPERPARAMETER_SWEEPS.md) | Automated sweep runner design. |
| [CALIBRATION_LOOP.md](learning-loops/CALIBRATION_LOOP.md) | End-to-end director calibration pipeline. |
| [GUARDRAILS.md](learning-loops/GUARDRAILS.md) | ML safety: bias, hallucination, OOD detection. |
| [AI_WORKFLOWS.md](learning-loops/AI_WORKFLOWS.md) | Multi-agent (Claude, OpenCode, Copilot) workflows. |
| [README.md](sota-benchmarks/README.md) | The 1000-point SOTA scale + band definitions. |
| [DOMAINS.md](sota-benchmarks/DOMAINS.md) | 15 domains with metrics, methods, and thresholds. |
| [METHODOLOGY.md](sota-benchmarks/METHODOLOGY.md) | Statistical rigor: bootstrap CI, effect sizes. |
| [BASELINES.md](sota-benchmarks/BASELINES.md) | Current TalkTeach baseline scores per domain. |
| [SCOREBOARD.md](sota-benchmarks/SCOREBOARD.md) | Auto-generated tracking matrix. |
| [VALIDATION.md](sota-benchmarks/VALIDATION.md) | How to run validation, Docker setup, CI integration. |
