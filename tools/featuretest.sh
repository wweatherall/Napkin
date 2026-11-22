#!/bin/bash
# Feature tests (~10 s): everything that checks Shop Sketch's answers against FreeCAD, with no window: the worker
# tests (native, runs, arrays, combos, properties, length input, the T48 scenario), the serve and length-protocol tests
# (plain python3, they start freecadcmd themselves), the units parser, the document controller's
# sequencing (test_document.gd), selection and context (test_selection.gd) and the decision log's sort script. Run them
# while building a feature, before its tool exists; tools/quicktest.sh runs them too, beside the viewport session.
#   tools/featuretest.sh [outdir]      exit status 0 = all passed; prints one summary line
cd "$(dirname "$0")/.."
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
GD=/Applications/Godot.app/Contents/MacOS/Godot
OUT=${1:-$(mktemp -d -t shopsketch-feature)}
mkdir -p "$OUT"
# name | command | summary line it prints
TESTS=(
  "native|$FC worker/test_native.py|NATIVE TESTS"
  "runs|$FC worker/test_runs.py|RUN TESTS"
  "arrays|$FC worker/test_arrays.py|ARRAY TESTS"
  "combos|$FC worker/test_combos.py|COMBO TESTS"
  "properties|$FC worker/test_properties.py|PROPERTY TESTS"
  "scenario|$FC worker/test_scenario.py|SCENARIO TESTS"
  "length|$FC worker/test_length_input.py|LENGTH TESTS"
  "lengthproto|python3 worker/test_length_protocol.py|LENGTH PROTOCOL"
  "serve|python3 worker/test_serve.py|SERVE TESTS"
  "units|$GD --headless --path viewport --script res://test_units.gd|UNITS TESTS"
  "document|$GD --headless --path viewport --script res://test_document.gd|DOCUMENT TESTS"
  "selection|$GD --headless --path viewport --script res://test_selection.gd|SELECTION TESTS"
  "logsort|python3 tools/test_sort_decision_log.py|LOG SORT TESTS"
  "ids|python3 tools/test_number_ids.py|ID TESTS"
  "startup|python3 tools/test_startup.py|STARTUP TESTS"
  "lock|python3 tools/test_integrator.py|LOCK TESTS"
)
PIDS=()
for t in "${TESTS[@]}"; do
  IFS='|' read -r name cmd _ <<< "$t"
  mkdir -p "$OUT/$name"
  ( TESTDIR="$OUT/$name" $cmd > "$OUT/$name.log" 2>&1 ) &
  PIDS+=($!)
done
wait "${PIDS[@]}"
OK=1; LINE=""
for t in "${TESTS[@]}"; do
  IFS='|' read -r name _ tag <<< "$t"
  grep -E "^FAIL" "$OUT/$name.log" | sed "s/^/[$name] /"
  s=$(grep -E "^$tag" "$OUT/$name.log" | head -1)
  LINE="$LINE${s:-$name did not finish} | "
  echo "$s" | grep -q " 0 failed" || OK=0
done
echo "features: ${LINE% | }  (logs: $OUT)"
[ $OK = 1 ]
