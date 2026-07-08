# Plan — Full-scoreboard automation: no fabrication, real CPU measures, B-001 unblock

## Context
The single authoritative SOTA is the generated 15-domain scoreboard. Today only 4/15 domains
(d01/d04/d06/d12) are genuinely measured. Five `validate_*` scripts emit **hardcoded fabricated
scores** (d03=900/platinum, d05/d09/d13/d14=800/gold, all "placeholder estimate"), which a full
`run_all.sh` would collect into the scoreboard — and the small-n gate would **not** catch them
(they carry no `num_clips`, so `assess_headline_eligibility`'s `n_clips > 0` guard treats them as
eligible). Four domains (d08/d10/d11/d15) are unimplemented stubs; two (d02/d07) are blocked by
B-001 (HF `datasets` v5 needs `torchcodec`, which is absent).

This change makes the full scoreboard honest and as-automated-as-truthfully-possible:
1. **Neutralize fabrication** — the 5 scripts abstain (`score 0`, `human_needed`), never fabricate.
2. **Partial-scope gate** — one chokepoint so scope-partial/proxy measures are excluded from the
   headline even when well-powered (advisor finding: `directional` set inside a measure method is
   overwritten by `aggregate_headline`; the gate must own it).
3. **Real CPU measures** — d08 (int8-quant delta), d10 (beam sweep), d11 (long-form proxy),
   d15 (disk/RAM), all honestly flagged `partial`; **d02** (CV17 WER) as a genuine eligible domain.
4. **B-001 fix** — torchcodec-free HF loader (`Audio(decode=False)` + soundfile; mp3 supported).
   d07 stays `human_needed` (FLEURS spec loads only `en_us`; the metric counts languages).

## Verified facts (this session)
- LibriSpeech test-clean: **2620 flac cached** → d08/d10/d11/d15/d01/d04/d06/d12 measurable on CPU.
- train-clean-100: **tar only, not extracted** → d03/d05/d09/d13 correctly stay abstained; routing
  them through `run_domain` would trigger a 6 GB extraction via `ensure_data` → use explicit payload.
- `datasets`==5.0.0, `torchcodec` MISSING (confirms B-001); `soundfile`==0.14.0 **MP3=True**;
  `psutil`==7.2.2 present; network ONLINE (loader fix live-verifiable); 216 fast tests (AGENTS.md
  says 198 — drifted, update).

## Design
- **Abstention payload (Task 1):** `score_0_1000=0`, `band="human_needed"`,
  `metrics={"status": "...", "requires": "..."}`. No numeric estimates. Add `human_needed` to
  `report.BAND_EMOJI`. Static test forbids `"score_0_1000": <positive int>` literals in any
  `validate_d*.py`.
- **Partial-scope gate (Task 2 mechanism):** `assess_headline_eligibility` returns
  `(False, "directional: <reason>")` when `metrics.get("partial")` is truthy — before the
  speaker/clip checks. Measure methods set `metrics["partial"]` for scope-partial/proxy results.
- **Measures (Task 2):** function-local heavy imports. d08 = |WER(int8) − WER(CT2-float32)| on same
  clips, metric named honestly, `partial="int8 quantization only (1 of 3 export targets)"`. d10 =
  beam∈{1,5} sweep, best WER, `partial="beam sweep only; no hotword/OOV domain-vocab set"`. d11 =
  concat clips to a configurable target (default ~10 min), Δ vs 1-min, `partial="proxy: N min < 60,
  concatenated read speech"`. d15 = CT2 model disk MB / audio-min (scored) + peak RSS (psutil,
  reported), `partial="disk scored; RAM/GB-hr reported not scored"`. Each sets `num_clips`.
- **Dispatch:** add d02/d08/d10/d11/d15 branches to `run_domain`; d02 reuses `measure_base_wer` on
  `common_voice_en` (n≈200 ≥ min_samples 100 → eligible). d07 → explicit abstention script.
- **B-001 (Task 3):** `download_hf_dataset` casts audio to `Audio(decode=False)`, decodes bytes/path
  via `soundfile.read(BytesIO)`, writes 16 kHz wav. Unit test with in-memory `datasets.Dataset`
  (no torchcodec) + live smoke `download(common_voice_en, max_samples=5)`.
- **Regenerate + single-source:** run runnable domains, regenerate `SCOREBOARD.{md,json}`, update
  `OVERALL.md`'s referenced `generated` stamp + coverage one-liner, update memory + AGENTS.md count.

## Steps
1. Task 1: rewrite 5 fabricated scripts → abstain; `human_needed` emoji; static integrity test.
2. Task 2 mechanism: `partial` gate in `assess_headline_eligibility` + unit test.
3. Task 2 measures: 5 `measure_*` methods + run_domain branches (d02/d08/d10/d11/d15); pure-helper
   unit tests for delta/per-min arithmetic.
4. Task 3: torchcodec-free loader + unit test + live smoke; d07 abstention script.
5. Regenerate scoreboard; update OVERALL.md stamp + coverage; memory; AGENTS.md test count.
6. Verify: fast suite green; run scripts on cache; confirm no fabrication, partial→directional,
   d02 eligible; lint/mypy clean. Merge to main.

## Verification of the change
- Static test fails on any hardcoded positive score; passes after rewrite.
- Running d03/d05/d09/d13/d14 → `score 0`, `human_needed`, no placeholder metrics.
- d08/d10/d11/d15 produce real numbers, all `directional` (partial); d02 measured, eligible.
- Loader unit test writes wav+txt without torchcodec; live smoke downloads 5 CV17 + 5 FLEURS clips.
- `SCOREBOARD.json` stamp == `OVERALL.md` referenced stamp (existing stamp-equality test).
- `make lint` + full fast suite green (new count recorded in AGENTS.md).

## Standards & Guardrails Evidence
- [x] **Tests / shift-left:** new fast tests in `backend/tests/test_sota_scoring.py:1` — static
  no-fabrication guard over `scripts/sota/validate_d03_train_efficiency.py:17` (the payload being
  removed), the `partial`-scope eligibility gate, delta/per-min pure helpers, and the
  torchcodec-free loader (`backend/talkteach/sota/datasets.py:127`).
- [x] **Reused patterns / grounding:** new measures live in `backend/talkteach/sota/harness.py:117`
  alongside `measure_base_wer`; d02 reuses it verbatim; the partial gate extends the existing
  `assess_headline_eligibility` (`backend/talkteach/sota/scoring.py:216`) rather than adding a second
  path; report/rescore already read `directional` (`backend/talkteach/sota/report.py:53`).
- [x] **Security:** N/A — offline benchmark measurement + one HF dataset loader change that only
  writes wav/txt to the user cache; no credentials or trust boundary
  (`backend/talkteach/sota/datasets.py:101`).
- [x] **Evidence classification:** `backend/talkteach/sota/scoring.py:216` — the `partial` flag +
  `human_needed` band (`backend/talkteach/sota/report.py:11`) separate real adequately-powered
  measurement from scope-partial/proxy and from abstained (needs training/labels/multi-config).
- [x] **Reproducibility:** `backend/talkteach/sota/datasets.py:137` — the loader writes deterministic
  16 kHz wav; measures use fixed `seed`/`beam_size` and heavy imports stay function-local (D-002,
  `backend/talkteach/sota/harness.py:139`).
- [x] **Statistical validity:** `backend/talkteach/sota/scoring.py:234` — every new measure sets
  `num_clips`; the small-n gate flags under-powered results directional, and `partial` excludes
  scope-limited ones from the mean.
- [x] **Baseline / SOTA calibration:** `backend/talkteach/sota/domains.py:199` — d08 metric is
  int8-quantization delta (not "export fidelity"), marked partial to avoid re-inflating the headline;
  d07 kept `human_needed` as the FLEURS spec loads only `en_us` (`backend/talkteach/sota/domains.py:176`).
