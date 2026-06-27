<!--
Title must be a valid Conventional Commit subject, e.g.:
  feat: spawn the Python backend as a Tauri sidecar
  fix: contain path traversal in clip uploads
Types: feat | fix | docs | test | chore | refactor | perf | build | ci
-->

## What & why

<!-- What does this change, and *why*? The "why" is the house style — explain the
reasoning, not just the diff. Link the issue/roadmap item if there is one. -->

Closes #

## Tier (see DECISIONS.md D-001)

- [ ] **A** — done & verified here (real code + passing tests)
- [ ] **B** — coded & guarded; full run needs network/GPU/root (behind a marker;
      "how to verify" documented)
- [ ] **C** — design + scaffolding

## Checklist

- [ ] `make check` is green (ruff + format-check + mypy + pytest); `make ui-check` too if this touches the UI
- [ ] Added/updated **tests** for the behaviour I changed
- [ ] Updated **`CHANGELOG.md`** under `[Unreleased]`
- [ ] Updated **`docs/ROADMAP_STATUS.md`** if a roadmap item changed tier/status
- [ ] Recorded any non-obvious choice in **`DECISIONS.md`** (top-5, scored 0–100)
- [ ] PR **title** is a valid conventional-commit subject
- [ ] Kept the promises: **offline-first**, **no GPU required** for the pure
      core, **children's recordings stay on device** (no telemetry without opt-in)

## Heavy paths (if applicable)

<!-- If this touches an [ml] / ffmpeg / GPU / Tauri-compile path, note how you
verified it and the exact command, e.g.:
  TALKTEACH_RUN_INTEGRATION=1 backend/.venv/bin/python -m pytest -m integration
-->
