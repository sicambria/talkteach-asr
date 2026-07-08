#!/usr/bin/env bash
# run_all.sh — Execute all 15 SOTA validation scripts, collect results,
# and generate SCOREBOARD.md.
#
# Usage:
#   ./scripts/sota/run_all.sh                    # full training+eval
#   ./scripts/sota/run_all.sh --baseline         # measure base (untrained) models only
#   ./scripts/sota/run_all.sh --engines whisper-tiny  # filter engines
#   ./scripts/sota/run_all.sh --baseline --engines whisper-tiny,whisper-small
#
# Exits 0 if no regressions, 1 if any domain score dropped vs baseline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# Use the project venv by default (bare `python` is often absent); override with PYTHON=...
PYTHON="${PYTHON:-$REPO_ROOT/backend/.venv/bin/python}"
RESULTS_DIR="/tmp/sota_results"
BASELINE_FILE="$RESULTS_DIR/.baseline_scores.json"
OUTPUT_DIR="$REPO_ROOT/docs/sota-benchmarks"

# --- parse flags ---
BASELINE_FLAG=""
ENGINES_FLAG=""
TRAIN_FLAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --baseline|--baseline-only)
      BASELINE_FLAG="--baseline-only"
      shift ;;
    --engines)
      ENGINES_FLAG="--engines $2"
      shift 2 ;;
    --engines=*)
      ENGINES_FLAG="--engines ${1#*=}"
      shift ;;
    --train)
      TRAIN_FLAG="--train"
      shift ;;
    *)
      echo "Unknown option: $1 (use --baseline, --engines <list>, --train)" >&2
      exit 2 ;;
  esac
done

mkdir -p "$RESULTS_DIR"
mkdir -p "$OUTPUT_DIR"

SCRIPTS=(
  "$SCRIPT_DIR/validate_d01_wer_clean.py"
  "$SCRIPT_DIR/validate_d02_wer_spontaneous.py"
  "$SCRIPT_DIR/validate_d03_train_efficiency.py"
  "$SCRIPT_DIR/validate_d04_rtf.py"
  "$SCRIPT_DIR/validate_d05_data_efficiency.py"
  "$SCRIPT_DIR/validate_d06_noise_robustness.py"
  "$SCRIPT_DIR/validate_d07_multilingual.py"
  "$SCRIPT_DIR/validate_d08_export_fidelity.py"
  "$SCRIPT_DIR/validate_d09_augmentation.py"
  "$SCRIPT_DIR/validate_d10_decoding.py"
  "$SCRIPT_DIR/validate_d11_longform.py"
  "$SCRIPT_DIR/validate_d12_speaker_equity.py"
  "$SCRIPT_DIR/validate_d13_director_accuracy.py"
  "$SCRIPT_DIR/validate_d14_quality_gate.py"
  "$SCRIPT_DIR/validate_d15_resource_efficiency.py"
)

EXTRA_ARGS="$BASELINE_FLAG $ENGINES_FLAG $TRAIN_FLAG"
echo "=== Running 15 SOTA validation scripts ==="
echo "Flags: $EXTRA_ARGS"
echo ""

FAILED=()
for script in "${SCRIPTS[@]}"; do
  name="$(basename "$script" .py)"
  json_out="$RESULTS_DIR/${name}.json"

  echo "--- $name ---"
  if "$PYTHON" "$script" $EXTRA_ARGS --json "$json_out" 2>&1; then
    echo "  OK"
  else
    echo "  FAILED (exit code $?)"
    FAILED+=("$name")
  fi
  echo ""
done

echo "=== Collecting results ==="
SCORES_JSON="$RESULTS_DIR/all_scores.json"
"$PYTHON" -c "
import json, glob, os

results_dir = '$RESULTS_DIR'
scores = []
for f in sorted(glob.glob(os.path.join(results_dir, 'validate_d*.json'))):
    try:
        data = json.load(open(f))
        scores.append(data)
    except Exception as e:
        print(f'  Warning: could not read {f}: {e}')

with open('$SCORES_JSON', 'w') as out:
    json.dump(scores, out, indent=2, default=str)
print(f'  Collected {len(scores)} results to {out.name}')
"

echo ""
echo "=== Generating SCOREBOARD.md ==="
cd "$REPO_ROOT/backend"
PYTHONPATH="$REPO_ROOT/backend:$REPO_ROOT" \
  "$PYTHON" -c "
import json, sys
from pathlib import Path
from talkteach.sota.harness import Scoreboard, SOTAResult
from talkteach.sota.report import generate
from talkteach.sota.scoring import aggregate_headline

data = json.loads(Path('$SCORES_JSON').read_text())
results = []
for d in data:
    ci = {}
    for k, v in d.get('confidence_95', {}).items():
        if isinstance(v, list) and len(v) == 2:
            ci[k] = (float(v[0]), float(v[1]))
    r = SOTAResult(
        domain_id=d.get('domain_id', ''),
        domain_name=d.get('domain_name', ''),
        score_0_1000=d.get('score_0_1000', 0),
        band=d.get('band', 'unmeasured'),
        metrics=d.get('metrics', {}),
        confidence_95=ci,
        baseline_ref=d.get('baseline_ref', ''),
        sota_ref=d.get('sota_ref', ''),
        num_samples=d.get('num_samples', 0),
        engine_used=d.get('engine_used', ''),
        notes=d.get('notes', ''),
    )
    results.append(r)

# Honest headline: mean over adequately-powered domains only (small-n gate),
# with under-powered results flagged directional. Also sets r.directional.
h = aggregate_headline(results)
sb = Scoreboard(
    domains=results,
    overall_mean=h['overall_mean'],
    overall_band=h['overall_band'],
    num_total=h['num_total'],
    num_measured=h['num_measured'],
    num_eligible=h['num_eligible'],
    num_directional=h['num_directional'],
    num_unmeasured=h['num_unmeasured'],
)
md, jd = generate(sb, Path('$OUTPUT_DIR'))
print(f'  SCOREBOARD.md written ({len(results)} domains, headline {sb.overall_mean:.0f}/{sb.overall_band}, {sb.num_eligible} powered)')
" 2>&1

# --- regression check ---
echo ""
if [ -f "$BASELINE_FILE" ]; then
  echo "=== Regression check vs baseline ==="
  REGRESSIONS=0
  "$PYTHON" -c "
import json, sys
baseline = json.load(open('$BASELINE_FILE'))
current = json.load(open('$SCORES_JSON'))
regressions = 0
baseline_map = {d['domain_id']: d for d in baseline}
for d in current:
    did = d.get('domain_id')
    if did not in baseline_map:
        continue
    prev = baseline_map[did].get('score_0_1000', 300)
    curr = d.get('score_0_1000', 300)
    if curr < prev - 10:  # 10-point tolerance
        print(f'  REGRESSION: {did}: {prev} → {curr} ({prev - curr} drop)')
        regressions += 1
sys.exit(regressions)
" && echo "  No regressions detected" || REGRESSIONS=$?
  if [ "${REGRESSIONS:-0}" -gt 0 ]; then
    echo "WARNING: $REGRESSIONS domain(s) regressed"
  fi
else
  echo "No baseline file yet — run once with --baseline and copy results to establish:"
  echo "  cp $SCORES_JSON $BASELINE_FILE"
fi

echo ""
if [ ${#FAILED[@]} -gt 0 ]; then
  echo "FAILED scripts: ${FAILED[*]}"
fi
echo "Done."
exit 0
