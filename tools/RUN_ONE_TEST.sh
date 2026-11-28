#!/bin/bash
# Run one test file the way tools/featuretest.sh runs it and print its summary line.
#   tools/RUN_ONE_TEST.sh <test-file>   exit status 0 = passed (0 failed and summary printed)
if [ $# -lt 1 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  echo "usage: tools/RUN_ONE_TEST.sh <test-file>"
  [ $# -lt 1 ] && exit 2 || exit 0
fi
ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
cd "$ROOT" || exit 1
f=$1
case "$f" in
  "$ROOT"/*) f=${f#"$ROOT"/} ;;
  ./*) f=${f#./} ;;
esac
if [ ! -f "$f" ]; then
  echo "not found: $f" >&2
  exit 2
fi
. tools/featuretest.sh || exit 1
. tools/gate.sh || exit 1
set_test_tmpdir || exit 1
test_runner_for "$f"
if [ "$TEST_RUNNER" = "none" ]; then
  echo "$f has runner: none (not a standalone test)" >&2
  exit 1
fi
OUT=$(mktemp -d "${TEST_TMPDIR%/}/napkin-one.XXXXXX") || exit 1
mkdir -p "$OUT/$TEST_NAME"
TESTDIR="$OUT/$TEST_NAME" $TEST_CMD > "$OUT/$TEST_NAME.log" 2>&1; RC=$?
grep -E "^FAIL" "$OUT/$TEST_NAME.log" | sed "s/^/[$TEST_NAME] /"
s=$(grep -E "$TAG" "$OUT/$TEST_NAME.log" | head -1)
if [ -n "$s" ]; then
  echo "$s"
else
  echo "[$TEST_NAME] did not finish (log: $OUT/$TEST_NAME.log)"
fi
echo "$s" | grep -q " 0 failed" && [ "$RC" -eq 0 ]
