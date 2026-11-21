#!/bin/bash
# Loads every viewport script once, headless, and prints any parse error. Exit 1 if there is one.
# The test scripts run this first: a script that doesn't parse leaves Godot sitting with no test running.
cd "$(dirname "$0")/.."
GD=/Applications/Godot.app/Contents/MacOS/Godot
BAD=0
for f in viewport/*.gd viewport/tools/*.gd; do
  ERR=$("$GD" --headless --path viewport --check-only --script "res://${f#viewport/}" 2>&1 | grep -E "SCRIPT ERROR|Parse Error" | head -3)
  if [ -n "$ERR" ]; then echo "PARSE $f:"; echo "$ERR"; BAD=1; fi
done
exit $BAD
