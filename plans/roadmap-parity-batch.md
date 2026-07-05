# Plan: the tractable additive parity batch (#46–#57) — the CPU-buildable slice of the open roadmap

> **Scope honesty first.** The request was "do all on roadmap and other open
> issues." There are **no open GitHub issues** (`gh issue list` empty). The roadmap
> still-open surface is larger than this plan covers: the 12 ⬜ parity items
> (#46–#57), ~13 🟡 partials, and #33 (⬜ diarization). This plan does **not** clear
> the whole roadmap — it delivers the coherent, high-value slice that is *additive,
> pure-Python, and fully CPU/CI-testable in this sandbox*: the parity batch #46–#57.
> Everything else is blocked on UI work, release/packaging infra, GPU/hardware, a
> calibration rig, external accounts, or art — enumerated in **Deferred** below so
> the reader sees the whole board, not a 25% slice framed as "done." A one-line
> scope confirmation to the user accompanies this plan; the subset is the defensible
> default if they'd rather I just drive.

## Summary

Bring TalkTeach to parity with the pro toolsets on the additive capabilities the
gap analysis (`COMPETITIVE_GAPS.md`) named — all pure-Python, no new ML research —
following the repo's established **pure-helper + guarded-ML** pattern
(`project/docs/DECISIONS.md` D-002): real CPU/CI-testable logic in torch-free
modules, heavy paths import-guarded, one test file per capability, one design-doc
touch, and a `ROADMAP_STATUS.md` row flip per item.

## Scope — what gets built (12 items)

Each item = a torch-free pure module (unit-tested in the dep-light CI job) + any
guarded ML path + docs + a `ROADMAP_STATUS.md` status flip. Grouped into 4 batches,
each independently committable and gated by `make check`.

**Batch A — Transcription output & evaluation**
- **#48 Subtitle/caption output** — `transcript/subtitles.py`: pure
  `segments_to_srt` / `segments_to_vtt` / `segments_to_text` from
  `[{start,end,text}]`. Fully testable (timestamp formatting, cue numbering).
- **#49 Long-form chunked transcription** — `transcript/longform.py`: pure
  `plan_chunks(duration_s, window_s, overlap_s)` + `merge_segments` (offset +
  dedup overlap); the actual decode is a thin guarded wrapper over the engine's
  `transcribe`. Pure windowing/merge logic tested without ML.
  - ⚠️ **Prereq (advisor):** `transcribe` at `whisper_lora.py:342` currently
    `" ".join(seg.text…)` and *discards* the `start`/`end` faster-whisper returns.
    Add a segment-returning decode (e.g. `transcribe_segments` → `[{start,end,text}]`)
    so #48/#49 and the "run `talkteach subtitle` on the toy dataset" verify step have
    a real timestamp source. Small, additive; existing `transcribe` unchanged.
- **#52 Richer evaluation** — `eval/report.py`: `per_utterance_wer`,
  `error_report` (substitution/insertion/deletion confusions), `normalized_vs_raw`.
  jiwer-only, fully testable; feeds active learning (#32).
  - ⚠️ **Confirm-before-build (advisor):** build the confusion aggregation on
    `jiwer.process_words(...).alignments` (sub/ins/del chunks); verify that API shape
    against the pinned `jiwer>=3.0` in a scratch REPL before writing the aggregator.
- **#50 Decoding controls** — `transcript/decode.py`: pure `DecodeOptions`
  (beam_size, initial_prompt/hotwords, temperature fallback ladder) +
  `to_faster_whisper_kwargs()`; `whisper_lora.transcribe` gains an optional
  `options` param threaded to the guarded decode. Builder tested pure.

**Batch B — Data & training breadth**
- **#47 Dataset import** — `data/import_manifest.py`: folder-of-pairs, manifest
  CSV/JSON, NeMo JSONL manifest, Common Voice TSV, LibriSpeech `.trans.txt` →
  the canonical `[{path,text,duration_s}]` manifest shape. Pure parsing, fully
  testable with tiny fixtures.
- **#46 Data augmentation** — `audio/augment.py`: pure-numpy `spec_augment`
  (time/freq masks), `perturb_speed`, `perturb_pitch` (resample-based), `mix_noise`
  (SNR-targeted); `director/policy.py::augmentation_for` auto-enables for tiny
  datasets. Numpy-only, fully testable.
- **#51 Punctuation/capitalization restoration** — `transcript/punctuate.py`:
  rule-based `restore(text)` (sentence-boundary capitalization + terminal period)
  as the always-available fallback; an optional guarded model path documented.
  Rules fully testable.

**Batch C — Interfaces, export, metrics**
- **#54 Headless CLI** — `talkteach/cli.py` + `[project.scripts] talkteach=`:
  subcommands `import`, `subtitle`, `eval`, `augment` wrapping the pure modules,
  and `train`/`export`/`transcribe` dispatching to engines (guarded). argparse
  wiring + light subcommands tested; heavy subcommands smoke-tested for dispatch.
- **#57 More export targets** — extend `whisper_lora.export`: `safetensors` real
  (guarded `save_pretrained(safe_serialization=True)` on the merged model);
  `torchscript` = encoder/`forward` trace **or** documented-scaffold if Whisper's
  `.generate()` (kv-cache + beam) resists `torch.jit` (⚠️ advisor: known trap — do
  not let it eat the batch); `gguf` = documented dry-run scaffold. Pure format-
  routing tested; dry-run path already covered.
- **#53 Local experiment metrics** — `obs/experiment.py`: append-only JSONL
  metrics log (`{epoch,loss,wer,cer,ts}`) + `read_curve()` reader (no telemetry,
  honours D-008); the training callback writes to it. Reader/writer fully testable.

**Batch D — Documented escape hatches (correct tier = design + thin plumbing)**
- **#55 Custom vocabulary / tokenizer extension** — `engines/vocab.py`:
  pure `merge_vocab(base_tokens, extra_words)` helper for the CTC path + `VOCAB.md`.
  Pure merge tested; live tokenizer extension documented as guarded.
- **#56 Optional multi-GPU / distributed** — ⚠️ **advisor:** HF multi-GPU is driven
  by the *launcher* (`torchrun` / `accelerate launch`), **not** a
  `Seq2SeqTrainingArguments` flag — do not invent a flag that doesn't map to DDP.
  So: document the `torchrun`/`accelerate` escape hatch in `MULTIGPU.md`, and at
  most add a real *passthrough* (e.g. honour `ddp_find_unused_parameters` if the
  plan sets it) — no fake knob. Multi-GPU run itself is doc-only (needs hardware).

**Delivery floor (scope discipline):** Batches are committed independently and in
value order, so partial delivery is always coherent. If quality/time pressure hits,
the committed floor is **Batch A + Batch B** (the 7 highest-value items: #46–#52);
Batch C/D degrade gracefully to their correct doc/scaffold tier rather than being
rushed. No item ships half-tested — an item is either done to the bar (module +
tests + doc + status flip) or left at its current tier.

## Deferred — complete accounting of the rest of the open roadmap (not faked)

Grouped by the blocker that keeps each out of *this* additive-backend batch. None
regress; each keeps its current tier + design doc.

- **Needs UI work** (product-flow / front-end surface, not an additive backend
  module): **#13** live recording meter (WebAudio, client-side) · **#18** pre-flight
  *screen* (API already done) · **#36** i18n UI strings · **#37** a11y pass · **#29**
  multi-project *app layer* (data layer already multi-project; the gap is `app.py` +
  UI, higher blast radius).
- **Needs release / packaging infra**: **#10** bundle ffmpeg · **#16** no-install
  runtime · **#24** signed installers (certs + per-OS runners) · **#4** ONNX/sherpa
  export (CT2 already real; ONNX needs the packaged runtime to verify).
- **Needs GPU / hardware / a calibration rig**: **#25** NeMo (GPU-only) · **#6**
  director calibration (needs real datasets + varied hardware) · **#12** forced
  alignment (needs the aligner model + long audio) · live **#56** multi-GPU run.
- **Needs external accounts / models / art**: **#27** cloud fallback (infra) ·
  **#31** mascot (artist) · **#33** diarization (pyannote/NeMo model + design) ·
  **#30** denoise (value *is* the neural DeepFilterNet model, already guarded-
  scaffolded; the pure part is a trivial gain helper, not worth a batch) · **#34**
  model-packs *publish* half (the local packing already ships as
  `scripts/pack_model.py`; "Publish to Hugging Face" needs network + auth).

**Why #29 / #34 / #30 are Deferred though 🟡, when parity-⬜ items are In:** the In
set is strictly *additive new backend modules with pure CPU-testable logic*. #29 is
a refactor of the shipping `app.py`/UI (product surface, not additive); #34's
remaining gap is network/auth publish (its pure half already shipped); #30's
remaining value is a guarded neural model. That is the boundary — additive-and-
pure-and-CPU-testable — and these three fall outside it, not by neglect.

## Steps (ordered)

1. Batch A: write 4 modules + `tests/test_transcript.py`, `tests/test_eval_report.py`;
   `make check`; commit.
2. Batch B: write 3 modules + `tests/test_dataset_import.py`, `tests/test_augment.py`,
   extend `tests/test_transcript.py`; wire `augmentation_for` into policy; `make check`;
   commit.
3. Batch C: write `cli.py` (+ `[project.scripts]`), extend `export`, add
   `obs/experiment.py` + wire the callback; `tests/test_cli.py`,
   `tests/test_experiment.py`, extend `test_engines.py` for export routing;
   `make check`; commit.
4. Batch D: `engines/vocab.py`, plan flag + kwargs, `VOCAB.md`/`MULTIGPU.md`;
   `tests/test_vocab.py`; `make check`; commit.
5. Docs sweep: flip the 12 `ROADMAP_STATUS.md` rows (⬜→✅/🟡 with evidence),
   update `FORMATS.md` (#47/#48/#49/#57 rows), add a `DECISIONS.md` record for the
   parity batch, refresh `CHANGELOG.md`, cross-link new docs; `make check`; commit.

## Risks / reversibility

- **Blast radius**: almost entirely *new* files. The only edits to shipping code
  are additive: `whisper_lora.transcribe` gains an optional `options=None` param
  (default preserves today's behaviour), `export` gains new `fmt` branches (unknown
  fmt already falls through to the dry-run manifest), `policy.py` gains a new
  function, `_whisper_train` callback gains an optional metrics-log write guarded on
  a path being set. No existing signature changes meaning; no endpoint is altered.
- **Rollback**: each batch is one commit on `main`; revert the commit. New modules
  are unreferenced by the product flow until explicitly called.
- **Dep discipline**: every new module is torch/transformers-free at import time
  (numpy + jiwer are already base/[ml]-light and used across the repo). Heavy work
  stays function-local + guarded, matching D-002 — so the dep-light CI `python` job
  stays green.
- **CI job coverage**: new tests must not import torch at module load. Verified by
  running the suite in the dep-light path (mypy + ruff + pytest via `make check`).

## Test plan

- New tests are pure and run in the default `make test` (no markers): SRT/VTT
  formatting, chunk-plan + merge math, per-utterance WER + confusion report,
  DecodeOptions→kwargs, all five import formats, each augmentation's shape/energy
  invariants, punctuation rules, CLI arg parse + light-subcommand dispatch, export
  fmt routing (dry-run assertions, no real convert), metrics JSONL round-trip,
  vocab merge, multi-GPU kwarg mapping.
- Regression: full `make check` after every batch; the existing 131 tests must stay
  green. Heavy/guarded paths keep their opt-in markers (`integration`), unchanged.
- Manual/verify: run `talkteach subtitle`/`import`/`eval` on the toy dataset from
  `scripts/make_toy_dataset.py` end-to-end to observe real output (the /verify bar).

## Standards & Guardrails Evidence

- Pure-helper + guarded-ML split, torch-free import: `backend/talkteach/engines/_train_common.py:1`
  (jiwer-only helpers) and `backend/talkteach/engines/whisper_lora.py:7` (guarded-import philosophy).
- Canonical manifest shape reused by import/augment: `backend/talkteach/tts/dataset.py:1`
  (`[{"path","text","duration_s"}]`).
- Transcribe signature to extend (add `options`): `backend/talkteach/engines/whisper_lora.py:296`.
- Export fmt routing to extend (dry-run fallback already present): `backend/talkteach/engines/whisper_lora.py:380`.
- WER/CER helpers to build richer eval on: `backend/talkteach/engines/_train_common.py:60`.
- Test/marker conventions + dep-light default: `backend/pyproject.toml` `[tool.pytest.ini_options]` markers; pure-parity test style `backend/tests/test_p2p3.py:1`.
- Verify contract: `Makefile:51` (`check: lint test`), lint = ruff + ruff format + mypy (`Makefile:36`).
- Status matrix to update: `project/docs/ROADMAP_STATUS.md:71` (parity rows #46–#57).
- Formats matrix to update: `project/docs/FORMATS.md:29` (#47/#48/#57 rows).
- Commit target = `main` directly (repo has no AGENTS.md worktree contract; per user memory).
</content>
