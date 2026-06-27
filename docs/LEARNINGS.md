# Learnings, errors & insights

A running log of things that went wrong, surprised us, or are worth remembering —
the institutional memory the design report (Part C) said the *real* risk lives in.
Newest entries at the top of each section.

## Insights

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
default*, not empirically tuned. `docs/CALIBRATION.md` defines the protocol to
turn these into measured values; until then they are marked as proposed in code
and here. This is tracked as ROADMAP #6 (Tier C).
</content>
