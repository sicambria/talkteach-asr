# Learnings, errors & insights

A running log of things that went wrong, surprised us, or are worth remembering —
the institutional memory the design report (Part C) said the *real* risk lives in.
Newest entries at the top of each section.

## Start here — gotchas that will waste your time if you don't know them

1. **Run tests with `backend/.venv/bin/python -m pytest`** — the venv is Python
   3.11 with the ML deps; system `python3` is 3.14 and can't import them.
2. **`pip` is absent in the venv** (it was made by `uv venv`). Install with
   `VIRTUAL_ENV=backend/.venv uv pip install <pkg>`, never `python -m pip`.
3. **The fast suite forces simulation** (`tests/conftest.py` sets
   `TALKTEACH_FORCE_SIMULATION=1`). To exercise the *real* model path, run the
   opt-in `-m integration` tests — and check they print `passed`, not `skipped`
   (a missing dep silently skips and looks like success).
4. **Heavy ML imports are always function-local and guarded.** Never hoist
   `import torch`/`transformers` to module scope — it breaks the no-ML invariant
   that keeps `pytest -q` fast and CI GPU-free.
5. **`make check` is the gate.** Run it before declaring anything done; it runs
   ruff + mypy + the fast suite against the venv.
6. **After editing a Tier-B path you can't run in the fast suite** (the real
   trainer, export), re-run `-m integration` — green unit tests do *not* cover it.

## Insights

- **A status matrix written up-front drifts; audit every cell against code at the
  end.** `ROADMAP_STATUS.md` was authored at spine time, *aspirationally*, then
  the build happened. By the coherence pass several ✅ cells pointed at wirings
  that never shipped (a live-meter UI, a preflight screen) or at files that were
  later renamed/consolidated (`fetch_runtime.py`→`build_sidecar.py`,
  `test_decode.py`→`test_audio_pipeline.py`). The fix is the *matrix*, not more
  code: soften rows to their true tier. Green test gates verify code; they do not
  verify that the docs tell the truth about the code — that audit is a separate,
  deliberate step. A cheap mechanical check (`grep` every file/symbol an evidence
  cell names) catches most of it.

- **A "skipped" opt-in test masquerades as a passing one.** The first
  `pytest -m integration` run reported success but had actually *skipped*
  (a dep was missing). Always confirm the heavy test printed `passed`, not
  `skipped`, before believing a Tier-B path is verified.


- **The Phase-0 invariant is the architecture's load-bearing wall.** Everything
  imports and tests with zero ML deps because every heavy import is
  function-local and guarded (`importlib.util.find_spec`, never a top-level
  `import torch`). When adding real training, the temptation is to hoist
  `import torch` to module scope — don't. The pure helpers
  (`_whisper_train.py`) take already-imported objects or plain Python, so they
  test without torch; only `train()` does the guarded import. This is what keeps
  `pytest -q` at sub-2-seconds and CI green without a GPU.

- **WER is the honest smartness signal; the synthetic curve was a placeholder.**
  The Phase-0 simulation emitted `0.92·(1−(1−p)²)` as "smartness". The real loop
  computes `1 − WER` on a held-out split. They must never be confused — the
  simulation keeps its `[SIMULATION]` marker so a glance at any checkpoint or
  progress message tells you which world you're in.

- **Tiering beats heroics.** Trying to actually build signed installers or run a
  full GPU fine-tune in a sandbox burns the entire budget for a flaky, unfinished
  result. Writing the real code path + a documented "how to verify" + a thin
  test of the pure logic delivers more reviewable value per minute. (D-001/D-002.)

## Errors encountered & fixes

- **transformers 5.x renamed `Seq2SeqTrainer(tokenizer=…)` → `processing_class=`.**
  The first real fine-tune run died with `TypeError: __init__() got an unexpected
  keyword argument 'tokenizer'` on transformers 5.12. Fix: try
  `processing_class=processor` first, fall back to `tokenizer=…` so the same code
  works on 4.40+ and 5.x. Lesson: the HF training surface churns across majors;
  the engine wrapper isolates that churn (and is excluded from the mypy gate for
  the same reason — see `pyproject.toml`).

- **The integration test silently *skipped* the first time** because `datasets`
  was declared in the `[ml]` extra but not actually installed in the venv. A
  skipped opt-in test reads as "passed" at a glance — always confirm it actually
  *ran* (`1 passed`, not `1 skipped`) before trusting it. Installed `datasets`,
  then the real loop ran green (whisper-tiny, 1 epoch, CPU, ~10 s after download).

- **A SQLite `CHECK` constraint silently blocked a new status value.** Adding the
  `interrupted` run status (job durability #40) raised `IntegrityError: CHECK
  constraint failed` because `schema.sql` enumerated the allowed statuses.
  `CREATE TABLE IF NOT EXISTS` won't alter an existing table's constraint, so the
  change applies to fresh DBs only (fine now; a real migration is needed later).
  Lesson: enum-style CHECK constraints are hidden coupling — grep the schema
  before introducing a new enum value.

- **`ruff --fix` rewrote a readable construct into an unreadable one.** Rule
  SIM905 turned a 99-language `"""…""".split()` into a 599-char list literal.
  Restored the string with a targeted `# noqa: SIM905`. Lesson: review what
  `--fix` changed; don't trust it blindly on expressive code.

- **`pip` is absent in `backend/.venv`.** The venv was created by `uv venv`,
  which doesn't install pip. `python -m pip install …` fails with
  `No module named pip`. Fix: install into it with
  `VIRTUAL_ENV=backend/.venv uv pip install <pkg>` (this is how jiwer landed).

- **Two Python versions on PATH.** System `python3` is 3.14; the project venv is
  3.11. Always invoke tests via `backend/.venv/bin/python -m pytest` so the ML
  deps (which live in the 3.11 venv) are importable.

- **Path-traversal in uploads (security #7).** `clip_dir / audio.filename` let a
  crafted `../../…` filename escape the project dir. The original code trusted a
  client-supplied string as a path component. Fix: never use the client name for
  the path — generate `clip_<uuid>.<ext>` with an extension allow-list (D-004).
  Lesson: *any* client-supplied string that reaches a filesystem path is a trust
  boundary; sanitise at the boundary, not downstream.

## Calibration debt (carried from report B.5)

Every threshold in `director/policy.py` and `audio/quality.py` is a *proposed
default*, not empirically tuned. `CALIBRATION.md` defines the protocol to
turn these into measured values; until then they are marked as proposed in code
and here. This is tracked as ROADMAP #6 (Tier C).
</content>
