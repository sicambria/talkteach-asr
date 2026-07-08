# Plan: Advanced-mode UI sweep — surface the 6 unsurfaced backend features (#57, #53, #48, #52, #50, #47)

> **Scope (user-confirmed):** "Full sweep" — give every shipped-but-UI-less
> feature a home in **Advanced mode** (the `⚙` toggle), keeping Easy mode (the
> wizard) untouched and friendly (labels-only tone; mascot stays). The rename
> just created Advanced mode + an `.advanced` panel on all 6 screens; this stocks
> them. ML deps (faster_whisper/torch/transformers/ctranslate2) are present, so
> every feature is **verifiable end-to-end in-sandbox**, not just build-guarded.

## Summary

Six additive features, each = a thin backend endpoint (reusing already-built,
tested pure modules) + an Advanced-mode UI touchpoint. Easy mode is unchanged:
every new control lives behind `{#if $advancedMode}` or is a secondary affordance.

## Scope — what gets built (value order = delivery floor first)

**Floor (small, ML-verifiable, roadmap-explicit):**

- **#57 Export-format picker** — `GET /api/export/formats` returns
  `[{fmt,label,real,notes}]` (ctranslate2/safetensors real; onnx/torchscript/gguf
  scaffold-honest). Screen4 Advanced: a `<select>` of formats feeding the existing
  `exportModel(runId, fmt)`; Easy mode keeps the one-tap ctranslate2 button.
  Reuses `whisper_lora.export` fmt routing (already built).
- **#53 Loss/WER curve** — `GET /api/metrics/{run_id}` → resolve
  `runs/{run_id}` workdir → `obs.experiment.read_curve(workdir)` (already built) →
  `[{epoch,loss,wer,...}]`. Screen3 Advanced: an inline SVG sparkline of loss + WER
  (no dep; ~40 lines). Easy mode keeps the "smartness" meter. Completes the
  "smartness ⇄ real metrics" split the rename set up.
- **#48 Subtitle/caption download** — extend `POST /api/transcribe` to return
  `segments` (via `engine.transcribe_segments`, whisper override = real timestamps)
  **and server-formatted `srt`/`vtt` strings** from the tested
  `transcript/subtitles.py` (advisor: format server-side — the process already has
  the segments + the tested formatter; the client just downloads a string it holds,
  no JS timestamp math, no round-trip). Placement: Advanced = "Download captions ▾
  .srt/.vtt/.txt"; Easy = one plain "Save captions" (.srt) button.

**Sweep (larger, still ML-verifiable):**

- **#50 Decode controls** — `POST /api/transcribe` accepts optional
  `options: {beam_size, hotwords, temperature}` → `DecodeOptions` →
  `to_faster_whisper_kwargs()` (already built) threaded into
  `whisper_lora.transcribe`. Screen4 Advanced: beam size (number), hotwords
  (text), temperature (number). Empty/omitted → today's defaults (behaviour-
  preserving).
- **#52 Report — honest split (advisor rescore).** Do **not** re-run the model on
  the *training* clips and call the result "accuracy" — that's an optimistic,
  misleading number. Two honest pieces instead:
  - **Generalization headline = the held-out val-WER that already exists**:
    `run.best_val_wer` (set at `app.py:493`; `smartness = 1 − val_WER` is explicitly
    on a held-out set per `base.py`). Surface it directly — no re-eval, no split
    machinery. For **simulated** runs (no `metrics.jsonl`, `[SIMULATION]` marker)
    label it honestly as a simulated figure.
  - **"Where it still struggles" = active-learning signal (#32), not accuracy**:
    `GET /api/eval/{run_id}` runs the model on the clips and returns
    `per_utterance_wer` + `error_report` confusions (`eval/report.py`), **labeled
    "hardest clips / likely mislabels to fix next"**, not "your model's accuracy".
    Guarded (`available:false` if `[ml]` missing). Screen3 Advanced (post-train).
- **#47 Dataset import** — `POST /api/import` (multipart). **Upload mechanism
  (advisor): `<input webkitdirectory>`** — the browser preserves each file's
  `webkitRelativePath`, so the server reconstructs the folder tree into a temp dir
  and runs `data/import_manifest.py` (auto-detect) **unchanged** on intact relative
  paths (no hand-rebuilt path mapping). Copy audio into the project clip dir via the
  `_safe_clip_name` traversal guard (#7); insert clips; return
  `{imported, skipped, issues}`. Screen0: secondary "Import a folder" affordance
  beside "Record"; Easy default stays "Record". Last batch (highest blast radius).

**Delivery floor (scope discipline):** commit in 3 batches — (1) #57+#53+#48,
(2) #50+#52, (3) #47 — each independently green (`make check` + `make ui-check` +
/verify). If time/quality pressure hits, the floor #57+#53+#48 ships coherent;
#47 (highest blast radius: upload + file copy + DB insert) is last so it can
degrade to "designed + endpoint-only" without blocking the rest.

## Steps (ordered)

1. **Backend batch 1** (app.py, one file — avoid conflicts): `/api/export/formats`,
   `/api/metrics/{run_id}`, extend `/api/transcribe` to return `segments`.
   `tests/test_api.py` cases (formats list, metrics 404 + happy, transcribe shape).
   `make check`.
2. **api.js batch 1** + **UI batch 1**: `exportFormats()`, `metrics(runId)`, extend
   `transcribe()`; Screen4 format picker + captions download; Screen3 sparkline.
   `make ui-check`.
3. **Backend batch 2**: decode `options` on `/api/transcribe`; `/api/eval/{run_id}`.
   Tests. `make check`.
4. **api.js + UI batch 2**: decode-control inputs (Screen4 Advanced); eval report
   (Screen3 Advanced). `make ui-check`.
5. **Backend batch 3**: `POST /api/import` (multipart, manifest + audio, safe copy,
   DB insert). Tests (parse + insert + traversal guard). `make check`.
6. **api.js + UI batch 3**: `importData()`; Screen0 "Import existing data".
   `make ui-check`.
7. **Verify (/run + /verify)**: backend up + Vite; drive each — export a real
   ctranslate2 + safetensors, view a metrics curve from a seeded run, transcribe
   and download an .srt, set beam/hotwords, run an accuracy report, import a tiny
   CSV manifest. Easy mode unchanged (toggle off → no new controls visible).
8. **Docs + status**: flip `ROADMAP_STATUS.md` rows 47/48/50/52/53/57 from
   backend-only to "backend + UI"; add a `DECISIONS.md` record for the Easy/Advanced
   tiering; note the Advanced-mode homes in the relevant design docs; `CHANGELOG.md`.
   Commit direct to `main`.

## Risks / reversibility

- **Blast radius:** additive endpoints + additive UI behind `advancedMode`. The one
  behaviour-touching edit is `/api/transcribe` gaining optional `segments` +
  `options` (both default to today's behaviour). No existing endpoint changes
  meaning. Easy mode renders identically (new controls are advanced-gated).
- **#47 is the real risk** (upload + filesystem write + DB insert): mitigated by
  reusing `_safe_clip_name` (#7 traversal guard) and the existing upload-validation
  path (`_read_validated_upload`, size/codec allow-list, #9); import is last so it
  never blocks the floor. Bad manifest → `{issues}`, never a crash.
- **#52/#50 need `[ml]`** at runtime → guarded like the existing transcribe
  (`available:false` + friendly message when absent); present in this sandbox so
  verifiable now.
- **Rollback:** 3 independent commits on `main`; revert any batch. New endpoints
  are unreferenced by Easy mode.

## Test plan

- **Backend (`make check`, per batch):** `test_api.py` — export-formats list shape;
  metrics 404 for unknown run + happy read from a seeded `metrics.jsonl`; transcribe
  returns `{text,segments}` + honours `options`; eval report shape (guarded-skip if
  no ml marker) ; import parses a fixture CSV, inserts clips, and **rejects a
  traversal filename** (extends the existing `test_upload_path_traversal` pattern).
- **UI (`make ui-check`, per batch):** vite build + svelte-check + eslint + prettier;
  new components lint clean; Easy mode (advancedMode=false) renders no new controls.
- **/verify (ML present):** the step-7 end-to-end drive is the acceptance gate —
  real export files on disk, a real curve, a downloaded .srt opened, an accuracy
  report with numbers, a CSV import adding clips.

## Standards & Guardrails Evidence

- Export fmt routing to reuse: `backend/talkteach/engines/whisper_lora.py:423`
  (`export(...,fmt)`), formats ct2/safetensors real (`:440`,`:464`).
- Metrics reader: `backend/talkteach/obs/experiment.py:44` (`read_curve`); workdir
  = `runs/{run_id}` (`backend/talkteach/app.py:534`).
- Segment decode + subtitle formatters: `engines/base.py:169`
  (`transcribe_segments`), `transcript/subtitles.py` (segments_to_srt/vtt/text).
- Decode options: `transcript/decode.py::DecodeOptions.to_faster_whisper_kwargs`,
  already threaded into `whisper_lora.transcribe`.
- Eval report: `eval/report.py::error_report` / `per_utterance_wer`.
- Import parser + auto-detect: `data/import_manifest.py`; path-traversal guard to
  reuse: `app.py::_safe_clip_name` (#7), upload validation `_read_validated_upload` (#9).
- Advanced-gate + tier: `ui/src/lib/store.js` (`advancedMode`), `.advanced` panels
  on Screen0–4 + App.svelte (post-rename).
- Existing transcribe/export/runs endpoints to extend: `app.py:430`, `:585`, `:601`.
- Verify contract: `Makefile` `check: lint test`; `make ui-check`.
- Commit target = `main` (no worktree contract; per user memory).
