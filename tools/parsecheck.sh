#!/bin/bash
# Loads every viewport script once, headless, and prints any parse error. Exit 1 if there is one.
# The test scripts run this first: a script that doesn't parse leaves Godot sitting with no test running.
# One Godot per script, all side by side (T49: 3.9 -> ~1 s).
cd "$(dirname "$0")/.."
. tools/gate.sh || exit 1
set_test_tmpdir || exit 1
GD=/Applications/Godot.app/Contents/MacOS/Godot
OUT=$(mktemp -d "${TEST_TMPDIR%/}/napkin-parse.XXXXXX") || exit 1
i=0
for f in viewport/*.gd viewport/tools/*.gd viewport/tests/*.gd viewport/tests/quick/*.gd viewport/tests/suites/*.gd; do
  ( ERR=$("$GD" --headless --path viewport --check-only --script "res://${f#viewport/}" 2>&1 | grep -E "SCRIPT ERROR|Parse Error" | head -3)
    [ -n "$ERR" ] && printf 'PARSE %s:\n%s\n' "$f" "$ERR" > "$OUT/$i" ) &
  i=$((i + 1))
done
wait
BAD=0
for e in "$OUT"/*; do [ -f "$e" ] && { cat "$e"; BAD=1; }; done
rm -rf "$OUT"
exit $BAD
