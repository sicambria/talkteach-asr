#!/usr/bin/env bash
#
# Fully-automatic TTS × ASR benchmark report.
#
# Generates synthetic speech (espeak + piper), fine-tunes each ASR engine, scores
# them on a shared held-out eval set, prints the ELO scoreboard, and RECORDS the
# Markdown report to benchmarks/REPORT.md (committable) + raw JSON under the workdir.
#
# Usage:
#   bash scripts/full_report.sh                      # uses benchmarks/quick.yaml
#   bash scripts/full_report.sh benchmarks/full.yaml # bigger matrix (incl. GPU NeMo)
#
# Needs the full stack:  make setup-ml   (or ./setup.sh --with-ml)
#   + the espeak-ng system binary for espeak cells (./setup.sh installs it).
#
# All generated audio/models go under a temp workdir (printed at the end) so the
# repo and your home dir stay clean; delete it to reclaim disk.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PY="backend/.venv/bin/python"
CONFIG="${1:-benchmarks/quick.yaml}"
WORKDIR="${TALKTEACH_BENCH_WORKDIR:-$(mktemp -d -t talkteach-bench-XXXXXX)}"
REPORT="${TALKTEACH_BENCH_REPORT:-$REPO_ROOT/benchmarks/REPORT.md}"

# Quiet, reproducible, and keep all generated data under the workdir (not $HOME).
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TRANSFORMERS_VERBOSITY=error
export TOKENIZERS_PARALLELISM=false
export TALKTEACH_DATA="$WORKDIR/data"

if [ ! -x "$PY" ]; then
  echo "No backend venv at $PY." >&2
  echo "Install the full stack first:  make setup-ml   (or ./setup.sh --with-ml)" >&2
  exit 1
fi

echo "==> Config:  $CONFIG"
echo "==> Workdir: $WORKDIR"
echo

"$PY" scripts/benchmark.py --config "$CONFIG" --workdir "$WORKDIR" --report "$REPORT"

echo
echo "==> Recorded report: $REPORT"
echo "==> Raw artifacts:   $WORKDIR   (delete to reclaim disk)"
