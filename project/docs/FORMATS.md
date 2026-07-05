# Formats & use cases — what works out of the box

An honest matrix of which file formats and use cases TalkTeach supports today,
what's behind an optional dependency, and what's a tracked gap (new roadmap items
#47/#48/#57 from the competitive analysis, see `COMPETITIVE_GAPS.md`).

## Input audio formats

| Format | Supported | How |
|---|---|---|
| WAV (PCM 8/16/32-bit) | ✅ out of the box | stdlib `wave` — no deps, no ffmpeg |
| webm / opus (browser `MediaRecorder`) | ✅ with ffmpeg | `audio/decode.py` → 16 kHz mono WAV (#10/#20) |
| mp3, m4a/mp4, ogg, flac, aac | ✅ with ffmpeg | same decode path; allow-list in `config.ALLOWED_AUDIO_EXTENSIONS` |
| anything else ffmpeg reads | ✅ with ffmpeg | ffmpeg is the universal front door |
| (no ffmpeg installed) | ⚠️ graceful | non-WAV is accepted but marked "not checked yet"; bundling = `BUNDLING.md` |

**Out of the box:** WAV always; everything else once ffmpeg is on PATH (bundled
in a packaged build, Tier B in this sandbox). Sample rate, channel count, and
bit-depth are normalized to 16 kHz mono PCM for both quality analysis and
training — the one canonical form (DECISIONS.md D-010).

## Transcript / dataset import

| Source | Supported | Notes |
|---|---|---|
| Record in-app + karaoke prompt as transcript | ✅ | the prompt is the label (#21) |
| Type/correct a transcript per clip | ✅ | `POST /api/clips/{id}/transcript` (#19) |
| Built-in toy dataset | ✅ | `/api/selftest` (#22) |
| Folder of (audio, transcript) pairs | ✅ | `data/import_manifest.py::import_folder_pairs` (#47) |
| Manifest CSV/JSON, NeMo JSONL, Common Voice TSV, LibriSpeech | ✅ | `data/import_manifest.py` + `talkteach import` (#47); HF `datasets` still a gap |

## Output / export formats

| Target | Supported | How |
|---|---|---|
| CTranslate2 int8 (offline desktop default) | ✅ verified | `engines/whisper_lora.py::export`; integration-tested (#4) |
| ONNX (streaming/edge via sherpa-onnx) | scaffold | via 🤗 optimum (#4, D-006) |
| Plain-text transcript | ✅ | "Try it" returns text (#5) |
| Subtitles (SRT / VTT) with timestamps | ✅ | `transcript/subtitles.py` + `talkteach subtitle` (#48) |
| HF `safetensors` | ✅ | `whisper_lora.py::export` (#57) |
| GGUF (whisper.cpp), TorchScript | 🟡 scaffold | dry-run export; `.generate` resists `torch.jit` (#57, `EXPORT.md`) |

## Use cases

| Use case | Status |
|---|---|
| Record → Check → Teach → Try → Use offline | ✅ the core flow, end-to-end |
| Train on a GPU, CPU/int8, or Apple MPS | ✅ director auto-selects (verified on CPU) |
| Resume an interrupted training run | ✅ checkpoint resume (#17/#40) |
| Transcribe one short clip ("Try it") | ✅ faster-whisper (#5, integration-tested) |
| Transcribe a long file / subtitle a video | ✅ chunked decode + SRT/VTT (#48/#49); heavy decode needs `[ml]` |
| Bring your own dataset | ✅ `talkteach import` — folder/CSV/JSON/NeMo/Common Voice/LibriSpeech (#47) |
| Multiple projects in the app | ⚠️ data layer ✅, app layer pending (#29) |
| Headless / CLI training | ✅ `talkteach train/eval/export/…` (#54) |

## Summary

The **core promise** (record → train a real model → use it offline) is supported
out of the box, with WAV needing zero deps and every other audio format covered by
the bundled ffmpeg. The former gaps — **dataset import (#47)**, **subtitle/long-form
transcription (#48/#49)**, **headless CLI (#54)**, and **safetensors export
(#57)** — are now built (pure logic CPU-tested; heavy decode/convert behind `[ml]`).
Remaining: HF `datasets` import, GGUF/TorchScript export (scaffold), and the app-
layer multi-project surface (#29).
