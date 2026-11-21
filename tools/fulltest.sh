#!/bin/bash
# Full check (~45 s): when tools/quicktest.sh fails, or before a merge. The six recorded viewport suites,
# each in its own session, compared with tests/reference (python3 tools/compare_suites.py); then every
# targeted test; the feature tests (tools/featuretest.sh) run beside them. Godot windows open one after another:
# don't use the mouse over them. Suites run at the quick test's pace (--fast, T48: same results, ~2.5x faster);
# --full-pace runs them as recorded. After an intended change in behaviour, refresh the references:
# tools/fulltest.sh --update-reference
cd "$(dirname "$0")/.."
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
GD=/Applications/Godot.app/Contents/MacOS/Godot
tools/parsecheck.sh || { echo "full test not run: a viewport script doesn't parse"; exit 1; }
OUT=$(mktemp -d -t shopsketch-full)
PORT=7890
while lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; do PORT=$((PORT + 1)); done
SERVE_PORT=$PORT "$FC" worker/replay.py > "$OUT/worker.log" 2>&1 &
W=$!
trap 'kill $W 2>/dev/null' EXIT
for i in $(seq 1 60); do grep -q "WORKER listening on 127.0.0.1:$PORT" "$OUT/worker.log" 2>/dev/null && break; sleep 0.5; done
FAST=--fast
for a in "$@"; do [ "$a" = "--full-pace" ] && FAST=""; done
tools/featuretest.sh "$OUT/feature" > "$OUT/feature.log" 2>&1 &
FEATURES=$!
FAIL=0
for suite in facetest movetest mirrortest infertest holetest zfighttest; do
  mkdir -p "$OUT/$suite/out" "$OUT/$suite/shots"
  timeout 300 "$GD" --path viewport -- --$suite $FAST --out="$OUT/$suite/out" --shots="$OUT/$suite/shots" --port=$PORT > "$OUT/$suite/godot.log" 2>&1 || FAIL=1
done
if [[ " $* " == *" --update-reference "* ]]; then
  for s in facetest movetest mirrortest infertest holetest zfighttest; do cp "$OUT/$s/out/bodies.json" "$OUT/$s/out/status.json" tests/reference/$s/; done
  echo "references updated from $OUT"
fi
python3 tools/compare_suites.py "$OUT" || FAIL=1
for t in undotest snaptest recttest shelltest jointest rejecttest; do
  mkdir -p "$OUT/$t/out" "$OUT/$t/shots"
  timeout 300 "$GD" --path viewport -- --$t $FAST --out="$OUT/$t/out" --shots="$OUT/$t/shots" --port=$PORT 2>&1 \
    | grep -E "TEST|SCRIPT ERROR" | grep -v " done$"
done
wait $FEATURES || FAIL=1
cat "$OUT/feature.log"
echo "full check logs: $OUT"
exit $FAIL
