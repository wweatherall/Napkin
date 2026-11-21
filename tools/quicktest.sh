#!/bin/bash
# Quick check, after every change (~20 s): the worker tests, and every viewport feature once in a single
# session (--quicktest; it starts its own worker, so it never touches a running Shop Sketch). Each step checks
# its own answer. If anything fails, run tools/fulltest.sh. Exit status 0 = all passed.
cd "$(dirname "$0")/.."
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
GD=/Applications/Godot.app/Contents/MacOS/Godot
tools/parsecheck.sh || { echo "quick test not run: a viewport script doesn't parse"; exit 1; }
OUT=$(mktemp -d -t shopsketch-quick)
mkdir -p "$OUT/native" "$OUT/arrays" "$OUT/vp/out" "$OUT/vp/shots"
( TESTDIR="$OUT/native" "$FC" worker/test_native.py > "$OUT/native.log" 2>&1
  TESTDIR="$OUT/arrays" "$FC" worker/test_arrays.py > "$OUT/arrays.log" 2>&1
  TESTDIR="$OUT/serve" python3 worker/test_serve.py > "$OUT/serve.log" 2>&1 ) &
WORKER_TESTS=$!
"$GD" --path viewport -- --quicktest --out="$OUT/vp/out" --shots="$OUT/vp/shots" --worker-log="$OUT/vp/worker.log" \
  > "$OUT/viewport.log" 2>&1 &
GDPID=$!
( sleep 120; kill $GDPID 2>/dev/null && echo "QUICK FAIL the viewport run took over 120 s: stopped it" >> "$OUT/viewport.log" ) &
WATCH=$!
wait $GDPID; VP=$?
kill $WATCH 2>/dev/null; wait $WATCH 2>/dev/null
wait $WORKER_TESTS
grep -E "^FAIL" "$OUT/native.log" "$OUT/arrays.log" "$OUT/serve.log"
grep -E "QUICK FAIL|SCRIPT ERROR" "$OUT/viewport.log"
N=$(grep -E "^NATIVE TESTS" "$OUT/native.log"); A=$(grep -E "^ARRAY TESTS" "$OUT/arrays.log"); W=$(grep -E "^SERVE TESTS" "$OUT/serve.log"); Q=$(grep -E "^QUICK [0-9]" "$OUT/viewport.log")
echo "worker: ${N:-did not finish} | ${A:-did not finish} | ${W:-serve did not finish} | viewport: ${Q:-did not finish}  (logs: $OUT)"
if [ $VP -eq 0 ] && echo "$N" | grep -q " 0 failed" && echo "$A" | grep -q " 0 failed" && echo "$W" | grep -q " 0 failed"; then exit 0; fi
exit 1
