# TalkTeach developer task runner.
#
# Thin wrapper over the real commands so contributors (and CI) have one obvious
# entry point. Uses the project venv directly (created by `uv venv`); see
# CONTRIBUTING.md. `make check` is the gate a PR must pass.

PY := backend/.venv/bin/python
RUFF := backend/.venv/bin/ruff
MYPY := backend/.venv/bin/mypy

.PHONY: help setup setup-ml test lint format check ui-check rust-check integration benchmark report all

help:  ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup:  ## Create the backend venv and install dev + light deps.
	uv venv backend/.venv
	VIRTUAL_ENV=backend/.venv uv pip install -e 'backend[dev]'

setup-ml:  ## Install the full benchmark stack ([ml,export,tts,dev]); needs espeak-ng for espeak cells.
	uv venv backend/.venv
	VIRTUAL_ENV=backend/.venv uv pip install -e 'backend[ml,export,tts,dev]'

test:  ## Run the fast Python test suite (no ML deps / GPU / network needed).
	cd backend && .venv/bin/python -m pytest -q

integration:  ## Run the opt-in heavy paths (needs [ml] + network/GPU).
	cd backend && TALKTEACH_RUN_INTEGRATION=1 .venv/bin/python -m pytest -m integration

benchmark:  ## Run the TTS×ASR benchmark + print the ELO scoreboard (needs setup-ml).
	backend/.venv/bin/python scripts/benchmark.py --config benchmarks/quick.yaml

report:  ## Run the full benchmark fully automatically and RECORD benchmarks/REPORT.md.
	bash scripts/full_report.sh

lint:  ## Lint Python (ruff) without modifying files.
	$(RUFF) check backend/talkteach backend/tests
	$(RUFF) format --check backend/talkteach backend/tests
	$(MYPY) --config-file backend/pyproject.toml backend/talkteach

format:  ## Auto-format Python (ruff).
	$(RUFF) check --fix backend/talkteach backend/tests
	$(RUFF) format backend/talkteach backend/tests

ui-check:  ## Build + type-check + format-check the Svelte UI.
	cd ui && npm run build && npm run check && npm run format:check

rust-check:  ## Format-check + clippy + check the Tauri shell (needs Rust toolchain).
	cd src-tauri && cargo fmt --check && cargo clippy -- -D warnings && cargo check

check: lint test  ## The PR gate: lint + type + fast tests.

all: check ui-check  ## Everything that can run without a GPU.
