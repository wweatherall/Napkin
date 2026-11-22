#!/bin/bash
# Feature tests (~10 s): everything that checks Shop Sketch's answers with no window, all side by side. The script
# finds them itself (T95): every worker/test_*.py, tools/test_*.py and viewport/test_*.gd, run the way its folder
# says (worker: freecadcmd; tools: python3; viewport: Godot headless) unless one of the file's first five lines says
# `runner: freecadcmd|python3|godot|none` (none: a helper, or a test run elsewhere). Each prints one summary line,
# "<NAME> TESTS: N passed, M failed"; a file that prints none fails, by name. Run them while building a feature,
# before its tool exists; tools/quicktest.sh runs them too, beside the viewport session.
#   tools/featuretest.sh [outdir]      exit status 0 = all passed; prints one summary line
#   tools/featuretest.sh --list        what it found and how it runs each, without running them
cd "$(dirname "$0")/.."
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
GD=/Applications/Godot.app/Contents/MacOS/Godot
TAG='^[A-Z][A-Z -]* TESTS: [0-9]+ passed, [0-9]+ failed'

# name | command, one per test file found
TESTS=()
for f in worker/test_*.py tools/test_*.py viewport/test_*.gd; do
  [ -f "$f" ] || continue
  runner=$(head -5 "$f" | grep -oE 'runner: *[a-z0-9]+' | head -1 | sed 's/runner: *//')
  if [ -z "$runner" ]; then
    case "$f" in worker/*) runner=freecadcmd;; tools/*) runner=python3;; viewport/*) runner=godot;; esac
  fi
  name=$(basename "$f"); name=${name#test_}; name=${name%.*}
  case "$runner" in
    none) continue;;
    freecadcmd) cmd="$FC $f";;
    python3) cmd="python3 $f";;
    godot) cmd="$GD --headless --path viewport --script res://${f#viewport/}";;
    *) cmd="false unknown-runner-$runner";;
  esac
  TESTS+=("$name|$cmd")
done

if [ "$1" = "--list" ]; then
  for t in "${TESTS[@]}"; do IFS='|' read -r name cmd <<< "$t"; printf '%-20s %s\n' "$name" "$cmd"; done
  exit 0
fi

OUT=${1:-$(mktemp -d -t shopsketch-feature)}
mkdir -p "$OUT"
PIDS=()
for t in "${TESTS[@]}"; do
  IFS='|' read -r name cmd <<< "$t"
  mkdir -p "$OUT/$name"
  ( TEST_START=$SECONDS
    TESTDIR="$OUT/$name" $cmd > "$OUT/$name.log" 2>&1; RC=$?
    echo "TIMING feature $name: $((SECONDS - TEST_START)) s" > "$OUT/$name.time"
    exit $RC
  ) &
  PIDS+=($!)
done
wait "${PIDS[@]}"
OK=1; LINE=""
for t in "${TESTS[@]}"; do
  IFS='|' read -r name _ <<< "$t"
  cat "$OUT/$name.time"
  grep -E "^FAIL" "$OUT/$name.log" | sed "s/^/[$name] /"
  s=$(grep -E "$TAG" "$OUT/$name.log" | head -1)
  LINE="$LINE${s:-$name did not finish} | "
  echo "$s" | grep -q " 0 failed" || OK=0
done
echo "features: ${LINE% | }  (logs: $OUT)"
[ $OK = 1 ]
