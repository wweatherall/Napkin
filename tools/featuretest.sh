#!/bin/bash
# Feature tests (~34 s): everything that checks Napkin's answers with no window, all side by side. The script
# finds them itself (T95): every worker/test_*.py, tools/test_*.py and viewport/test_*.gd, run the way its folder
# says (worker: freecadcmd; tools: python3; viewport: Godot headless) unless one of the file's first five lines says
# `runner: freecadcmd|python3|godot|none` (none: a helper, or a test run elsewhere). Each prints one summary line,
# "<NAME> TESTS: N passed, M failed"; a file that prints none fails, by name. Run them while building a feature,
# before its tool exists; tools/quicktest.sh runs them too, beside the viewport session.
#   tools/featuretest.sh [--tools-only] [outdir]  exit status 0 = all passed; prints one summary line
#   tools/featuretest.sh [--tools-only] --list    what it found and how it runs each, without running them
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
GD=/Applications/Godot.app/Contents/MacOS/Godot
TAG='^[A-Z][A-Z -]* TESTS: [0-9]+ passed, [0-9]+ failed'

test_runner_for() {
  local f=$1 runner dir base
  runner=$(head -5 "$f" | grep -oE 'runner: *[a-z0-9]+' | head -1 | sed 's/runner: *//')
  if [ -z "$runner" ]; then
    case "$f" in worker/*) runner=freecadcmd;; tools/*) runner=python3;; viewport/*) runner=godot;; *) runner=python3;; esac
  fi
  dir=${f%%/*}; base=$(basename "$f"); base=${base#test_}
  TEST_NAME="$dir-${base%.*}"
  TEST_RUNNER=$runner
  case "$runner" in
    none) TEST_CMD="";;
    freecadcmd) TEST_CMD="$FC $f";;
    python3) TEST_CMD="python3 $f";;
    godot) TEST_CMD="$GD --headless --path viewport --script res://${f#viewport/}";;
    *) TEST_CMD="false unknown-runner-$runner";;
  esac
}

run_test_command() {
  if [ "$1" = "$FC" ]; then
    shift
    "$FC" -u "$TESTDIR/user.cfg" -s "$TESTDIR/system.cfg" "$@"
  else
    "$@"
  fi
}

if [[ ${BASH_SOURCE[0]} != "$0" ]]; then return 0; fi

cd "$(dirname "$0")/.."

TOOLS_ONLY=0
LIST=0
OUT=""
for arg in "$@"; do
  case "$arg" in
    --tools-only) TOOLS_ONLY=1 ;;
    --list) LIST=1 ;;
    *) [ -z "$OUT" ] && OUT=$arg ;;
  esac
done

# name | command, one per test file found
TESTS=()
for f in worker/test_*.py tools/test_*.py viewport/test_*.gd; do
  [ -f "$f" ] || continue
  [ "$TOOLS_ONLY" -eq 1 ] && [[ "$f" != tools/* ]] && continue
  test_runner_for "$f"
  [ -z "$TEST_CMD" ] && continue
  TESTS+=("$TEST_NAME|$TEST_CMD")
done

if [ "$LIST" -eq 1 ]; then
  for t in "${TESTS[@]}"; do
    IFS='|' read -r name cmd <<< "$t"
    if [[ "$cmd" == "$FC "* ]]; then
      printf '%-26s %s -u "$TESTDIR/user.cfg" -s "$TESTDIR/system.cfg" %s\n' "$name" "$FC" "${cmd#"$FC "}"
    else
      printf '%-26s %s\n' "$name" "$cmd"
    fi
  done
  exit 0
fi

. tools/gate.sh || exit 1
set_test_tmpdir || exit 1
if [ -z "$OUT" ]; then OUT=$(mktemp -d "${TEST_TMPDIR%/}/napkin-feature.XXXXXX") || exit 1; fi
mkdir -p "$OUT" || exit 1
PIDS=()
for t in "${TESTS[@]}"; do
  IFS='|' read -r name cmd <<< "$t"
  mkdir -p "$OUT/$name" || exit 1
  ( TEST_START=$SECONDS
    TESTDIR="$OUT/$name" run_test_command $cmd > "$OUT/$name.log" 2>&1; RC=$?
    echo "TIMING feature $name: $((SECONDS - TEST_START)) s" > "$OUT/$name.time"
    echo $RC > "$OUT/$name.rc"
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
  rc=$(cat "$OUT/$name.rc" 2>/dev/null || echo "?")   # a summary of 0 failed still fails on a non-zero exit
  [ "$rc" = 0 ] || { OK=0; echo "[$name] exited $rc"; }
done
echo "features: ${LINE% | }  (logs: $OUT)"
[ $OK = 1 ]
