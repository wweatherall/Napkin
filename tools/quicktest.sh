#!/bin/bash
# Quick check, after every change (~20 s): the worker tests (native, arrays, combos, serve, length input, properties), the units parser (viewport/test_units.gd), and every viewport feature once in a single
# session (--quicktest; it starts its own worker, so it never touches a running Shop Sketch). Each step checks
# its own answer. If anything fails, run tools/fulltest.sh. Exit status 0 = all passed.
cd "$(dirname "$0")/.."
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
GD=/Applications/Godot.app/Contents/MacOS/Godot
tools/parsecheck.sh || { echo "quick test not run: a viewport script doesn't parse"; exit 1; }
OUT=$(mktemp -d -t shopsketch-quick)
mkdir -p "$OUT/native" "$OUT/arrays" "$OUT/combos" "$OUT/properties" "$OUT/vp/out" "$OUT/vp/shots"
( TESTDIR="$OUT/native" "$FC" worker/test_native.py > "$OUT/native.log" 2>&1
  TESTDIR="$OUT/arrays" "$FC" worker/test_arrays.py > "$OUT/arrays.log" 2>&1
  TESTDIR="$OUT/combos" "$FC" worker/test_combos.py > "$OUT/combos.log" 2>&1
  "$FC" worker/test_length_input.py > "$OUT/length.log" 2>&1
  TESTDIR="$OUT/properties" "$FC" worker/test_properties.py > "$OUT/properties.log" 2>&1
  python3 worker/test_length_protocol.py >> "$OUT/length.log" 2>&1
  TESTDIR="$OUT/serve" python3 worker/test_serve.py > "$OUT/serve.log" 2>&1
  "$GD" --headless --path viewport --script res://test_units.gd > "$OUT/units.log" 2>&1 ) &
WORKER_TESTS=$!
"$GD" --path viewport -- --quicktest --out="$OUT/vp/out" --shots="$OUT/vp/shots" --worker-log="$OUT/vp/worker.log" \
  > "$OUT/viewport.log" 2>&1 &
GDPID=$!
( sleep 120; kill $GDPID 2>/dev/null && echo "QUICK FAIL the viewport run took over 120 s: stopped it" >> "$OUT/viewport.log" ) &
WATCH=$!
wait $GDPID; VP=$?
kill $WATCH 2>/dev/null; wait $WATCH 2>/dev/null
wait $WORKER_TESTS
grep -E "^FAIL" "$OUT/native.log" "$OUT/arrays.log" "$OUT/combos.log" "$OUT/serve.log" "$OUT/units.log" "$OUT/length.log" "$OUT/properties.log"
grep -E "QUICK FAIL|SCRIPT ERROR" "$OUT/viewport.log"
N=$(grep -E "^NATIVE TESTS" "$OUT/native.log"); A=$(grep -E "^ARRAY TESTS" "$OUT/arrays.log"); C=$(grep -E "^COMBO TESTS" "$OUT/combos.log"); W=$(grep -E "^SERVE TESTS" "$OUT/serve.log"); U=$(grep -E "^UNITS TESTS" "$OUT/units.log"); L=$(grep -E "^LENGTH TESTS" "$OUT/length.log"); LP=$(grep -E "^LENGTH PROTOCOL" "$OUT/length.log"); P=$(grep -E "^PROPERTY TESTS" "$OUT/properties.log"); Q=$(grep -E "^QUICK [0-9]" "$OUT/viewport.log")
echo "worker: ${N:-did not finish} | ${A:-did not finish} | ${C:-combos did not finish} | ${W:-serve did not finish} | ${U:-units did not finish} | ${L:-length did not finish} | ${LP:-length protocol did not finish} | ${P:-properties did not finish} | viewport: ${Q:-did not finish}  (logs: $OUT)"
if [ $VP -eq 0 ] && echo "$N" | grep -q " 0 failed" && echo "$A" | grep -q " 0 failed" && echo "$C" | grep -q " 0 failed" && echo "$W" | grep -q " 0 failed" && echo "$U" | grep -q " 0 failed" && echo "$L" | grep -q " 0 failed" && echo "$LP" | grep -q " 0 failed" && echo "$P" | grep -q " 0 failed"; then exit 0; fi
exit 1
