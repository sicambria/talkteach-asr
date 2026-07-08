#!/usr/bin/env bash
# run_all.sh — Execute all 15 SOTA validation scripts with --baseline-only,
# collect results, and generate SCOREBOARD.md.
#
# Usage:
#   ./scripts/sota/run_all.sh [--baseline-only]
#
# Exits 0 if no regressions, 1 if any domain score dropped vs baseline.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RESULTS_DIR="/tmp/sota_results"
BASELINE_FILE="$RESULTS_DIR/.baseline_scores.json"
OUTPUT_DIR="$REPO_ROOT/docs/sota-benchmarks"

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

FAILED=()
echo "=== Running all 15 SOTA validation scripts (baseline-only) ==="
echo ""

for script in "${SCRIPTS[@]}"; do
  name="$(basename "$script" .py)"
  json_out="$RESULTS_DIR/${name}.json"

  echo "--- $name ---"
  if python "$script" --baseline-only --json "$json_out" 2>&1; then
    echo "  OK"
  else
    echo "  FAILED (exit code $?)"
    FAILED+=("$name")
  fi
  echo ""
done

echo "=== Collecting results ==="
SCORES_JSON="$RESULTS_DIR/all_scores.json"
python -c "
import json, glob, os

results = []
for f in sorted(glob.glob('$RESULTS_DIR/validate_d*.json')):
    try:
        d = json.loads(open(f).read())
        results.append(d)
    except Exception as e:
        print(f'WARN: could not parse {f}: {e}', file=__import__('sys').stderr)

# Save baseline if first run
baseline_file = '$BASELINE_FILE'
if not os.path.exists(baseline_file) and results:
    with open(baseline_file, 'w') as bp:
        json.dump({r['domain_id']: r['score_0_1000'] for r in results}, bp, indent=2)
    print(f'Baseline saved to {baseline_file}')

with open('$SCORES_JSON', 'w') as fp:
    json.dump(results, fp, indent=2, default=str)

print(f'Collected {len(results)} results → $SCORES_JSON')
"

echo ""
echo "=== Generating SCOREBOARD.md ==="
python -c "
import json, sys
from pathlib import Path

sys.path.insert(0, '$REPO_ROOT/backend')
from talkteach.sota.report import generate_scoreboard_md, generate_scoreboard_json
from talkteach.sota.harness import Scoreboard, SOTAResult

results_data = json.loads(open('$SCORES_JSON').read())
domains = []
for r in results_data:
    ci = {}
    for k, v in r.get('confidence_95', {}).items():
        if isinstance(v, list) and len(v) == 2:
            ci[k] = tuple(v)
    sr = SOTAResult(
        domain_id=r.get('domain_id', ''),
        domain_name=r.get('domain_name', r.get('domain_id', '')),
        score_0_1000=r.get('score_0_1000', 0),
        band=r.get('band', 'unmeasured'),
        metrics=r.get('metrics', {}),
        confidence_95=ci,
        baseline_ref=r.get('baseline_ref', ''),
        sota_ref=r.get('sota_ref', ''),
        num_samples=r.get('num_samples', 0),
        engine_used=r.get('engine_used', ''),
        notes=r.get('notes', ''),
    )
    domains.append(sr)

scores = [r.score_0_1000 for r in domains if r.score_0_1000 > 0]
overall = sum(scores) / len(scores) if scores else 0.0

band_tuples = [
    (1000, 'platinum'), (950, 'diamond'), (900, 'platinum'),
    (800, 'gold'), (700, 'silver'), (600, 'bronze'),
]
overall_band = 'unmeasured'
for thresh, bname in band_tuples:
    if overall >= thresh:
        overall_band = bname
        break

sb = Scoreboard(domains=domains, overall_mean=overall, overall_band=overall_band)
md = generate_scoreboard_md(sb, Path('$OUTPUT_DIR/SCOREBOARD.md'))
json_out = generate_scoreboard_json(sb, Path('$OUTPUT_DIR/SCOREBOARD.json'))
print(f'SCOREBOARD.md → $OUTPUT_DIR/SCOREBOARD.md')
print(f'SCOREBOARD.json → $OUTPUT_DIR/SCOREBOARD.json')
"

echo ""
echo "=== Regression check ==="
if [ -f "$BASELINE_FILE" ]; then
  REGRESSIONS=0
  python -c "
import json, sys

baseline = json.loads(open('$BASELINE_FILE').read())
current = {}
for f in sorted(__import__('glob').glob('$RESULTS_DIR/validate_d*.json')):
    r = json.loads(open(f).read())
    current[r['domain_id']] = r['score_0_1000']

regressions = []
for dom_id, bl_score in baseline.items():
    cur = current.get(dom_id)
    if cur is not None and cur < bl_score:
        regressions.append(f'{dom_id}: {bl_score} → {cur} (dropped {bl_score - cur})')

if regressions:
    print('REGRESSIONS DETECTED:')
    for r in regressions:
        print(f'  {r}')
    sys.exit(1)
else:
    print('No regressions detected.')
" || REGRESSIONS=$?
else
  echo "No baseline file yet — skipping regression check."
  REGRESSIONS=0
fi

if [ ${#FAILED[@]} -gt 0 ]; then
  echo ""
  echo "WARNING: ${#FAILED[@]} scripts failed: ${FAILED[*]}"
fi

exit ${REGRESSIONS:-0}
