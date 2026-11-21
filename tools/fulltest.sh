#!/bin/bash
# Full check (~2 min): when tools/quicktest.sh fails, or before a merge. The six recorded viewport suites,
# each in its own session, compared with tests/reference (python3 tools/compare_suites.py); then every
# targeted test; then the worker tests. Godot windows open one after another: don't use the mouse over them.
# After an intended change in behaviour, refresh the references: tools/fulltest.sh --update-reference
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
FAIL=0
for suite in facetest movetest mirrortest infertest holetest zfighttest; do
  mkdir -p "$OUT/$suite/out" "$OUT/$suite/shots"
  timeout 300 "$GD" --path viewport -- --$suite --out="$OUT/$suite/out" --shots="$OUT/$suite/shots" --port=$PORT > "$OUT/$suite/godot.log" 2>&1 || FAIL=1
done
if [ "$1" = "--update-reference" ]; then
  for s in facetest movetest mirrortest infertest holetest zfighttest; do cp "$OUT/$s/out/bodies.json" "$OUT/$s/out/status.json" tests/reference/$s/; done
  echo "references updated from $OUT"
fi
python3 tools/compare_suites.py "$OUT" || FAIL=1
for t in undotest snaptest recttest shelltest jointest rejecttest; do
  mkdir -p "$OUT/$t/out" "$OUT/$t/shots"
  timeout 300 "$GD" --path viewport -- --$t --out="$OUT/$t/out" --shots="$OUT/$t/shots" --port=$PORT 2>&1 \
    | grep -E "TEST|SCRIPT ERROR" | grep -v " done$"
done
mkdir -p "$OUT/native" "$OUT/arrays" "$OUT/combos" "$OUT/properties"
TESTDIR="$OUT/native" "$FC" worker/test_native.py 2>&1 | grep -E "^(FAIL|NATIVE)" ; TESTDIR="$OUT/arrays" "$FC" worker/test_arrays.py 2>&1 | grep -E "^(FAIL|ARRAY)"; TESTDIR="$OUT/combos" "$FC" worker/test_combos.py 2>&1 | grep -E "^(FAIL|COMBO)"; TESTDIR="$OUT/serve" python3 worker/test_serve.py 2>&1 | grep -E "^(FAIL|SERVE)"
"$GD" --headless --path viewport --script res://test_units.gd 2>&1 | grep -E "^(FAIL|UNITS)"
"$FC" worker/test_length_input.py 2>&1 | grep -E "^LENGTH|Error"; python3 worker/test_length_protocol.py 2>&1 | grep -E "^LENGTH|Error"
TESTDIR="$OUT/properties" "$FC" worker/test_properties.py 2>&1 | grep -E "^PROPERTY|Error"
echo "full check logs: $OUT"
exit $FAIL
