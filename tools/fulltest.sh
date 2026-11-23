#!/bin/bash
# Full check (~20 s): when tools/quicktest.sh fails, or before a merge. The six recorded viewport suites, each in
# its own session, compared with tests/reference (python3 tools/compare_suites.py); every targeted test; the
# feature tests (tools/featuretest.sh) beside them. The suites run in four lanes side by side (T49), each lane with
# its own worker on a port it picked itself, its suites one after another; Godot windows open and close as they go:
# don't use the mouse over them. Suites run at the quick test's pace (--fast, T48: same results); --full-pace runs
# them as recorded. After an intended change in behaviour, refresh the references:
#   tools/fulltest.sh --update-reference
#   --gate-ui-only is internal to gate.sh: quick already passed parsing and features.
cd "$(dirname "$0")/.."
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
START=$SECONDS
. tools/gate.sh || exit 1
set_test_tmpdir || exit 1
GD=/Applications/Godot.app/Contents/MacOS/Godot
# Only the gate uses this mode, after quicktest has parsed scripts and run feature tests.
GATE_UI_ONLY=0
for a in "$@"; do [ "$a" = "--gate-ui-only" ] && GATE_UI_ONLY=1; done
if [ $GATE_UI_ONLY -eq 0 ]; then
  run_stage "full: parse" tools/parsecheck.sh || { echo "full test not run: a viewport script doesn't parse"; exit 1; }
fi
if [ $GATE_UI_ONLY -eq 0 ]; then echo "TIMING parse: $((SECONDS - START)) s";
else echo "TIMING parse/features: reused successful quick checks"; fi
OUT=$(mktemp -d "${TEST_TMPDIR%/}/shopsketch-full.XXXXXX") || exit 1
FAST=--fast
for a in "$@"; do [ "$a" = "--full-pace" ] && FAST=""; done
RECORDED="facetest movetest mirrortest infertest holetest zfighttest"
TARGETED="undotest snaptest recttest shelltest jointest rejecttest"
# lanes balanced by time (seconds at --fast pace, 2026-11-21: undo 7, face/move/mirror/zfight 5, infer/hole 4,
# reject 3, the rest 2)
LANES=("undotest snaptest recttest" "facetest movetest shelltest" "mirrortest infertest jointest" "holetest zfighttest rejecttest")
FEATURES=""
if [ $GATE_UI_ONLY -eq 0 ]; then
  run_stage "full: feature tests" run_features "$OUT" &
  FEATURES=$!
fi
WORKERS=()
trap 'kill "${WORKERS[@]}" 2>/dev/null' EXIT
lane() {   # lane <n> <suites...>: its own worker, then each suite in turn
  local n=$1; shift
  local lane_start=$SECONDS
  SERVE_PORT=0 SERVE_PORT_FILE="$OUT/worker$n.port" "$FC" worker/replay.py > "$OUT/worker$n.log" 2>&1 &   # T47
  local w=$!
  for i in $(seq 1 300); do [ -s "$OUT/worker$n.port" ] && break; sleep 0.1; done
  local port; port=$(cat "$OUT/worker$n.port" 2>/dev/null) || { echo "lane $n: the worker didn't start" > "$OUT/lane$n.fail"; kill $w; return; }
  for suite in "$@"; do
    mkdir -p "$OUT/$suite/out" "$OUT/$suite/shots"
    local suite_start=$SECONDS
    for try in 1 2; do
      timeout 300 "$GD" --path viewport -- --$suite $FAST --out="$OUT/$suite/out" --shots="$OUT/$suite/shots" --port=$port \
        > "$OUT/$suite/godot.log" 2>&1
      local rc=$?
      # T80: Godot sometimes crashes at startup (signal 11 in macOS open-file handling) before any of our scripts
      # print. That says nothing about Shop Sketch: run the suite once more, and say so.
      if [ $rc -ge 128 ] && [ $rc -ne 143 ] && [ $try = 1 ] && \
         ! grep -qE "^(SHOT|TEST|SHOPSKETCH|SCRIPT ERROR|QUICK)|GDScript backtrace" "$OUT/$suite/godot.log"; then
        mv "$OUT/$suite/godot.log" "$OUT/$suite/godot-crash.log"
        echo "$suite: Godot crashed at startup (exit $rc) before our scripts ran; ran it again (log: $OUT/$suite/godot-crash.log)" >> "$OUT/retries"
        continue
      fi
      [ $rc = 0 ] || echo "$suite exited $rc" >> "$OUT/lane$n.fail"
      break
    done
    echo "TIMING suite $suite: $((SECONDS - suite_start)) s" >> "$OUT/timing$n.log"
  done
  echo "TIMING full lane $n: $((SECONDS - lane_start)) s" >> "$OUT/timing$n.log"
  kill $w 2>/dev/null
}
viewport_suites() {
  PIDS=()
  for i in "${!LANES[@]}"; do lane $((i + 1)) ${LANES[$i]} & PIDS+=($!); done
  wait "${PIDS[@]}"
  cat "$OUT"/timing*.log
  local failed=0
  [ -f "$OUT/retries" ] && cat "$OUT/retries"
  for f in "$OUT"/lane*.fail; do [ -f "$f" ] && { cat "$f"; failed=1; }; done
  return "$failed"
}
run_stage "full: viewport suites" viewport_suites
FAIL=$?
update_references() {
  local s
  for s in $RECORDED; do
    cp "$OUT/$s/out/bodies.json" "$OUT/$s/out/status.json" "tests/reference/$s/" || return 1
  done
  echo "references updated from $OUT"
}
if [[ " $* " == *" --update-reference "* ]]; then
  run_stage "full: update references" update_references || FAIL=1
fi
run_stage "full: compare suites" python3 tools/compare_suites.py "$OUT" || FAIL=1
for t in $TARGETED; do grep -E "TEST|SCRIPT ERROR" "$OUT/$t/godot.log" | grep -v " done$"; done
if [ -n "$FEATURES" ]; then
  wait $FEATURES || FAIL=1
  cat "$OUT/feature.log"
fi
echo "full check logs: $OUT"
exit $FAIL
