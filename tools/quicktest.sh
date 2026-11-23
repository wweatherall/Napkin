#!/bin/bash
# Quick check, after every change (~12 s): the feature tests (tools/featuretest.sh: every test_* file in worker/, tools/ and
# viewport/, no window) beside the UI test, every viewport feature once (--quicktest). The UI test runs in
# LANES windows side by side (T49), each with its own worker and a share of the sections (viewport/tests/quick_runner.gd QUICK_LANES),
# so it never touches a running Shop Sketch. Each step checks its own answer.
#   tools/quicktest.sh            the lanes side by side
#   tools/quicktest.sh --one      every section in one window, one after another (as before T49)
# If anything fails, run tools/fulltest.sh. Exit status 0 = all passed.
cd "$(dirname "$0")/.."
# Only exit on the guard's refusal; an unavailable helper must not block tests.
python3 tools/job.py guard-checkout
[ $? -eq 1 ] && exit 1
START=$SECONDS
GD=/Applications/Godot.app/Contents/MacOS/Godot
LANES=3
[ "$1" = "--one" ] && LANES=0
tools/parsecheck.sh || { echo "quick test not run: a viewport script doesn't parse"; exit 1; }
echo "TIMING parse: $((SECONDS - START)) s"
OUT=$(mktemp -d -t shopsketch-quick)
tools/featuretest.sh "$OUT/feature" > "$OUT/feature.log" 2>&1 &
FEATURES=$!
PIDS=()
if [ $LANES -eq 0 ]; then RUNS=(""); else RUNS=(); for i in $(seq 1 $LANES); do RUNS+=("--quick-lane=$i"); done; fi
for i in "${!RUNS[@]}"; do
  D="$OUT/vp$((i + 1))"; mkdir -p "$D/out" "$D/shots"
  "$GD" --path viewport -- --quicktest ${RUNS[$i]} --out="$D/out" --shots="$D/shots" --worker-log="$D/worker.log" \
    > "$D.log" 2>&1 &
  PIDS+=($!)
done
# The watchdog's sleep is its own process: stop it with the watchdog, and give neither our stdout, or a captured
# run ($(tools/quicktest.sh), the gate) would wait out the 120 s after the result (T86).
( sleep 120 & SLEEP=$!; trap 'kill $SLEEP 2>/dev/null; exit 0' TERM; wait $SLEEP
  for p in "${PIDS[@]}"; do kill $p 2>/dev/null && echo "QUICK FAIL the viewport run took over 120 s: stopped it" >> "$OUT/stopped.log"; done
) > /dev/null 2>&1 &
WATCH=$!
VP=0
for p in "${PIDS[@]}"; do wait $p || VP=1; done
kill $WATCH 2>/dev/null; wait $WATCH 2>/dev/null
wait $FEATURES; FT=$?
for i in "${!PIDS[@]}"; do
  sed -n "s/^QUICK .* in \(.*\)$/TIMING quick lane $((i + 1)): \1/p" "$OUT/vp$((i + 1)).log"
done
cat "$OUT"/stopped.log 2>/dev/null
grep -hE "QUICK FAIL|SCRIPT ERROR" "$OUT"/vp*.log
grep -vE "^features:" "$OUT/feature.log"
# one summary: checks added up over the lanes, the slowest lane's time
Q=$(cat "$OUT"/vp*.log | awk '/^QUICK [0-9]+ passed/ {p+=$2; f+=$4; n++; if ($7+0 > t) t=$7+0}
  END {if (n) printf "QUICK %d passed, %d failed in %.1f s (%d window%s)", p, f, t, n, (n>1 ? "s side by side" : "")}')
N=$(grep -lE "^QUICK [0-9]+ passed" "$OUT"/vp*.log 2>/dev/null | wc -l | tr -d ' ')
[ "$N" -eq "${#PIDS[@]}" ] || { Q="${Q:+$Q; }$(( ${#PIDS[@]} - N )) window(s) did not finish"; VP=1; }
echo "$(grep -E "^features:" "$OUT/feature.log" | sed 's/  (logs:.*//') | viewport: $Q  (logs: $OUT)"
[ $VP -eq 0 ] && [ $FT -eq 0 ]
