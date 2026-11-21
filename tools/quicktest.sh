#!/bin/bash
# Quick check, after every change (~20 s): the feature tests (tools/featuretest.sh: every FreeCAD-side test and the
# units parser, no window) beside the UI test, every viewport feature once in a single session (--quicktest; it
# starts its own worker, so it never touches a running Shop Sketch). Each step checks its own answer.
# If anything fails, run tools/fulltest.sh. Exit status 0 = all passed.
cd "$(dirname "$0")/.."
GD=/Applications/Godot.app/Contents/MacOS/Godot
tools/parsecheck.sh || { echo "quick test not run: a viewport script doesn't parse"; exit 1; }
OUT=$(mktemp -d -t shopsketch-quick)
mkdir -p "$OUT/vp/out" "$OUT/vp/shots"
tools/featuretest.sh "$OUT/feature" > "$OUT/feature.log" 2>&1 &
FEATURES=$!
"$GD" --path viewport -- --quicktest --out="$OUT/vp/out" --shots="$OUT/vp/shots" --worker-log="$OUT/vp/worker.log" \
  > "$OUT/viewport.log" 2>&1 &
GDPID=$!
( sleep 120; kill $GDPID 2>/dev/null && echo "QUICK FAIL the viewport run took over 120 s: stopped it" >> "$OUT/viewport.log" ) &
WATCH=$!
wait $GDPID; VP=$?
kill $WATCH 2>/dev/null; wait $WATCH 2>/dev/null
wait $FEATURES; FT=$?
grep -E "QUICK FAIL|SCRIPT ERROR" "$OUT/viewport.log"
grep -vE "^features:" "$OUT/feature.log"
Q=$(grep -E "^QUICK [0-9]" "$OUT/viewport.log")
echo "$(grep -E "^features:" "$OUT/feature.log" | sed 's/  (logs:.*//') | viewport: ${Q:-did not finish}  (logs: $OUT)"
[ $VP -eq 0 ] && [ $FT -eq 0 ]
