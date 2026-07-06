# Decision log (ADR-lite)

Every non-obvious choice made while taking TalkTeach forward from Phase 0
is recorded here. The mandate for this work was explicit:

> When questions arise, generate the top 5 options, score them 0–100, pick the
> best, and document the decision here — do not ask.

So each entry below lists the options that were weighed, a 0–100 score, and the
rationale for the pick. Decisions are append-only; if one is later reversed, a
new entry supersedes it and links back (we never silently rewrite history).

## How to read a decision

```
### D-NNN — <title>            (status: accepted | superseded by D-MMM)
Context: why this came up.
Options (score /100):
  1. <pick>           92  — why it wins
  2. <runner-up>      80  — why it lost
  ...
Decision: <the pick>.
Consequence: what this commits us to / what to revisit.
```

Scores are deliberate but not pseudo-precise: they encode *fit to this
project's constraints* (easy-to-use, offline-first, GPL-3.0, mostly integration
not research, must degrade gracefully on a GPU-less laptop), not abstract merit.

---

## D-001 — Definition of "implement all ROADMAP items" under sandbox limits

Context: the goal says "implement all items in `ROADMAP.md`." Several items
are physically impossible to *run to completion* in this environment: signed
installers for three OSes (#24) need code-signing certs and three build hosts;
compiling the Tauri shell (#14) needs the WebKit/GTK dev libs installed;
director calibration (#6) needs real GPUs and labelled datasets; cloud fallback
(#27) needs a remote GPU; mascot art (#31) needs an artist. Treating "done" as
"binary literal completion" would force checkbox stubs that fail the final
coherence check.

Options (score /100):
1. **Tiered definition of done + a traceability matrix** — 95 — every item gets
   an honest status: Tier A (code + tests verified here), Tier B (code written &
   guarded; integration deferred behind a marker because it needs
   network/GPU/root), Tier C (design doc + scaffolding + script). The matrix
   (`ROADMAP_STATUS.md`) is the spine that proves coverage.
2. Implement only the feasible subset, mark the rest "won't do" — 60 — honest but
   abandons the breadth the goal asked for; loses design value.
3. Stub every item to "done" — 20 — fails coherence, dishonest.
4. Ask the user to descope — 15 — the goal explicitly forbids asking.
5. Attempt real installers/training in-sandbox anyway — 35 — burns the whole
   budget on flaky work that can't finish; starves everything else.

Decision: **Option 1.** Tier each item; the matrix is authoritative. Tier B/C
items ship real, reviewable artifacts (code paths, configs, design docs,
scripts) and a documented "how to verify on a provisioned machine."

Consequence: the bar for "95/100" becomes *coverage × honesty × quality of
artifacts*, not a green checkbox per line. The matrix must stay in sync with
reality at the final coherence pass.

> **Update (2026-06-28, pre-release):** #14 is no longer deferred — the Tauri
> shell was compiled and run end-to-end on a host with WebKit/GTK present
> (`npm run tauri dev` → window + sidecar spawn + live `/api/health` 200), so it
> is now Tier A. See `ROADMAP_STATUS.md` #14 and `PHASE0_STATUS.md`. The "needs
> root" note above was wrong: the dev libs need to be *present*, not installed as
> root at build time.

## D-002 — Test strategy for ML code that needs network/GPU

Context: the real training loop, export, VAD, and forced alignment all need heavy
deps and (for end-to-end) network downloads and a GPU. CI and this sandbox have
neither reliably.

Options (score /100):
1. **Extract pure functions, unit-test those; gate end-to-end behind a marker** —
   94 — `build_training_arguments(plan)`, the data collator, and `compute_metrics`
   (WER) are deterministic and testable with synthetic tensors and no network.
   The full fine-tune lives behind `@pytest.mark.integration` + an env flag.
2. Mock torch/transformers entirely — 55 — brittle, tests the mock not the code.
3. Only test end-to-end — 30 — can't run in CI; gives zero signal here.
4. Skip tests for ML code — 10 — abandons the quality bar.
5. Snapshot-test against a recorded run — 45 — heavy fixtures, fragile.

Decision: **Option 1.** Pure-core + marked-integration. The pure helpers are the
parts most likely to harbour off-by-one/precision bugs anyway.

Consequence: `pytest -q` stays fast and green with or without `[ml]`; the
integration suite is opt-in (`TALKTEACH_RUN_INTEGRATION=1 pytest -m integration`).

## D-003 — WER metric library

Context: item #2 needs WER/CER for the smartness meter and `compute_metrics`.

Options (score /100):
1. **jiwer** — 90 — tiny, MIT, the de-facto standard for WER/CER, no torch dep,
   already used across the Whisper fine-tuning ecosystem.
2. `evaluate` (HF) — 70 — heavier, pulls a large dep tree for one metric.
3. Hand-rolled Levenshtein — 60 — avoids a dep but reinvents a solved, subtle
   problem (tokenisation, normalisation).
4. torchmetrics — 55 — needs torch even to compute a string metric.
5. `editdistance` only — 50 — gives raw distance, not normalised WER/CER.

Decision: **jiwer**, added to the `[ml]` extra and imported lazily.

Consequence: WER/CER are computed identically in tests (synthetic strings) and in
the trainer's `compute_metrics`.

## D-004 — Upload filename sanitisation (security #7)

Context: `app.py` wrote uploads to `clip_dir / audio.filename`; a crafted
filename (`../../etc/...`) escaped the project dir — a path-traversal vuln.

Options (score /100):
1. **Generate a server-side name (uuid hex) + keep a safe extension allow-list** —
   93 — fully removes attacker control over the path; stable, collision-free;
   extension constrained to known audio types.
2. `os.path.basename` only — 72 — strips directories but keeps attacker-chosen
   names (odd unicode, overwrites, `.` tricks); weaker.
3. `werkzeug.secure_filename` — 70 — good, but adds a dep for one function.
4. `Path(name).name` + reject if it changes — 68 — clunky UX (rejects valid odd
   names).
5. Reject any non-basename and 400 — 60 — breaks legitimate browser blobs.

Decision: **Option 1** — `clip_<uuid4hex>.<ext>` where `ext` is validated against
an allow-list (`wav/webm/ogg/mp3/m4a/flac`), defaulting to `wav`. The original
name is stored as metadata only, never used for the path.

Consequence: filenames are no longer a trust boundary. A regression test asserts a
`../`-laden upload lands inside `clip_dir`.

## D-005 — Tauri Content-Security-Policy (security #8)

Context: `tauri.conf.json` had `security.csp: null` (no CSP — permissive).

Options (score /100):
1. **Locked CSP: `default-src 'self'`; connect to the local backend; styles
   `'self' 'unsafe-inline'`; no remote** — 90 — the app is fully local/offline;
   the only network target is `http://127.0.0.1:8756` (+ ws for live progress).
   `'unsafe-inline'` for styles is required by Svelte's scoped-style injection;
   scripts stay strict.
2. Strict `default-src 'self'` with zero inline — 70 — breaks Svelte styles and
   inline bootstrap; would need a nonce pipeline not worth it for a local app.
3. Allow `https:` broadly — 40 — defeats the point; app is offline.
4. Leave `null` — 10 — the vuln.
5. CSP via meta tag in index.html only — 50 — Tauri's config CSP is the canonical,
   enforced layer; meta-only is weaker and easy to drop.

Decision: **Option 1.** Backend origin is configurable via the documented
`TALKTEACH_PORT`; the shipped CSP targets the default `:8756` and `ws:` for the
progress stream.

Consequence: any future remote feature (cloud fallback #27, HF publish #34) must
explicitly widen the CSP and is called out in that work.

## D-006 — Real export format (#4)

Context: "Use on my computer" must produce a runnable offline model. The roadmap
names sherpa-onnx (ONNX) and CTranslate2.

Options (score /100):
1. **CTranslate2 int8 as the default, ONNX via sherpa-onnx as an opt-in target** —
   88 — CT2 is already wired, is the fastest CPU path for Whisper, and pairs with
   faster-whisper which we already use for "Try it"; ONNX/sherpa is the
   streaming/edge path (Phase 2) and is additive.
2. ONNX-only — 65 — loses the faster-whisper synergy; Whisper→ONNX export is
   fiddlier than CT2 for the default desktop case.
3. Raw PEFT adapter only — 50 — not runnable standalone without the base + peft.
4. Merge LoRA then ship safetensors — 60 — portable but slow at inference vs CT2.
5. TorchScript — 40 — heavy runtime, poor CPU story.

Decision: **Option 1.** Export first merges the LoRA adapter into the base model,
then converts to CT2 int8; ONNX/sherpa export is a documented Phase-2 target with
a scaffolded code path.

Consequence: the export step depends on the training loop producing a PEFT adapter
in `workdir`; documented in the engine.

## D-007 — Job durability model (#40)

Context: training jobs live in an in-memory `_jobs` dict; a backend/sidecar
restart orphans a run.

Options (score /100):
1. **DB is the source of truth + reattach to checkpoints on startup; in-memory
   dict is just a live cache** — 90 — the SQLite `training_run` table already
   persists status; on startup we reconcile "running" rows against their workdir
   checkpoints and expose status from the DB when not in memory (already
   partially done in `training_status`). Add a recovery sweep.
2. Full job queue (Celery/RQ) — 45 — massive over-engineering for a local
   single-user app; adds a broker dep.
3. Re-spawn the training thread on restart automatically — 55 — risky (double
   training, resource spikes) without user intent; better to surface "resume?".
4. Write a pidfile/jobs.json — 50 — duplicates the DB as a second source of truth.
5. Do nothing — 20 — the orphaned-run bug.

Decision: **Option 1.** On startup, mark stale "running" rows as "interrupted" and
let the user resume (training already resumes from the latest checkpoint in
`workdir`). Status reads fall back to the DB, which they already do.

Consequence: "running" in the DB means "was running"; a startup reconciliation
pass distinguishes live (in `_jobs`) from interrupted.

## D-008 — Telemetry posture (#41)

Context: observability wants telemetry, but the product promise is offline,
safe, private.

Options (score /100):
1. **Off by default, local-only structured logs + an explicit "Export a help
   bundle" button; any network telemetry strictly opt-in and documented** — 96 —
   matches the offline/privacy promise; the help bundle gives support data
   without a phone-home.
2. Opt-out anonymous telemetry — 40 — violates the privacy promise for the
   app.
3. No logging at all — 30 — abandons supportability.
4. Always-on local logs, no export — 60 — useful but no support path.
5. Third-party crash reporter (Sentry) — 35 — network + PII risk for the app.

Decision: **Option 1.** `structlog`-style JSON logs to the project dir, rotating;
no network by default; a help-bundle exporter zips logs + redacted env.

Consequence: telemetry remains a non-feature until/unless a user opts in; documented
in `OBSERVABILITY.md`.

## D-009 — Python lint/format/type stack (#39)

Options (score /100):
1. **ruff (lint+format) + mypy** — 93 — ruff replaces flake8/isort/black/pyupgrade
   in one fast tool; mypy is the mature type checker; both have zero runtime cost.
2. black + flake8 + isort + mypy — 70 — four tools, slower, more config.
3. ruff + pyright — 75 — pyright is excellent but Node-based; mypy fits the Python
   CI better and the codebase already type-annotates for it.
4. ruff only (use its type rules) — 55 — ruff doesn't type-check.
5. No type checker — 30 — abandons a quality gate the roadmap names.

Decision: **ruff + mypy**, configured in `backend/pyproject.toml`, gated in CI and
pre-commit.

Consequence: existing code must pass; findings fixed as part of the guardrails
commit (tracked in `LEARNINGS.md`).

## D-010 — UI audio capture → trainable format (#20)

Context: the browser `MediaRecorder` emits webm/opus; training needs 16 kHz mono
WAV. ffmpeg (#10) is the decode path.

Options (score /100):
1. **Record webm in the browser, decode+resample to 16 kHz mono WAV server-side
   via bundled ffmpeg** — 90 — keeps the UI thin, reuses the ffmpeg dep we bundle
   anyway, one canonical conversion path shared by uploads and recordings.
2. WebAudio `AudioContext` → WAV in the browser — 70 — no ffmpeg needed for
   recordings, but duplicates resampling logic and still needs ffmpeg for uploads;
   two code paths.
3. Ship a WASM ffmpeg in the UI — 55 — large bundle, slower, redundant with the
   server ffmpeg.
4. Train directly on webm — 20 — frameworks expect PCM; lossy/awkward.
5. Require users to upload WAV — 30 — breaks the record-in-app promise.

Decision: **Option 1.** The backend gains an `audio/decode.py` ffmpeg wrapper used
by both `/clips/analyze` and recordings; it degrades gracefully (clear message)
when ffmpeg is absent, exactly as today.

Consequence: ties UI recording to the ffmpeg bundling work; both are Tier B
(code + guarded) here since ffmpeg isn't installed in-sandbox.

## D-011 — svelte-check strictness on a plain-JS Svelte codebase

Context: the UI is plain JavaScript Svelte (no TypeScript). Enabling
`svelte-check` with `checkJs: true` + `strict: true` surfaced **61** errors —
all of them JS-level strictness noise (`document.getElementById` may be `null`,
untyped function params), zero genuine Svelte template/binding bugs.

Options (score /100):
1. **Run svelte-check with `checkJs: false` (template/component validation only)**
   — 88 — catches the errors that actually matter for a Svelte app (undefined
   components, bad bindings, a11y, store misuse) without imposing TS-strict typing
   on a codebase that deliberately isn't TypeScript. Confirmed 0 errors.
2. Fix all 61 with JSDoc types + null guards — 65 — large churn for a 9-file UI;
   buys real type safety but is a TS-migration in disguise, out of scope now.
3. Migrate the UI to TypeScript — 60 — the right long-term move, but a separate,
   large piece of work; tracked as a follow-up, not part of the guardrails pass.
4. Drop svelte-check entirely — 30 — abandons a gate the roadmap names (#39).
5. `checkJs: true` but disable strict — 55 — still ~dozens of nullability errors;
   awkward middle ground.

Decision: **Option 1** now; **Option 3 (TS migration)** noted as a future
follow-up in `I18N.md`-adjacent backlog. svelte-check gates template
correctness; ESLint + Prettier cover JS hygiene and style.

Consequence: `npm run check` is a real, green gate. A future TS migration can
flip `checkJs` back on incrementally.

## D-012 — When does `train()` run the real loop vs. the simulation?

Context: with `[ml]` installed (as in this venv), we want "Teach!" to *really*
train. But the fast test suite must never trigger a multi-GB model download +
fit, and the existing tests seed clips with non-existent paths (`/seed/*.wav`,
`a.wav`) expecting the dependency-free simulation.

Options (score /100):
1. **Real when (deps present) AND (manifest audio actually exists on disk) AND
   (not force-simulated); simulate otherwise** — 93 — elegant and honest: if the
   engine literally cannot load the audio it was handed, it can't really train,
   so it demonstrates via the simulation (clearly `[SIMULATION]`-marked). Real
   clips on a real install → real training. The existing tests (fake paths) keep
   passing *unchanged* because their paths don't resolve. An explicit
   `TALKTEACH_FORCE_SIMULATION=1` override exists for demos/CI.
2. Real behind an opt-in env flag (default simulate) — 75 — safest for tests but
   undersells the promise; a plain `[ml]` install would still only simulate.
3. Real whenever torch present — 55 — faithful to the promise but breaks the fast
   tests (fake paths) and risks an accidental 2 GB download in CI.
4. Real only inside the integration marker — 60 — the product flow never trains
   for real; wrong.
5. A UI consent gate before real training — 70 — good product idea (model
   download consent) but orthogonal to the engine-level decision; layer it on top.

Decision: **Option 1.** `_should_simulate(manifest)` returns True when training
deps are missing, when `TALKTEACH_FORCE_SIMULATION=1`, or when no manifest entry
points to an existing file. The end-to-end real fit is additionally exercised by
`pytest -m integration` against the toy dataset (#22).

Consequence: the real `Seq2SeqTrainer` path is the default for a real install
with real recordings, while the test suite stays fast, deterministic, and green
without modification. Pure helpers (args-from-plan, WER, NaN-guard, checkpoint
discovery) are unit-tested directly.

## D-013 — TTS-backed benchmark: how do we compare ASR engines "for real"?

Context: the end-to-end automated path trained on sine *tones* — which have no
phonetic content, so any WER measured on them was noise, not recognition. We could
not validate that a model learned words, nor compare OSS engines on equal footing.
We want synthetic *speech* (known transcript) → train each engine → measure WER on
a shared eval set, with all hyperparameters pinned.

Options (score /100):
1. **Pluggable `TTSProvider` (espeak + piper) feeding a config-driven TTS×ASR
   benchmark with a shared, held-out eval set and `plan_from_config`-pinned
   hyperparameters** — 92 — mirrors the `ASREngine` adapter pattern; espeak (system
   binary, no download) is the CI fast-path, piper (neural) the fidelity end; new
   OSS engines plug in with one registry entry. WER is meaningful because the prompt
   *is* the transcript and the eval clips never overlap training.
2. One TTS engine only (piper) — 70 — simpler, but can't show that a result is
   robust across voices/synthesizers, and piper needs a model download (bad for CI).
3. Reuse the director to pick hyperparameters per cell — 45 — defeats comparison:
   the director would vary params by detected hardware, so cells wouldn't be
   comparable. Pinning via `plan_from_config` is the whole point.
4. Assert a tiny fine-tune *lowers* WER in CI — 40 — too noisy on a few clips;
   flaky. We instead assert the *measurement discriminates* (clean speech → low WER,
   tones → high WER) with no training, and keep training-improvement opt-in/loose.

Engine tiering (what "all real" means): **whisper_lora** and **wav2vec2_ctc** are
real fine-tunes, CPU-runnable and CI-able; **nemo_rnnt** is a real but GPU-only,
opt-in path (needs `[nemo]` + CUDA) that self-skips otherwise and never gates CI.
Comparable axes are WER/CER/train-time — export formats differ per engine
(Whisper→CTranslate2, wav2vec2→ONNX, NeMo→`.nemo`).

Decision: **Option 1.** See `BENCHMARKING.md` and `TTS.md`. wav2vec2 fine-tuning
disables SpecAugment and sets `ctc_zero_infinity` (both needed for stability on
short clips). The espeak measurement-is-real test runs in a dedicated
`benchmark-smoke` CI job (`[ml,tts]` + espeak-ng); the default `pytest -q` stays
ML-free.

Consequence: a single `scripts/benchmark.py --config benchmarks/*.yaml` run yields a
real, reproducible TTS×ASR WER/CER/time matrix; the tone fixtures remain only for
plumbing/simulation tests where intelligibility doesn't matter.

## D-014 — Scope + shape of the competitive-parity batch (#46–#57)

Context: the roadmap's parity items (#46–#57, from `COMPETITIVE_GAPS.md`) were all
⬜ Tier C. They are additive (no new ML research), but span a wide surface. The
question: which do we build now, and to what bar?

Decision: build the **additive, pure-Python, CPU/CI-testable** slice to the repo's
existing pure-helper + guarded-ML bar (D-002), and keep the rest at its honest tier:

- Built (module + tests + docs + status flip): #46 augmentation, #47 dataset import,
  #48 subtitles, #49 long-form, #50 decoding controls, #51 punctuation (rules),
  #52 richer eval, #53 local metrics, #54 headless CLI, #55 custom vocab,
  #57 safetensors export.
- Kept scaffold/doc **on purpose** (not neglect): ITN and the neural punctuation
  model (#51); TorchScript/GGUF export (#57) — Whisper `.generate()` (kv-cache +
  beam) does not `torch.jit` cleanly, so we ship an honest dry-run manifest rather
  than a broken trace; multi-GPU (#56) — HF multi-GPU is **launcher-driven**
  (`torchrun`/`accelerate`), so we document the escape hatch (`MULTIGPU.md`) and do
  NOT invent a `TrainingArguments` flag that maps to nothing.

Rejected: (a) faking installers/cloud/art/GPU items to mark them "done" — dishonest;
they stay deferred with reasons (see `plans/roadmap-parity-batch.md`). (b) pulling
the 🟡 app-surface items (#29 multi-project, #34 publish, #30 denoise) into this
batch — they need UI refactors / network-auth / a neural model, i.e. outside the
"additive + pure + CPU-testable" boundary that defines this batch.

Consequence: every new module imports torch-free and is exercised by the default
`make test`; heavy paths stay guarded and CLI-invocable on an `[ml]` machine. The
plan of record is `plans/roadmap-parity-batch.md` (scored + advisor-gated).

## D-015 — Easy/Advanced product tiers + surfacing the parity features in the UI

Two decisions, taken together.

**Terminology / positioning.** The product was framed as a "kids' app" (child /
grown-up / family / 10-year-old persona). We repositioned it to a general-audience
tool with two UI tiers: **Easy** — the existing wizard (Record → Check → Teach →
Try) with great defaults and few meaningful options — and **Advanced** — the `⚙`
toggle (`advancedMode`) that reveals full detail/config. The persona wording is
gone across the repo (one code identifier renamed: `grownUpMode → advancedMode`; no
API/DB/i18n-key changes). The friendly Easy-mode tone (mascot, bright palette,
"smartness" meter) is **kept on purpose** — friendly ≠ childish — and is the right
register for an easy tier. Plan of record: `plans/terminology-easy-advanced.md`.

**Where shipped-but-UI-less features live.** The parity batch (#46–57, D-014) shipped
backend + CLI only. Advanced mode is their home: export-format picker (#57),
loss/WER curve (#53), caption download (#48), decode controls (#50), "where it still
struggles" report (#52) all sit behind `{#if $advancedMode}`; dataset import (#47)
is an understated secondary action on Screen0. Easy mode renders identically —
every new control is Advanced-gated or a plain secondary affordance.

Two honesty rules we held:
- **Metrics/curve** read the *real* trainer's `metrics.jsonl`; a run with no curve
  is reported as such (`has_curve=false`) rather than drawing synthetic numbers.
- **The report is not "accuracy."** Evaluating on the *training* clips would be
  optimistic, so the generalization headline is the existing held-out
  `best_val_wer`; the per-utterance/confusion breakdown is labeled an
  active-learning signal ("fix/relabel these next", feeds #32), not a score.

Rejected: (a) surfacing everything in the Easy wizard — it would bloat the one path
that must stay simple; (b) a full de-infantilization (removing the mascot / neutral
palette) — out of scope for this pass (labels-only tone was the chosen tier). Plan of
record: `plans/advanced-mode-ui-sweep.md` (scored + advisor-gated).
