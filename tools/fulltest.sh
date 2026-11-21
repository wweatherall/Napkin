#!/bin/bash
# Full check (~20 s): when tools/quicktest.sh fails, or before a merge. The six recorded viewport suites, each in
# its own session, compared with tests/reference (python3 tools/compare_suites.py); every targeted test; the
# feature tests (tools/featuretest.sh) beside them. The suites run in four lanes side by side (T49), each lane with
# its own worker on a port it picked itself, its suites one after another; Godot windows open and close as they go:
# don't use the mouse over them. Suites run at the quick test's pace (--fast, T48: same results); --full-pace runs
# them as recorded. After an intended change in behaviour, refresh the references:
#   tools/fulltest.sh --update-reference
cd "$(dirname "$0")/.."
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
GD=/Applications/Godot.app/Contents/MacOS/Godot
tools/parsecheck.sh || { echo "full test not run: a viewport script doesn't parse"; exit 1; }
OUT=$(mktemp -d -t shopsketch-full)
FAST=--fast
for a in "$@"; do [ "$a" = "--full-pace" ] && FAST=""; done
RECORDED="facetest movetest mirrortest infertest holetest zfighttest"
TARGETED="undotest snaptest recttest shelltest jointest rejecttest"
# lanes balanced by time (seconds at --fast pace, 2026-11-21: undo 7, face/move/mirror/zfight 5, infer/hole 4,
# reject 3, the rest 2)
LANES=("undotest snaptest recttest" "facetest movetest shelltest" "mirrortest infertest jointest" "holetest zfighttest rejecttest")
tools/featuretest.sh "$OUT/feature" > "$OUT/feature.log" 2>&1 &
FEATURES=$!
WORKERS=()
trap 'kill "${WORKERS[@]}" 2>/dev/null' EXIT
lane() {   # lane <n> <suites...>: its own worker, then each suite in turn
  local n=$1; shift
  SERVE_PORT=0 SERVE_PORT_FILE="$OUT/worker$n.port" "$FC" worker/replay.py > "$OUT/worker$n.log" 2>&1 &   # T47
  local w=$!
  for i in $(seq 1 300); do [ -s "$OUT/worker$n.port" ] && break; sleep 0.1; done
  local port; port=$(cat "$OUT/worker$n.port" 2>/dev/null) || { echo "lane $n: the worker didn't start" > "$OUT/lane$n.fail"; kill $w; return; }
  for suite in "$@"; do
    mkdir -p "$OUT/$suite/out" "$OUT/$suite/shots"
    timeout 300 "$GD" --path viewport -- --$suite $FAST --out="$OUT/$suite/out" --shots="$OUT/$suite/shots" --port=$port \
      > "$OUT/$suite/godot.log" 2>&1 || echo "$suite exited $?" >> "$OUT/lane$n.fail"
  done
  kill $w 2>/dev/null
}
PIDS=()
for i in "${!LANES[@]}"; do lane $((i + 1)) ${LANES[$i]} & PIDS+=($!); done
wait "${PIDS[@]}"
FAIL=0
for f in "$OUT"/lane*.fail; do [ -f "$f" ] && { cat "$f"; FAIL=1; }; done
if [[ " $* " == *" --update-reference "* ]]; then
  for s in $RECORDED; do cp "$OUT/$s/out/bodies.json" "$OUT/$s/out/status.json" tests/reference/$s/; done
  echo "references updated from $OUT"
fi
python3 tools/compare_suites.py "$OUT" || FAIL=1
for t in $TARGETED; do grep -E "TEST|SCRIPT ERROR" "$OUT/$t/godot.log" | grep -v " done$"; done
wait $FEATURES || FAIL=1
cat "$OUT/feature.log"
echo "full check logs: $OUT"
exit $FAIL
